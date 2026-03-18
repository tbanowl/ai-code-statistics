# Git-AI 重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 根据 git-ai API 文档重构项目，实现基于 Metrics API 的数据采集和统计系统，完全分离两套表结构以避免耦合。

**架构:** 采用工厂模式和适配器模式，Metrics 数据通过 API 接收存储到独立表结构，定时任务从 Metrics 原始表聚合生成统计表。混合存储方式：JSON 原始数据 + 结构化解析表。

**Tech Stack:** Flask, SQLite (可扩展 PostgreSQL/MySQL), JWT (PyJWT), APScheduler

---

## 阶段一：基础设施 - 数据模型和数据库扩展

### Task 1: 创建 Metrics 数据模型

**Files:**
- Create: `core/models/metrics.py`

**Step 1: 创建空的 metrics.py 文件**

```python
# core/models/metrics.py
"""Metrics 相关数据模型"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class MetricsRawRecord:
    """Metrics 原始批次记录"""
    batch_id: str
    version: int = 1
    event_count: int = 0
    payload_json: str = ""
    received_at: int = 0
    created_at: int = 0


@dataclass_json
@dataclass
class MetricsCommittedRecord:
    """Committed 事件记录"""
    raw_id: int
    event_id: int = 1
    timestamp: int = 0
    human_additions: Optional[int] = None
    git_diff_deleted_lines: Optional[int] = None
    git_diff_added_lines: Optional[int] = None
    first_checkpoint_ts: Optional[int] = None
    commit_subject: Optional[str] = None
    commit_body: Optional[str] = None
    tool_model_pairs: Optional[str] = None
    mixed_additions: Optional[str] = None
    ai_additions: Optional[str] = None
    ai_accepted: Optional[str] = None
    total_ai_additions: Optional[str] = None
    total_ai_deletions: Optional[str] = None
    time_waiting_for_ai: Optional[str] = None
    git_ai_version: Optional[str] = None
    repo_url: Optional[str] = None
    author: Optional[str] = None
    commit_sha: Optional[str] = None
    base_commit_sha: Optional[str] = None
    branch: Optional[str] = None
    tool: Optional[str] = None
    model: Optional[str] = None
    prompt_id: Optional[str] = None
    external_prompt_id: Optional[str] = None
    custom_attributes: Optional[str] = None
    created_at: int = 0


@dataclass_json
@dataclass
class MetricsCheckpointRecord:
    """Checkpoint 事件记录"""
    raw_id: int
    event_id: int = 4
    timestamp: int = 0
    checkpoint_ts: Optional[int] = None
    kind: Optional[str] = None
    file_path: Optional[str] = None
    lines_added: Optional[int] = None
    lines_deleted: Optional[int] = None
    lines_added_sloc: Optional[int] = None
    lines_deleted_sloc: Optional[int] = None
    git_ai_version: Optional[str] = None
    repo_url: Optional[str] = None
    author: Optional[str] = None
    commit_sha: Optional[str] = None
    base_commit_sha: Optional[str] = None
    branch: Optional[str] = None
    tool: Optional[str] = None
    model: Optional[str] = None
    prompt_id: Optional[str] = None
    created_at: int = 0


@dataclass_json
@dataclass
class MetricsAgentUsageRecord:
    """AgentUsage 事件记录"""
    raw_id: int
    event_id: int = 2
    timestamp: int = 0
    git_ai_version: Optional[str] = None
    repo_url: Optional[str] = None
    author: Optional[str] = None
    commit_sha: Optional[str] = None
    base_commit_sha: Optional[str] = None
    branch: Optional[str] = None
    tool: Optional[str] = None
    model: Optional[str] = None
    prompt_id: Optional[str] = None
    external_prompt_id: Optional[str] = None
    created_at: int = 0


@dataclass_json
@dataclass
class MetricsInstallHooksRecord:
    """InstallHooks 事件记录"""
    raw_id: int
    event_id: int = 3
    timestamp: int = 0
    tool_id: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    git_ai_version: Optional[str] = None
    created_at: int = 0


@dataclass_json
@dataclass
class MetricsDailyStat:
    """按天统计"""
    date: str
    date_ts: int
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    total_commits: int = 0
    commits_with_ai: int = 0
    tool_model_breakdown: Optional[str] = None
    start_date: Optional[int] = None
    end_date: Optional[int] = None
    created_at: int = 0
    updated_at: int = 0


@dataclass_json
@dataclass
class MetricsWeeklyStat:
    """按周统计"""
    year: int
    week: int
    week_start: str
    week_start_ts: int
    week_end: str
    week_end_ts: int
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    total_commits: int = 0
    commits_with_ai: int = 0
    tool_model_breakdown: Optional[str] = None
    created_at: int = 0
    updated_at: int = 0


@dataclass_json
@dataclass
class MetricsMonthlyStat:
    """按月统计"""
    year: int
    month: int
    month_start: str
    month_start_ts: int
    month_end: str
    month_end_ts: int
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    total_commits: int = 0
    commits_with_ai: int = 0
    tool_model_breakdown: Optional[str] = None
    created_at: int = 0
    updated_at: int = 0


@dataclass_json
@dataclass
class MetricsRepoStat:
    """按仓库统计"""
    repo_id: str
    repo_name: str
    repo_url: str
    provider_type: Optional[str] = None
    branch: Optional[str] = None
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    total_commits: int = 0
    commits_with_ai: int = 0
    tool_model_breakdown: Optional[str] = None
    start_date: Optional[int] = None
    end_date: Optional[int] = None
    created_at: int = 0
    updated_at: int = 0


@dataclass_json
@dataclass
class MetricsContributorStat:
    """按贡献者统计（多粒度）"""
    author: str
    author_email: Optional[str] = None
    granularity: str = "daily"
    date: Optional[str] = None
    year_week: Optional[str] = None
    year_month: Optional[str] = None
    date_ts: int = 0
    total_commits: int = 0
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    repos_breakdown: Optional[str] = None
    start_date: Optional[int] = None
    end_date: Optional[int] = None
    created_at: int = 0
    updated_at: int = 0
```

**Step 2: 创建 models/__init__.py 的 __all__ 导出**

`core/models/__init__.py` 添加:

```python
from .metrics import (
    MetricsRawRecord,
    MetricsCommittedRecord,
    MetricsCheckpointRecord,
    MetricsAgentUsageRecord,
    MetricsInstallHooksRecord,
    MetricsDailyStat,
    MetricsWeeklyStat,
    MetricsMonthlyStat,
    MetricsRepoStat,
    MetricsContributorStat,
)

__all__ = [
    # 现有导出...
    "MetricsRawRecord",
    "MetricsCommittedRecord",
    "MetricsCheckpointRecord",
    "MetricsAgentUsageRecord",
    "MetricsInstallHooksRecord",
    "MetricsDailyStat",
    "MetricsWeeklyStat",
    "MetricsMonthlyStat",
    "MetricsRepoStat",
    "MetricsContributorStat",
]
```

**Step 3: 运行验证导入**

Run: `python -c "from core.models import MetricsRawRecord; print('Import OK')"`
Expected: `Import OK`

**Step 4: 提交**

```bash
git add core/models/metrics.py core/models/__init__.py
git commit -m "feat: 添加 Metrics 数据模型"
```

---

### Task 2: 扩展 Database 基类接口

**Files:**
- Modify: `core/database/base.py`

**Step 1: 添加 Metrics 方法接口定义**

在 `Database` 类中添加以下方法：

```python
from core.models.metrics import (
    MetricsRawRecord, MetricsCommittedRecord,
    MetricsCheckpointRecord, MetricsAgentUsageRecord,
    MetricsInstallHooksRecord, MetricsDailyStat,
    MetricsWeeklyStat, MetricsMonthlyStat,
    MetricsRepoStat, MetricsContributorStat
)
```

然后在 `Database` 类中添加这些抽象方法（在现有方法之后）：

