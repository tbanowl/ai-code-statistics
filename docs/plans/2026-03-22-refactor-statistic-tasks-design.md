# 重构定时统计任务 — 设计文档

> 日期：2026-03-22
> 状态：已确认
> 关联需求：`docs/refactor-statistic-tasks.md`

## 1. 背景与目标

当前统计系统存在以下问题：

1. **维度缺失**：`metrics_daily_stats` 仅以"天"为维度，缺少仓库和贡献者维度
2. **Checkpoint 未统计**：AI 代码生成量（checkpoint 事件 kind=ai_agent）完全未纳入统计
3. **任务冗余**：8 个定时任务（daily/weekly/monthly/repo/contributor stats + dimensions + cleanup）存在大量重复聚合逻辑
4. **内存聚合**：所有计算在 Python 内存中完成，未利用 SQL 聚合能力
5. **ID 体系**：使用自增 ID，不适合分布式场景

### 目标

- 以 **(天, 仓库, 贡献者)** 为三维联合维度重建每日统计表
- 新增 AI 代码生成量指标（来自 checkpoint 事件）
- 所有表使用 XID 主键 + 毫秒时间戳
- 简化定时任务为 1 个核心聚合任务
- 提供完整的查询 API 和前端报表
- **完全替换旧表和旧代码逻辑，不保留兼容性**

## 2. 方案选型

**完全重写**：创建全新统计表体系（`stats_` 前缀），删除旧的统计表、旧定时任务代码、旧 API 路由和旧 DB 操作类。同时将原始事件表（`metrics_events_*`）和 CAS 表的 ID 也改为 XID，时间字段统一为毫秒精度。

理由：
- 需求文档明确使用"重构"一词，意图是重做而非修补
- 旧表/旧代码不保留，降低维护成本
- 原始事件数据完好，可随时从 `metrics_events_committed` 和 `metrics_events_checkpoint` 回填
- **全库统一 XID + 毫秒时间戳规范**，避免新旧 ID 体系混用

## 3. 数据库设计

### 3.1 公共规范

- **统计表名前缀**：`stats_`（原始事件表保留 `metrics_events_` 前缀，CAS 表保留 `cas_objects`）
- **主键**：**所有表**（包括原始事件表和 CAS 表）使用 XID 生成（String 类型，20 字符）
- **时间字段**：**所有表**的时间字段使用 BIGINT 毫秒时间戳。如果上游数据为秒级时间戳（10 位），写入时补 `* 1000`
- **每张表公共字段**：`id`（XID）、`created_at`（毫秒）、`updated_at`（毫秒，如适用）

### 3.1.1 原始事件表和 CAS 表的 ID/时间戳变更

以下现有表的 `id` 从 `BigInteger autoincrement` 改为 `String(20) XID`：

| 表名 | 变更项 |
|------|--------|
| `metrics_events_raw` | `id` → XID；`received_at`、`created_at` 确保毫秒 |
| `metrics_events_committed` | `id` → XID；`raw_id` 外键类型从 BigInteger 改为 String(20)；`created_at` 确保毫秒 |
| `metrics_events_checkpoint` | `id` → XID；`raw_id` 外键类型改为 String(20)；`created_at` 确保毫秒 |
| `metrics_events_agent_usage` | `id` → XID；`raw_id` 外键类型改为 String(20)；`created_at` 确保毫秒 |
| `metrics_events_install_hooks` | `id` → XID；`raw_id` 外键类型改为 String(20)；`created_at` 确保毫秒 |
| `cas_objects` | `id` → XID；`created_at`、`updated_at` 确保毫秒 |
| `task_executions` | `id` → XID；`created_at`、`updated_at` 确保毫秒 |

**`MetricsService` 时间戳修复**（`core/services/metrics_service.py`）：

当前代码中 `received_at` 和各事件的 `created_at` 使用的是**秒级**时间戳：
```python
# 当前（错误 — 秒级）
received_at = int(datetime.now().timestamp())
now = int(datetime.now().timestamp())
```

需修改为毫秒：
```python
# 修正（毫秒级）
received_at = int(datetime.now().timestamp() * 1000)
now = int(datetime.now().timestamp() * 1000)
```

