-- ============================================================================
-- APScheduler JobStore 表结构 - PostgreSQL
-- ============================================================================
-- 此脚本用于创建 APScheduler SQLAlchemyJobStore 所需的数据库表
-- 注意：APScheduler 支持自动创建表，此脚本仅用于文档化和审计
-- ============================================================================

-- apscheduler_jobs (任务调度状态表)
CREATE TABLE IF NOT EXISTS apscheduler_jobs (
    -- 任务唯一标识（对应 job_id）
    id VARCHAR(191) NOT NULL,
    -- 下次运行时间（带时区的时间戳）
    next_run_time TIMESTAMP WITH TIME ZONE,
    -- 任务序列化状态（包含 trigger, func, args 等）
    job_state BYTEA NOT NULL,
    -- 主键约束
    PRIMARY KEY (id)
);

-- 索引：按下次运行时间查询（提高查询调度器性能）
CREATE INDEX IF NOT EXISTS idx_apscheduler_jobs_next_run_time
ON apscheduler_jobs (next_run_time);

-- ============================================================================
-- 完成
-- ============================================================================