```python
    # Metrics 原始数据方法
    @abstractmethod
    def save_metrics_raw(self, batch_id: str, version: int,
                        event_count: int, payload_json: str,
                        received_at: int) -> int:
        """保存原始 metrics batch，返回 raw_id"""
        pass

    @abstractmethod
    def get_committed_events_in_range(self, start: datetime, end: datetime) -> List[Dict]:
        """获取时间范围内的 Committed 事件"""
        pass

    @abstractmethod
    def save_committed_event(self, event: MetricsCommittedRecord) -> int:
        """保存 Committed 事件"""
        pass

    @abstractmethod
    def save_checkpoint_event(self, event: MetricsCheckpointRecord) -> int:
        """保存 Checkpoint 事件"""
        pass

    @abstractmethod
    def save_agent_usage_event(self, event: MetricsAgentUsageRecord) -> int:
        """保存 AgentUsage 事件"""
        pass

    @abstractmethod
    def save_install_hooks_event(self, event: MetricsInstallHooksRecord) -> int:
        """保存 InstallHooks 事件"""
        pass

    # CAS 方法
    @abstractmethod
    def save_cas_object(self, hash: str, content_json: str,
                        metadata_json: str = None) -> None:
        """保存 CAS 对象"""
        pass

    @abstractmethod
    def get_cas_object(self, hash: str) -> Optional[Dict]:
        """获取 CAS 对象"""
        pass

    # Metrics 汇总表方法
    @abstractmethod
    def save_metrics_daily_stat(self, stat: MetricsDailyStat) -> int:
        """保存按天统计"""
        pass

    @abstractmethod
    def save_metrics_weekly_stat(self, stat: MetricsWeeklyStat) -> int:
        """保存按周统计"""
        pass

    @abstractmethod
    def save_metrics_monthly_stat(self, stat: MetricsMonthlyStat) -> int:
        """保存按月统计"""
        pass

    @abstractmethod
    def save_metrics_repo_stat(self, stat: MetricsRepoStat) -> int:
        """保存按仓库统计"""
        pass

    @abstractmethod
    def save_metrics_contributor_stat(self, stat: MetricsContributorStat) -> int:
        """保存按贡献者统计"""
        pass

    @abstractmethod
    def get_latest_metrics_stat(self, granularity: str) -> Optional[Dict]:
        """获取最新的统计记录（day/week/month）"""
        pass
```

**Step 2: 运行检查 Python 语法**

Run: `python -m py_compile core/database/base.py`
Expected: 无输出（语法检查通过）

**Step 3: 提交**

```bash
git add core/database/base.py
git commit -m "feat: 扩展 Database 基类添加 Metrics 方法接口"
```

---

### Task 3: 在 SQLiteDatabase 中实现 Metrics 表初始化

**Files:**
- Modify: `core/database/sqlite.py`

**Step 1: 添加 Metrics 表初始化 SQL**

在 `init_db()` 方法中，在现有表创建之后添加：

```python
    def init_db(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            # 现有表创建代码...
            # (保持现有的 stat_records, repo_stat_records 等表)

            # ============ Metrics 原始数据表 ============

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_events_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    event_count INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    received_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_events_committed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_id INTEGER,
                    event_id INTEGER NOT NULL DEFAULT 1,
                    timestamp INTEGER NOT NULL,
                    human_additions INTEGER,
                    git_diff_deleted_lines INTEGER,
                    git_diff_added_lines INTEGER,
                    first_checkpoint_ts INTEGER,
                    commit_subject TEXT,
                    commit_body TEXT,
                    tool_model_pairs TEXT,
                    mixed_additions TEXT,
                    ai_additions TEXT,
                    ai_accepted TEXT,
                    total_ai_additions TEXT,
                    total_ai_deletions TEXT,
                    time_waiting_for_ai TEXT,
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
                    custom_attributes TEXT,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_events_checkpoint (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_id INTEGER,
                    event_id INTEGER NOT NULL DEFAULT 4,
                    timestamp INTEGER NOT NULL,
                    checkpoint_ts INTEGER,
                    kind TEXT,
                    file_path TEXT,
                    lines_added INTEGER,
                    lines_deleted INTEGER,
                    lines_added_sloc INTEGER,
                    lines_deleted_sloc INTEGER,
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
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_events_agent_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_id INTEGER,
                    event_id INTEGER NOT NULL DEFAULT 2,
                    timestamp INTEGER NOT NULL,
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
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_events_install_hooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_id INTEGER,
                    event_id INTEGER NOT NULL DEFAULT 3,
                    timestamp INTEGER NOT NULL,
                    tool_id TEXT,
                    status TEXT,
                    message TEXT,
                    git_ai_version TEXT,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id)
                )
            ''')

            # ============ Metrics 汇总统计表 ============

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    date_ts INTEGER NOT NULL,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    total_commits INTEGER DEFAULT 0,
                    commits_with_ai INTEGER DEFAULT 0,
                    tool_model_breakdown TEXT,
                    start_date INTEGER,
                    end_date INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(date)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_weekly_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    week INTEGER NOT NULL,
                    week_start TEXT NOT NULL,
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
                    updated_at INTEGER NOT NULL,
                    UNIQUE(year, week)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_monthly_stats (
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
                    updated_at INTEGER NOT NULL,
                    UNIQUE(year, month)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_repo_stats (
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
                    tool_model_breakdown TEXT,
                    start_date INTEGER,
                    end_date INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(repo_id, repo_name)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_contributor_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author TEXT NOT NULL,
                    author_email TEXT,
                    granularity TEXT NOT NULL DEFAULT 'daily',
                    date TEXT,
                    year_week TEXT,
                    year_month TEXT,
                    date_ts INTEGER NOT NULL,
                    total_commits INTEGER DEFAULT 0,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    repos_breakdown TEXT,
                    start_date INTEGER,
                    end_date INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(author, granularity, date, year_week, year_month)
                )
            ''')

            # ============ CAS 对象表 ============

            conn.execute('''
                CREATE TABLE IF NOT EXISTS cas_objects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT UNIQUE NOT NULL,
                    content_json TEXT,
                    metadata_json TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')

            # 创建索引
            conn.execute('CREATE INDEX IF NOT EXISTS idx_metrics_raw_batch_id ON metrics_events_raw(batch_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_metrics_raw_received_at ON metrics_events_raw(received_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_committed_timestamp ON metrics_events_committed(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_committed_repo_url ON metrics_events_committed(repo_url)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_committed_author ON metrics_events_committed(author)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_committed_commit_sha ON metrics_events_committed(commit_sha)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_checkpoint_timestamp ON metrics_events_checkpoint(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_agent_usage_timestamp ON metrics_events_agent_usage(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON metrics_daily_stats(date)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_contributor_stats_date_ts ON metrics_contributor_stats(date_ts)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_contributor_stats_granularity ON metrics_contributor_stats(granularity)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_cas_hash ON cas_objects(hash)')
```

**Step 2: 测试数据库初始化**

Run: `python -c "from core.database.factory import create_database; from config_loader import ConfigLoader; db = create_database(ConfigLoader.load().get('database', {})); db.init_db(); print('DB init OK')"`
Expected: `DB init OK`

**Step 3: 提交**

```bash
git add core/database/sqlite.py
git commit -m "feat: 实现 SQLiteDatabase Metrics 表初始化"
```

---

### Task 4: 实现 SQLiteDatabase Metrics 方法（原始数据）

**Files:**
- Modify: `core/database/sqlite.py`

**Step 1: 实现 save_metrics_raw 方法**

在类中添加：

```python
    def save_metrics_raw(self, batch_id: str, version: int,
                        event_count: int, payload_json: str,
                        received_at: int) -> int:
        """保存原始 metrics batch"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_events_raw
                (batch_id, version, event_count, payload_json, received_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                batch_id, version, event_count, payload_json,
                received_at, int(datetime.now().timestamp())
            ))
            conn.commit()
            return cursor.lastrowid
```

**Step 2: 实现 get_committed_events_in_range 方法**

```python
    def get_committed_events_in_range(self, start: datetime, end: datetime) -> List[Dict]:
        """获取时间范围内的 Committed 事件"""
        query = 'SELECT * FROM metrics_events_committed WHERE timestamp >= ? AND timestamp <= ?'
        params = (int(start.timestamp()), int(end.timestamp()))

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]
```

**Step 3: 实现 save_committed_event 方法**

```python
    def save_committed_event(self, event: MetricsCommittedRecord) -> int:
        """保存 Committed 事件"""
        now = int(datetime.now().timestamp())
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_events_committed
                (raw_id, event_id, timestamp, human_additions, git_diff_deleted_lines,
                 git_diff_added_lines, first_checkpoint_ts, commit_subject, commit_body,
                 tool_model_pairs, mixed_additions, ai_additions, ai_accepted,
                 total_ai_additions, total_ai_deletions, time_waiting_for_ai,
                 git_ai_version, repo_url, author, commit_sha, base_commit_sha,
                 branch, tool, model, prompt_id, external_prompt_id,
                 custom_attributes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.raw_id, event.event_id, event.timestamp,
                event.human_additions, event.git_diff_deleted_lines,
                event.git_diff_added_lines, event.first_checkpoint_ts,
                event.commit_subject, event.commit_body,
                event.tool_model_pairs, event.mixed_additions,
                event.ai_additions, event.ai_accepted,
                event.total_ai_additions, event.total_ai_deletions,
                event.time_waiting_for_ai, event.git_ai_version,
                event.repo_url, event.author, event.commit_sha,
                event.base_commit_sha, event.branch, event.tool,
                event.model, event.prompt_id, event.external_prompt_id,
                event.custom_attributes, event.created_at
            ))
            conn.commit()
            return cursor.lastrowid
```

**Step 4: 实现 Checkpoint 存储方法**

