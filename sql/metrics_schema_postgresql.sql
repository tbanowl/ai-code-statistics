-- ============================================================================
-- Git-AI Metrics DDL Script for PostgreSQL
-- ============================================================================
-- 版本: 2.0
-- 日期: 2026-03-24
-- 说明: 基于 core/database/models.py 实体定义的数据库表结构
--       所有主键使用 XID (VARCHAR(20))
--       所有时间字段使用毫秒时间戳 (BIGINT)
--       JSON 数据使用 JSONB 类型存储
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

-- 注释
COMMENT ON TABLE metrics_events_raw IS 'Metrics 原始事件表，存储上传的原始批次数据';
COMMENT ON COLUMN metrics_events_raw.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN metrics_events_raw.version IS '批次版本号';
COMMENT ON COLUMN metrics_events_raw.event_count IS '批次中的事件数量';
COMMENT ON COLUMN metrics_events_raw.payload_json IS '原始 JSON 载荷数据';
COMMENT ON COLUMN metrics_events_raw.extract IS '提取标识：0-未提取、1-提取成功、2-提取中、3-提取失败';
COMMENT ON COLUMN metrics_events_raw.extract_fail IS '提取失败原因';
COMMENT ON COLUMN metrics_events_raw.received_at IS '接收时间戳（毫秒）';
COMMENT ON COLUMN metrics_events_raw.created_at IS '创建时间戳（毫秒）';

-- 索引：按接收时间查询
CREATE INDEX IF NOT EXISTS idx_metrics_raw_received_at ON metrics_events_raw(received_at);