> 注意：事件中的 `timestamp` 字段（来自客户端上报的 `event['t']`）本身已经是毫秒级，无需修改。

### 3.2 stats_repositories 仓库表

```sql
CREATE TABLE stats_repositories (
    id          VARCHAR(20) PRIMARY KEY,      -- XID
    repo_url    VARCHAR(500) NOT NULL,         -- 仓库完整地址
    repo_name   VARCHAR(255) NOT NULL,         -- 截除协议+域名后的路径 (org/repo)
    created_at  BIGINT NOT NULL,               -- 创建时间（毫秒）
    updated_at  BIGINT NOT NULL,               -- 更新时间（毫秒）

    UNIQUE(repo_url)
);
CREATE INDEX idx_stats_repositories_name ON stats_repositories(repo_name);
```

**repo_name 提取规则**：
- `https://github.com/org/repo.git` → `org/repo`
- `git@github.com:org/repo.git` → `org/repo`
- 去除 `.git` 后缀

### 3.3 stats_contributors 贡献者表

```sql
CREATE TABLE stats_contributors (
    id               VARCHAR(20) PRIMARY KEY,  -- XID
    name             VARCHAR(255) NOT NULL,     -- 贡献者姓名 (git author name)
    email            VARCHAR(255),              -- 贡献者邮箱 (git author email)
    contributor_uid  VARCHAR(255) NOT NULL,     -- 贡献者唯一业务标识 (来自 committed 事件的 author 字段)
    created_at       BIGINT NOT NULL,
    updated_at       BIGINT NOT NULL,

    UNIQUE(contributor_uid)
);
CREATE INDEX idx_stats_contributors_name ON stats_contributors(name);
```

> **说明**：
> - `contributor_uid` 是贡献者的业务唯一标识，来源于 committed 事件的 `author` 字段。命名为 `contributor_uid` 而非 `contributor_id`，避免与关联表中引用主键 `id` 的外键字段 `contributor_id` 混淆。
> - `email` 来源于 committed 事件的 `author_email` 字段（可选，可能为空）。

### 3.4 stats_repo_contributors 仓库贡献者关系表

```sql
CREATE TABLE stats_repo_contributors (
    id               VARCHAR(20) PRIMARY KEY,  -- XID
    repo_id          VARCHAR(20) NOT NULL,      -- FK → stats_repositories.id
    contributor_id   VARCHAR(20) NOT NULL,      -- FK → stats_contributors.id
    created_at       BIGINT NOT NULL,
    updated_at       BIGINT NOT NULL,

    UNIQUE(repo_id, contributor_id)
);
```

> 此处 `contributor_id` 是外键，引用 `stats_contributors.id`（XID 主键），与贡献者表的业务标识 `contributor_uid` 不会混淆。

### 3.5 stats_daily_stats 每日统计表（核心）

```sql
CREATE TABLE stats_daily_stats (
    id                  VARCHAR(20) PRIMARY KEY,  -- XID
    stat_date           BIGINT NOT NULL,           -- 当天 00:00:00 的毫秒时间戳
    repo_id             VARCHAR(20) NOT NULL,      -- FK → stats_repositories.id
    repo_name           VARCHAR(255),              -- 冗余，便于查询
    contributor_id      VARCHAR(20) NOT NULL,      -- FK → stats_contributors.id
    contributor_name    VARCHAR(255),              -- 冗余，便于查询
    ai_generated_lines  INTEGER DEFAULT 0,         -- AI 代码生成量 (checkpoint kind=ai_agent)
    ai_accepted_lines   INTEGER DEFAULT 0,         -- AI 代码采纳量 (committed ai_additions)
    human_lines         INTEGER DEFAULT 0,         -- 人类代码量 (committed human_additions)
    ai_percentage       DECIMAL(5,2) DEFAULT 0.0,  -- AI 占比 = ai_accepted / (human + ai_accepted) × 100
    git_ai_version      VARCHAR(50),               -- git-ai 客户端版本
    created_at          BIGINT NOT NULL,
    updated_at          BIGINT NOT NULL,

    UNIQUE(stat_date, repo_id, contributor_id)
);
CREATE INDEX idx_stats_daily_stats_date ON stats_daily_stats(stat_date);
CREATE INDEX idx_stats_daily_stats_repo ON stats_daily_stats(repo_id);
CREATE INDEX idx_stats_daily_stats_contributor ON stats_daily_stats(contributor_id);
```

