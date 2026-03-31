-- ============================================================================
-- Git-AI Metrics DDL Script for SQLite
-- ============================================================================
-- 版本: 2.0
-- 日期: 2026-03-24
-- 说明: 基于 core/database/models.py 实体定义的数据库表结构
--       所有主键使用 XID (VARCHAR(20))
--       所有时间字段使用毫秒时间戳 (BIGINT)
--       不使用外键约束，关系通过应用层维护
-- ============================================================================

-- ============================================================================
-- Metrics 事件表
-- ============================================================================

-- metrics_events_raw (原始事件表)
CREATE TABLE IF NOT EXISTS metrics_events_raw (
    -- 主键，使用 XID (20字符字符串)
    id VARCHAR(20) PRIMARY KEY,
    -- 批次版本号
    version INTEGER NOT NULL DEFAULT 1,
    -- 批次中的事件数量
    event_count INTEGER NOT NULL,
    -- 原始 JSON 载荷数据
    payload_json TEXT NOT NULL,
    -- 提取标识：0-未提取、1-提取成功、2-提取中、3-提取失败
    extract INTEGER NOT NULL DEFAULT 0,
    -- 提取失败原因
    extract_fail TEXT,
    -- 接收时间戳（毫秒）
    received_at BIGINT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

-- 索引：按接收时间查询
CREATE INDEX IF NOT EXISTS idx_metrics_raw_received_at ON metrics_events_raw(received_at);

-- metrics_events_committed (Committed 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_committed (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 唯一标识符
    uid TEXT NOT NULL,
    -- 关联的原始批次表 ID
    raw_id VARCHAR(20),
    -- 事件类型 ID (1=Committed)
    event_id INTEGER NOT NULL DEFAULT 1,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- ==================== 标量值字段 ====================

    -- 人类手动添加的代码行数
    human_additions INTEGER,
    -- Git diff 删除的代码行数
    git_diff_deleted_lines INTEGER,
    -- Git diff 新增的代码行数
    git_diff_added_lines INTEGER,
    -- 首次检查点时间戳
    first_checkpoint_ts BIGINT,
    -- 提交标题
    commit_subject TEXT,
    -- 提交内容
    commit_body TEXT,
    -- ==================== JSON 存储字段 ====================

    -- 工具-模型配对，JSON 数组格式（索引 0 为总计，其他为各工具统计）
    tool_model_pairs TEXT,
    -- 混合生成的代码行数，JSON 数组格式
    mixed_additions TEXT,
    -- AI 生成的代码行数，JSON 数组格式
    ai_additions TEXT,
    -- 接受的 AI 代码行数，JSON 数组格式
    ai_accepted TEXT,
    -- 总计 AI 新增代码行数，JSON 数组格式
    total_ai_additions TEXT,
    -- 总计 AI 删除代码行数，JSON 数组格式
    total_ai_deletions TEXT,
    -- 等待 AI 响应的时间，JSON 数组格式
    time_waiting_for_ai TEXT,
    -- ==================== 事件属性字段 ====================

    -- Git-AI 客户端版本号
    git_ai_version TEXT,
    -- 仓库 URL
    repo_url TEXT,
    -- 提交作者
    author TEXT,
    -- 提交的 SHA 校验码
    commit_sha TEXT,
    -- 基础提交的 SHA 校验码
    base_commit_sha TEXT,
    -- 分支名称
    branch TEXT,
    -- 使用的工具（如 claude, copilot）
    tool TEXT,
    -- 使用的模型（如 claude-opus-4-6）
    model TEXT,
    -- 提示词 ID
    prompt_id TEXT,
    -- 外部提示词 ID
    external_prompt_id TEXT,
    -- 自定义属性，JSON 格式
    custom_attributes TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

-- 索引：按时间戳查询
CREATE INDEX IF NOT EXISTS idx_committed_timestamp ON metrics_events_committed(timestamp);
-- 索引：按仓库 URL 查询
CREATE INDEX IF NOT EXISTS idx_committed_repo_url ON metrics_events_committed(repo_url);
-- 索引：按作者查询
CREATE INDEX IF NOT EXISTS idx_committed_author ON metrics_events_committed(author);
-- 索引：按提交 SHA 查询
CREATE INDEX IF NOT EXISTS idx_committed_commit_sha ON metrics_events_committed(commit_sha);

-- metrics_events_checkpoint (Checkpoint 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_checkpoint (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 唯一标识符
    uid TEXT NOT NULL,
    -- 关联的原始批次表 ID
    raw_id VARCHAR(20),
    -- 事件类型 ID (4=Checkpoint)
    event_id INTEGER NOT NULL DEFAULT 4,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- 检查点时间戳
    checkpoint_ts BIGINT,
    -- 检查点类型
    kind TEXT,
    -- 文件路径
    file_path TEXT,
    -- 新增代码行数
    lines_added INTEGER,
    -- 删除代码行数
    lines_deleted INTEGER,
    -- 新增代码源代码行数（不含注释和空行）
    lines_added_sloc INTEGER,
    -- 删除代码源代码行数（不含注释和空行）
    lines_deleted_sloc INTEGER,
    -- Git-AI 客户端版本号
    git_ai_version TEXT,
    -- 仓库 URL
    repo_url TEXT,
    -- 提交作者
    author TEXT,
    -- 提交的 SHA 校验码
    commit_sha TEXT,
    -- 基础提交的 SHA 校验码
    base_commit_sha TEXT,
    -- 分支名称
    branch TEXT,
    -- 使用的工具
    tool TEXT,
    -- 使用的模型
    model TEXT,
    -- 提示词 ID
    prompt_id TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

-- 索引：按时间戳查询
CREATE INDEX IF NOT EXISTS idx_checkpoint_timestamp ON metrics_events_checkpoint(timestamp);
-- 索引：按文件路径查询
CREATE INDEX IF NOT EXISTS idx_checkpoint_file_path ON metrics_events_checkpoint(file_path);

-- metrics_events_agent_usage (AgentUsage 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_agent_usage (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 唯一标识符
    uid TEXT NOT NULL,
    -- 关联的原始批次表 ID
    raw_id VARCHAR(20),
    -- 事件类型 ID (2=AgentUsage)
    event_id INTEGER NOT NULL DEFAULT 2,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- Git-AI 客户端版本号
    git_ai_version TEXT,
    -- 仓库 URL
    repo_url TEXT,
    -- 提交作者
    author TEXT,
    -- 提交的 SHA 校验码
    commit_sha TEXT,
    -- 基础提交的 SHA 校验码
    base_commit_sha TEXT,
    -- 分支名称
    branch TEXT,
    -- 使用的工具
    tool TEXT,
    -- 使用的模型
    model TEXT,
    -- 提示词 ID
    prompt_id TEXT,
    -- 外部提示词 ID
    external_prompt_id TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

-- 索引：按时间戳查询
CREATE INDEX IF NOT EXISTS idx_agent_usage_timestamp ON metrics_events_agent_usage(timestamp);

-- metrics_events_install_hooks (InstallHooks 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_install_hooks (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 唯一标识符
    uid TEXT NOT NULL,
    -- 关联的原始批次表 ID
    raw_id VARCHAR(20),
    -- 事件类型 ID (3=InstallHooks)
    event_id INTEGER NOT NULL DEFAULT 3,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- 工具 ID
    tool_id TEXT,
    -- 安装状态
    status TEXT,
    -- 安装消息
    message TEXT,
    -- Git-AI 客户端版本号
    git_ai_version TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

-- metrics_event_errors (事件解析错误记录表)
CREATE TABLE IF NOT EXISTS metrics_event_errors (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 关联的原始批次表 ID
    raw_id VARCHAR(20),
    -- 事件在批次中的索引
    event_index INTEGER NOT NULL,
    -- 原始事件数据
    event_data_raw TEXT NOT NULL,
    -- 错误消息
    error_message TEXT NOT NULL,
    -- 载荷片段（可选）
    payload_snippet TEXT,
    -- 重试次数
    retry_count INTEGER NOT NULL DEFAULT 0,
    -- 最后重试时间（毫秒）
    last_retry_at BIGINT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

-- 索引：按 raw_id 和 event_index 查询
CREATE INDEX IF NOT EXISTS idx_errors_raw_event_index ON metrics_event_errors(raw_id, event_index);

-- ============================================================================
-- CAS 对象表
-- ============================================================================

-- cas_objects (CAS Content Addressable Storage 对象表)
CREATE TABLE IF NOT EXISTS cas_objects (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 内容哈希值（唯一标识）
    hash VARCHAR(100) UNIQUE NOT NULL,
    -- 存储的内容，JSON 格式
    content_json TEXT,
    -- 元数据，JSON 格式
    metadata_json TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

-- 索引：按哈希值查询
CREATE INDEX IF NOT EXISTS idx_cas_hash ON cas_objects(hash);

-- ============================================================================
-- 统计表 (stats_ 前缀)
-- ============================================================================

-- stats_repositories (仓库表)
CREATE TABLE IF NOT EXISTS stats_repositories (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库路径（唯一）
    repo_path VARCHAR(500) NOT NULL UNIQUE,
    -- 仓库名称（可选）
    repo_name VARCHAR(255),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

-- 索引：按仓库名称查询
CREATE INDEX IF NOT EXISTS idx_stats_repositories_name ON stats_repositories(repo_name);

-- stats_contributors (贡献者表)
CREATE TABLE IF NOT EXISTS stats_contributors (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 贡献者唯一标识符
    contributor_uid VARCHAR(255) NOT NULL UNIQUE,
    -- 贡献者姓名
    name VARCHAR(255) NOT NULL,
    -- 贡献者邮箱
    email VARCHAR(255),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

-- 索引：按邮箱查询
CREATE INDEX IF NOT EXISTS idx_stats_contributors_email ON stats_contributors(email);

-- stats_repo_contributors (仓库贡献者关联表)
CREATE TABLE IF NOT EXISTS stats_repo_contributors (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 关联的仓库 ID
    repo_id VARCHAR(20),
    -- 关联的贡献者 ID
    contributor_id VARCHAR(20),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

-- 索引：按仓库 ID 查询
CREATE INDEX IF NOT EXISTS idx_stats_repo_contributors_repo ON stats_repo_contributors(repo_id);
-- 索引：按贡献者 ID 查询
CREATE INDEX IF NOT EXISTS idx_stats_repo_contributors_contributor ON stats_repo_contributors(contributor_id);

-- stats_daily_stats (每日统计表)
CREATE TABLE IF NOT EXISTS stats_daily_stats (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 统计日期（当天 00:00:00 的毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 关联的仓库 ID
    repo_id VARCHAR(20),
    -- 仓库名称（冗余字段，用于查询优化）
    repo_name VARCHAR(255),
    -- 关联的贡献者 ID
    contributor_id VARCHAR(20),
    -- 贡献者名称（冗余字段，用于查询优化）
    contributor_name VARCHAR(255),
    -- AI 生成的代码行数（不含注释和空行，来自 checkpoint lines_added_sloc）
    ai_generated_lines INTEGER DEFAULT 0,
    -- AI 生成的代码行数总计（包含所有内容，来自 checkpoint lines_added）
    ai_generated_lines_total INTEGER DEFAULT 0,
    -- 接受的 AI 代码行数（来自 committed ai_additions 数组第一个总值）
    ai_accepted_lines INTEGER DEFAULT 0,
    -- 人类手动编写的代码行数（来自 committed human_additions）
    human_lines INTEGER DEFAULT 0,
    -- AI 代码占比百分比 (ai_accepted/(ai_accepted+human)*100)
    ai_percentage DECIMAL(5, 2) DEFAULT 0.0,
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(50),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

-- 索引：按统计日期查询
CREATE INDEX IF NOT EXISTS idx_stats_daily_stats_date ON stats_daily_stats(stat_date);
-- 索引：按仓库 ID 查询
CREATE INDEX IF NOT EXISTS idx_stats_daily_stats_repo ON stats_daily_stats(repo_id);
-- 索引：按贡献者 ID 查询
CREATE INDEX IF NOT EXISTS idx_stats_daily_stats_contributor ON stats_daily_stats(contributor_id);

-- ============================================================================
-- 任务执行表
-- ============================================================================

-- task_executions (任务执行记录表)
CREATE TABLE IF NOT EXISTS task_executions (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 任务 ID（对应调度器的 job_id）
    job_id VARCHAR(100) NOT NULL,
    -- 执行状态: pending, running, completed, failed
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- 开始执行时间（毫秒）
    started_at BIGINT,
    -- 完成时间（毫秒）
    finished_at BIGINT,
    -- 执行耗时（毫秒）
    execution_time_ms INTEGER,
    -- 错误消息
    error_message TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

-- 索引：按任务 ID 查询
CREATE INDEX IF NOT EXISTS idx_task_executions_job ON task_executions(job_id);


-- telemetry_envelope (GIT AI 数据收集表)
CREATE TABLE IF NOT EXISTS telemetry_envelope (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- envelope_data
    envelope_data Text NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);


-- ============================================================================
-- REST Notes Store 表
-- ============================================================================

-- authorship_notes (作者注释表 - 用于 REST Notes Store API)
CREATE TABLE IF NOT EXISTS authorship_notes (
    -- 主键，使用 XID (20字符字符串)
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库远程 URL
    repo_url TEXT NOT NULL,
    -- 分支名称
    branch TEXT NOT NULL,
    -- 当前提交 SHA（40 字符）
    commit_sha VARCHAR(40) NOT NULL,
    -- note blob SHA
    note_blob_oid VARCHAR(40)  NOT NULL,
    -- 提交者名称
    author_name TEXT NOT NULL,
    -- 提交者邮箱
    author_email TEXT NOT NULL,
    -- AuthorshipLog 原始内容
    note_content TEXT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 唯一约束：同一仓库同一提交只能有一条记录
    UNIQUE(repo_url, commit_sha)
);

-- 索引：按仓库 URL 查询
CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_url ON authorship_notes(repo_url);
-- 索引：按仓库 URL 和提交 SHA 联合查询
CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_commit ON authorship_notes(repo_url, commit_sha);


-- ============================================================================
-- 完成
-- ============================================================================
