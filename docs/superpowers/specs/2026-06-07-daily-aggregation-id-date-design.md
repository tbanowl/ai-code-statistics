# 每日聚合 ID 游标与提交日期设计

## 背景

当前 `metrics_event_processor` 将 committed 事件的 `timestamp` 保存为毫秒级时间戳，并且若干可聚合指标只保存在 JSON 数组字段中。`daily_aggregation` 任务会把 committed 事件读取到 Python 内存中逐条累加，并用 `stats_repositories.last_daily_aggregation_commit_sha` 记录进度。

新的需求是让 committed 事件表可以直接被 SQL 聚合，用 committed 事件 ID 记录每个仓库的聚合进度，并且避免同一仓库、同一天的数据分批到达时出现漏统计。

## 目标

- committed 事件的 `timestamp` 改为保存秒级时间戳，并由该秒级时间戳生成 `yyyyMMdd` 格式的 `commit_date`。
- 在 `metrics_events_committed` 上为 JSON 数组指标增加可直接求和的数值快照字段。
- 为 `authorship_notes` 和 `metrics_events_committed` 增加 `commit_date`。
- 用明确的 committed 指标字段替换 `stats_commit_daily` 旧的 `*_lines` 字段。
- 按仓库、天、人维度用 SQL `SUM` 聚合统计。
- 用 `stats_repositories.last_daily_aggregation_id` 作为每个仓库的聚合进度游标。
- 当 `require_authorship_notes` 启用时，只统计同时存在于 `metrics_events_committed` 和 `authorship_notes` 的 commit。

## 表结构变更

### metrics_events_committed

新处理的 committed 事件中，`timestamp` 语义从毫秒级改为秒级。

新增字段：

- `commit_date BIGINT/INT NULL`：由秒级 `timestamp` 转换得到的 `yyyyMMdd`。
- `mixed_additions_total INT DEFAULT 0`
- `ai_additions_total INT DEFAULT 0`
- `ai_accepted_total INT DEFAULT 0`
- `total_ai_additions_total INT DEFAULT 0`
- `total_ai_deletions_total INT DEFAULT 0`
- `time_waiting_for_ai_total BIGINT/INT DEFAULT 0`

这些 `_total` 字段从对应数组字段的第一个元素提取。字段缺失、数组为空或值非法时按 `0` 处理。

建议增加支撑新聚合路径的索引：

- `(repo_url, id)`
- `(repo_url, commit_date)`
- 保留现有 `commit_sha` 索引，用于 authorship notes 关联查询。

### authorship_notes

新增字段：

- `commit_date BIGINT/INT NULL`：由 `commit_time` 转换得到的 `yyyyMMdd`。

`commit_time` 按秒级时间戳处理。迁移回填时可以兼容历史毫秒级数据：如果值看起来像毫秒级时间戳，则先除以 `1000` 再格式化。

建议索引：

- `(repo_url, commit_sha)`
- `(repo_url, commit_date)`

### stats_repositories

新增字段：

- `last_daily_aggregation_id VARCHAR(20) NULL`

废弃并从 ORM 使用中移除：

- `last_daily_aggregation_commit_sha`

新游标记录某个仓库在一次成功聚合中发现到的最大 `metrics_events_committed.id`。

### stats_commit_daily

新增数值字段：

- `human_additions`
- `unknown_additions`
- `git_diff_deleted_lines`
- `git_diff_added_lines`
- `mixed_additions`
- `ai_additions`
- `ai_accepted`
- `total_ai_additions`
- `total_ai_deletions`

删除旧字段：

- `ai_lines`
- `ai_total_lines`
- `ai_accepted_lines`
- `human_lines`
- `total_lines`

保留现有唯一维度模型：

- `stat_date`
- `repo_id`
- `contributor_name`
- `contributor_email`

`stat_date` 保存与 committed 事件 `commit_date` 相同的 `yyyyMMdd` 值。不新增单独的 `stats_date` 字段。

## Metrics 事件处理流程

处理 committed 事件时：

1. 从原始事件读取事件时间戳。
2. 将 `MetricsEventsCommitted.timestamp` 保存为秒级时间戳。
3. 基于秒级 `timestamp` 计算 `commit_date`。
4. 继续保存原 JSON 数组指标字段，兼容已有展示和查询逻辑。
5. 从数组第一个元素提取并填充新的 `_total` 数值快照字段。
6. 继续按现有逻辑规范化 `repo_url`。
7. 继续使用现有 `uid` 语义做 upsert。