```python
    def save_checkpoint_event(self, event: MetricsCheckpointRecord) -> int:
        """保存 Checkpoint 事件"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_events_checkpoint
                (raw_id, event_id, timestamp, checkpoint_ts, kind, file_path,
                 lines_added, lines_deleted, lines_added_sloc, lines_deleted_sloc,
                 git_ai_version, repo_url, author, commit_sha, base_commit_sha,
                 branch, tool, model, prompt_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.raw_id, event.event_id, event.timestamp, event.checkpoint_ts,
                event.kind, event.file_path, event.lines_added, event.lines_deleted,
                event.lines_added_sloc, event.lines_deleted_sloc,
                event.git_ai_version, event.repo_url, event.author,
                event.commit_sha, event.base_commit_sha, event.branch,
                event.tool, event.model, event.prompt_id, event.created_at
            ))
            conn.commit()
            return cursor.lastrowid
```

**Step 5: 实现 AgentUsage 存储方法**

```python
    def save_agent_usage_event(self, event: MetricsAgentUsageRecord) -> int:
        """保存 AgentUsage 事件"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_events_agent_usage
                (raw_id, event_id, timestamp, git_ai_version, repo_url, author,
                 commit_sha, base_commit_sha, branch, tool, model,
                 prompt_id, external_prompt_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.raw_id, event.event_id, event.timestamp, event.git_ai_version,
                event.repo_url, event.author, event.commit_sha,
                event.base_commit_sha, event.branch, event.tool,
                event.model, event.prompt_id, event.external_prompt_id,
                event.created_at
            ))
            conn.commit()
            return cursor.lastrowid
```

**Step 6: 实现 InstallHooks 存储方法**

```python
    def save_install_hooks_event(self, event: MetricsInstallHooksRecord) -> int:
        """保存 InstallHooks 事件"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_events_install_hooks
                (raw_id, event_id, timestamp, tool_id, status, message,
                 git_ai_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.raw_id, event.event_id, event.timestamp,
                event.tool_id, event.status, event.message,
                event.git_ai_version, event.created_at
            ))
            conn.commit()
            return cursor.lastrowid
```

**Step 7: 运行语法检查**

Run: `python -m py_compile core/database/sqlite.py`
Expected: 无输出

**Step 8: 提交**

```bash
git add core/database/sqlite.py
git commit -m "feat: 实现 SQLiteDatabase Metrics 原始数据方法"
```

---

### Task 5: 实现 SQLiteDatabase CAS 和汇总表方法

**Files:**
- Modify: `core/database/sqlite.py`

**Step 1: 实现 CAS 方法**

```python
    def save_cas_object(self, hash: str, content_json: str,
                        metadata_json: str = None) -> None:
        """保存 CAS 对象"""
        now = int(datetime.now().timestamp())
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO cas_objects
                (hash, content_json, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (hash, content_json, metadata_json, now, now))
            conn.commit()

    def get_cas_object(self, hash: str) -> Optional[Dict]:
        """获取 CAS 对象"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM cas_objects WHERE hash = ?',
                (hash,)
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None
```

**Step 2: 实现 daily_stats 方法**

```python
    def save_metrics_daily_stat(self, stat: MetricsDailyStat) -> int:
        """保存按天统计"""
        now = int(datetime.now().timestamp())
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO metrics_daily_stats
                (date, date_ts, total_lines, ai_lines, ai_percentage,
                 total_commits, commits_with_ai, tool_model_breakdown,
                 start_date, end_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stat.date, stat.date_ts, stat.total_lines, stat.ai_lines,
                stat.ai_percentage, stat.total_commits, stat.commits_with_ai,
                stat.tool_model_breakdown, stat.start_date, stat.end_date,
                stat.created_at, now
            ))
            conn.commit()
            return cursor.lastrowid

    def get_latest_metrics_stat(self, granularity: str) -> Optional[Dict]:
        """获取最新的统计记录（day/week/month）"""
        table_map = {
            'daily': 'metrics_daily_stats',
            'weekly': 'metrics_weekly_stats',
            'monthly': 'metrics_monthly_stats'
        }
        table = table_map.get(granularity)
        if not table:
            return None

        order_col_map = {
            'daily': 'date_ts',
            'weekly': 'week_start_ts',
            'monthly': 'month_start_ts'
        }
        order_col = order_col_map.get(granularity, 'id')

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f'SELECT * FROM {table} ORDER BY {order_col} DESC LIMIT 1'
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None
```

**Step 3: 实现 weekly_stats 方法**

```python
    def save_metrics_weekly_stat(self, stat: MetricsWeeklyStat) -> int:
        """保存按周统计"""
        now = int(datetime.now().timestamp())
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO metrics_weekly_stats
                (year, week, week_start, week_start_ts, week_end, week_end_ts,
                 total_lines, ai_lines, ai_percentage, total_commits,
                 commits_with_ai, tool_model_breakdown, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stat.year, stat.week, stat.week_start, stat.week_start_ts,
                stat.week_end, stat.week_end_ts, stat.total_lines,
                stat.ai_lines, stat.ai_percentage, stat.total_commits,
                stat.commits_with_ai, stat.tool_model_breakdown,
                stat.created_at, now
            ))
            conn.commit()
            return cursor.lastrowid
```

**Step 4: 实现 monthly_stats 方法**

```python
    def save_metrics_monthly_stat(self, stat: MetricsMonthlyStat) -> int:
        """保存按月统计"""
        now = int(datetime.now().timestamp())
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO metrics_monthly_stats
                (year, month, month_start, month_start_ts, month_end, month_end_ts,
                 total_lines, ai_lines, ai_percentage, total_commits,
                 commits_with_ai, tool_model_breakdown, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stat.year, stat.month, stat.month_start, stat.month_start_ts,
                stat.month_end, stat.month_end_ts, stat.total_lines,
                stat.ai_lines, stat.ai_percentage, stat.total_commits,
                stat.commits_with_ai, stat.tool_model_breakdown,
                stat.created_at, now
            ))
            conn.commit()
            return cursor.lastrowid
```

**Step 5: 实现 repo_stats 方法**

```python
    def save_metrics_repo_stat(self, stat: MetricsRepoStat) -> int:
        """保存按仓库统计"""
        now = int(datetime.now().timestamp())
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO metrics_repo_stats
                (repo_id, repo_name, repo_url, provider_type, branch,
                 total_lines, ai_lines, ai_percentage, total_commits,
                 commits_with_ai, tool_model_breakdown, start_date, end_date,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stat.repo_id, stat.repo_name, stat.repo_url, stat.provider_type,
                stat.branch, stat.total_lines, stat.ai_lines, stat.ai_percentage,
                stat.total_commits, stat.commits_with_ai, stat.tool_model_breakdown,
                stat.start_date, stat.end_date, stat.created_at, now
            ))
            conn.commit()
            return cursor.lastrowid
```

**Step 6: 实现 contributor_stats 方法**

```python
    def save_metrics_contributor_stat(self, stat: MetricsContributorStat) -> int:
        """保存按贡献者统计"""
        now = int(datetime.now().timestamp())
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO metrics_contributor_stats
                (author, author_email, granularity, date, year_week, year_month,
                 date_ts, total_commits, total_lines, ai_lines, ai_percentage,
                 repos_breakdown, start_date, end_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stat.author, stat.author_email, stat.granularity,
                stat.date, stat.year_week, stat.year_month, stat.date_ts,
                stat.total_commits, stat.total_lines, stat.ai_lines,
                stat.ai_percentage, stat.repos_breakdown,
                stat.start_date, stat.end_date, stat.created_at, now
            ))
            conn.commit()
            return cursor.lastrowid
```

**Step 7: 运行测试**

Run: `python -c "from core.database.factory import create_database; from config_loader import ConfigLoader; db = create_database(ConfigLoader.load().get('database', {})); db.init_db(); print('All methods OK')"`
Expected: `All methods OK`

**Step 8: 提交**

```bash
git add core/database/sqlite.py
git commit -m "feat: 实现 SQLiteDatabase CAS 和汇总表方法"
```

---

## 阶段二：API 实现

### Task 6: 创建认证中间件

**Files:**
- Create: `core/middleware/auth.py`
- Create: `core/middleware/__init__.py`

**Step 1: 创建中间件目录结构并编写 auth.py**

先创建目录：
```bash
mkdir -p core/middleware
```

然后创建 `core/middleware/auth.py`:

