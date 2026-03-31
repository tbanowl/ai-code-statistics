CREATE TABLE IF NOT EXISTS metrics_events_raw (
    id VARCHAR(20) PRIMARY KEY,
    version INTEGER NOT NULL DEFAULT 1,
    event_count INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    extract INTEGER NOT NULL DEFAULT 0,
    extract_fail TEXT,
    received_at BIGINT NOT NULL,
    created_at BIGINT NOT NULL
);

COMMENT ON TABLE metrics_events_raw IS 'Metrics 原始事件表';
COMMENT ON COLUMN metrics_events_raw.id IS '主键，使用 XID (20字符字符串)';
COMMENT ON COLUMN metrics_events_raw.version IS '批次版本号';
COMMENT ON COLUMN metrics_events_raw.event_count IS '批次中的事件数量';
COMMENT ON COLUMN metrics_events_raw.payload_json IS '原始 JSON 载荷数据';
COMMENT ON COLUMN metrics_events_raw.extract IS '提取标识：0-未提取、1-提取成功、2-提取中、3-提取失败';
COMMENT ON COLUMN metrics_events_raw.extract_fail IS '提取失败原因';
COMMENT ON COLUMN metrics_events_raw.received_at IS '接收时间戳（毫秒）';
COMMENT ON COLUMN metrics_events_raw.created_at IS '创建时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_metrics_raw_received_at ON metrics_events_raw(received_at);

CREATE TABLE IF NOT EXISTS metrics_events_committed (
    id VARCHAR(20) PRIMARY KEY,
    uid VARCHAR(100) NOT NULL,
    raw_id VARCHAR(20),
    event_id INTEGER NOT NULL DEFAULT 1,
    timestamp BIGINT NOT NULL,
    human_additions INTEGER,
    git_diff_deleted_lines INTEGER,
    git_diff_added_lines INTEGER,
    first_checkpoint_ts BIGINT,
    commit_subject TEXT,
    commit_body TEXT,
    tool_model_pairs JSONB,
    mixed_additions JSONB,
    ai_additions JSONB,
    ai_accepted JSONB,
    total_ai_additions JSONB,
    total_ai_deletions JSONB,
    time_waiting_for_ai JSONB,
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
    created_at BIGINT NOT NULL
);

COMMENT ON TABLE metrics_events_committed IS 'Committed 事件表';
COMMENT ON COLUMN metrics_events_committed.id IS '主键，使用 XID';
COMMENT ON COLUMN metrics_events_committed.uid IS '事件唯一标识';
COMMENT ON COLUMN metrics_events_committed.raw_id IS '关联的原始批次 ID';
COMMENT ON COLUMN metrics_events_committed.event_id IS '事件类型 ID (1=Committed)';
COMMENT ON COLUMN metrics_events_committed.timestamp IS '事件时间戳（毫秒）';
COMMENT ON COLUMN metrics_events_committed.human_additions IS '人类手动添加代码行数';
COMMENT ON COLUMN metrics_events_committed.git_diff_deleted_lines IS 'Git diff 删除行数';
COMMENT ON COLUMN metrics_events_committed.git_diff_added_lines IS 'Git diff 新增行数';
COMMENT ON COLUMN metrics_events_committed.first_checkpoint_ts IS '首次检查点时间戳';
COMMENT ON COLUMN metrics_events_committed.commit_subject IS '提交标题';
COMMENT ON COLUMN metrics_events_committed.commit_body IS '提交正文';
COMMENT ON COLUMN metrics_events_committed.tool_model_pairs IS '工具-模型配对 JSON';
COMMENT ON COLUMN metrics_events_committed.mixed_additions IS '混合生成代码行数 JSON';
COMMENT ON COLUMN metrics_events_committed.ai_additions IS 'AI 生成代码行数 JSON';
COMMENT ON COLUMN metrics_events_committed.ai_accepted IS '被接受的 AI 代码行数 JSON';
COMMENT ON COLUMN metrics_events_committed.total_ai_additions IS '总 AI 新增代码行数 JSON';
COMMENT ON COLUMN metrics_events_committed.total_ai_deletions IS '总 AI 删除代码行数 JSON';
COMMENT ON COLUMN metrics_events_committed.time_waiting_for_ai IS '等待 AI 响应时长 JSON';
COMMENT ON COLUMN metrics_events_committed.git_ai_version IS 'Git-AI 客户端版本号';
COMMENT ON COLUMN metrics_events_committed.repo_url IS '仓库 URL';
COMMENT ON COLUMN metrics_events_committed.author IS '提交作者';
COMMENT ON COLUMN metrics_events_committed.commit_sha IS '提交 SHA';
COMMENT ON COLUMN metrics_events_committed.base_commit_sha IS '基础提交 SHA';
COMMENT ON COLUMN metrics_events_committed.branch IS '分支名称';
COMMENT ON COLUMN metrics_events_committed.tool IS '使用工具';
COMMENT ON COLUMN metrics_events_committed.model IS '使用模型';
COMMENT ON COLUMN metrics_events_committed.prompt_id IS '提示词 ID';
COMMENT ON COLUMN metrics_events_committed.external_prompt_id IS '外部提示词 ID';
COMMENT ON COLUMN metrics_events_committed.custom_attributes IS '自定义属性 JSON';
COMMENT ON COLUMN metrics_events_committed.created_at IS '创建时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_committed_timestamp ON metrics_events_committed(timestamp);
CREATE INDEX IF NOT EXISTS idx_committed_repo_url ON metrics_events_committed(repo_url);
CREATE INDEX IF NOT EXISTS idx_committed_author ON metrics_events_committed(author);
CREATE INDEX IF NOT EXISTS idx_committed_commit_sha ON metrics_events_committed(commit_sha);
CREATE INDEX IF NOT EXISTS idx_committed_ai_accepted ON metrics_events_committed USING GIN (ai_accepted);

