# Git-AI 重构设计文档

**日期**: 2026-03-17
**版本**: 1.0
**方案**: 方案一 - 完全分离的两套表结构

---

## 一、概述

本文档描述基于 git-ai-client API 接口文档的重构设计，将项目从基于 Git Notes 的数据采集方式转变为基于 Metrics API 的方式。

### 1.1 目标

1. 根据接口内的参数与响应重新设计表结构
2. 完善 git-ai 相关接口实现（OAuth、CAS、Metrics、Releases）
3. 修改定时任务不再从 git notes 仓库拉取数据分析，而是根据数据库 metrics 相关信息中获取
4. 定时任务分析后的数据与 git-ai 数据创建两套表结构，以免耦合

### 1.2 约束条件

- 数据来源：通过 API 接收（git-ai 客户端通过 /worker/metrics/upload 上传）
- 表结构：混合方式（JSON 原始存储 + 结构化解析表）并为不同事件创建数据实体
- 统计维度：基础汇总（按仓库、用户、时间范围）
- 时间聚合：多粒度（天、周、月）

---

## 二、Metrics 原始数据表设计

### 2.1 metrics_events_raw （原始事件表）

用于存储接收的完整 MetricsBatch JSON 数据，保证数据完整性和可追溯性。

```sql
CREATE TABLE metrics_events_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,           -- 接收批次 ID (UUID)
    version INTEGER NOT NULL DEFAULT 1,  -- API 版本号
    event_count INTEGER NOT NULL,     -- 本批次事件数量
    payload_json TEXT NOT NULL,        -- 完整的 JSON payload
    received_at INTEGER NOT NULL,     -- 接收时间戳 (Unix timestamp)
    created_at INTEGER NOT NULL       -- 记录创建时间
);

CREATE INDEX idx_metrics_raw_batch_id ON metrics_events_raw(batch_id);
CREATE INDEX idx_metrics_raw_received_at ON metrics_events_raw(received_at);
```

### 2.2 metrics_events_committed （Committed 事件表）

存储已解析的 Committed（Event ID 1）事件数据。

```sql
CREATE TABLE metrics_events_committed (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER,                    -- 关联原始记录 ID
    event_id INTEGER NOT NULL,         -- 事件 ID (固定为 1)
    timestamp INTEGER NOT NULL,       -- 事件时间戳 (Unix timestamp)

    -- Scalar values
    human_additions INTEGER,
    git_diff_deleted_lines INTEGER,
    git_diff_added_lines INTEGER,
    first_checkpoint_ts INTEGER,
    commit_subject TEXT,
    commit_body TEXT,

    -- Array values (JSON 存储，索引 0=all, 1+=per tool)
    tool_model_pairs TEXT,             -- JSON array
    mixed_additions TEXT,              -- JSON array
    ai_additions TEXT,                 -- JSON array
    ai_accepted TEXT,                  -- JSON array
    total_ai_additions TEXT,           -- JSON array
    total_ai_deletions TEXT,           -- JSON array
    time_waiting_for_ai TEXT,          -- JSON array

    -- Event attributes
    git_ai_version TEXT,
    repo_url TEXT,
    author TEXT,
    commit_sha TEXT,
    base_commit_sha TEXT,
    branch TEXT,
    tool TEXT,
    model TEXT,
    prompt_id TEXT,
    external_prompt_id TEXT,
    custom_attributes TEXT,             -- JSON

    created_at INTEGER NOT NULL,

    FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id)
);

CREATE INDEX idx_committed_timestamp ON metrics_events_committed(timestamp);
CREATE INDEX idx_committed_repo_url ON metrics_events_committed(repo_url);
CREATE INDEX idx_committed_author ON metrics_events_committed(author);
CREATE INDEX idx_committed_commit_sha ON metrics_events_committed(commit_sha);
-- ...
```

### 2.3 metrics_events_checkpoint （Checkpoint 事件表）

