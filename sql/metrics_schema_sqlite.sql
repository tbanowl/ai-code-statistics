-- ============================================================================
-- Git-AI Metrics DDL Script for SQLite
-- ============================================================================
-- 版本: 1.0
-- 日期: 2026-03-17
-- 说明: 基于 git-ai-client API 设计的 Metrics 数据存储表结构
-- ============================================================================

-- 启用外键约束
PRAGMA foreign_keys = ON;

-- ============================================================================
-- Metrics 原始数据表
-- ============================================================================

-- metrics_events_raw (原始事件表)
CREATE TABLE IF NOT EXISTS metrics_events_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    event_count INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    received_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_raw_batch_id ON metrics_events_raw(batch_id);
CREATE INDEX IF NOT EXISTS idx_metrics_raw_received_at ON metrics_events_raw(received_at);

-- metrics_events_committed (Committed 事件表)
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
);

CREATE INDEX IF NOT EXISTS idx_committed_timestamp ON metrics_events_committed(timestamp);
CREATE INDEX IF NOT EXISTS idx_committed_repo_url ON metrics_events_committed(repo_url);
CREATE INDEX IF NOT EXISTS idx_committed_author ON metrics_events_committed(author);
CREATE INDEX IF NOT EXISTS idx_committed_commit_sha ON metrics_events_committed(commit_sha);

-- metrics_events_checkpoint (Checkpoint 事件表)
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
);

CREATE INDEX IF NOT EXISTS idx_checkpoint_timestamp ON metrics_events_checkpoint(timestamp);

-- metrics_events_agent_usage (AgentUsage 事件表)
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
);

CREATE INDEX IF NOT EXISTS idx_agent_usage_timestamp ON metrics_events_agent_usage(timestamp);

-- metrics_events_install_hooks (InstallHooks 事件表)
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
);

-- ============================================================================
-- Metrics 汇总统计表
-- ============================================================================

CREATE TABLE IF NOT EXISTS metrics_daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
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
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON metrics_daily_stats(date);

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
);

CREATE INDEX IF NOT EXISTS idx_weekly_stats_year_week ON metrics_weekly_stats(year, week);

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
);

CREATE INDEX IF NOT EXISTS idx_monthly_stats_year_month ON metrics_monthly_stats(year, month);

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
    start_date INTEGER,
    end_date INTEGER,
    tool_model_breakdown TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(repo_id, repo_name)
);

CREATE INDEX IF NOT EXISTS idx_repo_stats_repo ON metrics_repo_stats(repo_id, repo_name);

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
);

CREATE INDEX IF NOT EXISTS idx_contributor_stats_author_granularity ON metrics_contributor_stats(author, granularity, date, year_week, year_month);
CREATE INDEX IF NOT EXISTS idx_contributor_stats_date_ts ON metrics_contributor_stats(date_ts);
CREATE INDEX IF NOT EXISTS idx_contributor_stats_granularity ON metrics_contributor_stats(granularity);

-- ============================================================================
-- CAS 对象表
-- ============================================================================

CREATE TABLE IF NOT EXISTS cas_objects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,
    content_json TEXT,
    metadata_json TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cas_hash ON cas_objects(hash);

-- ============================================================================
-- 维度主表
-- ============================================================================

-- metrics_repos (仓库维度主表)
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
);

CREATE INDEX IF NOT EXISTS idx_repos_repo_id ON metrics_repos(repo_id);
CREATE INDEX IF NOT EXISTS idx_repos_repo_name ON metrics_repos(repo_name);

-- metrics_contributors (作者维度主表)
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
);

CREATE INDEX IF NOT EXISTS idx_contributors_author ON metrics_contributors(author);
CREATE INDEX IF NOT EXISTS idx_contributors_author_email ON metrics_contributors(author_email);

-- metrics_repo_contributors (仓库作者关联表)
CREATE TABLE IF NOT EXISTS metrics_repo_contributors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id TEXT NOT NULL,
    author TEXT NOT NULL,
    first_seen_ts INTEGER,
    last_seen_ts INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(repo_id, author)
);

CREATE INDEX IF NOT EXISTS idx_repo_contributors_repo_author ON metrics_repo_contributors(repo_id, author);

-- ============================================================================
-- 完成
-- ============================================================================