CREATE TABLE IF NOT EXISTS metrics_events_checkpoint (
    id VARCHAR(20) PRIMARY KEY,
    uid VARCHAR(100) NOT NULL,
    raw_id VARCHAR(20),
    event_id INTEGER NOT NULL DEFAULT 4,
    timestamp BIGINT NOT NULL,
    checkpoint_ts BIGINT,
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
    created_at BIGINT NOT NULL
);

COMMENT ON TABLE metrics_events_checkpoint IS 'Checkpoint 事件表';
COMMENT ON COLUMN metrics_events_checkpoint.id IS '主键，使用 XID';
COMMENT ON COLUMN metrics_events_checkpoint.uid IS '事件唯一标识';
COMMENT ON COLUMN metrics_events_checkpoint.raw_id IS '关联的原始批次 ID';
COMMENT ON COLUMN metrics_events_checkpoint.event_id IS '事件类型 ID (4=Checkpoint)';
COMMENT ON COLUMN metrics_events_checkpoint.timestamp IS '事件时间戳（毫秒）';
COMMENT ON COLUMN metrics_events_checkpoint.checkpoint_ts IS '检查点时间戳';
COMMENT ON COLUMN metrics_events_checkpoint.kind IS '检查点类型';
COMMENT ON COLUMN metrics_events_checkpoint.file_path IS '文件路径';
COMMENT ON COLUMN metrics_events_checkpoint.lines_added IS '新增行数';
COMMENT ON COLUMN metrics_events_checkpoint.lines_deleted IS '删除行数';
COMMENT ON COLUMN metrics_events_checkpoint.lines_added_sloc IS '新增源代码行数';
COMMENT ON COLUMN metrics_events_checkpoint.lines_deleted_sloc IS '删除源代码行数';
COMMENT ON COLUMN metrics_events_checkpoint.git_ai_version IS 'Git-AI 客户端版本号';
COMMENT ON COLUMN metrics_events_checkpoint.repo_url IS '仓库 URL';
COMMENT ON COLUMN metrics_events_checkpoint.author IS '提交作者';
COMMENT ON COLUMN metrics_events_checkpoint.commit_sha IS '提交 SHA';
COMMENT ON COLUMN metrics_events_checkpoint.base_commit_sha IS '基础提交 SHA';
COMMENT ON COLUMN metrics_events_checkpoint.branch IS '分支名称';
COMMENT ON COLUMN metrics_events_checkpoint.tool IS '使用工具';
COMMENT ON COLUMN metrics_events_checkpoint.model IS '使用模型';
COMMENT ON COLUMN metrics_events_checkpoint.prompt_id IS '提示词 ID';
COMMENT ON COLUMN metrics_events_checkpoint.created_at IS '创建时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_checkpoint_timestamp ON metrics_events_checkpoint(timestamp);
CREATE INDEX IF NOT EXISTS idx_checkpoint_file_path ON metrics_events_checkpoint(file_path);