```python
"""认证中间件"""
from functools import wraps
from flask import request, jsonify
import jwt


def auth_required(f):
    """认证装饰器 - 支持 Authorization Header 或 X-API-Key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查 API Key（优先）
        api_key = request.headers.get('X-API-Key')
        if api_key:
            # 验证 API Key（从配置读取）
            from config_loader import ConfigLoader
            config_key = ConfigLoader.load().get('git_ai', {}).get('api_key')
            if config_key and api_key == config_key:
                return f(*args, **kwargs)
            if not config_key:
                # 未配置则接受任意 API Key（开发模式）
                return f(*args, **kwargs)
            return jsonify({'error': 'Invalid API key'}), 401

        # 检查 Bearer Token
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]  # 去掉 "Bearer " 前缀
            try:
                # 验证 JWT
                secret = ConfigLoader.load().get('git_ai', {}).get('oauth', {}).get('secret_key', 'secret')
                payload = jwt.decode(token, secret, algorithms=['HS256'])
                # 验证通过，继续处理
                request.user = payload
                return f(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Invalid token'}), 401

        # 都没有则返回 401（可选：开发模式下可以跳过）
        from config_loader import ConfigLoader
        if ConfigLoader.load().get('web', {}).get('debug', False):
            # 开发模式允许跳过认证
            return f(*args, **kwargs)

        return jsonify({'error': 'Unauthorized'}), 401

    return decorated_function
```

**Step 2: 创建 __init__.py**

```python
from .auth import auth_required

__all__ = ['auth_required']
```

**Step 3: 测试导入**

Run: `python -c "from core.middleware.auth import auth_required; print('Import OK')"`
Expected: `Import OK`

**Step 4: 提交**

```bash
git add core/middleware/
git commit -m "feat: 添加认证中间件"
```

---

### Task 7: 创建 Services 层目录结构和框架

**Files:**
- Create: `core/services/__init__.py`

**Step 1: 创建 services 目录和 __init__.py**

```bash
mkdir -p core/services
```

创建 `core/services/__init__.py`:

```python
"""Services 模块提供业务逻辑处理"""
```

**Step 2: 提交**

```bash
git add core/services/__init__.py
git commit -m "feat: 创建 services 层目录结构"
```

---

### Task 8: 实现 MetricsService

**Files:**
- Create: `core/services/metrics_service.py`

**Step 1: 创建 MetricsService 基础框架**

```python
"""Metrics 数据处理服务"""
import json
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from core.config.logging import Logger


class MetricsService:
    """Metrics 数据处理服务"""

    def __init__(self):
        self.logger = Logger.get_logger('services.metrics')
        from core.database.factory import create_database
        from config_loader import ConfigLoader
        config = ConfigLoader.load()
        self.database = create_database(config.get('database', {}))

    def process_metrics_batch(self, events: List[Dict]) -> List[Dict]:
        """
        批量处理 metrics 事件

        返回失败的事件列表，每个包含 index 和 error
        """
        if not events:
            return []

        batch_id = str(uuid.uuid4())
        received_at = int(datetime.now().timestamp())

        # 存储原始数据
        payload_json = json.dumps({'v': 1, 'events': events})
        raw_id = self.database.save_metrics_raw(
            batch_id=batch_id,
            version=1,
            event_count=len(events),
            payload_json=payload_json,
            received_at=received_at
        )

        errors = []

        # 处理每个事件
        for index, event in enumerate(events):
            try:
                self._process_single_event(event, raw_id)
            except Exception as e:
                self.logger.error(f"处理事件 {index} 失败: {e}")
                errors.append({
                    'index': index,
                    'error': str(e)
                })

        return errors

    def _process_single_event(self, event: Dict, raw_id: int):
        """处理单个事件"""
        event_id = event.get('e')
        timestamp = event.get('t')
        values = event.get('v', {})
        attrs = event.get('a', {})

        # 导入数据模型
        from core.models.metrics import (
            MetricsCommittedRecord, MetricsCheckpointRecord,
            MetricsAgentUsageRecord, MetricsInstallHooksRecord
        )

        now = int(datetime.now().timestamp())

        if event_id == 1:  # Committed
            record = MetricsCommittedRecord(
                raw_id=raw_id,
                event_id=1,
                timestamp=timestamp,
                human_additions=self._get_u32(values, '0'),
                git_diff_deleted_lines=self._get_u32(values, '1'),
                git_diff_added_lines=self._get_u32(values, '2'),
                first_checkpoint_ts=self._get_u64(values, '10'),
                commit_subject=self._get_string(values, '11'),
                commit_body=self._get_string(values, '12'),
                tool_model_pairs=json.dumps(self._get_array(values, '3')),
                mixed_additions=json.dumps(self._get_u32_array(values, '4')),
                ai_additions=json.dumps(self._get_u32_array(values, '5')),
                ai_accepted=json.dumps(self._get_u32_array(values, '6')),
                total_ai_additions=json.dumps(self._get_u32_array(values, '7')),
                total_ai_deletions=json.dumps(self._get_u32_array(values, '8')),
                time_waiting_for_ai=json.dumps(self._get_u64_array(values, '9')),
                git_ai_version=self._get_string(attrs, '0'),
                repo_url=self._get_string(attrs, '1'),
                author=self._get_string(attrs, '2'),
                commit_sha=self._get_string(attrs, '3'),
                base_commit_sha=self._get_string(attrs, '4'),
                branch=self._get_string(attrs, '5'),
                tool=self._get_string(attrs, '20'),
                model=self._get_string(attrs, '21'),
                prompt_id=self._get_string(attrs, '22'),
                external_prompt_id=self._get_string(attrs, '23'),
                custom_attributes=self._get_string(attrs, '30'),
                created_at=now
            )
            self.database.save_committed_event(record)

        elif event_id == 2:  # AgentUsage
            record = MetricsAgentUsageRecord(
                raw_id=raw_id,
                event_id=2,
                timestamp=timestamp,
                git_ai_version=self._get_string(attrs, '0'),
                repo_url=self._get_string(attrs, '1'),
                author=self._get_string(attrs, '2'),
                commit_sha=self._get_string(attrs, '3'),
                base_commit_sha=self._get_string(attrs, '4'),
                branch=self._get_string(attrs, '5'),
                tool=self._get_string(attrs, '20'),
                model=self._get_string(attrs, '21'),
                prompt_id=self._get_string(attrs, '22'),
                external_prompt_id=self._get_string(attrs, '23'),
                created_at=now
            )
            self.database.save_agent_usage_event(record)

        elif event_id == 3:  # InstallHooks
            record = MetricsInstallHooksRecord(
                raw_id=raw_id,
                event_id=3,
                timestamp=timestamp,
                tool_id=self._get_string(values, '0'),
                status=self._get_string(values, '1'),
                message=self._get_string(values, '2'),
                git_ai_version=self._get_string(attrs, '0'),
                created_at=now
            )
            self.database.save_install_hooks_event(record)

        elif event_id == 4:  # Checkpoint
            record = MetricsCheckpointRecord(
                raw_id=raw_id,
                event_id=4,
                timestamp=timestamp,
                checkpoint_ts=self._get_u64(values, '0'),
                kind=self._get_string(values, '1'),
                file_path=self._get_string(values, '2'),
                lines_added=self._get_u32(values, '3'),
                lines_deleted=self._get_u32(values, '4'),
                lines_added_sloc=self._get_u32(values, '5'),
                lines_deleted_sloc=self._get_u32(values, '6'),
                git_ai_version=self._get_string(attrs, '0'),
                repo_url=self._get_string(attrs, '1'),
                author=self._get_string(attrs, '2'),
                commit_sha=self._get_string(attrs, '3'),
                base_commit_sha=self._get_string(attrs, '4'),
                branch=self._get_string(attrs, '5'),
                tool=self._get_string(attrs, '20'),
                model=self._get_string(attrs, '21'),
                prompt_id=self._get_string(attrs, '22'),
                created_at=now
            )
            self.database.save_checkpoint_event(record)

        else:
            self.logger.warning(f"未知事件类型: {event_id}")

    @staticmethod
    def _get_u32(arr: Dict, pos: str) -> Optional[int]:
        val = arr.get(pos)
        if val is not None and isinstance(val, (int, float)):
            return int(val)
        return None

    @staticmethod
    def _get_u64(arr: Dict, pos: str) -> Optional[int]:
        val = arr.get(pos)
        if val is not None and isinstance(val, (int, float)):
            return int(val)
        return None

    @staticmethod
    def _get_string(arr: Dict, pos: str) -> Optional[str]:
        val = arr.get(pos)
        if val is not None:
            if isinstance(val, str):
                return val
            if isinstance(val, bool):
                return 'true' if val else 'false'
        return None

    @staticmethod
    def _get_array(arr: Dict, pos: str) -> List:
        val = arr.get(pos)
        if isinstance(val, list):
            return val
        return []

    @staticmethod
    def _get_u32_array(arr: Dict, pos: str) -> List[int]:
        vals = MetricsService._get_array(arr, pos)
        result = []
        for v in vals:
            if isinstance(v, (int, float)):
                result.append(int(v))
        return result

    @staticmethod
    def _get_u64_array(arr: Dict, pos: str) -> List[int]:
        vals = MetricsService._get_array(arr, pos)
        result = []
        for v in vals:
            if isinstance(v, (int, float)):
                result.append(int(v))
        return result
```