-- metrics_events_committed (Committed 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_committed (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 唯一标识符
    uid VARCHAR(200) NOT NULL,
    -- 关联的原始批次表 ID (外键，级联删除)
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
    commit_subject VARCHAR(255),
    -- 提交内容
    commit_body TEXT,
    -- ==================== JSON 存储字段 ====================

    -- 工具-模型配对，JSON 数组格式（索引 0 为总计，其他为各工具统计）
    tool_model_pairs JSONB,
    -- 混合生成的代码行数，JSON 数组格式
    mixed_additions JSONB,
    -- AI 生成的代码行数，JSON 数组格式
    ai_additions JSONB,
    -- 接受的 AI 代码行数，JSON 数组格式
    ai_accepted JSONB,
    -- 总计 AI 新增代码行数，JSON 数组格式
    total_ai_additions JSONB,
    -- 总计 AI 删除代码行数，JSON 数组格式
    total_ai_deletions JSONB,
    -- 等待 AI 响应的时间，JSON 数组格式
    time_waiting_for_ai JSONB,
    -- ==================== 事件属性字段 ====================

    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(50),
    -- 仓库 URL
    repo_url VARCHAR(500),
    -- 提交作者
    author VARCHAR(255),
    -- 提交的 SHA 校验码
    commit_sha VARCHAR(40),
    -- 基础提交的 SHA 校验码
    base_commit_sha VARCHAR(40),
    -- 分支名称
    branch VARCHAR(255),
    -- 使用的工具（如 claude, copilot）
    tool VARCHAR(50),
    -- 使用的模型（如 claude-opus-4-6）
    model VARCHAR(50),
    -- 提示词 ID
    prompt_id VARCHAR(200),
    -- 外部提示词 ID
    external_prompt_id VARCHAR(200),
    -- 自定义属性，JSON 格式
    custom_attributes JSONB,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

-- 注释
COMMENT ON TABLE metrics_events_committed IS 'Committed 事件表，存储代码提交相关的 Metrics 数据';
COMMENT ON COLUMN metrics_events_committed.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN metrics_events_committed.uid IS '唯一标识符';
COMMENT ON COLUMN metrics_events_committed.raw_id IS '关联的原始批次表 ID';
COMMENT ON COLUMN metrics_events_committed.event_id IS '事件类型 ID (1=Committed)';
COMMENT ON COLUMN metrics_events_committed.timestamp IS '事件时间戳（毫秒）';
COMMENT ON COLUMN metrics_events_committed.human_additions IS '人类手动添加的代码行数';
COMMENT ON COLUMN metrics_events_committed.git_diff_deleted_lines IS 'Git diff 删除的代码行数';
COMMENT ON COLUMN metrics_events_committed.git_diff_added_lines IS 'Git diff 新增的代码行数';
COMMENT ON COLUMN metrics_events_committed.first_checkpoint_ts IS '首次检查点时间戳';
COMMENT ON COLUMN metrics_events_committed.commit_subject IS '提交标题';
COMMENT ON COLUMN metrics_events_committed.commit_body IS '提交内容';
COMMENT ON COLUMN metrics_events_committed.tool_model_pairs IS '工具-模型配对，JSON 数组（索引 0 为总计）';
COMMENT ON COLUMN metrics_events_committed.mixed_additions IS '混合生成的代码行数，JSON 数组';
COMMENT ON COLUMN metrics_events_committed.ai_additions IS 'AI 生成的代码行数，JSON 数组';
COMMENT ON COLUMN metrics_events_committed.ai_accepted IS '接受的 AI 代码行数，JSON 数组';
COMMENT ON COLUMN metrics_events_committed.total_ai_additions IS '总计 AI 新增代码行数，JSON 数组';
COMMENT ON COLUMN metrics_events_committed.total_ai_deletions IS '总计 AI 删除代码行数，JSON 数组';
COMMENT ON COLUMN metrics_events_committed.time_waiting_for_ai IS '等待 AI 响应的时间，JSON 数组';
COMMENT ON COLUMN metrics_events_committed.git_ai_version IS 'Git-AI 客户端版本号';
COMMENT ON COLUMN metrics_events_committed.repo_url IS '仓库 URL';
COMMENT ON COLUMN metrics_events_committed.author IS '提交作者';
COMMENT ON COLUMN metrics_events_committed.commit_sha IS '提交的 SHA 校验码';
COMMENT ON COLUMN metrics_events_committed.base_commit_sha IS '基础提交的 SHA 校验码';
COMMENT ON COLUMN metrics_events_committed.branch IS '分支名称';
COMMENT ON COLUMN metrics_events_committed.tool IS '使用的工具（如 claude, copilot）';
COMMENT ON COLUMN metrics_events_committed.model IS '使用的模型（如 claude-opus-4-6）';
COMMENT ON COLUMN metrics_events_committed.prompt_id IS '提示词 ID';
COMMENT ON COLUMN metrics_events_committed.external_prompt_id IS '外部提示词 ID';
COMMENT ON COLUMN metrics_events_committed.custom_attributes IS '自定义属性，JSON 格式';
COMMENT ON COLUMN metrics_events_committed.created_at IS '创建时间戳（毫秒）';

-- 索引：按时间戳查询
CREATE INDEX IF NOT EXISTS idx_committed_timestamp ON metrics_events_committed(timestamp);
-- 索引：按仓库 URL 查询
CREATE INDEX IF NOT EXISTS idx_committed_repo_url ON metrics_events_committed(repo_url);
-- 索引：按作者查询
CREATE INDEX IF NOT EXISTS idx_committed_author ON metrics_events_committed(author);
-- 索引：按提交 SHA 查询
CREATE INDEX IF NOT EXISTS idx_committed_commit_sha ON metrics_events_committed(commit_sha);
-- 索引：按 ai_accepted JSON 字段查询（GIN 索引）
CREATE INDEX IF NOT EXISTS idx_committed_ai_accepted ON metrics_events_committed USING GIN (ai_accepted);

-- metrics_events_checkpoint (Checkpoint 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_checkpoint (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 唯一标识符
    uid VARCHAR(200) NOT NULL,
    -- 关联的原始批次表 ID (外键，级联删除)
    raw_id VARCHAR(20),
    -- 事件类型 ID (4=Checkpoint)
    event_id INTEGER NOT NULL DEFAULT 4,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- 检查点时间戳
    checkpoint_ts BIGINT,
    -- 检查点类型
    kind VARCHAR(50),
    -- 文件路径
    file_path VARCHAR(500),
    -- 新增代码行数
    lines_added INTEGER,
    -- 删除代码行数
    lines_deleted INTEGER,
    -- 新增代码源代码行数（不含注释和空行）
    lines_added_sloc INTEGER,
    -- 删除代码源代码行数（不含注释和空行）
    lines_deleted_sloc INTEGER,
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(50),
    -- 仓库 URL
    repo_url VARCHAR(500),
    -- 提交作者
    author VARCHAR(255),
    -- 提交的 SHA 校验码
    commit_sha VARCHAR(40),
    -- 基础提交的 SHA 校验码
    base_commit_sha VARCHAR(40),
    -- 分支名称
    branch VARCHAR(255),
    -- 使用的工具
    tool VARCHAR(50),
    -- 使用的模型
    model VARCHAR(50),
    -- 提示词 ID
    prompt_id VARCHAR(200),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

-- 注释
COMMENT ON TABLE metrics_events_checkpoint IS 'Checkpoint 事件表，存储检查点相关的 Metrics 数据';
COMMENT ON COLUMN metrics_events_checkpoint.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN metrics_events_checkpoint.uid IS '唯一标识符';
COMMENT ON COLUMN metrics_events_checkpoint.raw_id IS '关联的原始批次表 ID';
COMMENT ON COLUMN metrics_events_checkpoint.event_id IS '事件类型 ID (4=Checkpoint)';
COMMENT ON COLUMN metrics_events_checkpoint.timestamp IS '事件时间戳（毫秒）';
COMMENT ON COLUMN metrics_events_checkpoint.checkpoint_ts IS '检查点时间戳';
COMMENT ON COLUMN metrics_events_checkpoint.kind IS '检查点类型';
COMMENT ON COLUMN metrics_events_checkpoint.file_path IS '文件路径';
COMMENT ON COLUMN metrics_events_checkpoint.lines_added IS '新增代码行数';
COMMENT ON COLUMN metrics_events_checkpoint.lines_deleted IS '删除代码行数';
COMMENT ON COLUMN metrics_events_checkpoint.lines_added_sloc IS '新增代码源代码行数（不含注释空行）';
COMMENT ON COLUMN metrics_events_checkpoint.lines_deleted_sloc IS '删除代码源代码行数（不含注释空行）';
COMMENT ON COLUMN metrics_events_checkpoint.git_ai_version IS 'Git-AI 客户端版本号';
COMMENT ON COLUMN metrics_events_checkpoint.repo_url IS '仓库 URL';
COMMENT ON COLUMN metrics_events_checkpoint.author IS '提交作者';
COMMENT ON COLUMN metrics_events_checkpoint.commit_sha IS '提交的 SHA 校验码';
COMMENT ON COLUMN metrics_events_checkpoint.base_commit_sha IS '基础提交的 SHA 校验码';
COMMENT ON COLUMN metrics_events_checkpoint.branch IS '分支名称';
COMMENT ON COLUMN metrics_events_checkpoint.tool IS '使用的工具';
COMMENT ON COLUMN metrics_events_checkpoint.model IS '使用的模型';
COMMENT ON COLUMN metrics_events_checkpoint.prompt_id IS '提示词 ID';
COMMENT ON COLUMN metrics_events_checkpoint.created_at IS '创建时间戳（毫秒）';

-- 索引：按时间戳查询
CREATE INDEX IF NOT EXISTS idx_checkpoint_timestamp ON metrics_events_checkpoint(timestamp);
-- 索引：按文件路径查询
CREATE INDEX IF NOT EXISTS idx_checkpoint_file_path ON metrics_events_checkpoint(file_path);

-- metrics_events_agent_usage (AgentUsage 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_agent_usage (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 唯一标识符
    uid VARCHAR(200) NOT NULL,
    -- 关联的原始批次表 ID (外键，级联删除)
    raw_id VARCHAR(20),
    -- 事件类型 ID (2=AgentUsage)
    event_id INTEGER NOT NULL DEFAULT 2,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(50),
    -- 仓库 URL
    repo_url VARCHAR(500),
    -- 提交作者
    author VARCHAR(255),
    -- 提交的 SHA 校验码
    commit_sha VARCHAR(40),
    -- 基础提交的 SHA 校验码
    base_commit_sha VARCHAR(40),
    -- 分支名称
    branch VARCHAR(255),
    -- 使用的工具
    tool VARCHAR(50),
    -- 使用的模型
    model VARCHAR(50),
    -- 提示词 ID
    prompt_id VARCHAR(200),
    -- 外部提示词 ID
    external_prompt_id VARCHAR(200),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

-- 注释
COMMENT ON TABLE metrics_events_agent_usage IS 'AgentUsage 事件表，存储 AI 助手使用记录';
COMMENT ON COLUMN metrics_events_agent_usage.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN metrics_events_agent_usage.uid IS '唯一标识符';
COMMENT ON COLUMN metrics_events_agent_usage.raw_id IS '关联的原始批次表 ID';
COMMENT ON COLUMN metrics_events_agent_usage.event_id IS '事件类型 ID (2=AgentUsage)';
COMMENT ON COLUMN metrics_events_agent_usage.timestamp IS '事件时间戳（毫秒）';
COMMENT ON COLUMN metrics_events_agent_usage.git_ai_version IS 'Git-AI 客户端版本号';
COMMENT ON COLUMN metrics_events_agent_usage.repo_url IS '仓库 URL';
COMMENT ON COLUMN metrics_events_agent_usage.author IS '提交作者';
COMMENT ON COLUMN metrics_events_agent_usage.commit_sha IS '提交的 SHA 校验码';
COMMENT ON COLUMN metrics_events_agent_usage.base_commit_sha IS '基础提交的 SHA 校验码';
COMMENT ON COLUMN metrics_events_agent_usage.branch IS '分支名称';
COMMENT ON COLUMN metrics_events_agent_usage.tool IS '使用的工具';
COMMENT ON COLUMN metrics_events_agent_usage.model IS '使用的模型';
COMMENT ON COLUMN metrics_events_agent_usage.prompt_id IS '提示词 ID';
COMMENT ON COLUMN metrics_events_agent_usage.external_prompt_id IS '外部提示词 ID';
COMMENT ON COLUMN metrics_events_agent_usage.created_at IS '创建时间戳（毫秒）';

-- 索引：按时间戳查询
CREATE INDEX IF NOT EXISTS idx_agent_usage_timestamp ON metrics_events_agent_usage(timestamp);

-- metrics_events_install_hooks (InstallHooks 事件表)
CREATE TABLE IF NOT EXISTS metrics_events_install_hooks (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 唯一标识符
    uid VARCHAR(200) NOT NULL,
    -- 关联的原始批次表 ID
    raw_id VARCHAR(20),
    -- 事件类型 ID (3=InstallHooks)
    event_id INTEGER NOT NULL DEFAULT 3,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- 工具 ID
    tool_id VARCHAR(50),
    -- 安装状态
    status VARCHAR(50),
    -- 安装消息
    message VARCHAR(500),
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(50),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

-- 注释
COMMENT ON TABLE metrics_events_install_hooks IS 'InstallHooks 事件表，存储 Hooks 安装记录';
COMMENT ON COLUMN metrics_events_install_hooks.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN metrics_events_install_hooks.uid IS '唯一标识符';
COMMENT ON COLUMN metrics_events_install_hooks.raw_id IS '关联的原始批次表 ID';
COMMENT ON COLUMN metrics_events_install_hooks.event_id IS '事件类型 ID (3=InstallHooks)';
COMMENT ON COLUMN metrics_events_install_hooks.timestamp IS '事件时间戳（毫秒）';
COMMENT ON COLUMN metrics_events_install_hooks.tool_id IS '工具 ID';
COMMENT ON COLUMN metrics_events_install_hooks.status IS '安装状态';
COMMENT ON COLUMN metrics_events_install_hooks.message IS '安装消息';
COMMENT ON COLUMN metrics_events_install_hooks.git_ai_version IS 'Git-AI 客户端版本号';
COMMENT ON COLUMN metrics_events_install_hooks.created_at IS '创建时间戳（毫秒）';

-- metrics_event_errors (事件解析错误记录表)
CREATE TABLE IF NOT EXISTS metrics_event_errors (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 关联的原始批次表 ID (外键，级联删除)
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

-- 注释
COMMENT ON TABLE metrics_event_errors IS '事件解析错误记录表';
COMMENT ON COLUMN metrics_event_errors.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN metrics_event_errors.raw_id IS '关联的原始批次表 ID';
COMMENT ON COLUMN metrics_event_errors.event_index IS '事件在批次中的索引';
COMMENT ON COLUMN metrics_event_errors.event_data_raw IS '原始事件数据';
COMMENT ON COLUMN metrics_event_errors.error_message IS '错误消息';
COMMENT ON COLUMN metrics_event_errors.payload_snippet IS '载荷片段';
COMMENT ON COLUMN metrics_event_errors.retry_count IS '重试次数';
COMMENT ON COLUMN metrics_event_errors.last_retry_at IS '最后重试时间（毫秒）';
COMMENT ON COLUMN metrics_event_errors.created_at IS '创建时间戳（毫秒）';

-- 索引：按 raw_id 和 event_index 查询（组合索引，与模型中定义一致）
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
    content_json JSONB,
    -- 元数据，JSON 格式
    metadata_json JSONB,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

-- 注释
COMMENT ON TABLE cas_objects IS 'CAS (Content Addressable Storage) 对象表';
COMMENT ON COLUMN cas_objects.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN cas_objects.hash IS '内容哈希值（唯一标识）';
COMMENT ON COLUMN cas_objects.content_json IS '存储的内容，JSON 格式';
COMMENT ON COLUMN cas_objects.metadata_json IS '元数据，JSON 格式';
COMMENT ON COLUMN cas_objects.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN cas_objects.updated_at IS '更新时间戳（毫秒）';

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

-- 注释
COMMENT ON TABLE stats_repositories IS '仓库表';
COMMENT ON COLUMN stats_repositories.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN stats_repositories.repo_path IS '仓库路径（唯一）';
COMMENT ON COLUMN stats_repositories.repo_name IS '仓库名称（可选）';
COMMENT ON COLUMN stats_repositories.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_repositories.updated_at IS '更新时间戳（毫秒）';

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

-- 注释
COMMENT ON TABLE stats_contributors IS '贡献者表';
COMMENT ON COLUMN stats_contributors.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN stats_contributors.contributor_uid IS '贡献者唯一标识符';
COMMENT ON COLUMN stats_contributors.name IS '贡献者姓名';
COMMENT ON COLUMN stats_contributors.email IS '贡献者邮箱';
COMMENT ON COLUMN stats_contributors.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_contributors.updated_at IS '更新时间戳（毫秒）';

-- 索引：按邮箱查询
CREATE INDEX IF NOT EXISTS idx_stats_contributors_email ON stats_contributors(email);

-- stats_repo_contributors (仓库贡献者关联表)
CREATE TABLE IF NOT EXISTS stats_repo_contributors (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 关联的仓库 ID (外键，级联删除)
    repo_id VARCHAR(20) NOT NULL,
    -- 关联的贡献者 ID (外键，级联删除)
    contributor_id VARCHAR(20) NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    CONSTRAINT fk_stats_repo_contributors_contributor
);

-- 注释
COMMENT ON TABLE stats_repo_contributors IS '仓库贡献者关联表';
COMMENT ON COLUMN stats_repo_contributors.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN stats_repo_contributors.repo_id IS '关联的仓库 ID';
COMMENT ON COLUMN stats_repo_contributors.contributor_id IS '关联的贡献者 ID';
COMMENT ON COLUMN stats_repo_contributors.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_repo_contributors.updated_at IS '更新时间戳（毫秒）';

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
    -- 关联的仓库 ID (外键，级联删除)
    repo_id VARCHAR(20) NOT NULL,
    -- 仓库名称（冗余字段，用于查询优化）
    repo_name VARCHAR(255),
    -- 关联的贡献者 ID (外键，级联删除)
    contributor_id VARCHAR(20) NOT NULL,
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
    ai_percentage NUMERIC(5, 2) DEFAULT 0.0,
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(50),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    CONSTRAINT fk_stats_daily_stats_contributor
);

-- 注释
COMMENT ON TABLE stats_daily_stats IS '每日统计表';
COMMENT ON COLUMN stats_daily_stats.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN stats_daily_stats.stat_date IS '统计日期（当天 00:00:00 的毫秒时间戳）';
COMMENT ON COLUMN stats_daily_stats.repo_id IS '关联的仓库 ID';
COMMENT ON COLUMN stats_daily_stats.repo_name IS '仓库名称（冗余字段，用于查询优化）';
COMMENT ON COLUMN stats_daily_stats.contributor_id IS '关联的贡献者 ID';
COMMENT ON COLUMN stats_daily_stats.contributor_name IS '贡献者名称（冗余字段，用于查询优化）';
COMMENT ON COLUMN stats_daily_stats.ai_generated_lines IS 'AI 生成的代码行数（不含注释和空行）';
COMMENT ON COLUMN stats_daily_stats.ai_generated_lines_total IS 'AI 生成的代码行数总计（包含所有内容）';
COMMENT ON COLUMN stats_daily_stats.ai_accepted_lines IS '接受的 AI 代码行数';
COMMENT ON COLUMN stats_daily_stats.human_lines IS '人类手动编写的代码行数';
COMMENT ON COLUMN stats_daily_stats.ai_percentage IS 'AI 代码占比百分比';
COMMENT ON COLUMN stats_daily_stats.git_ai_version IS 'Git-AI 客户端版本号';
COMMENT ON COLUMN stats_daily_stats.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_daily_stats.updated_at IS '更新时间戳（毫秒）';

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

-- 注释
COMMENT ON TABLE task_executions IS '任务执行记录表';
COMMENT ON COLUMN task_executions.id IS '主键，使用 XID 字符串 (20字符)';
COMMENT ON COLUMN task_executions.job_id IS '任务 ID（对应调度器的 job_id）';
COMMENT ON COLUMN task_executions.status IS '执行状态: pending, running, completed, failed';
COMMENT ON COLUMN task_executions.started_at IS '开始执行时间（毫秒）';
COMMENT ON COLUMN task_executions.finished_at IS '完成时间（毫秒）';
COMMENT ON COLUMN task_executions.execution_time_ms IS '执行耗时（毫秒）';
COMMENT ON COLUMN task_executions.error_message IS '错误消息';
COMMENT ON COLUMN task_executions.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN task_executions.updated_at IS '更新时间戳（毫秒）';

-- 索引：按任务 ID 查询
CREATE INDEX IF NOT EXISTS idx_task_executions_job ON task_executions(job_id);

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

-- 需要自动更新 updated_at 的表列表
DROP TRIGGER IF EXISTS trigger_update_cas_objects_updated_at ON cas_objects;
CREATE TRIGGER trigger_update_cas_objects_updated_at
    BEFORE UPDATE ON cas_objects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_repositories_updated_at ON stats_repositories;
CREATE TRIGGER trigger_update_stats_repositories_updated_at
    BEFORE UPDATE ON stats_repositories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_contributors_updated_at ON stats_contributors;
CREATE TRIGGER trigger_update_stats_contributors_updated_at
    BEFORE UPDATE ON stats_contributors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_repo_contributors_updated_at ON stats_repo_contributors;
CREATE TRIGGER trigger_update_stats_repo_contributors_updated_at
    BEFORE UPDATE ON stats_repo_contributors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_daily_stats_updated_at ON stats_daily_stats;
CREATE TRIGGER trigger_update_stats_daily_stats_updated_at
    BEFORE UPDATE ON stats_daily_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_task_executions_updated_at ON task_executions;
CREATE TRIGGER trigger_update_task_executions_updated_at
    BEFORE UPDATE ON task_executions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 完成
-- ============================================================================