CREATE TABLE IF NOT EXISTS metrics_events_agent_usage (
    id VARCHAR(20) PRIMARY KEY,
    uid VARCHAR(100) NOT NULL,
    raw_id VARCHAR(20),
    event_id INTEGER NOT NULL DEFAULT 2,
    timestamp BIGINT NOT NULL,
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
    created_at BIGINT NOT NULL
);

COMMENT ON TABLE metrics_events_agent_usage IS 'AgentUsage 事件表';
COMMENT ON COLUMN metrics_events_agent_usage.id IS '主键，使用 XID';
COMMENT ON COLUMN metrics_events_agent_usage.uid IS '事件唯一标识';
COMMENT ON COLUMN metrics_events_agent_usage.raw_id IS '关联的原始批次 ID';
COMMENT ON COLUMN metrics_events_agent_usage.event_id IS '事件类型 ID (2=AgentUsage)';
COMMENT ON COLUMN metrics_events_agent_usage.timestamp IS '事件时间戳（毫秒）';
COMMENT ON COLUMN metrics_events_agent_usage.git_ai_version IS 'Git-AI 客户端版本号';
COMMENT ON COLUMN metrics_events_agent_usage.repo_url IS '仓库 URL';
COMMENT ON COLUMN metrics_events_agent_usage.author IS '提交作者';
COMMENT ON COLUMN metrics_events_agent_usage.commit_sha IS '提交 SHA';
COMMENT ON COLUMN metrics_events_agent_usage.base_commit_sha IS '基础提交 SHA';
COMMENT ON COLUMN metrics_events_agent_usage.branch IS '分支名称';
COMMENT ON COLUMN metrics_events_agent_usage.tool IS '使用工具';
COMMENT ON COLUMN metrics_events_agent_usage.model IS '使用模型';
COMMENT ON COLUMN metrics_events_agent_usage.prompt_id IS '提示词 ID';
COMMENT ON COLUMN metrics_events_agent_usage.external_prompt_id IS '外部提示词 ID';
COMMENT ON COLUMN metrics_events_agent_usage.created_at IS '创建时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_agent_usage_timestamp ON metrics_events_agent_usage(timestamp);

CREATE TABLE IF NOT EXISTS metrics_events_install_hooks (
    id VARCHAR(20) PRIMARY KEY,
    uid VARCHAR(100) NOT NULL,
    raw_id VARCHAR(20),
    event_id INTEGER NOT NULL DEFAULT 3,
    timestamp BIGINT NOT NULL,
    tool_id TEXT,
    status TEXT,
    message TEXT,
    git_ai_version TEXT,
    created_at BIGINT NOT NULL
);

COMMENT ON TABLE metrics_events_install_hooks IS 'InstallHooks 事件表';
COMMENT ON COLUMN metrics_events_install_hooks.id IS '主键，使用 XID';
COMMENT ON COLUMN metrics_events_install_hooks.uid IS '事件唯一标识';
COMMENT ON COLUMN metrics_events_install_hooks.raw_id IS '关联的原始批次 ID';
COMMENT ON COLUMN metrics_events_install_hooks.event_id IS '事件类型 ID (3=InstallHooks)';
COMMENT ON COLUMN metrics_events_install_hooks.timestamp IS '事件时间戳（毫秒）';
COMMENT ON COLUMN metrics_events_install_hooks.tool_id IS '工具 ID';
COMMENT ON COLUMN metrics_events_install_hooks.status IS '安装状态';
COMMENT ON COLUMN metrics_events_install_hooks.message IS '安装消息';
COMMENT ON COLUMN metrics_events_install_hooks.git_ai_version IS 'Git-AI 客户端版本号';
COMMENT ON COLUMN metrics_events_install_hooks.created_at IS '创建时间戳（毫秒）';