```sql
CREATE TABLE metrics_events_checkpoint (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER,
    event_id INTEGER NOT NULL,         -- 固定为 4
    timestamp INTEGER NOT NULL,

    -- Values
    checkpoint_ts INTEGER,
    kind TEXT,                         -- "human", "ai_agent", "ai_tab"
    file_path TEXT,
    lines_added INTEGER,
    lines_deleted INTEGER,
    lines_added_sloc INTEGER,
    lines_deleted_sloc INTEGER,

    -- Event attributes
    git_ai_version TEXT,
    repo_url TEXT,
    author TEXT,
    commit_sha TEXT,
    base_commit_sha TEXT,
    branch TEXT,
    tool TEXT,
    model TEXT,
    prompt_id TEXT,

    created_at INTEGER NOT NULL,

    FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id)
);
```

### 2.4 metrics_events_agent_usage （AgentUsage 事件表）

```sql
CREATE TABLE metrics_events_agent_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER,
    event_id INTEGER NOT NULL,         -- 固定为 2
    timestamp INTEGER NOT NULL,

    -- Event attributes (values is empty for agent_usage)
    git_ai_version TEXT,
    repo_url TEXT,
    author TEXT,
    commit_sha TEXT,
    base_commit_sha TEXT,
    branch TEXT,
    tool TEXT,
    model TEXT,
    prompt_id TEXT,
    external_prompt_id TEXT,

    created_at INTEGER NOT NULL,

    FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id)
);
```

### 2.5 metrics_events_install_hooks （InstallHooks 事件表）

```sql
CREATE TABLE metrics_events_install_hooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER,
    event_id INTEGER NOT NULL,         -- 固定为 3
    timestamp INTEGER NOT NULL,

    -- Values
    tool_id TEXT,
    status TEXT,                       -- "not_found", "installed", "already_installed", "failed"
    message TEXT,

    -- Event attributes
    git_ai_version TEXT,

    created_at INTEGER NOT NULL,

    FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id)
);
```

---

## 三、Metrics 汇总统计表设计

### 3.1 metrics_daily_stats （按天汇总）

```sql
CREATE TABLE metrics_daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,                -- YYYY-MM-DD
    date_ts INTEGER NOT NULL,         -- 当天开始时间戳

    -- 汇总数据
    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    ai_percentage REAL DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    commits_with_ai INTEGER DEFAULT 0,

    -- 工具/模型细分 (JSON 存储)
    tool_model_breakdown TEXT,         -- {"claude-code:claude-3": {...}, ...}

    -- 时间范围
    start_date INTEGER,
    end_date INTEGER,

    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX idx_daily_stats_date ON metrics_daily_stats(date);
```

### 3.2 metrics_weekly_stats （按周汇总）

```sql
CREATE TABLE metrics_weekly_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,             -- ISO 周数
    week_start TEXT NOT NULL,         -- YYYY-MM-DD
    week_start_ts INTEGER NOT NULL,
    week_end TEXT NOT NULL,
    week_end_ts INTEGER NOT NULL,

    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    ai_percentage REAL DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    commits_with_ai INTEGER DEFAULT 0,
    tool_model_breakdown TEXT,

    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX idx_weekly_stats_year_week ON metrics_weekly_stats(year, week);
```

### 3.3 metrics_monthly_stats （按月汇总）

```sql
CREATE TABLE metrics_monthly_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_start TEXT NOT NULL,
    month_start_ts INTEGER NOT NULL,
    month_end TEXT NOT NULL,
    month_end_ts INTEGER NOT NULL,

    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    ai_percentage REAL DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    commits_with_ai INTEGER DEFAULT 0,
    tool_model_breakdown TEXT,

    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX idx_monthly_stats_year_month ON metrics_monthly_stats(year, month);
```

### 3.4 metrics_repo_stats （按仓库汇总）