**Step 2: 测试导入**

Run: `python -c "from core.services.metrics_service import MetricsService; print('Import OK')"`
Expected: `Import OK`

**Step 3: 提交**

```bash
git add core/services/metrics_service.py
git commit -m "feat: 实现 MetricsService"
```

---

### Task 9: 实现 OAuthService

**Files:**
- Create: `core/services/oauth_service.py`

**Step 1: 创建 OAuthService**

```python
"""OAuth 设备授权流程服务"""
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional
from core.config.logging import Logger


class OAuthService:
    """OAuth 设备授权流程服务"""

    def __init__(self):
        self.logger = Logger.get_logger('services.oauth')
        # 存储设备授权码状态（生产环境应该使用 Redis）
        self.device_codes = {}

        from config_loader import ConfigLoader
        self.config = ConfigLoader.load().get('git_ai', {}).get('oauth', {})

    def create_device_code(self) -> Dict:
        """创建设备授权码"""
        device_code = secrets.token_urlsafe(32)

        expires_in = self.config.get('device_code_expiry_seconds', 900)
        interval = self.config.get('device_code_check_interval', 5)

        self.device_codes[device_code] = {
            'user_code': self._generate_user_code(),
            'expires_at': datetime.now() + timedelta(seconds=expires_in),
            'approved': False,
            'interval': interval
        }

        # TODO: 从配置获取 verification_uri
        verification_uri = 'http://localhost:8888/verify'

        return {
            'device_code': device_code,
            'user_code': self.device_codes[device_code]['user_code'],
            'verification_uri': verification_uri,
            'verification_uri_complete': f'{verification_uri}?code={self.device_codes[device_code]["user_code"]}',
            'expires_in': expires_in,
            'interval': interval
        }

    def exchange_token(self, grant_type: str, device_code: Optional[str],
                      refresh_token: Optional[str], install_nonce: Optional[str],
                      client_id: Optional[str]) -> Dict:
        """交换令牌"""
        if grant_type == 'urn:ietf:params:oauth:grant-type:device_code':
            return self._exchange_device_code(device_code, client_id)
        elif grant_type == 'refresh_token':
            return self._exchange_refresh_token(refresh_token, client_id)
        elif grant_type == 'install_nonce':
            return self._exchange_install_nonce(install_nonce, client_id)
        else:
            return {
                'error': 'unsupported_grant_type',
                'error_description': f'不支持的授权类型: {grant_type}'
            }

    def _exchange_device_code(self, device_code: Optional[str], client_id: Optional[str]) -> Dict:
        """设备授权码交换令牌"""
        if not device_code:
            return {'error': 'invalid_request', 'error_description': '缺少 device_code'}

        auth = self.device_codes.get(device_code)

        if not auth:
            return {'error': 'invalid_grant', 'error_description': '无效的设备授权码'}

        if datetime.now() > auth['expires_at']:
            del self.device_codes[device_code]
            return {'error': 'expired_token', 'error_description': '设备授权码已过期'}

        if not auth['approved']:
            return {'error': 'authorization_pending', 'error_description': '用户尚未授权'}

        # 生成令牌
        tokens = self._generate_tokens(client_id or 'git-ai-cli')

        # 清理设备授权码
        del self.device_codes[device_code]

        return tokens

    def _exchange_refresh_token(self, refresh_token: Optional[str], client_id: Optional[str]) -> Dict:
        """刷新令牌交换"""
        if not refresh_token:
            return {'error': 'invalid_request', 'error_description': '缺少 refresh_token'}

        # 生产环境应该验证 refresh_token
        tokens = self._generate_tokens(client_id or 'git-ai-cli')
        return tokens

    def _exchange_install_nonce(self, install_nonce: Optional[str], client_id: Optional[str]) -> Dict:
        """安装 nonce 交换"""
        if not install_nonce:
            return {'error': 'invalid_request', 'error_description': '缺少 install_nonce'}

        # 生产环境应该验证 nonce
        tokens = self._generate_tokens(client_id or 'git-ai-cli')
        return tokens

    def _generate_tokens(self, client_id: str) -> Dict:
        """生成 access_token 和 refresh_token"""
        secret = self.config.get('secret_key', 'your-secret-key')

        now = datetime.now()
        access_expiry_hours = self.config.get('token_expiry_hours', 1)
        refresh_expiry_days = self.config.get('refresh_token_expiry_days', 90)

        access_payload = {
            'sub': 'user_id',
            'email': 'user@example.com',
            'name': 'User Name',
            'orgs': [{'org_id': '1', 'org_name': 'Organization', 'org_slug': 'org', 'role': 'owner'}],
            'personal_org_id': '1',
            'exp': (now + timedelta(hours=access_expiry_hours)).timestamp(),
            'iat': now.timestamp()
        }

        refresh_payload = {
            'sub': 'user_id',
            'email': 'user@example.com',
            'exp': (now + timedelta(days=refresh_expiry_days)).timestamp(),
            'iat': now.timestamp()
        }

        access_token = jwt.encode(access_payload, secret, algorithm='HS256')
        refresh_token = jwt.encode(refresh_payload, secret, algorithm='HS256')

        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': access_expiry_hours * 3600,
            'refresh_token': refresh_token,
            'refresh_expires_in': refresh_expiry_days * 86400
        }

    @staticmethod
    def _generate_user_code() -> str:
        """生成类似 XXXX-XXXX 格式的用户验证码"""
        chars = 'BCDFGHJKLMNPQRSTVWXYZ23456789'
        code = ''.join(secrets.choice(chars) for _ in range(4))
        code += '-' + ''.join(secrets.choice(chars) for _ in range(4))
        return code

    def approve_device_code(self, user_code: str) -> bool:
        """用户授权批准设备授权码"""
        for device_code, auth in self.device_codes.items():
            if auth['user_code'] == user_code:
                auth['approved'] = True
                return True
        return False
```

**Step 2: 测试导入**

Run: `python -c "from core.services.oauth_service import OAuthService; print('Import OK')"`
Expected: `Import OK`

**Step 3: 提交**

```bash
git add core/services/oauth_service.py
git commit -m "feat: 实现 OAuthService"
```

---

### Task 10: 实现 CasService

**Files:**
- Create: `core/services/cas_service.py`

**Step 1: 创建 CasService**

```python
"""CAS (Content Addressable Storage) 服务"""
import json
from typing import List, Dict
from core.config.logging import Logger


class CasService:
    """CAS (Content Addressable Storage) 服务"""

    def __init__(self):
        self.logger = Logger.get_logger('services.cas')
        from core.database.factory import create_database
        from config_loader import ConfigLoader
        config = ConfigLoader.load()
        self.database = create_database(config.get('database', {}))

        from config_loader import ConfigLoader
        cas_config = ConfigLoader.load().get('git_ai', {}).get('cas', {})
        self.max_objects = cas_config.get('max_objects_per_request', 100)

    def upload_objects(self, objects: List[Dict]) -> Dict:
        """
        上传 CAS 对象

        请求格式:
        {
            "objects": [
                {
                    "content": {...},
                    "hash": "string",
                    "metadata": {...}
                },
                ...
            ]
        }

        响应格式:
        {
            "results": [{"hash": "...", "status": "ok", "error": null}],
            "success_count": 1,
            "failure_count": 0
        }
        """
        if len(objects) > self.max_objects:
            return {
                'error': f'Too many objects, maximum {self.max_objects} allowed',
                'results': [],
                'success_count': 0,
                'failure_count': 0
            }

        results = []
        success_count = 0
        failure_count = 0

        for obj in objects:
            obj_hash = obj.get('hash')
            content = obj.get('content')
            metadata = obj.get('metadata')

            try:
                self.database.save_cas_object(
                    hash=obj_hash,
                    content_json=json.dumps(content) if content else None,
                    metadata_json=json.dumps(metadata) if metadata else None
                )
                results.append({
                    'hash': obj_hash,
                    'status': 'ok',
                    'error': None
                })
                success_count += 1
            except Exception as e:
                self.logger.error(f"保存 CAS 对象失败: {e}")
                results.append({
                    'hash': obj_hash,
                    'status': 'error',
                    'error': str(e)
                })
                failure_count += 1

        return {
            'results': results,
            'success_count': success_count,
            'failure_count': failure_count
        }

    def read_objects(self, hashes: List[str]) -> Dict:
        """
        读取 CAS 对象

        请求格式: hashes=hash1,hash2,hash3

        响应格式:
        {
            "results": [
                {
                    "hash": "hash1",
                    "status": "ok",
                    "content": {...},
                    "error": None
                }
            ],
            "success_count": 1,
            "failure_count": 0
        }
        """
        results = []
        success_count = 0
        failure_count = 0

        for obj_hash in hashes:
            obj = self.database.get_cas_object(obj_hash)

            if obj:
                try:
                    content = json.loads(obj['content_json']) if obj.get('content_json') else None
                    results.append({
                        'hash': obj_hash,
                        'status': 'ok',
                        'content': content,
                        'error': None
                    })
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"解析 CAS 对象内容失败: {e}")
                    results.append({
                        'hash': obj_hash,
                        'status': 'error',
                        'content': None,
                        'error': str(e)
                    })
                    failure_count += 1
            else:
                results.append({
                    'hash': obj_hash,
                    'status': 'error',
                    'content': None,
                    'error': 'Not found'
                })
                failure_count += 1

        return {
            'results': results,
            'success_count': success_count,
            'failure_count': failure_count
        }
```

