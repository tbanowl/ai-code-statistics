# Stats Blame 仓库与人员维度统计设计

## 目标

调整 Git Blame 代码行数统计的持久化口径：不再保存文件维度统计，只保存仓库汇总和仓库-人员明细。统计日期默认使用任务执行当天，移除 `contributor_id` 依赖，移除 AI 占比字段和计算，并在 `stats_repositories` 记录每个仓库最后一次成功产出统计数据的日期。

## 设计结论

采用“仓库汇总表 + 仓库人员明细表”的方案：

- `stats_blame_repo` 继续作为仓库级快照表，按 `repo_id + stat_date + branch` 唯一。
- `stats_blame_repo_contributor` 继续作为仓库-人员明细表，但人员身份使用 `contributor_name` 和 `contributor_email`，不再使用 `contributor_id`。
- `stats_blame_file` 和 `stats_blame_file_contributor` 不再写入。文件级分析结果只作为内存中间数据，用于汇总仓库和人员行数。
- `ai_ratio` 从 stats blame 全链路移除，包括 schema、ORM、保存逻辑、查询返回和前端展示。

该方案保留仓库总览查询的稳定性，同时满足“不再以文件为维度保存数据”的要求。

## 数据结构

### stats_repositories

新增字段：

```sql
last_stat_date BIGINT COMMENT '最后统计日期，格式 yyyyMMdd'
```

字段含义：仓库最后一次 Git Blame 统计成功产出数据的日期。一个仓库存在多个分支时，只要至少一个分支统计并保存成功，即可更新为本次任务的 `stat_date`。

### stats_blame_repo

保留字段：

- `id`
- `repo_id`
- `stat_date`
- `commit_sha`
- `branch`
- `total_lines`
- `ai_lines`
- `non_ai_lines`
- `total_files`
- `created_at`
- `updated_at`

移除字段：

- `ai_ratio`

唯一键继续使用 `repo_id + stat_date + branch`。

### stats_blame_repo_contributor

保留字段：

- `id`
- `repo_id`
- `branch`
- `stat_date`
- `contributor_name`
- `contributor_email`
- `ai_lines`
- `non_ai_lines`
- `total_lines`
- `created_at`
- `updated_at`

移除字段：

- `contributor_id`

唯一键调整为 `repo_id + stat_date + branch + contributor_name + contributor_email`。`contributor_email` 在保存前统一归一化为空字符串，并在数据库中设为 `NOT NULL DEFAULT ''`，避免 MySQL 唯一索引允许多条 `NULL` 邮箱记录。

### 文件维度表

以下表不再作为 stats blame 的写入目标：

- `stats_blame_file`
- `stats_blame_file_contributor`

如果生产环境已有历史数据，可以选择保留表但停止写入；如果当前环境允许破坏式 schema 简化，可以从建表脚本、ORM 和查询 API 中移除。

## 统计流程

### 统计日期

任务默认 `stat_date` 从“昨天”改为“当天”：

```python
datetime.now().strftime("%Y%m%d")
```

如果手动执行任务时 `context` 显式传入 `stat_date`，继续优先使用传入值，便于补算和测试。

### 分析阶段

`BlameStatsService` 仍然逐文件执行 `git blame --line-porcelain`，并通过 `authorship_notes` 判断每行是否为 AI 代码。文件级统计只承担中间聚合作用：

1. 每个文件计算 `total_lines`、`ai_lines`、`non_ai_lines`。
2. 每个文件按 blame author 聚合人员行数。
3. 仓库级结果累加文件总数和行数。
4. 仓库-人员结果把所有文件的人员统计合并到 `contributor_stats`。

返回结果中不再需要携带用于持久化的 `files_results`。如果为了降低改动风险短期保留 `files_results` 字段，也只能作为内存数据，不能继续传入 DB 层保存。

### 保存阶段

每个分支统计成功后，只保存两类对象：

- 一个 `StatsBlameRepo` 仓库汇总对象
- 多个 `StatsBlameRepoContributor` 仓库人员明细对象

DB 层批量保存方法调整为在同一事务内：

1. 删除相同 `repo_id + stat_date + branch` 的旧仓库汇总。
2. 删除相同 `repo_id + stat_date + branch` 的旧人员明细。
3. 插入新的仓库汇总和人员明细。