**指标计算公式**：

| 指标 | 数据来源 | 计算方式 |
|------|----------|----------|
| ai_generated_lines | `metrics_events_checkpoint` WHERE kind='ai_agent' | SUM(lines_added) |
| ai_accepted_lines | `metrics_events_committed` | SUM(每条记录的 ai_additions JSON 数组之和) |
| human_lines | `metrics_events_committed` | SUM(human_additions) |
| ai_percentage | 计算字段 | ai_accepted_lines / (human_lines + ai_accepted_lines) × 100 |

### 3.6 表关系图

```
stats_repositories ──┐
                     ├── stats_repo_contributors
stats_contributors ──┘
       │                      │
       └──────────────────────┴── stats_daily_stats
                                    (stat_date, repo_id, contributor_id)
```

### 3.7 旧表处置

**完全删除旧的统计/维度表及相关代码**：

| 要删除的旧表 | 说明 |
|-------------|------|
| metrics_daily_stats | 旧日统计 |
| metrics_weekly_stats | 旧周统计 |
| metrics_monthly_stats | 旧月统计 |
| metrics_repo_stats | 旧仓库统计 |
| metrics_contributor_stats | 旧贡献者统计 |
| metrics_repos | 旧仓库维度 |
| metrics_contributors | 旧贡献者维度 |
| metrics_repo_contributors | 旧关系表 |

**保留不动的表**（原始事件数据）：
- `metrics_events_raw`
- `metrics_events_committed`
- `metrics_events_checkpoint`
- `metrics_events_agent_usage`
- `metrics_events_install_hooks`
- `cas_objects`
- `task_executions`

**要删除的旧代码**：
- `core/database/dimensions_db.py` — DimensionsDatabase 类
- `core/scheduler/tasks/daily_stats_task.py` — 旧日统计任务
- `core/scheduler/tasks/weekly_stats_task.py` — 旧周统计任务
- `core/scheduler/tasks/monthly_stats_task.py` — 旧月统计任务
- `core/scheduler/tasks/repo_stats_task.py` — 旧仓库统计任务
- `core/scheduler/tasks/contributor_stats_task.py` — 旧贡献者统计任务
- `core/scheduler/tasks/dimensions_task.py` — 旧维度更新任务
- `core/services/metrics_aggregation_service.py` — 旧聚合服务
- `api/routes/dimensions.py` — 旧维度 API 路由
- `api/routes/stats.py` — 旧统计 API 路由
- `core/database/models.py` 中旧的统计/维度模型类（MetricsDailyStats, MetricsWeeklyStats, MetricsMonthlyStats, MetricsRepoStats, MetricsContributorStats, MetricsRepo, MetricsContributor, MetricsRepoContributor）

## 4. 定时任务设计

### 4.1 任务简化

**Before（8 个任务）**：
- DailyStatsTask, WeeklyStatsTask, MonthlyStatsTask
- RepoStatsTask, ContributorStatsTask
- DimensionsUpdateTask
- TaskCleanupTask
- (unnamed metrics task)

**After（2 个任务）**：

| 任务 | Cron | 说明 |
|------|------|------|
| `DailyAggregationTask` | `0 2 * * *` | 核心聚合任务 |
| `TaskCleanupTask` | `0 3 * * *` | 清理旧执行记录（保留） |

旧的 6 个统计任务文件全部删除，不是禁用。

### 4.2 DailyAggregationTask 逻辑

```python
def execute(self, context=None):
    """
    参数（均可选，通过 context 传入）：
    - repo_url: str        指定仓库（不传则统计所有）
    - contributor: str     指定贡献者（不传则统计所有）
    - start_date: int      开始日期毫秒时间戳（不传则默认当天）
    - end_date: int        结束日期毫秒时间戳（不传则默认当天）
    """
```