**Step 2: 测试导入**

Run: `python -c "from core.services.cas_service import CasService; print('Import OK')"`
Expected: `Import OK`

**Step 3: 提交**

```bash
git add core/services/cas_service.py
git commit -m "feat: 实现 CasService"
```

---

### Task 11: 实现并注册 Metrics Upload API

**Files:**
- Modify: `api/routes/git_ai_worker.py`

**Step 1: 完全重写 git_ai_worker.py**

```python
"""Git-AI Worker API 路由"""
from flask import Blueprint, request, jsonify
from core.config.logging import Logger
from core.middleware.auth import auth_required

# 创建蓝图
metrics_bp = Blueprint('metrics', __name__, url_prefix='/worker/metrics')
cas_bp = Blueprint('cas', __name__, url_prefix='/worker/cas')
oauth_bp = Blueprint('oauth', __name__, url_prefix='/worker/oauth')
releases_bp = Blueprint('releases', __name__, url_prefix='/worker/releases')

# 初始化日志记录器
logger = Logger.get_logger('api.git_ai_worker')

# ============ Metrics API ============

@metrics_bp.route('/upload', methods=['POST'])
@auth_required
def metrics_upload():
    """上传 metrics 数据"""
    from core.services.metrics_service import MetricsService

    try:
        data = request.get_json()

        # 验证版本
        version = data.get('v', 1)
        if version != 1:
            return jsonify({
                'errors': [{'index': -1, 'error': f'Unsupported version: {version}'}]
            }), 400

        events = data.get('events', [])
        if not events:
            return jsonify({'errors': []}), 200

        # 处理 metrics
        service = MetricsService()
        errors = service.process_metrics_batch(events)

        logger.info(f'Metrics batch processed: {len(events)} events, {len(errors)} errors')

        return jsonify({'errors': errors}), 200

    except Exception as e:
        logger.error(f'Metrics upload error: {e}')
        return jsonify({'errors': [{'index': -1, 'error': str(e)}]}), 500


# ============ CAS API ============

@cas_bp.route('/upload', methods=['POST'])
@auth_required
def cas_upload():
    """上传 CAS 对象"""
    from core.services.cas_service import CasService

    try:
        data = request.get_json()
        objects = data.get('objects', [])

        service = CasService()
        results = service.upload_objects(objects)

        logger.info(f'CAS upload: {results["success_count"]} success, {results["failure_count"]} failed')

        return jsonify(results), 200

    except Exception as e:
        logger.error(f'CAS upload error: {e}')
        return jsonify({
            'results': [],
            'success_count': 0,
            'failure_count': 0,
            'error': str(e)
        }), 500


@cas_bp.route('/', methods=['GET'])
@auth_required
def cas_read():
    """读取 CAS 对象"""
    from core.services.cas_service import CasService

    try:
        hashes_param = request.args.get('hashes', '')
        hashes = [h.strip() for h in hashes_param.split(',') if h.strip()]

        if len(hashes) > 100:
            return jsonify({'error': 'Too many hashes, maximum 100 allowed'}), 400

        if not hashes:
            return jsonify({
                'results': [],
                'success_count': 0,
                'failure_count': 0
            }), 200

        service = CasService()
        results = service.read_objects(hashes)

        return jsonify(results), 200

    except Exception as e:
        logger.error(f'CAS read error: {e}')
        return jsonify({'error': str(e)}), 500


# ============ OAuth API ============

@oauth_bp.route('/device/code', methods=['POST'])
def device_code():
    """获取设备授权码"""
    from core.services.oauth_service import OAuthService

    try:
        data = request.get_json() or {}

        service = OAuthService()
        result = service.create_device_code()

        logger.info(f'Device code created: {result["device_code"]}')

        return jsonify(result), 200

    except Exception as e:
        logger.error(f'Device code error: {e}')
        return jsonify({'error': str(e)}), 500


@oauth_bp.route('/token', methods=['POST'])
def oauth_token():
    """交换令牌"""
    from core.services.oauth_service import OAuthService

    try:
        data = request.get_json()
        grant_type = data.get('grant_type')
        client_id = data.get('client_id')

        service = OAuthService()
        result = service.exchange_token(
            grant_type=grant_type,
            device_code=data.get('device_code'),
            refresh_token=data.get('refresh_token'),
            install_nonce=data.get('install_nonce'),
            client_id=client_id
        )

        logger.info(f'Token exchange: grant_type={grant_type}, success={not result.get("error")}')

        if result.get('error'):
            return jsonify(result), 400

        return jsonify(result), 200

    except Exception as e:
        logger.error(f'OAuth token error: {e}')
        return jsonify({
            'error': None,
            'error_description': str(e)
        }), 500


# ============ Releases API ============

@releases_bp.route('/', methods=['GET'])
def get_releases():
    """获取发布信息"""
    from config_loader import ConfigLoader

    try:
        config = ConfigLoader.load()
        releases_config = config.get('git_ai', {}).get('releases', {})
        version = releases_config.get('version', '0.0.0')
        checksum = releases_config.get('checksum', '')

        channels = {
            'latest': {'version': version, 'checksum': checksum},
            'next': {'version': '', 'checksum': ''},
            'enterprise-latest': {'version': '', 'checksum': ''},
            'enterprise-next': {'version': '', 'checksum': ''}
        }

        return jsonify({'channels': channels}), 200

    except Exception as e:
        logger.error(f'Releases API error: {e}')
        return jsonify({'error': str(e)}), 500
```

**Step 2: 更新 app.py 注册新蓝图**

在 `app.py` 中找到蓝图注册部分，添加新蓝图：

```python
from api.routes.git_ai_worker import metrics_bp, cas_bp, oauth_bp, releases_bp
```

然后在注册蓝图的代码块后添加：

```python
# 注册 Git-AI Worker 蓝图
app.register_blueprint(metrics_bp)
app.register_blueprint(cas_bp)
app.register_blueprint(oauth_bp)
app.register_blueprint(releases_bp)
```

**Step 3: 测试启动应用**

Run: `python app.py &` (后台启动)
Expected: 应用正常启动，监听在 8888 端口

**Step 4: 测试 API 端点**

```bash
# 测试 OAuth device code
curl -X POST http://localhost:8888/worker/oauth/device/code \
     -H "Content-Type: application/json" \
     -d '{}'
```

Expected: JSON 响应包含 device_code, user_code 等

**Step 5: 停止应用**

```bash
pkill -f "python app.py"
```

**Step 6: 提交**

```bash
git add api/routes/git_ai_worker.py app.py
git commit -m "feat: 实现并注册 Git-AI Worker API"
```

---

## 阶段三：定时任务实现

### Task 12: 创建 MetricsAnalysisTask

**Files:**
- Create: `core/scheduler/metrics_task.py`

**Step 1: 创建 MetricsAnalysisTask**

