-- Metrics 原始事件表
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

CREATE INDEX IF NOT EXISTS idx_metrics_raw_received_at ON metrics_events_raw(received_at);

-- Committed 事件表
CREATE TABLE IF NOT EXISTS metrics_events_committed (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 事件唯一标识
    uid VARCHAR(100) NOT NULL,
    -- 关联的原始批次 ID
    raw_id VARCHAR(20),
    -- 事件类型 ID (1=Committed)
    event_id INTEGER NOT NULL DEFAULT 1,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- 人类手动添加代码行数
    human_additions INTEGER,
    -- Git diff 删除行数
    git_diff_deleted_lines INTEGER,
    -- Git diff 新增行数
    git_diff_added_lines INTEGER,
    -- 首次检查点时间戳
    first_checkpoint_ts BIGINT,
    -- 提交标题
    commit_subject TEXT,
    -- 提交正文
    commit_body TEXT,
    -- 工具-模型配对 JSON
    tool_model_pairs TEXT,
    -- 混合生成代码行数 JSON
    mixed_additions TEXT,
    -- AI 生成代码行数 JSON
    ai_additions TEXT,
    -- 被接受的 AI 代码行数 JSON
    ai_accepted TEXT,
    -- 总 AI 新增代码行数 JSON
    total_ai_additions TEXT,
    -- 总 AI 删除代码行数 JSON
    total_ai_deletions TEXT,
    -- 等待 AI 响应时长 JSON
    time_waiting_for_ai TEXT,
    -- Git-AI 客户端版本号
    git_ai_version TEXT,
    -- 仓库 URL
    repo_url TEXT,
    -- 提交作者
    author TEXT,
    -- 提交 SHA
    commit_sha TEXT,
    -- 基础提交 SHA
    base_commit_sha TEXT,
    -- 分支名称
    branch TEXT,
    -- 使用工具
    tool TEXT,
    -- 使用模型
    model TEXT,
    -- 提示词 ID
    prompt_id TEXT,
    -- 外部提示词 ID
    external_prompt_id TEXT,
    -- 自定义属性 JSON
    custom_attributes TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_committed_timestamp ON metrics_events_committed(timestamp);
CREATE INDEX IF NOT EXISTS idx_committed_repo_url ON metrics_events_committed(repo_url);
CREATE INDEX IF NOT EXISTS idx_committed_author ON metrics_events_committed(author);
CREATE INDEX IF NOT EXISTS idx_committed_commit_sha ON metrics_events_committed(commit_sha);

-- Checkpoint 事件表
CREATE TABLE IF NOT EXISTS metrics_events_checkpoint (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 事件唯一标识
    uid VARCHAR(100) NOT NULL,
    -- 关联的原始批次 ID
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
    -- 新增行数
    lines_added INTEGER,
    -- 删除行数
    lines_deleted INTEGER,
    -- 新增源代码行数
    lines_added_sloc INTEGER,
    -- 删除源代码行数
    lines_deleted_sloc INTEGER,
    -- Git-AI 客户端版本号
    git_ai_version TEXT,
    -- 仓库 URL
    repo_url TEXT,
    -- 提交作者
    author TEXT,
    -- 提交 SHA
    commit_sha TEXT,
    -- 基础提交 SHA
    base_commit_sha TEXT,
    -- 分支名称
    branch TEXT,
    -- 使用工具
    tool TEXT,
    -- 使用模型
    model TEXT,
    -- 提示词 ID
    prompt_id TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_checkpoint_timestamp ON metrics_events_checkpoint(timestamp);
CREATE INDEX IF NOT EXISTS idx_checkpoint_file_path ON metrics_events_checkpoint(file_path);

-- AgentUsage 事件表
CREATE TABLE IF NOT EXISTS metrics_events_agent_usage (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 事件唯一标识
    uid VARCHAR(100) NOT NULL,
    -- 关联的原始批次 ID
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
    -- 提交 SHA
    commit_sha TEXT,
    -- 基础提交 SHA
    base_commit_sha TEXT,
    -- 分支名称
    branch TEXT,
    -- 使用工具
    tool TEXT,
    -- 使用模型
    model TEXT,
    -- 提示词 ID
    prompt_id TEXT,
    -- 外部提示词 ID
    external_prompt_id TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_usage_timestamp ON metrics_events_agent_usage(timestamp);

-- InstallHooks 事件表
CREATE TABLE IF NOT EXISTS metrics_events_install_hooks (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 事件唯一标识
    uid VARCHAR(100) NOT NULL,
    -- 关联的原始批次 ID
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

-- 事件解析错误记录表
CREATE TABLE IF NOT EXISTS metrics_event_errors (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 关联的原始批次 ID
    raw_id VARCHAR(20),
    -- 事件在批次中的索引
    event_index INTEGER NOT NULL,
    -- 原始事件数据
    event_data_raw TEXT NOT NULL,
    -- 错误消息
    error_message TEXT NOT NULL,
    -- 载荷片段
    payload_snippet TEXT,
    -- 重试次数
    retry_count INTEGER NOT NULL DEFAULT 0,
    -- 最后重试时间（毫秒）
    last_retry_at BIGINT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_event_index ON metrics_event_errors(raw_id, event_index);

-- CAS 对象表
CREATE TABLE IF NOT EXISTS cas_objects (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 内容哈希值
    hash VARCHAR(100) NOT NULL UNIQUE,
    -- 内容 JSON
    content_json TEXT,
    -- 元数据 JSON
    metadata_json TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cas_hash ON cas_objects(hash);

-- 仓库表
CREATE TABLE IF NOT EXISTS stats_repositories (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库路径
    repo_path TEXT NOT NULL UNIQUE,
    -- 仓库名称
    repo_name TEXT,
    -- 是否启用归因统计（0/1）
    repo_stats_flag INTEGER DEFAULT 1,
    -- 关联的 SSH Key ID
    ssh_key_id VARCHAR(20),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stats_repositories_name ON stats_repositories(repo_name);

-- 贡献者表
CREATE TABLE IF NOT EXISTS stats_contributors (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 贡献者唯一标识
    contributor_uid TEXT NOT NULL UNIQUE,
    -- 贡献者名称
    name TEXT NOT NULL,
    -- 贡献者邮箱
    email TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stats_contributors_email ON stats_contributors(email);

-- 仓库贡献者关联表
CREATE TABLE IF NOT EXISTS stats_repo_contributors (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 贡献者 ID
    contributor_id VARCHAR(20) NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stats_repo_contributors_repo ON stats_repo_contributors(repo_id);
CREATE INDEX IF NOT EXISTS idx_stats_repo_contributors_contributor ON stats_repo_contributors(contributor_id);

-- 每日统计表
CREATE TABLE IF NOT EXISTS stats_daily_stats (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 统计日期（毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 仓库名称冗余字段
    repo_name TEXT,
    -- 贡献者 ID
    contributor_id VARCHAR(20) NOT NULL,
    -- 贡献者名称冗余字段
    contributor_name TEXT,
    -- AI 生成源代码行数
    ai_generated_lines INTEGER DEFAULT 0,
    -- AI 生成总行数
    ai_generated_lines_total INTEGER DEFAULT 0,
    -- 被接受的 AI 代码行数
    ai_accepted_lines INTEGER DEFAULT 0,
    -- 人类代码行数
    human_lines INTEGER DEFAULT 0,
    -- AI 占比
    ai_percentage DECIMAL(5, 2) DEFAULT 0.0,
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(50),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stats_daily_stats_date ON stats_daily_stats(stat_date);
CREATE INDEX IF NOT EXISTS idx_stats_daily_stats_repo ON stats_daily_stats(repo_id);
CREATE INDEX IF NOT EXISTS idx_stats_daily_stats_contributor ON stats_daily_stats(contributor_id);

-- 任务执行记录表
CREATE TABLE IF NOT EXISTS task_executions (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 调度任务 ID
    job_id TEXT NOT NULL,
    -- 执行状态
    status TEXT NOT NULL DEFAULT 'pending',
    -- 开始执行时间（毫秒）
    started_at BIGINT,
    -- 完成时间（毫秒）
    finished_at BIGINT,
    -- 执行耗时（毫秒）
    execution_time_ms INTEGER,
    -- 错误信息
    error_message TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_executions_job ON task_executions(job_id);

-- GIT AI 数据收集表
CREATE TABLE IF NOT EXISTS telemetry_envelope (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 包络 JSON 数据
    envelope_data TEXT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

-- 作者注释表
CREATE TABLE IF NOT EXISTS authorship_notes (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库 URL
    repo_url TEXT NOT NULL,
    -- 分支名称
    branch TEXT NOT NULL,
    -- 提交 SHA
    commit_sha VARCHAR(40) NOT NULL,
    -- Note Blob OID
    note_blob_oid VARCHAR(40),
    -- 作者名称
    author_name TEXT NOT NULL,
    -- 作者邮箱
    author_email TEXT NOT NULL,
    -- 注释内容
    note_content TEXT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 同一仓库同一提交唯一
    UNIQUE(repo_url, commit_sha)
);

CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_url ON authorship_notes(repo_url);
CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_commit ON authorship_notes(repo_url, commit_sha);

-- SSH Key 表
CREATE TABLE IF NOT EXISTS stats_ssh_keys (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- Key 名称
    key_name TEXT NOT NULL UNIQUE,
    -- 公钥内容
    public_key TEXT NOT NULL,
    -- 加密后的私钥内容
    private_key_encrypted TEXT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ssh_key_name ON stats_ssh_keys(key_name);

-- 仓库级归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_repo (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 统计日期（毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 当前统计提交 SHA
    commit_sha VARCHAR(40) NOT NULL,
    -- 分支名称
    branch TEXT NOT NULL,
    -- 总行数
    total_lines INTEGER NOT NULL,
    -- AI 代码行数
    ai_lines INTEGER NOT NULL,
    -- 非 AI 代码行数
    non_ai_lines INTEGER NOT NULL,
    -- AI 代码占比
    ai_ratio DECIMAL(5, 2) NOT NULL,
    -- 文件总数
    total_files INTEGER NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 同一仓库同一日期唯一
    UNIQUE(repo_id, stat_date)
);

CREATE INDEX IF NOT EXISTS idx_blame_repo_date ON stats_blame_repo(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_stat_date ON stats_blame_repo(stat_date);

-- 文件级归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_file (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 统计日期（毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 文件路径
    file_path TEXT NOT NULL,
    -- 当前统计提交 SHA
    commit_sha VARCHAR(40) NOT NULL,
    -- 总行数
    total_lines INTEGER NOT NULL,
    -- AI 代码行数
    ai_lines INTEGER NOT NULL,
    -- 非 AI 代码行数
    non_ai_lines INTEGER NOT NULL,
    -- AI 代码占比
    ai_ratio DECIMAL(5, 2) NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 同一仓库同一日期同一路径唯一
    UNIQUE(repo_id, stat_date, file_path)
);

CREATE INDEX IF NOT EXISTS idx_blame_file_repo ON stats_blame_file(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_file_date ON stats_blame_file(stat_date);

-- 仓库贡献者归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_repo_contributor (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 统计日期（毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 贡献者 ID
    contributor_id VARCHAR(20) NOT NULL,
    -- 贡献者名称
    contributor_name TEXT NOT NULL,
    -- 贡献者邮箱
    contributor_email TEXT,
    -- AI 代码行数
    ai_lines INTEGER NOT NULL DEFAULT 0,
    -- 非 AI 代码行数
    non_ai_lines INTEGER NOT NULL DEFAULT 0,
    -- 总行数
    total_lines INTEGER NOT NULL DEFAULT 0,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 同一仓库同一日期同一贡献者唯一
    UNIQUE(repo_id, stat_date, contributor_id)
);

CREATE INDEX IF NOT EXISTS idx_blame_rc_repo ON stats_blame_repo_contributor(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_rc_date ON stats_blame_repo_contributor(stat_date);

-- 文件贡献者归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_file_contributor (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 文件级统计 ID
    file_id VARCHAR(20) NOT NULL,
    -- 统计日期（毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 文件路径
    file_path TEXT NOT NULL,
    -- 贡献者 ID
    contributor_id VARCHAR(20) NOT NULL,
    -- 贡献者名称
    contributor_name TEXT NOT NULL,
    -- 贡献者邮箱
    contributor_email TEXT,
    -- AI 代码行数
    ai_lines INTEGER NOT NULL DEFAULT 0,
    -- 非 AI 代码行数
    non_ai_lines INTEGER NOT NULL DEFAULT 0,
    -- 总行数
    total_lines INTEGER NOT NULL DEFAULT 0,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 同一文件同一日期同一贡献者唯一
    UNIQUE(file_id, stat_date, contributor_id)
);

CREATE INDEX IF NOT EXISTS idx_blame_fc_file ON stats_blame_file_contributor(repo_id, stat_date, file_path);
CREATE INDEX IF NOT EXISTS idx_blame_fc_date ON stats_blame_file_contributor(stat_date);

-- APScheduler JobStore 表
CREATE TABLE IF NOT EXISTS apscheduler_jobs (
    -- 任务 ID
    id VARCHAR(191) NOT NULL PRIMARY KEY,
    -- 下次运行时间
    next_run_time REAL,
    -- 序列化任务状态
    job_state BLOB NOT NULL
);