**执行流程**：

1. **确定日期范围**
   - 手动触发：使用传入的 start_date 和 end_date
   - 定时触发：默认统计昨天（凌晨 2 点执行，统计前一天数据）

2. **遍历每一天**，对每天执行：

3. **查询 committed 事件**
   - 按日期范围 + 可选的 repo_url/author 过滤
   - 按 (repo_url, author) 分组

4. **查询 checkpoint 事件**（新增）
   - 按日期范围 + kind='ai_agent' + 可选的 repo_url/author 过滤
   - 按 (repo_url, author) 分组

5. **合并计算**：对每个 (日期, repo_url, author) 组合：
   - `ai_generated_lines` = checkpoint 的 SUM(lines_added)
   - `ai_accepted_lines` = committed 的 SUM(ai_additions)
   - `human_lines` = committed 的 SUM(human_additions)
   - `ai_percentage` = ai_accepted / (human + ai_accepted) × 100

6. **Upsert 维度表**：
   - 根据 repo_url 查找或创建 `stats_repositories` 记录
   - 根据 author 查找或创建 `stats_contributors` 记录（同时填入 email）
   - 查找或创建 `stats_repo_contributors` 关系记录

7. **Upsert stats_daily_stats**：
   - 按 (stat_date, repo_id, contributor_id) 唯一约束进行 UPSERT
   - **逻辑**：先查询是否存在同 (stat_date, repo_id, contributor_id) 的记录
     - 存在 → UPDATE 覆盖所有指标字段（ai_generated_lines, ai_accepted_lines, human_lines, ai_percentage, git_ai_version, updated_at）
     - 不存在 → INSERT 新记录
   - SQLite 使用 `INSERT OR REPLACE`，PostgreSQL 使用 `INSERT ... ON CONFLICT ... DO UPDATE`
   - SQLAlchemy 使用 `session.merge()` 实现跨数据库兼容的 UPSERT

### 4.3 config.yaml 调度配置

```yaml
scheduler:
  enabled: true
  timezone: Asia/Shanghai
  jobs:
    daily_aggregation:
      cron: "0 2 * * *"
      enabled: true
```

旧任务配置项直接删除。

## 5. API 设计

### 5.1 仓库分页接口

```
GET /api/v2/repositories
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 20 |
| keyword | string | 否 | 按 repo_name 模糊搜索 |

**响应**：
```json
{
  "success": true,
  "data": [...],
  "pagination": { "total": 42, "page": 1, "page_size": 20 }
}
```

### 5.2 贡献者分页接口

```
GET /api/v2/contributors
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页条数 |
| keyword | string | 否 | 按姓名模糊搜索 |

### 5.3 统计数据查询接口（图表聚合用）

```
GET /api/v2/stats
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| repo_id | string | 否 | 仓库 ID 过滤 |
| contributor_id | string | 否 | 贡献者 ID 过滤 |
| start_date | int | 是 | 开始日期（毫秒时间戳） |
| end_date | int | 是 | 结束日期 |
| granularity | string | 否 | daily/weekly/monthly，默认 daily |

**周/月粒度**：不需要独立表，从 `stats_daily_stats` 通过应用层按周/月分组聚合。

**响应**：
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "period": "2026-03-21",
        "ai_generated_lines": 150,
        "ai_accepted_lines": 120,
        "human_lines": 300,
        "ai_percentage": 28.57
      }
    ],
    "summary": {
      "total_ai_generated": 1500,
      "total_ai_accepted": 1200,
      "total_human": 3000,
      "avg_ai_percentage": 28.57
    }
  }
}
```

### 5.4 每日统计明细分页接口（表格列表用）