```python
"""Metrics 数据分析定时任务"""
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict
from core.config.logging import Logger


class MetricsAnalysisTask:
    """Metrics 数据分析任务执行器"""

    def __init__(self, config: Dict):
        self.config = config
        from core.database.factory import create_database
        self.database = create_database(config.get('database', {}))
        self.logger = Logger.get_logger('scheduler.metrics_task')

    def execute(self) -> Dict:
        """执行 metrics 数据分析任务"""
        self.logger.info('开始执行 Metrics 数据分析任务')

        # 1. 确定分析时间范围
        end_date = datetime.now()
        start_date = self._get_analysis_start_date()

        self.logger.debug(f'分析时间范围: {start_date} 至 {end_date}')

        # 2. 获取未聚合的 committed 事件
        events = self._get_unprocessed_events(start_date, end_date)

        if not events:
            self.logger.info('没有新数据需要处理')
            return {'success': True, 'processed': 0}

        self.logger.info(f'获取到 {len(events)} 条 Committed 事件')

        # 3. 按不同粒度聚合统计
        results = {
            'daily': self._aggregate_daily(events, start_date, end_date),
            'weekly': self._aggregate_weekly(events, start_date, end_date),
            'monthly': self._aggregate_monthly(events, start_date, end_date),
            'repo': self._aggregate_by_repo(events, start_date, end_date),
            'contributor': self._aggregate_by_contributor(events, start_date, end_date)
        }

        self.logger.info(
            f'分析完成 - 处理事件数: {len(events)}, '
            f'daily: {len(results["daily"])}, '
            f'weekly: {len(results["weekly"])}, '
            f'monthly: {len(results["monthly"])}, '
            f'repo: {len(results["repo"])}, '
            f'contributor: {len(results["contributor"])}'
        )

        return {
            'success': True,
            'processed': len(events),
            'results': results
        }

    def _get_analysis_start_date(self) -> datetime:
        """获取分析起始日期"""
        # 查询最新的 daily 统计记录
        latest = self.database.get_latest_metrics_stat('daily')
        if latest:
            return datetime.fromtimestamp(latest['date_ts'])
        return datetime.now() - timedelta(days=30)

    def _get_unprocessed_events(self, start: datetime, end: datetime) -> list:
        """获取未处理的 Committed 事件"""
        return self.database.get_committed_events_in_range(start, end)

    def _aggregate_daily(self, events: list, start: datetime, end: datetime) -> list:
        """按天聚合"""
        from core.models.metrics import MetricsDailyStat

        daily_stats = {}

        for event in events:
            date = datetime.fromtimestamp(event['timestamp']).strftime('%Y-%m-%d')

            if date not in daily_stats:
                daily_stats[date] = self._init_day_stat(date)

            self._update_stat_with_event(daily_stats[date], event)

        # 保存到数据库
        saved = []
        for date_key, stat in daily_stats.items():
            record = MetricsDailyStat(
                date=stat['date'],
                date_ts=stat['date_ts'],
                total_lines=stat['total_lines'],
                ai_lines=stat['ai_lines'],
                ai_percentage=stat['ai_percentage'],
                total_commits=stat['total_commits'],
                commits_with_ai=stat['commits_with_ai'],
                start_date=int(start.timestamp()),
                end_date=int(end.timestamp()),
                created_at=int(datetime.now().timestamp()),
                updated_at=int(datetime.now().timestamp())
            )
            saved.append(self.database.save_metrics_daily_stat(record))

        return saved

    def _aggregate_weekly(self, events: list, start: datetime, end: datetime) -> list:
        """按周聚合（ISO 周）"""
        from core.models.metrics import MetricsWeeklyStat

        weekly_stats = {}

        for event in events:
            dt = datetime.fromtimestamp(event['timestamp'])
            iso_week = dt.isocalendar()
            week_key = (iso_week[0], iso_week[1])  # (year, week number)

            if week_key not in weekly_stats:
                weekly_stats[week_key] = self._init_week_stat(dt)

            self._update_stat_with_event(weekly_stats[week_key], event)

        # 保存到数据库
        saved = []
        for (year, week), stat in weekly_stats.items():
            # 计算周的起止日期
            monday = datetime.strptime(f"{year}-W{week:02d}-1", "%Y-W%W-%w")
            sunday = monday + timedelta(days=6)

            record = MetricsWeeklyStat(
                year=year,
                week=week,
                week_start=monday.strftime('%Y-%m-%d'),
                week_start_ts=int(monday.timestamp()),
                week_end=sunday.strftime('%Y-%m-%d'),
                week_end_ts=int(sunday.timestamp()),
                total_lines=stat['total_lines'],
                ai_lines=stat['ai_lines'],
                ai_percentage=stat['ai_percentage'],
                total_commits=stat['total_commits'],
                commits_with_ai=stat['commits_with_ai'],
                created_at=int(datetime.now().timestamp()),
                updated_at=int(datetime.now().timestamp())
            )
            saved.append(self.database.save_metrics_weekly_stat(record))

        return saved

    def _aggregate_monthly(self, events: list, start: datetime, end: datetime) -> list:
        """按月聚合"""
        from core.models.metrics import MetricsMonthlyStat

        monthly_stats = {}

        for event in events:
            dt = datetime.fromtimestamp(event['timestamp'])
            month_key = (dt.year, dt.month)

            if month_key not in monthly_stats:
                monthly_stats[month_key] = self._init_month_stat(dt)

            self._update_stat_with_event(monthly_stats[month_key], event)

        # 保存到数据库
        saved = []
        for (year, month), stat in monthly_stats.items():
            # 计算月的起止日期
            month_start = datetime(year, month, 1)
            if month == 12:
                month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = datetime(year, month + 1, 1) - timedelta(days=1)

            record = MetricsMonthlyStat(
                year=year,
                month=month,
                month_start=month_start.strftime('%Y-%m-%d'),
                month_start_ts=int(month_start.timestamp()),
                month_end=month_end.strftime('%Y-%m-%d'),
                month_end_ts=int(month_end.timestamp()),
                total_lines=stat['total_lines'],
                ai_lines=stat['ai_lines'],
                ai_percentage=stat['ai_percentage'],
                total_commits=stat['total_commits'],
                commits_with_ai=stat['commits_with_ai'],
                created_at=int(datetime.now().timestamp()),
                updated_at=int(datetime.now().timestamp())
            )
            saved.append(self.database.save_metrics_monthly_stat(record))

        return saved

    def _aggregate_by_repo(self, events: list, start: datetime, end: datetime) -> list:
        """按仓库聚合"""
        from core.models.metrics import MetricsRepoStat

        repo_stats = {}

        for event in events:
            repo_url = event.get('repo_url', '')
            branch = event.get('branch', 'main')
            repo_key = (repo_url, branch)

            if repo_key not in repo_stats:
                repo_stats[repo_key] = self._init_repo_stat(event)

            self._update_repo_stat_with_event(repo_stats[repo_key], event)

        # 保存到数据库
        saved = []
        for (repo_url, branch), stat in repo_stats.items():
            record = MetricsRepoStat(
                repo_id=stat['repo_id'],
                repo_name=stat['repo_name'],
                repo_url=repo_url,
                provider_type='metrics',  # 标记来源
                branch=branch,
                total_lines=stat['total_lines'],
                ai_lines=stat['ai_lines'],
                ai_percentage=stat['ai_percentage'],
                total_commits=stat['total_commits'],
                commits_with_ai=stat['commits_with_ai'],
                start_date=int(start.timestamp()),
                end_date=int(end.timestamp()),
                created_at=int(datetime.now().timestamp()),
                updated_at=int(datetime.now().timestamp())
            )
            saved.append(self.database.save_metrics_repo_stat(record))

        return saved

    def _aggregate_by_contributor(self, events: list, start: datetime, end: datetime) -> list:
        """按贡献者聚合（多粒度）"""
        from core.models.metrics import MetricsContributorStat

        metrics = {}

        for event in events:
            author = event.get('author', 'unknown')
            date = datetime.fromtimestamp(event['timestamp'])

            # daily
            day_key = ('daily', author, date.strftime('%Y-%m-%d'))
            if day_key not in metrics:
                metrics[day_key] = self._init_contributor_stat('daily', author, date)
            self._update_contributor_stat_with_event(metrics[day_key], event)

            # weekly
            iso_week = date.isocalendar()
            week_key = ('weekly', author, f"{iso_week[0]}-W{iso_week[1]:02d}")
            if week_key not in metrics:
                metrics[week_key] = self._init_contributor_stat('weekly', author, date)
            self._update_contributor_stat_with_event(metrics[week_key], event)

            # monthly
            month_key = ('monthly', author, date.strftime('%Y-%m'))
            if month_key not in metrics:
                metrics[month_key] = self._init_contributor_stat('monthly', author, date)
            self._update_contributor_stat_with_event(metrics[month_key], event)

        # 保存到数据库
        saved = []
        for (granularity, author, period), stat in metrics.items():
            record = MetricsContributorStat(
                author=author,
                granularity=granularity,
                date=stat.get('date'),
                year_week=stat.get('year_week'),
                year_month=stat.get('year_month'),
                date_ts=stat['date_ts'],
                total_commits=stat['total_commits'],
                total_lines=stat['total_lines'],
                ai_lines=stat['ai_lines'],
                ai_percentage=stat['ai_percentage'],
                start_date=int(start.timestamp()),
                end_date=int(end.timestamp()),
                created_at=int(datetime.now().timestamp()),
                updated_at=int(datetime.now().timestamp())
            )
            saved.append(self.database.save_metrics_contributor_stat(record))

        return saved

    # Helper methods
    def _init_day_stat(self, date: str) -> dict:
        """初始化天统计"""
        return {
            'date': date,
            'date_ts': int(datetime.strptime(date, '%Y-%m-%d').timestamp()),
            'total_lines': 0,
            'ai_lines': 0,
            'total_commits': 0,
            'commits_with_ai': 0
        }

    def _init_week_stat(self, dt: datetime) -> dict:
        """初始化周统计"""
        # 计算周一
        monday = dt - timedelta(days=dt.weekday())
        return {
            'total_lines': 0,
            'ai_lines': 0,
            'total_commits': 0,
            'commits_with_ai': 0
        }

    def _init_month_stat(self, dt: datetime) -> dict:
        """初始化月统计"""
        return {
            'total_lines': 0,
            'ai_lines': 0,
            'total_commits': 0,
            'commits_with_ai': 0
        }

    def _init_repo_stat(self, event: dict) -> dict:
        """初始化仓库统计"""
        repo_url = event.get('repo_url', '')
        return {
            'repo_id': self._extract_repo_id(repo_url),
            'repo_name': self._extract_repo_name(repo_url),
            'total_lines': 0,
            'ai_lines': 0,
            'total_commits': 0,
            'commits_with_ai': 0
        }

    def _init_contributor_stat(self, granularity: str, author: str, date: datetime) -> dict:
        """初始化贡献者统计"""
        stat = {
            'author': author,
            'total_commits': 0,
            'total_lines': 0,
            'ai_lines': 0
        }

        if granularity == 'daily':
            stat['date'] = date.strftime('%Y-%m-%d')
            stat['date_ts'] = int(date.timestamp())
        elif granularity == 'weekly':
            iso_week = date.isocalendar()
            stat['year_week'] = f"{iso_week[0]}-W{iso_week[1]:02d}"
            monday = date - timedelta(days=date.weekday())
            stat['date_ts'] = int(monday.timestamp())
        elif granularity == 'monthly':
            stat['year_month'] = date.strftime('%Y-%m')
            month_start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            stat['date_ts'] = int(month_start.timestamp())

        return stat

    def _update_stat_with_event(self, stat: dict, event: dict):
        """用事件更新统计"""
        stat['total_lines'] += event.get('git_diff_added_lines', 0)

        # 解析 ai_additions 数组
        ai_additions = event.get('ai_additions')
        if ai_additions:
            try:
                arr = json.loads(ai_additions) if isinstance(ai_additions, str) else ai_additions
                ai_lines = arr[0] if arr and len(arr) > 0 else 0
                stat['ai_lines'] += ai_lines
            except:
                pass

        stat['total_commits'] += 1
        if stat['ai_lines'] > 0:
            stat['commits_with_ai'] += 1

        stat['ai_percentage'] = (stat['ai_lines'] / stat['total_lines'] * 100) if stat['total_lines'] > 0 else 0

    def _update_repo_stat_with_event(self, stat: dict, event: dict):
        """更新仓库统计"""
        self._update_stat_with_event(stat, event)

    def _update_contributor_stat_with_event(self, stat: dict, event: dict):
        """更新贡献者统计"""
        stat['total_lines'] += event.get('git_diff_added_lines', 0)

        ai_additions = event.get('ai_additions')
        if ai_additions:
            try:
                arr = json.loads(ai_additions) if isinstance(ai_additions, str) else ai_additions
                ai_lines = arr[0] if arr and len(arr) > 0 else 0
                stat['ai_lines'] += ai_lines
            except:
                pass

        stat['total_commits'] += 1
        stat['ai_percentage'] = (stat['ai_lines'] / stat['total_lines'] * 100) if stat['total_lines'] > 0 else 0

    def _extract_repo_id(self, repo_url: str) -> str:
        """从 URL 提取 repo ID（简化版）"""
        return hashlib.md5(repo_url.encode()).hexdigest()

    def _extract_repo_name(self, repo_url: str) -> str:
        """从 URL 提取仓库名"""
        parts = repo_url.strip('/').split('/')
        return parts[-1] if parts else 'unknown'
```

