-- ============================================================================
-- Git-AI Metrics DDL Script for PostgreSQL
-- ============================================================================
-- 版本: 1.0
-- 日期: 2026-03-17
-- 说明: 基于 git-ai-client API 设计的 Metrics 数据存储表结构
-- ============================================================================

-- ============================================================================
-- Metrics 原始数据表
-- ============================================================================

-- metrics_events_raw (原始事件表)
CREATE TABLE IF NOT EXISTS metrics_events_raw (
    id BIGSERIAL PRIMARY KEY,
    batch_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    event_count INTEGER NOT NULL,
    payload_json JSONB NOT NULL,
    received_at BIGINT NOT NULL,
    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
);

CREATE INDEX IF NOT EXISTS idx_metrics_raw_batch_id ON metrics_events_raw(batch_id);
CREATE INDEX IF NOT EXISTS idx_metrics_raw_received_at ON metrics_events_raw(received_at);

-- metrics_events_committed (Committed 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_committed (
    id BIGSERIAL PRIMARY KEY,
    raw_id BIGINT,
    event_id INTEGER NOT NULL DEFAULT 1,
    timestamp BIGINT NOT NULL,

    -- Scalar values
    human_additions INTEGER,
    git_diff_deleted_lines INTEGER,
    git_diff_added_lines INTEGER,
    first_checkpoint_ts BIGINT,
    commit_subject TEXT,
    commit_body TEXT,

    -- Array values (JSONB 存储，索引 0=all, 1+=per tool)
    tool_model_pairs JSONB,
    mixed_additions JSONB,
    ai_additions JSONB,
    ai_accepted JSONB,
    total_ai_additions JSONB,
    total_ai_deletions JSONB,
    time_waiting_for_ai JSONB,

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
    custom_attributes JSONB,

    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,

    CONSTRAINT fk_committed_raw FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_committed_timestamp ON metrics_events_committed(timestamp);
CREATE INDEX IF NOT EXISTS idx_committed_repo_url ON metrics_events_committed(repo_url);
CREATE INDEX IF NOT EXISTS idx_committed_author ON metrics_events_committed(author);
CREATE INDEX IF NOT EXISTS idx_committed_commit_sha ON metrics_events_committed(commit_sha);
CREATE INDEX IF NOT EXISTS idx_committed_ai_additions ON metrics_events_committed USING GIN (ai_additions);

-- metrics_events_checkpoint (Checkpoint 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_checkpoint (
    id BIGSERIAL PRIMARY KEY,
    raw_id BIGINT,
    event_id INTEGER NOT NULL DEFAULT 4,
    timestamp BIGINT NOT NULL,

    -- Values
    checkpoint_ts BIGINT,
    kind TEXT,
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

    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,

    CONSTRAINT fk_checkpoint_raw FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_checkpoint_timestamp ON metrics_events_checkpoint(timestamp);
CREATE INDEX IF NOT EXISTS idx_checkpoint_file_path ON metrics_events_checkpoint(file_path);

-- metrics_events_agent_usage (AgentUsage 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_agent_usage (
    id BIGSERIAL PRIMARY KEY,
    raw_id BIGINT,
    event_id INTEGER NOT NULL DEFAULT 2,
    timestamp BIGINT NOT NULL,

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

    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,

    CONSTRAINT fk_agent_usage_raw FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_usage_timestamp ON metrics_events_agent_usage(timestamp);

-- metrics_events_install_hooks (InstallHooks 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_install_hooks (
    id BIGSERIAL PRIMARY KEY,
    raw_id BIGINT,
    event_id INTEGER NOT NULL DEFAULT 3,
    timestamp BIGINT NOT NULL,

    -- Values
    tool_id TEXT,
    status TEXT,
    message TEXT,

    -- Event attributes
    git_ai_version TEXT,

    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,

    CONSTRAINT fk_install_hooks_raw FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id) ON DELETE CASCADE
);

-- ============================================================================
-- Metrics 汇总统计表
-- ============================================================================

-- metrics_daily_stats (按天汇总)
CREATE TABLE IF NOT EXISTS metrics_daily_stats (
    id BIGSERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    date_ts BIGINT NOT NULL,

    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    ai_percentage NUMERIC(5, 2) DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    commits_with_ai INTEGER DEFAULT 0,

    tool_model_breakdown JSONB,

    start_date BIGINT,
    end_date BIGINT,

    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,
    updated_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,

    CONSTRAINT uk_daily_stats_date UNIQUE(date)
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON metrics_daily_stats(date);
CREATE INDEX IF NOT EXISTS idx_daily_stats_date_ts ON metrics_daily_stats(date_ts);
CREATE INDEX IF NOT EXISTS idx_daily_stats_breakdown ON metrics_daily_stats USING GIN (tool_model_breakdown);

-- metrics_weekly_stats (按周汇总)
CREATE TABLE IF NOT EXISTS metrics_weekly_stats (
    id BIGSERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,
    week_start TEXT NOT NULL,
    week_start_ts BIGINT NOT NULL,
    week_end TEXT NOT NULL,
    week_end_ts BIGINT NOT NULL,

    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    ai_percentage NUMERIC(5, 2) DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    commits_with_ai INTEGER DEFAULT 0,
    tool_model_breakdown JSONB,

    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,
    updated_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,

    CONSTRAINT uk_weekly_stats_year_week UNIQUE(year, week)
);

CREATE INDEX IF NOT EXISTS idx_weekly_stats_year_week ON metrics_weekly_stats(year, week);
CREATE INDEX IF NOT EXISTS idx_weekly_stats_week_start_ts ON metrics_weekly_stats(week_start_ts);

-- metrics_monthly_stats (按月汇总)
CREATE TABLE IF NOT EXISTS metrics_monthly_stats (
    id BIGSERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_start TEXT NOT NULL,
    month_start_ts BIGINT NOT NULL,
    month_end TEXT NOT NULL,
    month_end_ts BIGINT NOT NULL,

    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    ai_percentage NUMERIC(5, 2) DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    commits_with_ai INTEGER DEFAULT 0,
    tool_model_breakdown JSONB,

    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,
    updated_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,

    CONSTRAINT uk_monthly_stats_year_month UNIQUE(year, month)
);

CREATE INDEX IF NOT EXISTS idx_monthly_stats_year_month ON metrics_monthly_stats(year, month);
CREATE INDEX IF NOT EXISTS idx_monthly_stats_month_start_ts ON metrics_monthly_stats(month_start_ts);

-- metrics_repo_stats (按仓库汇总)
CREATE TABLE IF NOT EXISTS metrics_repo_stats (
    id BIGSERIAL PRIMARY KEY,
    repo_id TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    repo_url TEXT NOT NULL,
    provider_type TEXT,
    branch TEXT,

    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    ai_percentage NUMERIC(5, 2) DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    commits_with_ai INTEGER DEFAULT 0,

    start_date BIGINT,
    end_date BIGINT,
    tool_model_breakdown JSONB,

    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,
    updated_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,

    CONSTRAINT uk_repo_stats UNIQUE(repo_id, repo_name)
);

CREATE INDEX IF NOT EXISTS idx_repo_stats_repo ON metrics_repo_stats(repo_id, repo_name);
CREATE INDEX IF NOT EXISTS idx_repo_stats_url ON metrics_repo_stats(repo_url);

-- metrics_contributor_stats (按贡献者多粒度汇总)
CREATE TABLE IF NOT EXISTS metrics_contributor_stats (
    id BIGSERIAL PRIMARY KEY,
    author TEXT NOT NULL,
    author_email TEXT,

    granularity TEXT NOT NULL DEFAULT 'daily',

    date TEXT,
    year_week TEXT,
    year_month TEXT,
    date_ts BIGINT NOT NULL,

    total_commits INTEGER DEFAULT 0,
    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    ai_percentage NUMERIC(5, 2) DEFAULT 0,
    repos_breakdown JSONB,

    start_date BIGINT,
    end_date BIGINT,

    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,
    updated_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,

    CONSTRAINT uk_contributor_stats UNIQUE(author, granularity, date, year_week, year_month)
);

CREATE INDEX IF NOT EXISTS idx_contributor_stats_author_granularity ON metrics_contributor_stats(author, granularity);
CREATE INDEX IF NOT EXISTS idx_contributor_stats_date_ts ON metrics_contributor_stats(date_ts);
CREATE INDEX IF NOT EXISTS idx_contributor_stats_author_date ON metrics_contributor_stats(author, date);
CREATE INDEX IF NOT EXISTS idx_contributor_stats_repos_breakdown ON metrics_contributor_stats USING GIN (repos_breakdown);

-- ============================================================================
-- CAS 对象表
-- ============================================================================

CREATE TABLE IF NOT EXISTS cas_objects (
    id BIGSERIAL PRIMARY KEY,
    hash TEXT UNIQUE NOT NULL,
    content_json JSONB,
    metadata_json JSONB,
    created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,
    updated_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
);

CREATE INDEX IF NOT EXISTS idx_cas_hash ON cas_objects(hash);

-- ============================================================================
-- 触发器: 自动更新 updated_at 字段
-- ============================================================================

-- 创建更新时间戳触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为需要的表添加触发器
-- DROP TRIGGER IF EXISTS trigger_update_daily_stats_updated_at ON metrics_daily_stats;
CREATE TRIGGER trigger_update_daily_stats_updated_at
    BEFORE UPDATE ON metrics_daily_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- DROP TRIGGER IF EXISTS trigger_update_weekly_stats_updated_at ON metrics_weekly_stats;
CREATE TRIGGER trigger_update_weekly_stats_updated_at
    BEFORE UPDATE ON metrics_weekly_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- DROP TRIGGER IF EXISTS trigger_update_monthly_stats_updated_at ON metrics_monthly_stats;
CREATE TRIGGER trigger_update_monthly_stats_updated_at
    BEFORE UPDATE ON metrics_monthly_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- DROP TRIGGER IF EXISTS trigger_update_repo_stats_updated_at ON metrics_repo_stats;
CREATE TRIGGER trigger_update_repo_stats_updated_at
    BEFORE UPDATE ON metrics_repo_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- DROP TRIGGER IF EXISTS trigger_update_contributor_stats_updated_at ON metrics_contributor_stats;
CREATE TRIGGER trigger_update_contributor_stats_updated_at
    BEFORE UPDATE ON metrics_contributor_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- DROP TRIGGER IF EXISTS trigger_update_cas_objects_updated_at ON cas_objects;
CREATE TRIGGER trigger_update_cas_objects_updated_at
    BEFORE UPDATE ON cas_objects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 完成
-- ============================================================================
