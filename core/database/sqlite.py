import sqlite3
import json
import uuid
import os
from datetime import datetime
from typing import List, Dict, Optional
from .base import Database
from core.models.stats import StatRecord, RepoStatRecord, ContributorStatRecord
from core.models.metrics import (
    MetricsCommittedRecord,
    MetricsCheckpointRecord, MetricsAgentUsageRecord,
    MetricsInstallHooksRecord, MetricsDailyStat,
    MetricsWeeklyStat, MetricsMonthlyStat,
    MetricsRepoStat, MetricsContributorStat,
    MetricsRepo, MetricsContributor, MetricsRepoContributor
)
from core.config.logging import Logger


class SQLiteDatabase(Database):
    """SQLite 数据库实现"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.db_path = config.get('path', 'data/ai_stats.db')
        _ensure_db_directory(self.db_path)

        # 初始化日志记录器
        self.logger = Logger.get_logger('database.sqlite')

    def _get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)

    def init_db(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS stat_records (
                    id TEXT PRIMARY KEY,
                    timestamp INTEGER NOT NULL,
                    total_lines INTEGER DEFAULT 0,
                    total_ai_lines INTEGER DEFAULT 0,
                    overall_percentage REAL DEFAULT 0,
                    total_commits INTEGER DEFAULT 0,
                    commits_with_ai INTEGER DEFAULT 0,
                    start_date INTEGER,
                    end_date INTEGER,
                    repos_count INTEGER DEFAULT 0
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS repo_stat_records (
                    id TEXT PRIMARY KEY,
                    stat_id TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    repo_id TEXT NOT NULL,
                    provider_type TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    total_commits INTEGER DEFAULT 0,
                    commits_with_ai INTEGER DEFAULT 0,
                    start_date INTEGER,
                    end_date INTEGER,
                    commit_details TEXT,
                    FOREIGN KEY (stat_id) REFERENCES stat_records(id)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS contributor_stat_records (
                    id TEXT PRIMARY KEY,
                    stat_id TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    author_email TEXT NOT NULL,
                    total_commits INTEGER DEFAULT 0,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    repos_breakdown TEXT,
                    start_date INTEGER,
                    end_date INTEGER,
                    FOREIGN KEY (stat_id) REFERENCES stat_records(id)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS repo_contributor_stat_records (
                    id TEXT PRIMARY KEY,
                    stat_id TEXT NOT NULL,
                    repo_stat_id TEXT NOT NULL,
                    contributor_stat_id TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    repo_id TEXT NOT NULL,
                    provider_type TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    author_email TEXT NOT NULL,
                    total_commits INTEGER DEFAULT 0,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    start_date INTEGER,
                    end_date INTEGER,
                    commit_details TEXT,
                    FOREIGN KEY (stat_id) REFERENCES stat_records(id)
                )
            ''')

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

            # ============ 维度表 ============

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_repos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id TEXT NOT NULL UNIQUE,
                    repo_name TEXT NOT NULL,
                    repo_url TEXT NOT NULL,
                    provider_type TEXT,
                    branch TEXT,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    human_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    total_commits INTEGER DEFAULT 0,
                    ai_commits INTEGER DEFAULT 0,
                    tool_model_breakdown TEXT,
                    first_commit_ts INTEGER,
                    last_commit_ts INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_contributors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author TEXT NOT NULL UNIQUE,
                    author_email TEXT,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    human_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    total_commits INTEGER DEFAULT 0,
                    ai_commits INTEGER DEFAULT 0,
                    tool_model_breakdown TEXT,
                    first_commit_ts INTEGER,
                    last_commit_ts INTEGER,
                    repos_count INTEGER DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_repo_contributors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id TEXT NOT NULL,
                    author TEXT NOT NULL,
                    first_seen_ts INTEGER,
                    last_seen_ts INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(repo_id, author)
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
            conn.execute('CREATE INDEX IF NOT EXISTS idx_stat_timestamp ON stat_records(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_repo_stat_id ON repo_stat_records(stat_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_contributor_stat_id ON contributor_stat_records(stat_id)')
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

            # 维度表索引
            conn.execute('CREATE INDEX IF NOT EXISTS idx_repos_repo_id ON metrics_repos(repo_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_contributors_author ON metrics_contributors(author)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_repo_contributors_repo_author ON metrics_repo_contributors(repo_id, author)')

    def save_stats(self, stats: StatRecord) -> str:
        """保存统计数据"""
        stat_id = stats.id or str(uuid.uuid4())

        with self._get_connection() as conn:
            # 保存主记录
            conn.execute('''
                INSERT OR REPLACE INTO stat_records
                (id, timestamp, total_lines, total_ai_lines, overall_percentage,
                 total_commits, commits_with_ai, start_date, end_date, repos_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stat_id,
                int(stats.timestamp.timestamp()),
                stats.total_lines,
                stats.total_ai_lines,
                stats.overall_percentage,
                stats.total_commits,
                stats.commits_with_ai,
                int(stats.start_date.timestamp()) if stats.start_date else None,
                int(stats.end_date.timestamp()) if stats.end_date else None,
                stats.repos_count
            ))
            conn.commit()

        return stat_id

    def save_repo_stat(self, repo_stat: RepoStatRecord) -> str:
        """保存仓库统计数据"""
        stat_id = repo_stat.id or str(uuid.uuid4())

        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO repo_stat_records
                (id, stat_id, repo_name, repo_id, provider_type, branch,
                 total_lines, ai_lines, ai_percentage, total_commits, commits_with_ai,
                 start_date, end_date, commit_details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stat_id,
                repo_stat.stat_id,
                repo_stat.repo_name,
                repo_stat.repo_id,
                repo_stat.provider_type,
                repo_stat.branch,
                repo_stat.total_lines,
                repo_stat.ai_lines,
                repo_stat.ai_percentage,
                repo_stat.total_commits,
                repo_stat.commits_with_ai,
                int(repo_stat.start_date.timestamp()) if repo_stat.start_date else None,
                int(repo_stat.end_date.timestamp()) if repo_stat.end_date else None,
                json.dumps(repo_stat.commit_details) if repo_stat.commit_details else None
            ))
            conn.commit()

        return stat_id

    def get_latest_stat(self) -> Optional[Dict]:
        """获取最新的统计记录"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM stat_records ORDER BY timestamp DESC LIMIT 1'
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def get_stats_history(self, start: Optional[datetime] = None,
                         end: Optional[datetime] = None,
                         limit: int = 100) -> List[Dict]:
        """获取统计历史记录"""
        query = 'SELECT * FROM stat_records'
        params = []

        conditions = []
        if start:
            conditions.append('timestamp >= ?')
            params.append(int(start.timestamp()))
        if end:
            conditions.append('timestamp <= ?')
            params.append(int(end.timestamp()))

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_stat_by_id(self, stat_id: str) -> Optional[Dict]:
        """根据 ID 获取单条统计记录"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM stat_records WHERE id = ?', (stat_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def get_repo_stats(self, stat_id: Optional[str] = None,
                      repo_name: Optional[str] = None) -> List[RepoStatRecord]:
        """获取仓库级统计数据"""
        query = 'SELECT * FROM repo_stat_records'
        params = []
        conditions = []

        if stat_id:
            conditions.append('stat_id = ?')
            params.append(stat_id)
        if repo_name:
            conditions.append('repo_name = ?')
            params.append(repo_name)

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            records = []
            for row in cursor.fetchall():
                record = self._row_to_dict(row)
                # 解析 JSON 字段
                if record.get('commit_details'):
                    record['commit_details'] = json.loads(record['commit_details'])
                records.append(RepoStatRecord(**record))
            return records

    def get_contributor_stats(self, stat_id: Optional[str] = None,
                              author_email: Optional[str] = None) -> List[ContributorStatRecord]:
        """获取贡献者级统计数据"""
        query = 'SELECT * FROM contributor_stat_records'
        params = []
        conditions = []

        if stat_id:
            conditions.append('stat_id = ?')
            params.append(stat_id)
        if author_email:
            conditions.append('author_email = ?')
            params.append(author_email)

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            records = []
            for row in cursor.fetchall():
                record = self._row_to_dict(row)
                if record.get('repos_breakdown'):
                    record['repos_breakdown'] = json.loads(record['repos_breakdown'])
                records.append(ContributorStatRecord(**record))
            return records

    def validate_connection(self) -> bool:
        """验证数据库连接"""
        try:
            with self._get_connection() as conn:
                conn.execute('SELECT 1')
                return True
        except Exception:
            return False

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """将 SQLite Row 转换为 Dict"""
        return dict(row)

    # ========== Metrics 原始数据方法 ==========

    def save_metrics_raw(self, batch_id: str, version: int,
                        event_count: int, payload_json: str,
                        received_at: int) -> int | None:
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

    def get_committed_events_in_range(self, start: datetime, end: datetime) -> List[Dict]:
        """获取时间范围内的 Committed 事件"""
        query = 'SELECT * FROM metrics_events_committed WHERE timestamp >= ? AND timestamp <= ?'
        params = (int(start.timestamp()), int(end.timestamp()))

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]

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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?  )
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

    def save_agent_usage_event(self, event: MetricsAgentUsageRecord) -> int:
        """保存 AgentUsage 事件"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_events_agent_usage
                (raw_id, event_id, timestamp, git_ai_version, repo_url, author,
                 commit_sha, base_commit_sha, branch, tool, model,
                 prompt_id, external_prompt_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.raw_id, event.event_id, event.timestamp, event.git_ai_version,
                event.repo_url, event.author, event.commit_sha,
                event.base_commit_sha, event.branch, event.tool,
                event.model, event.prompt_id, event.external_prompt_id,
                event.created_at
            ))
            conn.commit()
            return cursor.lastrowid

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

    # ========== CAS 方法 ==========

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

    # ========== Metrics 汇总表方法 ==========

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

    def get_latest_metrics_stat(self, granularity: str) -> Optional[Dict]:
        """获取最新的统计记录（day/week/month）"""
        table_map = {
            'day': 'metrics_daily_stats',
            'week': 'metrics_weekly_stats',
            'month': 'metrics_monthly_stats',
            'daily': 'metrics_daily_stats',
            'weekly': 'metrics_weekly_stats',
            'monthly': 'metrics_monthly_stats'
        }
        table = table_map.get(granularity)
        if not table:
            return None

        order_col_map = {
            'daily': 'date_ts',
            'metrics_daily_stats': 'date_ts',
            'weekly': 'week_start_ts',
            'metrics_weekly_stats': 'week_start_ts',
            'month': 'month_start_ts',
            'metrics_monthly_stats': 'month_start_ts'
        }
        order_col = order_col_map.get(table, 'id')

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f'SELECT * FROM {table} ORDER BY {order_col} DESC LIMIT 1'
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    # ========== 维度表方法 ==========

    def save_metrics_repo(self, repo: MetricsRepo) -> int:
        """保存仓库维度记录，返回记录 id"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_repos (
                    repo_id, repo_name, repo_url, provider_type, branch,
                    total_lines, ai_lines, human_lines, ai_percentage,
                    total_commits, ai_commits, tool_model_breakdown,
                    first_commit_ts, last_commit_ts, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                repo.repo_id, repo.repo_name, repo.repo_url,
                repo.provider_type, repo.branch,
                repo.total_lines, repo.ai_lines, repo.human_lines,
                repo.ai_percentage, repo.total_commits, repo.ai_commits,
                repo.tool_model_breakdown,
                repo.first_commit_ts, repo.last_commit_ts,
                repo.created_at, repo.updated_at
            ))
            conn.commit()
            return cursor.lastrowid

    def get_metrics_repo(self, repo_id: str) -> Optional[Dict]:
        """获取仓库维度记录"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM metrics_repos WHERE repo_id = ?',
                (repo_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def get_metrics_repos(self, page: int = 1, page_size: int = 20,
                          sort: str = None) -> Dict:
        """获取仓库维度列表，支持分页和排序"""
        offset = (page - 1) * page_size

        # 构建查询
        if sort:
            # 简单排序验证
            allowed_sorts = [
                'total_lines', 'ai_lines', 'ai_percentage',
                'total_commits', 'ai_commits',
                'created_at', 'updated_at'
            ]
            if sort in allowed_sorts:
                order_clause = f'ORDER BY {sort} DESC'
            else:
                order_clause = 'ORDER BY created_at DESC'
        else:
            order_clause = 'ORDER BY created_at DESC'

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            # 查询总数
            cursor = conn.execute('SELECT COUNT(*) FROM metrics_repos')
            total = cursor.fetchone()[0]

            # 查询数据
            cursor = conn.execute(f'''
                SELECT * FROM metrics_repos
                {order_clause}
                LIMIT ? OFFSET ?
            ''', (page_size, offset))

            data = [self._row_to_dict(row) for row in cursor.fetchall()]

            return {
                'data': data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': (total + page_size - 1) // page_size
                }
            }

    def save_metrics_contributor(self, contributor: MetricsContributor) -> int:
        """保存作者维度记录，返回记录 id"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_contributors (
                    author, author_email,
                    total_lines, ai_lines, human_lines, ai_percentage,
                    total_commits, ai_commits, tool_model_breakdown,
                    first_commit_ts, last_commit_ts, repos_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                contributor.author, contributor.author_email,
                contributor.total_lines, contributor.ai_lines,
                contributor.human_lines, contributor.ai_percentage,
                contributor.total_commits, contributor.ai_commits,
                contributor.tool_model_breakdown,
                contributor.first_commit_ts, contributor.last_commit_ts,
                contributor.repos_count,
                contributor.created_at, contributor.updated_at
            ))
            conn.commit()
            return cursor.lastrowid

    def get_metrics_contributor(self, author: str) -> Optional[Dict]:
        """获取作者维度记录"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM metrics_contributors WHERE author = ?',
                (author,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def get_metrics_contributors(self, page: int = 1, page_size: int = 20,
                                  sort: str = None) -> Dict:
        """获取作者维度列表，支持分页和排序"""
        offset = (page - 1) * page_size

        if sort:
            allowed_sorts = [
                'total_lines', 'ai_lines', 'ai_percentage',
                'total_commits', 'ai_commits',
                'created_at', 'updated_at'
            ]
            if sort in allowed_sorts:
                order_clause = f'ORDER BY {sort} DESC'
            else:
                order_clause = 'ORDER BY created_at DESC'
        else:
            order_clause = 'ORDER BY created_at DESC'

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT COUNT(*) FROM metrics_contributors')
            total = cursor.fetchone()[0]

            cursor = conn.execute(f'''
                SELECT * FROM metrics_contributors
                {order_clause}
                LIMIT ? OFFSET ?
            ''', (page_size, offset))

            data = [self._row_to_dict(row) for row in cursor.fetchall()]

            return {
                'data': data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': (total + page_size - 1) // page_size
                }
            }

    def save_metrics_repo_contributor(
        self, repo_contributor: MetricsRepoContributor
    ) -> int:
        """保存仓库作者关联记录，返回记录 id"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_repo_contributors (
                    repo_id, author, first_seen_ts, last_seen_ts,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                repo_contributor.repo_id, repo_contributor.author,
                repo_contributor.first_seen_ts, repo_contributor.last_seen_ts,
                repo_contributor.created_at, repo_contributor.updated_at
            ))
            conn.commit()
            return cursor.lastrowid

    def get_metrics_repo_contributors(
        self, repo_id: str = None, author: str = None,
        page: int = 1, page_size: int = 20
    ) -> Dict:
        """获取仓库作者关联列表，支持按仓库或作者筛选"""
        offset = (page - 1) * page_size

        # 构建查询条件
        where_clause = ''
        params = []

        if repo_id and author:
            where_clause = 'WHERE repo_id = ? AND author = ?'
            params.append(repo_id)
            params.append(author)
        elif repo_id:
            where_clause = 'WHERE repo_id = ?'
            params.append(repo_id)
        elif author:
            where_clause = 'WHERE author = ?'
            params.append(author)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            count_sql = f'SELECT COUNT(*) FROM metrics_repo_contributors {where_clause}'
            cursor = conn.execute(count_sql, params)
            total = cursor.fetchone()[0]

            data_sql = f'''
                SELECT * FROM metrics_repo_contributors
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            '''
            cursor = conn.execute(data_sql, params + [page_size, offset])

            data = [self._row_to_dict(row) for row in cursor.fetchall()]

            return {
                'data': data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': (total + page_size - 1) // page_size
                }
            }


    # ========== 聚合任务辅助方法 ==========

    def get_latest_daily_stat(self) -> Optional[MetricsDailyStat]:
        """获取最新的日统计记录"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM metrics_daily_stats ORDER BY date_ts DESC LIMIT 1'
            )
            row = cursor.fetchone()
            if row:
                data = self._row_to_dict(row)
                return MetricsDailyStat(**data)
            return None

    def get_latest_weekly_stat(self) -> Optional[MetricsWeeklyStat]:
        """获取最新的周统计记录"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM metrics_weekly_stats ORDER BY week_start_ts DESC LIMIT 1'
            )
            row = cursor.fetchone()
            if row:
                data = self._row_to_dict(row)
                return MetricsWeeklyStat(**data)
            return None

    def get_latest_monthly_stat(self) -> Optional[MetricsMonthlyStat]:
        """获取最新的月统计记录"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM metrics_monthly_stats ORDER BY month_start_ts DESC LIMIT 1'
            )
            row = cursor.fetchone()
            if row:
                data = self._row_to_dict(row)
                return MetricsMonthlyStat(**data)
            return None

    def get_all_repo_urls(self) -> List[str]:
        """获取所有仓库 URL 列表"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                'SELECT DISTINCT repo_url FROM metrics_events_committed WHERE repo_url IS NOT NULL'
            )
            return [row[0] for row in cursor.fetchall()]

    def get_all_authors(self) -> List[str]:
        """获取所有作者列表"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                'SELECT DISTINCT author FROM metrics_events_committed WHERE author IS NOT NULL'
            )
            return [row[0] for row in cursor.fetchall()]

    def get_committed_events_by_date_range(self, start_ts: int, end_ts: int) -> List[Dict]:
        """按时间范围查询 committed 事件"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM metrics_events_committed WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp',
                (start_ts, end_ts)
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_committed_events_by_repo(self, repo_url: str) -> List[Dict]:
        """按仓库查询 committed 事件"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM metrics_events_committed WHERE repo_url = ? ORDER BY timestamp',
                (repo_url,)
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_committed_events_by_author(self, author: str) -> List[Dict]:
        """按作者查询 committed 事件"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM metrics_events_committed WHERE author = ? ORDER BY timestamp',
                (author,)
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]


def _ensure_db_directory(db_path: str):
    """确保数据库目录存在"""
    db_abspath = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(db_abspath, exist_ok=True)