```sql
CREATE TABLE metrics_repo_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    repo_url TEXT NOT NULL,
    provider_type TEXT,
    branch TEXT,

    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    ai_percentage REAL DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    commits_with_ai INTEGER DEFAULT 0,

    start_date INTEGER,
    end_date INTEGER,

    tool_model_breakdown TEXT,

    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX idx_repo_stats_repo ON metrics_repo_stats(repo_id, repo_name);
```

### 3.5 metrics_contributor_stats （按贡献者多粒度汇总）

```sql
CREATE TABLE metrics_contributor_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT NOT NULL,
    author_email TEXT,

    -- 粒度类型: 'daily', 'weekly', 'monthly'
    granularity TEXT NOT NULL,

    -- 时间范围 (根据粒度填充)
    date TEXT,                        -- YYYY-MM-DD (daily)
    year_week TEXT,                   -- YYYY-Www (weekly, ISO week)
    year_month TEXT,                  -- YYYY-MM (monthly)

    date_ts INTEGER NOT NULL,         -- 时间段开始时间戳

    -- 汇总数据
    total_commits INTEGER DEFAULT 0,
    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    ai_percentage REAL DEFAULT 0,

    -- 仓库细分
    repos_breakdown TEXT,              -- [{"repo_id": "...", "repo_name": "...", "repo_url": "...", "total_lines": ..., "ai_lines": ...}, ...]

    -- 时间范围
    start_date INTEGER,
    end_date INTEGER,

    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX idx_contributor_stats_author_granularity ON metrics_contributor_stats(author, granularity, date, year_week, year_month);
CREATE INDEX idx_contributor_stats_date_ts ON metrics_contributor_stats(date_ts);
CREATE INDEX idx_contributor_stats_granularity ON metrics_contributor_stats(granularity);
```

### 3.6 cas_objects （CAS 对象表）

```sql
CREATE TABLE cas_objects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,
    content_json TEXT,
    metadata_json TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX idx_cas_hash ON cas_objects(hash);
```

---

## 四、数据流设计

### 4.1 数据接收流程

```
git-ai 客户端
    ↓ POST /worker/metrics/upload
Metrics Upload API
    ↓ 解析 MetricsBatch
┌─────────────────────────────────────────┐
│ - 生成 batch_id (UUID)                   │
│ - 存储到 metrics_events_raw             │
│ - 逐事件解析并存储到对应表               │
│ - 返回响应 (errors 数组标记失败事件)     │
└─────────────────────────────────────────┘
    ↓
数据库:
  - metrics_events_raw (原始 JSON)
  - metrics_events_committed (Committed 事件)
  - metrics_events_checkpoint (Checkpoint 事件)
  - metrics_events_agent_usage (AgentUsage 事件)
  - metrics_events_install_hooks (InstallHooks 事件)
```

### 4.2 定时任务统计流程

```
定时任务触发
    ↓
从 metrics_events_committed 查询数据
    ↓ (按时间范围)
┌─────────────────────────────────────────┐
│ 聚合统计:                             │
│ - 按天 → metrics_daily_stats           │
│ - 按周 → metrics_weekly_stats          │
│ - 按月 → metrics_monthly_stats         │
│ - 按仓库 → metrics_repo_stats         │
│ - 按贡献者 → metrics_contributor_stats │
└─────────────────────────────────────────┘
    ↓
更新/插入汇总表
    ↓
完成
```

---

## 五、API 接口设计

### 5.1 Metrics Upload API

`POST /worker/metrics/upload`

接收 git-ai 客户端上报的 metrics 数据。

**请求格式:**
```json
{
    "v": 1,
    "events": [
        {
            "t": 1704067200,
            "e": 1,
            "v": {"0": 50, "1": 20, "2": 150},
            "a": {"0": "1.0.0", "1": "https://github.com/user/repo"}
        }
    ]
}
```

**响应格式:**
```json
{
    "errors": [
        {
            "index": 0,
            "error": "error message"
        }
    ]
}
```

### 5.2 CAS Upload API