该流程保证同一天重复执行同一分支统计是幂等的。

### 仓库最后统计日期

每个仓库只要至少一个分支保存成功，就更新：

- `stats_repositories.last_blame_commit_sha = result.commit_sha`
- `stats_repositories.last_stat_date = stat_date`

如果某个分支失败但其他分支成功，仓库仍视为有成功统计产出，允许更新 `last_stat_date`。如果所有分支失败或仓库被跳过，则不更新。

## API 影响

### 保留 API

`GET /api/stats-repo/blame/repo/<repo_id>`：返回仓库级统计，响应中移除 `ai_ratio`。

`GET /api/stats-repo/blame/repos`：返回仓库级分页列表，响应中移除 `ai_ratio`。

`GET /api/stats-repo/blame/repo/<repo_id>/contributors`：返回仓库人员统计，响应中移除 `contributor_id`。

### 废弃 API

`GET /api/stats-repo/blame/file/<repo_id>` 不再有持久化数据来源，应删除或返回明确的废弃响应。推荐删除后端路由和前端调用，避免调用方误以为文件维度仍然可用。

## 前端影响

前端所有 stats blame 展示移除 AI 占比列，不再由前端重新计算占比。涉及页面包括仓库归因统计列表、首页 blame 统计表，以及任何依赖 `ai_ratio` 字段的 API 类型定义。

贡献者统计类型移除 `contributor_id`，以 `contributor_name` 和 `contributor_email` 展示人员身份。

## 数据库脚本

新库脚本更新 `sql/metrics_schema_mysql.sql`：

- `stats_repositories` 增加 `last_stat_date`。
- `stats_blame_repo` 删除 `ai_ratio`。
- `stats_blame_repo_contributor` 删除 `contributor_id`，唯一键改为自然身份字段。
- 不再创建文件维度 stats blame 表，或保留建表但标注废弃并确保代码不写入。

旧库迁移建议新增独立 MySQL 脚本：

```sql
ALTER TABLE stats_repositories ADD COLUMN last_stat_date BIGINT COMMENT '最后统计日期，格式 yyyyMMdd';
ALTER TABLE stats_blame_repo DROP COLUMN ai_ratio;
ALTER TABLE stats_blame_repo_contributor DROP INDEX uk_blame_rc_branch_contributor;
UPDATE stats_blame_repo_contributor SET contributor_email = '' WHERE contributor_email IS NULL;
ALTER TABLE stats_blame_repo_contributor MODIFY contributor_email VARCHAR(100) NOT NULL DEFAULT '' COMMENT '贡献者邮箱';
ALTER TABLE stats_blame_repo_contributor DROP COLUMN contributor_id;
ALTER TABLE stats_blame_repo_contributor
  ADD UNIQUE KEY uk_blame_rc_branch_contributor_identity
  (repo_id, stat_date, branch, contributor_name, contributor_email(100));
```

文件维度表是否 drop 由部署策略决定。保守迁移只停止写入并保留历史表；破坏式迁移可额外 `DROP TABLE stats_blame_file_contributor` 和 `DROP TABLE stats_blame_file`。

## 验证

后端单元测试覆盖：

- `GitBlameStatsTask.execute()` 默认 `stat_date` 为当天 `yyyyMMdd`。
- `_save_branch_stats()` 只构造仓库汇总和仓库人员明细，不构造文件统计对象。
- `save_branch_stats_batch()` 重复保存同一 `repo_id + stat_date + branch` 时只保留最新仓库和人员数据。
- `update_repository_last_stat_date` 或合并后的仓库状态更新方法能同时更新 `last_blame_commit_sha` 和 `last_stat_date`。
- 查询方法返回值不包含 `ai_ratio` 和 `contributor_id`。

前端类型或构建验证覆盖：

- TypeScript 类型中不再声明 stats blame 的 `ai_ratio` 和贡献者 `contributor_id`。
- 页面构建不再引用 AI 占比列。

## 非目标

- 不改变 Git blame 行归属判断逻辑。
- 不改变 `authorship_notes` 的解析格式。
- 不改变仓库、分支、SSH Key 的管理逻辑。
- 不为 stats blame 增加新的 AI 占比派生字段。