```
GET /api/v2/stats/daily
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 20 |
| repo_id | string | 否 | 仓库 ID 过滤 |
| contributor_id | string | 否 | 贡献者 ID 过滤 |
| start_date | int | 否 | 开始日期 |
| end_date | int | 否 | 结束日期 |

**响应**：
```json
{
  "success": true,
  "data": [
    {
      "id": "cq...",
      "stat_date": 1711065600000,
      "repo_id": "cq...",
      "repo_name": "org/repo",
      "contributor_id": "cq...",
      "contributor_name": "张三",
      "ai_generated_lines": 150,
      "ai_accepted_lines": 120,
      "human_lines": 300,
      "ai_percentage": 28.57,
      "git_ai_version": "1.2.0"
    }
  ],
  "pagination": { "total": 200, "page": 1, "page_size": 20 }
}
```

### 5.5 手动触发统计任务

```
POST /api/v2/stats/aggregate
```

**请求体**：
```json
{
  "repo_id": "可选",
  "contributor_id": "可选",
  "start_date": 1711065600000,
  "end_date": 1711152000000
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "execution_id": 123,
    "status": "running",
    "message": "统计任务已提交"
  }
}
```

复用现有 scheduler 的 `TaskExecution` 跟踪机制，异步执行。

## 6. 前端 UI 设计

### 6.1 首页 Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│ 筛选栏: [日期范围 ▼] [仓库 ▼] [贡献者 ▼]  [查询] [手动统计] │
├─────────────┬──────────────┬────────────┬───────────────────┤
│ AI 生成量   │ AI 采纳量     │ 人类代码量  │ AI 占比            │
│   1,500     │   1,200      │   3,000    │  28.57%           │
├─────────────┴──────────────┴────────────┴───────────────────┤
│                                                             │
│              趋势折线图（按天）                                │
│   --- AI生成  --- AI采纳  --- 人类代码  --- AI占比             │
│                                                             │
├──────────────────────┬──────────────────────────────────────┤
│  按仓库分布（柱状图）  │  按贡献者分布（柱状图）                 │
│                      │                                      │
├──────────────────────┴──────────────────────────────────────┤
│                                                             │
│  每日统计明细表格（分页）                                      │
│  ┌──────┬──────┬────────┬────────┬──────┬──────┬─────────┐  │
│  │ 日期  │ 仓库  │ 贡献者  │ AI生成  │ AI采纳│ 人类  │ AI占比  │  │
│  ├──────┼──────┼────────┼────────┼──────┼──────┼─────────┤  │
│  │ ...  │ ...  │ ...    │ ...    │ ...  │ ...  │ ...     │  │
│  └──────┴──────┴────────┴────────┴──────┴──────┴─────────┘  │
│  < 1 2 3 ... 10 >                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

- 默认查询最近 7 天数据
- 日期范围变更后自动刷新图表和表格
- 支持按仓库、贡献者维度筛选和对比
- **每日统计明细表格**：展示 `stats_daily_stats` 的逐行明细，支持分页、排序
- 表格和图表共享同一组筛选条件

### 6.2 手动统计触发

- Dashboard 右上角"手动统计"按钮
- 弹窗选择：仓库（可选）、贡献者（可选）、开始日期、结束日期
- 提交后显示 execution_id 和进度状态

### 6.3 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 图表库 | ECharts + vue-echarts | 功能全、中文友好、社区活跃 |
| 日期选择器 | flatpickr（已有） | 复用现有依赖 |
| 组件化 | 拆分 App.vue → 组件架构 | 当前 771 行单文件不可维护 |

## 7. 错误处理

### 7.1 聚合任务

- 单个 (日期, 仓库, 贡献者) 组合失败不影响其他组合的聚合
- 失败记录写入 TaskExecution 的 error_message
- 支持重试：手动触发时指定相同日期范围会覆盖已有数据（UPSERT）

### 7.2 API

- 参数校验失败返回 400 + 明确错误信息
- 内部错误返回 500 + 错误 ID（便于日志追踪）
- 分页参数超出范围返回空列表而非错误

### 7.3 数据一致性

- stats_daily_stats 的唯一约束 `(stat_date, repo_id, contributor_id)` 保证同一天同仓库同贡献者不会重复
- UPSERT 语义确保重跑安全（幂等性）

## 8. 依赖变更

| 依赖 | 包名 | 版本 |
|------|------|------|
| Python XID | `xid-python` | latest |
| Frontend ECharts | `echarts` | ^5.x |
| Frontend Vue ECharts | `vue-echarts` | ^7.x |