`POST /worker/cas/upload`

接收 CAS (Content Addressable Storage) 对象。

### 5.3 CAS Read API

`GET /worker/cas/?hashes=hash1,hash2,...`

根据 hash 读取 CAS 对象。

### 5.4 OAuth Device Code API

`POST /worker/oauth/device/code`

获取设备授权码用于 OAuth 设备流程。

### 5.5 OAuth Token API

`POST /worker/oauth/token`

令牌交换（支持设备授权流程、刷新令牌、nonce 交换）。

### 5.6 Releases API

`GET /worker/releases`

获取最新的发行版本信息。

---

## 六、文件结构

```
git-ai-code-metrics/
├── api/
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── stats.py
│   │   ├── scheduler.py
│   │   ├── projects.py
│   │   ├── git_ai.py
│   │   └── git_ai_worker.py      # 新增/修改：OAuth, CAS, Metrics, Releases
│   └── schemas/
│       ├── metrics_schema.py     # 新增
│       ├── oauth_schema.py       # 新增
│       ├── cas_schema.py         # 新增
│       └── releases_schema.py    # 新增
│
├── core/
│   ├── database/
│   │   ├── base.py               # 扩展：metrics 方法
│   │   ├── sqlite.py             # 实现：metrics 方法
│   │   └── factory.py
│   │
│   ├── models/
│   │   ├── stats.py
│   │   └── metrics.py            # 新增
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── metrics_service.py    # 新增
│   │   ├── oauth_service.py      # 新增
│   │   └── cas_service.py        # 新增
│   │
│   ├── scheduler/
│   │   ├── scheduler.py
│   │   ├── stats_task.py         # 保留原有任务
│   │   └── metrics_task.py       # 新增 Metrics 分析任务
│   │
│   └── middleware/
│       ├── auth.py               # 新增：认证中间件
│
└── config.yaml                   # 扩展：git_ai 配置节
```

---

## 七、配置文件扩展

```yaml
# Git-AI Service 配置
git_ai:
  enabled: true

  # OAuth 配置
  oauth:
    secret_key: ${GIT_AI_OAUTH_SECRET:default-secret-key}
    token_expiry_hours: 1
    refresh_token_expiry_days: 90
    device_code_expiry_seconds: 900
    device_code_check_interval: 5

  # CAS 配置
  cas:
    enabled: true
    max_objects_per_request: 100
    max_hash_length: 255

  # Metrics 配置
  metrics:
    enabled: true
    max_events_per_batch: 250

  # Releases 配置
  releases:
    enabled: true
    version: ${RELEASE_VERSION:0.0.0}
    checksum: ''
    channels:
      - latest
      - next
      - enterprise-latest
      - enterprise-next

# 定时任务配置更新
scheduler:
  enabled: true
  timezone: Asia/Shanghai
  jobs:
    - id: daily_metrics_stats
      name: 每日 Metrics 统计
      type: cron
      cron: "0 2 * * *"
    - id: weekly_metrics_stats
      name: 每周 Metrics 统计
      type: cron
      cron: "0 3 * * 0"
    - id: monthly_metrics_stats
      name: 每月 Metrics 统计
      type: cron
      cron: "0 4 1 * *"
```

---

## 八、迁移计划

### 阶段一：基础设施
1. 创建新的表结构
2. 扩展 Database 基类接口
3. 实现 SQLAlchemy 适配器

### 阶段二：API 实现
1. 实现 Metrics Upload API
2. 实现 CAS API
3. 实现 OAuth API
4. 实现 Releases API
5. 添加认证中间件

### 阶段三：定时任务
1. 实现 MetricsAnalysisTask
2. 替换/保留原有 AICodeStatsTask
3. 配置新的定时任务

### 阶段四：测试验证
1. 单元测试
2. 集成测试
3. 端到端测试

---

## 九、相关文档

- [git-ai-api-reference.md](../git-ai-api-reference.md) - Git-AI API 接口文档