CREATE TABLE IF NOT EXISTS metrics_event_errors (
    id VARCHAR(20) PRIMARY KEY,
    raw_id VARCHAR(20),
    event_index INTEGER NOT NULL,
    event_data_raw TEXT NOT NULL,
    error_message TEXT NOT NULL,
    payload_snippet TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_at BIGINT,
    created_at BIGINT NOT NULL
);

COMMENT ON TABLE metrics_event_errors IS '事件解析错误记录表';
COMMENT ON COLUMN metrics_event_errors.id IS '主键，使用 XID';
COMMENT ON COLUMN metrics_event_errors.raw_id IS '关联的原始批次 ID';
COMMENT ON COLUMN metrics_event_errors.event_index IS '事件在批次中的索引';
COMMENT ON COLUMN metrics_event_errors.event_data_raw IS '原始事件数据';
COMMENT ON COLUMN metrics_event_errors.error_message IS '错误消息';
COMMENT ON COLUMN metrics_event_errors.payload_snippet IS '载荷片段';
COMMENT ON COLUMN metrics_event_errors.retry_count IS '重试次数';
COMMENT ON COLUMN metrics_event_errors.last_retry_at IS '最后重试时间（毫秒）';
COMMENT ON COLUMN metrics_event_errors.created_at IS '创建时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_raw_event_index ON metrics_event_errors(raw_id, event_index);