如果生产环境已有毫秒级历史 committed 数据，并且这些数据也需要参与新聚合路径，需要通过迁移脚本回填秒级 `timestamp`、`commit_date` 和 `_total` 字段。

## 每日聚合流程

任务按 `stats_repositories` 循环仓库。对每个仓库执行：

1. 读取 `repo_path` 和 `last_daily_aggregation_id`。
2. 查询该仓库游标之后的新 committed 行：
   - `repo_url = repo_path`
   - 当游标存在时增加 `id > last_daily_aggregation_id`
3. 如果 `require_authorship_notes` 为 `true`，这个“发现受影响日期”的查询需要按 `(repo_url, commit_sha)` 关联 `authorship_notes`，只有两张表都存在的 commit 才能产生受影响日期。
4. 从发现到的新行中提取 distinct `commit_date` 列表，以及最大的 committed 事件 `id`。
5. 对这些受影响日期执行第二次 SQL 聚合查询。聚合查询查询该仓库这些日期的全部匹配行，而不是只查询游标之后的新行。
6. SQL 聚合维度：
   - `commit_date`
   - 规范化后的仓库 URL
   - committed 事件中保存的作者身份
7. SQL 对所有 daily stat 指标字段执行 `SUM`。
8. 按覆盖语义 upsert `stats_commit_daily` 中受影响的 `(stat_date, repo_id, contributor_name, contributor_email)` 行。
9. 该仓库所有受影响 daily stat 写入成功后，将 `stats_repositories.last_daily_aggregation_id` 更新为本轮发现到的最大 committed 事件 ID。

`last_daily_aggregation_id` 只用于发现哪些日期发生变化，不用于限制最终 `SUM` 查询范围。这样可以避免以下漏统计场景：第一次已经聚合了 1 号的一部分数据，第二次又收到 1 号的新数据；第二次应重算并覆盖 1 号整天的聚合结果，而不是只累加游标之后的新行。

## Authorship Notes 过滤

当 `require_authorship_notes` 为 `false` 时，聚合只使用 `metrics_events_committed`。

当 `require_authorship_notes` 为 `true` 时，“发现受影响日期”的查询和“按日期聚合”的查询都必须关联 `authorship_notes`：

```sql
metrics_events_committed.repo_url = authorship_notes.repo_url
AND metrics_events_committed.commit_sha = authorship_notes.commit_sha
```

最终被统计的数据集合等价于：同时存在 committed 事件和 authorship note 的 commit。

## 字段语义

- `human_additions`：求和 committed 事件的 `human_additions`。
- `unknown_additions`：求和 committed 事件的 `unknown_additions`；在 committed 源字段尚不存在前按 `0` 聚合。
- `git_diff_deleted_lines`：求和 committed 事件的 `git_diff_deleted_lines`。
- `git_diff_added_lines`：求和 committed 事件的 `git_diff_added_lines`。
- `mixed_additions`：求和 committed 事件的 `mixed_additions_total`。
- `ai_additions`：求和 committed 事件的 `ai_additions_total`。
- `ai_accepted`：求和 committed 事件的 `ai_accepted_total`。
- `total_ai_additions`：求和 committed 事件的 `total_ai_additions_total`。
- `total_ai_deletions`：求和 committed 事件的 `total_ai_deletions_total`。

作者解析沿用现有行为：形如 `Name <email@example.com>` 的 stored author 字符串在 upsert daily stat 前拆分成贡献者名称和邮箱。

## 错误处理

- 某个仓库在游标之后没有新 committed 行时，跳过该仓库。
- 新 committed 行没有有效 `commit_date` 时，不应静默推进该仓库游标；任务应按现有数据库错误处理方式记录日志或失败。
- 任意 daily stat upsert 失败时，不更新该仓库的 `last_daily_aggregation_id`。
- 更新 `last_daily_aggregation_id` 失败时，任务应失败，让下一次运行可以重试。

## 测试范围

重点覆盖：

- Metrics processor 将 committed `timestamp` 保存为秒级。
- Metrics processor 基于秒级 `timestamp` 计算 `commit_date`。
- Metrics processor 从数组第一个值填充所有新的 `_total` 快照字段。
- SQL 聚合只用 ID 发现受影响日期，然后按完整日期重算。
- 第二次运行收到已聚合日期的新行时，会用该日期完整合计覆盖 daily stat。
- `require_authorship_notes=true` 时，只统计能关联到 `authorship_notes` 的 committed 行。
- `last_daily_aggregation_id` 只在聚合成功后推进。
- Daily stat upsert 写入新字段名，不再引用已删除的 `*_lines` 字段。
- schema/model 测试覆盖所有新增字段。