**Step 2: 测试导入**

Run: `python -c "from core.scheduler.metrics_task import MetricsAnalysisTask; print('Import OK')"`
Expected: `Import OK`

**Step 3: 提交**

```bash
git add core/scheduler/metrics_task.py
git commit -m "feat: 添加 MetricsAnalysisTask"
```

---

### Task 13: 配置和注册新定时任务

**Files:**
- Modify: `config.yaml`
- Modify: `core/scheduler/scheduler.py`

**Step 1: 更新 config.yaml 添加 git_ai 配置**

在 `config.yaml` 末尾添加：

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
# 找到 scheduler.jobs 节点并添加以下任务
# scheduler.jobs 新增:
#   - id: daily_metrics_stats
#     name: 每日 Metrics 统计
#     type: cron
#     cron: "0 2 * * *"
#     params:
#       granularity: daily
#   - id: weekly_metrics_stats
#     name: 每周 Metrics 统计
#     type: cron
#     cron: "0 3 * * 0"
#     params:
#       granularity: weekly
#   - id: monthly_metrics_stats
#     name: 每月 Metrics 统计
#     type: cron
#     cron: "0 4 1 * *"
#     params:
#       granularity: monthly
```

**Step 2: 更新 scheduler.py 支持 Metrics 任务**

在 `core/scheduler/scheduler.py` 中，找到任务注册部分，添加：

```python
from core.scheduler.metrics_task import MetricsAnalysisTask
```

然后在任务函数注册部分添加：

```python
def execute_metrics_analysis_task(job_config: dict) -> dict:
    """执行 Metrics 分析任务"""
    task = MetricsAnalysisTask(current_app.config)
    return task.execute()

# 在 register_jobs 函数中添加任务类型映射：
task_handlers = {
    # ... 现有映射
    'metrics_analysis': execute_metrics_analysis_task,
}
```

**然后在 register_jobs 函数中，遍历 jobs 配置时，处理 metrics 任务：**

找到 jobs 遍历的代码部分，在现有处理逻辑中添加：

```python
for job_config in jobs_config:
    job_id = job_config.get('id')

    # 检查是否为 metrics 任务
    if job_id in ['daily_metrics_stats', 'weekly_metrics_stats', 'monthly_metrics_stats']:
        task_type = 'metrics_analysis'
        job_config['task_type'] = task_type
    else:
        # 现有逻辑
        job_config['task_type'] = job_config.get('type', 'cron')

    # ... 后续代码不变
```

**Step 3: 测试配置加载**

Run: `python -c "from config_loader import ConfigLoader; c = ConfigLoader.load(); print('git_ai' in c); print(c.get('git_ai', {}).get('oauth', {}).get('secret_key'))"`
Expected: `True` 和一个 secret 值

**Step 4: 提交**

```bash
git add config.yaml core/scheduler/scheduler.py
git commit -m "feat: 配置和注册 Metrics 定时任务"
```

---

### Task 14: 更新包依赖 requirements.txt

**Files:**
- Modify: `requirements.txt`

**Step 1: 添加 PyJWT 依赖**

在 `requirements.txt` 末尾添加：

```
PyJWT>=2.8.0
```

**Step 2: 安装新依赖并验证**

Run: `pip install -r requirements.txt`
Expected: 安装 PyJWT 成功

**Step 3: 提交**

```bash
git add requirements.txt
git commit -m "chore: 添加 PyJWT 依赖"
```

---

## 阶段四：清理旧代码

### Task 15: 清理 git_ai.py 中的占位代码

**Files:**
- Modify: `api/routes/git_ai.py`

**Step 1: 清理 git_ai.py 内容**

如果保留此路由用于前端用户界面访问，可以保留并实现有用的端点，或删除占位路由。

建议删除占位代码并保留空蓝图用于未来扩展：

```python
"""Git-AI 相关 API（用户界面端点）"""
from flask import Blueprint

git_ai_bp = Blueprint('git_ai', __name__, url_prefix='/api/git-ai')

# 预留的 Git-AI 用户界面 API
# 例如：数据查询、展示页面等
```

**Step 2: 提交**

```bash
git add api/routes/git_ai.py
git commit -m "refactor: 清理 git_ai.py 占位代码"
```

---

## 总结

本实现计划包含 15 个任务，涵盖：

### 阶段一：基础设施 (Tasks 1-5)
- 数据模型定义
- Database 基类接口扩展
- SQLiteDatabase 表初始化
- Metrics 原始数据方法实现
- CAS 和汇总表方法实现

### 阶段二：API 实现 (Tasks 6-11)
- 认证中间件
- Services 层框架
- MetricsService
- OAuthService
- CasService
- API 路由实现和注册

### 阶段三：定时任务 (Tasks 12-13)
- MetricsAnalysisTask
- 配置和注册新定时任务

### 阶段四：依赖和清理 (Tasks 14-15)
- 更新依赖
- 清理旧代码

---

## 测试建议

1. **单元测试**: 为每个 Service 和 Task 编写单元测试
2. **集成测试**: 测试 API 端到端流程
3. **数据库测试**: 测试数据库 CRUD 操作
4. **定时任务测试**: 手动触发定时任务验证聚合逻辑

---

## 相关文档

- **设计文档**: `docs/plans/2026-03-17-git-ai-refactor-design.md`
- **API 文档**: `docs/git-ai-api-reference.md`