CREATE TABLE IF NOT EXISTS cas_objects (
    id VARCHAR(20) PRIMARY KEY,
    hash VARCHAR(100) NOT NULL UNIQUE,
    content_json JSONB,
    metadata_json JSONB,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

COMMENT ON TABLE cas_objects IS 'CAS 对象表';
COMMENT ON COLUMN cas_objects.id IS '主键，使用 XID';
COMMENT ON COLUMN cas_objects.hash IS '内容哈希值';
COMMENT ON COLUMN cas_objects.content_json IS '内容 JSON';
COMMENT ON COLUMN cas_objects.metadata_json IS '元数据 JSON';
COMMENT ON COLUMN cas_objects.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN cas_objects.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_cas_hash ON cas_objects(hash);

CREATE TABLE IF NOT EXISTS stats_repositories (
    id VARCHAR(20) PRIMARY KEY,
    repo_path TEXT NOT NULL UNIQUE,
    repo_name TEXT,
    repo_stats_flag INTEGER DEFAULT 1,
    ssh_key_id VARCHAR(20),
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

COMMENT ON TABLE stats_repositories IS '仓库表';
COMMENT ON COLUMN stats_repositories.id IS '主键，使用 XID';
COMMENT ON COLUMN stats_repositories.repo_path IS '仓库路径';
COMMENT ON COLUMN stats_repositories.repo_name IS '仓库名称';
COMMENT ON COLUMN stats_repositories.repo_stats_flag IS '是否启用归因统计（0/1）';
COMMENT ON COLUMN stats_repositories.ssh_key_id IS '关联的 SSH Key ID';
COMMENT ON COLUMN stats_repositories.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_repositories.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_stats_repositories_name ON stats_repositories(repo_name);

CREATE TABLE IF NOT EXISTS stats_contributors (
    id VARCHAR(20) PRIMARY KEY,
    contributor_uid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    email TEXT,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

COMMENT ON TABLE stats_contributors IS '贡献者表';
COMMENT ON COLUMN stats_contributors.id IS '主键，使用 XID';
COMMENT ON COLUMN stats_contributors.contributor_uid IS '贡献者唯一标识';
COMMENT ON COLUMN stats_contributors.name IS '贡献者名称';
COMMENT ON COLUMN stats_contributors.email IS '贡献者邮箱';
COMMENT ON COLUMN stats_contributors.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_contributors.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_stats_contributors_email ON stats_contributors(email);

CREATE TABLE IF NOT EXISTS stats_repo_contributors (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    contributor_id VARCHAR(20) NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

COMMENT ON TABLE stats_repo_contributors IS '仓库贡献者关联表';
COMMENT ON COLUMN stats_repo_contributors.id IS '主键，使用 XID';
COMMENT ON COLUMN stats_repo_contributors.repo_id IS '仓库 ID';
COMMENT ON COLUMN stats_repo_contributors.contributor_id IS '贡献者 ID';
COMMENT ON COLUMN stats_repo_contributors.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_repo_contributors.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_stats_repo_contributors_repo ON stats_repo_contributors(repo_id);
CREATE INDEX IF NOT EXISTS idx_stats_repo_contributors_contributor ON stats_repo_contributors(contributor_id);

CREATE TABLE IF NOT EXISTS stats_daily_stats (
    id VARCHAR(20) PRIMARY KEY,
    stat_date BIGINT NOT NULL,
    repo_id VARCHAR(20) NOT NULL,
    repo_name TEXT,
    contributor_id VARCHAR(20) NOT NULL,
    contributor_name TEXT,
    ai_generated_lines INTEGER DEFAULT 0,
    ai_generated_lines_total INTEGER DEFAULT 0,
    ai_accepted_lines INTEGER DEFAULT 0,
    human_lines INTEGER DEFAULT 0,
    ai_percentage NUMERIC(5, 2) DEFAULT 0.0,
    git_ai_version VARCHAR(50),
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

COMMENT ON TABLE stats_daily_stats IS '每日统计表';
COMMENT ON COLUMN stats_daily_stats.id IS '主键，使用 XID';
COMMENT ON COLUMN stats_daily_stats.stat_date IS '统计日期（毫秒时间戳）';
COMMENT ON COLUMN stats_daily_stats.repo_id IS '仓库 ID';
COMMENT ON COLUMN stats_daily_stats.repo_name IS '仓库名称冗余字段';
COMMENT ON COLUMN stats_daily_stats.contributor_id IS '贡献者 ID';
COMMENT ON COLUMN stats_daily_stats.contributor_name IS '贡献者名称冗余字段';
COMMENT ON COLUMN stats_daily_stats.ai_generated_lines IS 'AI 生成源代码行数';
COMMENT ON COLUMN stats_daily_stats.ai_generated_lines_total IS 'AI 生成总行数';
COMMENT ON COLUMN stats_daily_stats.ai_accepted_lines IS '被接受的 AI 代码行数';
COMMENT ON COLUMN stats_daily_stats.human_lines IS '人类代码行数';
COMMENT ON COLUMN stats_daily_stats.ai_percentage IS 'AI 占比';
COMMENT ON COLUMN stats_daily_stats.git_ai_version IS 'Git-AI 客户端版本号';
COMMENT ON COLUMN stats_daily_stats.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_daily_stats.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_stats_daily_stats_date ON stats_daily_stats(stat_date);
CREATE INDEX IF NOT EXISTS idx_stats_daily_stats_repo ON stats_daily_stats(repo_id);
CREATE INDEX IF NOT EXISTS idx_stats_daily_stats_contributor ON stats_daily_stats(contributor_id);

CREATE TABLE IF NOT EXISTS task_executions (
    id VARCHAR(20) PRIMARY KEY,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at BIGINT,
    finished_at BIGINT,
    execution_time_ms INTEGER,
    error_message TEXT,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

COMMENT ON TABLE task_executions IS '任务执行记录表';
COMMENT ON COLUMN task_executions.id IS '主键，使用 XID';
COMMENT ON COLUMN task_executions.job_id IS '调度任务 ID';
COMMENT ON COLUMN task_executions.status IS '执行状态';
COMMENT ON COLUMN task_executions.started_at IS '开始执行时间（毫秒）';
COMMENT ON COLUMN task_executions.finished_at IS '完成时间（毫秒）';
COMMENT ON COLUMN task_executions.execution_time_ms IS '执行耗时（毫秒）';
COMMENT ON COLUMN task_executions.error_message IS '错误信息';
COMMENT ON COLUMN task_executions.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN task_executions.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_task_executions_job ON task_executions(job_id);

CREATE TABLE IF NOT EXISTS telemetry_envelope (
    id VARCHAR(20) PRIMARY KEY,
    envelope_data JSONB NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

COMMENT ON TABLE telemetry_envelope IS 'GIT AI 数据收集表';
COMMENT ON COLUMN telemetry_envelope.id IS '主键，使用 XID';
COMMENT ON COLUMN telemetry_envelope.envelope_data IS '包络 JSON 数据';
COMMENT ON COLUMN telemetry_envelope.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN telemetry_envelope.updated_at IS '更新时间戳（毫秒）';

CREATE TABLE IF NOT EXISTS authorship_notes (
    id VARCHAR(20) PRIMARY KEY,
    repo_url TEXT NOT NULL,
    branch TEXT NOT NULL,
    commit_sha VARCHAR(40) NOT NULL,
    note_blob_oid VARCHAR(40),
    author_name TEXT NOT NULL,
    author_email TEXT NOT NULL,
    note_content TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(repo_url, commit_sha)
);

COMMENT ON TABLE authorship_notes IS '作者注释表';
COMMENT ON COLUMN authorship_notes.id IS '主键，使用 XID';
COMMENT ON COLUMN authorship_notes.repo_url IS '仓库 URL';
COMMENT ON COLUMN authorship_notes.branch IS '分支名称';
COMMENT ON COLUMN authorship_notes.commit_sha IS '提交 SHA';
COMMENT ON COLUMN authorship_notes.note_blob_oid IS 'Note Blob OID';
COMMENT ON COLUMN authorship_notes.author_name IS '作者名称';
COMMENT ON COLUMN authorship_notes.author_email IS '作者邮箱';
COMMENT ON COLUMN authorship_notes.note_content IS '注释内容';
COMMENT ON COLUMN authorship_notes.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN authorship_notes.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_url ON authorship_notes(repo_url);
CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_commit ON authorship_notes(repo_url, commit_sha);

CREATE TABLE IF NOT EXISTS stats_ssh_keys (
    id VARCHAR(20) PRIMARY KEY,
    key_name TEXT NOT NULL UNIQUE,
    public_key TEXT NOT NULL,
    private_key_encrypted TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

COMMENT ON TABLE stats_ssh_keys IS 'SSH Key 表';
COMMENT ON COLUMN stats_ssh_keys.id IS '主键，使用 XID';
COMMENT ON COLUMN stats_ssh_keys.key_name IS 'Key 名称';
COMMENT ON COLUMN stats_ssh_keys.public_key IS '公钥内容';
COMMENT ON COLUMN stats_ssh_keys.private_key_encrypted IS '加密后的私钥内容';
COMMENT ON COLUMN stats_ssh_keys.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_ssh_keys.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_ssh_key_name ON stats_ssh_keys(key_name);

CREATE TABLE IF NOT EXISTS stats_blame_repo (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    commit_sha VARCHAR(40) NOT NULL,
    branch TEXT NOT NULL,
    total_lines INTEGER NOT NULL,
    ai_lines INTEGER NOT NULL,
    non_ai_lines INTEGER NOT NULL,
    ai_ratio NUMERIC(5, 2) NOT NULL,
    total_files INTEGER NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(repo_id, stat_date)
);

COMMENT ON TABLE stats_blame_repo IS '仓库级归因统计表';
COMMENT ON COLUMN stats_blame_repo.id IS '主键，使用 XID';
COMMENT ON COLUMN stats_blame_repo.repo_id IS '仓库 ID';
COMMENT ON COLUMN stats_blame_repo.stat_date IS '统计日期（毫秒时间戳）';
COMMENT ON COLUMN stats_blame_repo.commit_sha IS '当前统计提交 SHA';
COMMENT ON COLUMN stats_blame_repo.branch IS '分支名称';
COMMENT ON COLUMN stats_blame_repo.total_lines IS '总行数';
COMMENT ON COLUMN stats_blame_repo.ai_lines IS 'AI 代码行数';
COMMENT ON COLUMN stats_blame_repo.non_ai_lines IS '非 AI 代码行数';
COMMENT ON COLUMN stats_blame_repo.ai_ratio IS 'AI 代码占比';
COMMENT ON COLUMN stats_blame_repo.total_files IS '文件总数';
COMMENT ON COLUMN stats_blame_repo.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_blame_repo.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_blame_repo_date ON stats_blame_repo(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_stat_date ON stats_blame_repo(stat_date);

CREATE TABLE IF NOT EXISTS stats_blame_file (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    file_path TEXT NOT NULL,
    commit_sha VARCHAR(40) NOT NULL,
    total_lines INTEGER NOT NULL,
    ai_lines INTEGER NOT NULL,
    non_ai_lines INTEGER NOT NULL,
    ai_ratio NUMERIC(5, 2) NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(repo_id, stat_date, file_path)
);

COMMENT ON TABLE stats_blame_file IS '文件级归因统计表';
COMMENT ON COLUMN stats_blame_file.id IS '主键，使用 XID';
COMMENT ON COLUMN stats_blame_file.repo_id IS '仓库 ID';
COMMENT ON COLUMN stats_blame_file.stat_date IS '统计日期（毫秒时间戳）';
COMMENT ON COLUMN stats_blame_file.file_path IS '文件路径';
COMMENT ON COLUMN stats_blame_file.commit_sha IS '当前统计提交 SHA';
COMMENT ON COLUMN stats_blame_file.total_lines IS '总行数';
COMMENT ON COLUMN stats_blame_file.ai_lines IS 'AI 代码行数';
COMMENT ON COLUMN stats_blame_file.non_ai_lines IS '非 AI 代码行数';
COMMENT ON COLUMN stats_blame_file.ai_ratio IS 'AI 代码占比';
COMMENT ON COLUMN stats_blame_file.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_blame_file.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_blame_file_repo ON stats_blame_file(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_file_date ON stats_blame_file(stat_date);

CREATE TABLE IF NOT EXISTS stats_blame_repo_contributor (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    contributor_id VARCHAR(20) NOT NULL,
    contributor_name TEXT NOT NULL,
    contributor_email TEXT,
    ai_lines INTEGER NOT NULL DEFAULT 0,
    non_ai_lines INTEGER NOT NULL DEFAULT 0,
    total_lines INTEGER NOT NULL DEFAULT 0,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(repo_id, stat_date, contributor_id)
);

COMMENT ON TABLE stats_blame_repo_contributor IS '仓库贡献者归因统计表';
COMMENT ON COLUMN stats_blame_repo_contributor.id IS '主键，使用 XID';
COMMENT ON COLUMN stats_blame_repo_contributor.repo_id IS '仓库 ID';
COMMENT ON COLUMN stats_blame_repo_contributor.stat_date IS '统计日期（毫秒时间戳）';
COMMENT ON COLUMN stats_blame_repo_contributor.contributor_id IS '贡献者 ID';
COMMENT ON COLUMN stats_blame_repo_contributor.contributor_name IS '贡献者名称';
COMMENT ON COLUMN stats_blame_repo_contributor.contributor_email IS '贡献者邮箱';
COMMENT ON COLUMN stats_blame_repo_contributor.ai_lines IS 'AI 代码行数';
COMMENT ON COLUMN stats_blame_repo_contributor.non_ai_lines IS '非 AI 代码行数';
COMMENT ON COLUMN stats_blame_repo_contributor.total_lines IS '总行数';
COMMENT ON COLUMN stats_blame_repo_contributor.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_blame_repo_contributor.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_blame_rc_repo ON stats_blame_repo_contributor(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_rc_date ON stats_blame_repo_contributor(stat_date);

CREATE TABLE IF NOT EXISTS stats_blame_file_contributor (
    id VARCHAR(20) PRIMARY KEY,
    file_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    repo_id VARCHAR(20) NOT NULL,
    file_path TEXT NOT NULL,
    contributor_id VARCHAR(20) NOT NULL,
    contributor_name TEXT NOT NULL,
    contributor_email TEXT,
    ai_lines INTEGER NOT NULL DEFAULT 0,
    non_ai_lines INTEGER NOT NULL DEFAULT 0,
    total_lines INTEGER NOT NULL DEFAULT 0,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(file_id, stat_date, contributor_id)
);

COMMENT ON TABLE stats_blame_file_contributor IS '文件贡献者归因统计表';
COMMENT ON COLUMN stats_blame_file_contributor.id IS '主键，使用 XID';
COMMENT ON COLUMN stats_blame_file_contributor.file_id IS '文件级统计 ID';
COMMENT ON COLUMN stats_blame_file_contributor.stat_date IS '统计日期（毫秒时间戳）';
COMMENT ON COLUMN stats_blame_file_contributor.repo_id IS '仓库 ID';
COMMENT ON COLUMN stats_blame_file_contributor.file_path IS '文件路径';
COMMENT ON COLUMN stats_blame_file_contributor.contributor_id IS '贡献者 ID';
COMMENT ON COLUMN stats_blame_file_contributor.contributor_name IS '贡献者名称';
COMMENT ON COLUMN stats_blame_file_contributor.contributor_email IS '贡献者邮箱';
COMMENT ON COLUMN stats_blame_file_contributor.ai_lines IS 'AI 代码行数';
COMMENT ON COLUMN stats_blame_file_contributor.non_ai_lines IS '非 AI 代码行数';
COMMENT ON COLUMN stats_blame_file_contributor.total_lines IS '总行数';
COMMENT ON COLUMN stats_blame_file_contributor.created_at IS '创建时间戳（毫秒）';
COMMENT ON COLUMN stats_blame_file_contributor.updated_at IS '更新时间戳（毫秒）';

CREATE INDEX IF NOT EXISTS idx_blame_fc_file ON stats_blame_file_contributor(repo_id, stat_date, file_path);
CREATE INDEX IF NOT EXISTS idx_blame_fc_date ON stats_blame_file_contributor(stat_date);

CREATE TABLE IF NOT EXISTS apscheduler_jobs (
    id VARCHAR(191) NOT NULL PRIMARY KEY,
    next_run_time TIMESTAMP WITH TIME ZONE,
    job_state BYTEA NOT NULL
);

COMMENT ON TABLE apscheduler_jobs IS 'APScheduler JobStore 表';
COMMENT ON COLUMN apscheduler_jobs.id IS '任务 ID';
COMMENT ON COLUMN apscheduler_jobs.next_run_time IS '下次运行时间';
COMMENT ON COLUMN apscheduler_jobs.job_state IS '序列化任务状态';

CREATE INDEX IF NOT EXISTS idx_apscheduler_jobs_next_run_time ON apscheduler_jobs(next_run_time);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_cas_objects_updated_at ON cas_objects;
CREATE TRIGGER trigger_update_cas_objects_updated_at BEFORE UPDATE ON cas_objects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_repositories_updated_at ON stats_repositories;
CREATE TRIGGER trigger_update_stats_repositories_updated_at BEFORE UPDATE ON stats_repositories FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_contributors_updated_at ON stats_contributors;
CREATE TRIGGER trigger_update_stats_contributors_updated_at BEFORE UPDATE ON stats_contributors FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_repo_contributors_updated_at ON stats_repo_contributors;
CREATE TRIGGER trigger_update_stats_repo_contributors_updated_at BEFORE UPDATE ON stats_repo_contributors FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_daily_stats_updated_at ON stats_daily_stats;
CREATE TRIGGER trigger_update_stats_daily_stats_updated_at BEFORE UPDATE ON stats_daily_stats FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_task_executions_updated_at ON task_executions;
CREATE TRIGGER trigger_update_task_executions_updated_at BEFORE UPDATE ON task_executions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_telemetry_envelope_updated_at ON telemetry_envelope;
CREATE TRIGGER trigger_update_telemetry_envelope_updated_at BEFORE UPDATE ON telemetry_envelope FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_authorship_notes_updated_at ON authorship_notes;
CREATE TRIGGER trigger_update_authorship_notes_updated_at BEFORE UPDATE ON authorship_notes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_ssh_keys_updated_at ON stats_ssh_keys;
CREATE TRIGGER trigger_update_stats_ssh_keys_updated_at BEFORE UPDATE ON stats_ssh_keys FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_blame_repo_updated_at ON stats_blame_repo;
CREATE TRIGGER trigger_update_stats_blame_repo_updated_at BEFORE UPDATE ON stats_blame_repo FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_blame_file_updated_at ON stats_blame_file;
CREATE TRIGGER trigger_update_stats_blame_file_updated_at BEFORE UPDATE ON stats_blame_file FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_blame_repo_contributor_updated_at ON stats_blame_repo_contributor;
CREATE TRIGGER trigger_update_stats_blame_repo_contributor_updated_at BEFORE UPDATE ON stats_blame_repo_contributor FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_stats_blame_file_contributor_updated_at ON stats_blame_file_contributor;
CREATE TRIGGER trigger_update_stats_blame_file_contributor_updated_at BEFORE UPDATE ON stats_blame_file_contributor FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
