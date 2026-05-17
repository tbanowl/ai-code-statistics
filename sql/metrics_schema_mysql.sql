-- Metrics 原始事件表
CREATE TABLE IF NOT EXISTS metrics_events_raw (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID (20字符字符串)',
    version INT NOT NULL DEFAULT 1 COMMENT '批次版本号',
    event_count INT NOT NULL COMMENT '批次中的事件数量',
    payload_json TEXT NOT NULL COMMENT '原始 JSON 载荷数据',
    extract INT NOT NULL DEFAULT 0 COMMENT '提取标识：0-未提取、1-提取成功、2-提取中、3-提取失败',
    extract_fail VARCHAR(100) COMMENT '提取失败原因',
    received_at BIGINT NOT NULL COMMENT '接收时间戳（毫秒）',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    INDEX idx_metrics_raw_received_at (received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Metrics 原始事件表';

-- Committed 事件表
CREATE TABLE IF NOT EXISTS metrics_events_committed (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    uid VARCHAR(100) NOT NULL COMMENT '事件唯一标识',
    raw_id VARCHAR(20) COMMENT '关联的原始批次 ID',
    event_id INT NOT NULL DEFAULT 1 COMMENT '事件类型 ID (1=Committed)',
    timestamp BIGINT NOT NULL COMMENT '事件时间戳（毫秒）',
    human_additions INT COMMENT '人类手动添加代码行数',
    git_diff_deleted_lines INT COMMENT 'Git diff 删除行数',
    git_diff_added_lines INT COMMENT 'Git diff 新增行数',
    first_checkpoint_ts BIGINT COMMENT '首次检查点时间戳',
    commit_subject VARCHAR(200) COMMENT '提交标题',
    commit_body VARCHAR(1000) COMMENT '提交正文',
    tool_model_pairs JSON COMMENT '工具-模型配对 JSON',
    mixed_additions JSON COMMENT '混合生成代码行数 JSON',
    ai_additions JSON COMMENT 'AI 生成代码行数 JSON',
    ai_accepted JSON COMMENT '被接受的 AI 代码行数 JSON',
    total_ai_additions JSON COMMENT '总 AI 新增代码行数 JSON',
    total_ai_deletions JSON COMMENT '总 AI 删除代码行数 JSON',
    time_waiting_for_ai JSON COMMENT '等待 AI 响应时长 JSON',
    git_ai_version VARCHAR(20) COMMENT 'Git-AI 客户端版本号',
    repo_url VARCHAR(400) COMMENT '仓库 URL',
    author VARCHAR(100) COMMENT '提交作者',
    commit_sha VARCHAR(40) COMMENT '提交 SHA',
    base_commit_sha VARCHAR(40) COMMENT '基础提交 SHA',
    branch VARCHAR(50) COMMENT '分支名称',
    tool VARCHAR(1000) COMMENT '使用工具',
    model VARCHAR(50) COMMENT '使用模型',
    prompt_id VARCHAR(200) COMMENT '提示词 ID',
    external_prompt_id VARCHAR(200) COMMENT '外部提示词 ID',
    custom_attributes JSON COMMENT '自定义属性 JSON',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    INDEX idx_committed_timestamp (timestamp),
    INDEX idx_committed_repo_url (repo_url),
    INDEX idx_committed_author (author),
    INDEX idx_committed_commit_sha (commit_sha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Committed 事件表';

-- Checkpoint 事件表
CREATE TABLE IF NOT EXISTS metrics_events_checkpoint (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    uid VARCHAR(100) NOT NULL COMMENT '事件唯一标识',
    raw_id VARCHAR(20) COMMENT '关联的原始批次 ID',
    event_id INT NOT NULL DEFAULT 4 COMMENT '事件类型 ID (4=Checkpoint)',
    timestamp BIGINT NOT NULL COMMENT '事件时间戳（毫秒）',
    checkpoint_ts BIGINT COMMENT '检查点时间戳',
    kind VARCHAR(100) COMMENT '检查点类型',
    file_path VARCHAR(500) COMMENT '文件路径',
    lines_added INT COMMENT '新增行数',
    lines_deleted INT COMMENT '删除行数',
    lines_added_sloc INT COMMENT '新增源代码行数',
    lines_deleted_sloc INT COMMENT '删除源代码行数',
    git_ai_version VARCHAR(20) COMMENT 'Git-AI 客户端版本号',
    repo_url VARCHAR(400) COMMENT '仓库 URL',
    author VARCHAR(100) COMMENT '提交作者',
    commit_sha VARCHAR(40) COMMENT '提交 SHA',
    base_commit_sha VARCHAR(40) COMMENT '基础提交 SHA',
    branch VARCHAR(50) COMMENT '分支名称',
    tool VARCHAR(1000) COMMENT '使用工具',
    model VARCHAR(50) COMMENT '使用模型',
    prompt_id VARCHAR(200) COMMENT '提示词 ID',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    INDEX idx_checkpoint_timestamp (timestamp),
    INDEX idx_checkpoint_file_path (file_path)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Checkpoint 事件表';

-- AgentUsage 事件表
CREATE TABLE IF NOT EXISTS metrics_events_agent_usage (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    uid VARCHAR(100) NOT NULL COMMENT '事件唯一标识',
    raw_id VARCHAR(20) COMMENT '关联的原始批次 ID',
    event_id INT NOT NULL DEFAULT 2 COMMENT '事件类型 ID (2=AgentUsage)',
    timestamp BIGINT NOT NULL COMMENT '事件时间戳（毫秒）',
    git_ai_version VARCHAR(20) COMMENT 'Git-AI 客户端版本号',
    repo_url VARCHAR(400) COMMENT '仓库 URL',
    author VARCHAR(100) COMMENT '提交作者',
    commit_sha VARCHAR(40) COMMENT '提交 SHA',
    base_commit_sha VARCHAR(40) COMMENT '基础提交 SHA',
    branch VARCHAR(50) COMMENT '分支名称',
    tool VARCHAR(1000) COMMENT '使用工具',
    model VARCHAR(50) COMMENT '使用模型',
    prompt_id VARCHAR(200) COMMENT '提示词 ID',
    external_prompt_id VARCHAR(200) COMMENT '外部提示词 ID',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    INDEX idx_agent_usage_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AgentUsage 事件表';

-- InstallHooks 事件表
CREATE TABLE IF NOT EXISTS metrics_events_install_hooks (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    uid VARCHAR(100) NOT NULL COMMENT '事件唯一标识',
    raw_id VARCHAR(20) COMMENT '关联的原始批次 ID',
    event_id INT NOT NULL DEFAULT 3 COMMENT '事件类型 ID (3=InstallHooks)',
    timestamp BIGINT NOT NULL COMMENT '事件时间戳（毫秒）',
    tool_id VARCHAR(100) COMMENT '工具 ID',
    status VARCHAR(100) COMMENT '安装状态',
    message TEXT COMMENT '安装消息',
    git_ai_version VARCHAR(20) COMMENT 'Git-AI 客户端版本号',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='InstallHooks 事件表';

-- 事件解析错误记录表
CREATE TABLE IF NOT EXISTS metrics_event_errors (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    raw_id VARCHAR(20) COMMENT '关联的原始批次 ID',
    event_index INT NOT NULL COMMENT '事件在批次中的索引',
    event_data_raw TEXT NOT NULL COMMENT '原始事件数据',
    error_message TEXT NOT NULL COMMENT '错误消息',
    payload_snippet TEXT COMMENT '载荷片段',
    retry_count INT NOT NULL DEFAULT 0 COMMENT '重试次数',
    last_retry_at BIGINT COMMENT '最后重试时间（毫秒）',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    INDEX idx_raw_event_index (raw_id, event_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='事件解析错误记录表';

-- Claude Code OTLP Logs Skill 调用计数表
CREATE TABLE IF NOT EXISTS otel_invocation_counts (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    source VARCHAR(50) NOT NULL DEFAULT 'claude_code' COMMENT '来源',
    category VARCHAR(50) NOT NULL DEFAULT 'skill' COMMENT '分类',
    plugin_name VARCHAR(200) NOT NULL COMMENT '插件名称',
    skill_name VARCHAR(200) NOT NULL COMMENT '技能名称',
    invocation_trigger VARCHAR(50) COMMENT '调用触发方式',
    org_user VARCHAR(200) NOT NULL COMMENT '组织/用户标识',
    service_name VARCHAR(200) COMMENT '服务名称',
    service_version VARCHAR(100) COMMENT '服务版本',
    count INT NOT NULL DEFAULT 1 COMMENT '调用次数',
    time_unix_nano VARCHAR(30) COMMENT 'Unix 纳秒时间戳',
    received_at BIGINT NOT NULL COMMENT '接收时间戳（毫秒）',
    otel_log_date CHAR(8) NOT NULL COMMENT '日志日期（YYYYMMDD）',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    INDEX idx_otel_invocation_received_at (received_at),
    INDEX idx_otel_invocation_org_plugin_skill (org_user, plugin_name, skill_name)
    INDEX idx_otel_log_date_plugin_skill_user (otel_log_date, plugin_name, skill_name, org_user)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Claude Code OTLP Logs Skill 调用计数表';

-- CAS 对象表
CREATE TABLE IF NOT EXISTS cas_objects (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    hash VARCHAR(100) NOT NULL COMMENT '内容哈希值',
    content_json JSON COMMENT '内容 JSON',
    metadata_json JSON COMMENT '元数据 JSON',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_cas_hash (hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='CAS 对象表';

-- 仓库表
CREATE TABLE IF NOT EXISTS stats_repositories (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_path VARCHAR(200) NOT NULL COMMENT '仓库路径',
    repo_name VARCHAR(100) COMMENT '仓库名称',
    repo_stats_flag INT DEFAULT 1 COMMENT '是否启用归因统计（0/1）',
    ssh_key_id VARCHAR(20) COMMENT '关联的 SSH Key ID',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_stats_repositories_name (repo_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='仓库表';

-- 仓库分支表
CREATE TABLE IF NOT EXISTS stats_repo_branch_config (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    branch_pattern TEXT NOT NULL COMMENT '分支模式',
    pattern_type VARCHAR(20) NOT NULL DEFAULT 'exact' COMMENT "正则类型: exact, wildcard, special",
    enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at BIGINT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_repo_branch_config_repo (repo_id),
    INDEX idx_repo_branch_config_enabled (repo_id, enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='仓库分支表';

-- 仓库实际分支表
CREATE TABLE IF NOT EXISTS stats_repositories_branch (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    branch_name VARCHAR(255) NOT NULL COMMENT '分支名称',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_repositories_branch_repo_name (repo_id, branch_name),
    INDEX idx_repositories_branch_repo (repo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='仓库实际分支表';

-- 贡献者表
CREATE TABLE IF NOT EXISTS stats_contributors (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    name VARCHAR(100) NOT NULL COMMENT '贡献者名称',
    email VARCHAR(100) COMMENT '贡献者邮箱',
    display_name VARCHAR(50) COMMENT '显示名称',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_stats_contributors_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='贡献者表';

-- 仓库贡献者关联表
CREATE TABLE IF NOT EXISTS stats_repo_contributors (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    contributor_id VARCHAR(20) NOT NULL COMMENT '贡献者 ID',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_stats_repo_contributors_repo (repo_id),
    INDEX idx_stats_repo_contributors_contributor (contributor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='仓库贡献者关联表';

-- 每日统计表
CREATE TABLE IF NOT EXISTS stats_daily_stats (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    stat_date BIGINT NOT NULL COMMENT '统计日期（毫秒时间戳）',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    repo_name VARCHAR(100) COMMENT '仓库名称冗余字段',
    contributor_id VARCHAR(20) NOT NULL COMMENT '贡献者 ID',
    contributor_name VARCHAR(100) COMMENT '贡献者名称冗余字段',
    ai_generated_lines INT DEFAULT 0 COMMENT 'AI 生成源代码行数',
    ai_generated_lines_total INT DEFAULT 0 COMMENT 'AI 生成总行数',
    ai_accepted_lines INT DEFAULT 0 COMMENT '被接受的 AI 代码行数',
    human_lines INT DEFAULT 0 COMMENT '人类代码行数',
    ai_percentage DECIMAL(5, 2) DEFAULT 0.0 COMMENT 'AI 占比',
    git_ai_version VARCHAR(50) COMMENT 'Git-AI 客户端版本号',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_stats_daily_stats_date (stat_date),
    INDEX idx_stats_daily_stats_repo (repo_id),
    INDEX idx_stats_daily_stats_contributor (contributor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='每日统计表';

-- GIT AI 数据收集表
CREATE TABLE IF NOT EXISTS telemetry_envelope (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    envelope_data JSON NOT NULL COMMENT '包络 JSON 数据',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='GIT AI 数据收集表';

-- 作者注释表
CREATE TABLE IF NOT EXISTS authorship_notes (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_url VARCHAR(400) NOT NULL COMMENT '仓库 URL',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    commit_sha VARCHAR(40) NOT NULL COMMENT '提交 SHA',
    commit_time BIGINT NOT NULL DEFAULT 0 COMMENT '提交时间戳（秒）',
    note_blob_oid VARCHAR(40) COMMENT 'Note Blob OID',
    author_name VARCHAR(100) NOT NULL COMMENT '作者名称',
    author_email VARCHAR(100) NOT NULL COMMENT '作者邮箱',
    note_content TEXT NOT NULL COMMENT '注释内容',
    content_hash VARCHAR(71) NOT NULL COMMENT 'note_content 的 SHA-256 摘要',
    change_seq BIGINT NOT NULL COMMENT '服务端单调递增变更序号',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_authorship_notes_repo_commit (repo_url, commit_sha),
    INDEX idx_authorship_notes_repo_url (repo_url),
    INDEX idx_authorship_notes_repo_commit (repo_url, commit_sha),
    INDEX idx_authorship_notes_repo_change_seq (repo_url, change_seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='作者注释表';

CREATE TABLE IF NOT EXISTS authorship_notes_seq (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '全局 authorship_notes change_seq',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Authorship Notes 变更序列表';

-- SSH Key 表
CREATE TABLE IF NOT EXISTS stats_ssh_keys (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    key_name VARCHAR(100) NOT NULL COMMENT 'Key 名称',
    public_key TEXT COMMENT '公钥内容',
    private_key_encrypted TEXT NOT NULL COMMENT '加密后的私钥内容',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_ssh_key_name (key_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='SSH Key 表';

-- 仓库级归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_repo (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    stat_date BIGINT NOT NULL COMMENT '统计日期（毫秒时间戳）',
    commit_sha VARCHAR(40) NOT NULL COMMENT '当前统计提交 SHA',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    total_lines INT NOT NULL COMMENT '总行数',
    ai_lines INT NOT NULL COMMENT 'AI 代码行数',
    non_ai_lines INT NOT NULL COMMENT '非 AI 代码行数',
    ai_ratio DECIMAL(5, 2) NOT NULL COMMENT 'AI 代码占比',
    total_files INT NOT NULL COMMENT '文件总数',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_blame_repo_date_branch (repo_id, stat_date, branch),
    INDEX idx_blame_repo_date (repo_id, stat_date),
    INDEX idx_blame_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='仓库级归因统计表';

-- 文件级归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_file (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    stat_date BIGINT NOT NULL COMMENT '统计日期（毫秒时间戳）',
    file_path VARCHAR(500) NOT NULL COMMENT '文件路径',
    commit_sha VARCHAR(40) NOT NULL COMMENT '当前统计提交 SHA',
    total_lines INT NOT NULL COMMENT '总行数',
    ai_lines INT NOT NULL COMMENT 'AI 代码行数',
    non_ai_lines INT NOT NULL COMMENT '非 AI 代码行数',
    ai_ratio DECIMAL(5, 2) NOT NULL COMMENT 'AI 代码占比',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_blame_file_branch_path (repo_id, stat_date, branch, file_path),
    INDEX idx_blame_file_repo (repo_id, stat_date),
    INDEX idx_blame_file_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='文件级归因统计表';

-- 仓库贡献者归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_repo_contributor (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    stat_date BIGINT NOT NULL COMMENT '统计日期（毫秒时间戳）',
    contributor_id VARCHAR(20) NOT NULL COMMENT '贡献者 ID',
    contributor_name VARCHAR(100) NOT NULL COMMENT '贡献者名称',
    contributor_email VARCHAR(100) COMMENT '贡献者邮箱',
    ai_lines INT NOT NULL DEFAULT 0 COMMENT 'AI 代码行数',
    non_ai_lines INT NOT NULL DEFAULT 0 COMMENT '非 AI 代码行数',
    total_lines INT NOT NULL DEFAULT 0 COMMENT '总行数',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_blame_rc_branch_contributor (repo_id, stat_date, branch, contributor_id),
    INDEX idx_blame_rc_repo (repo_id, stat_date),
    INDEX idx_blame_rc_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='仓库贡献者归因统计表';

-- 文件贡献者归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_file_contributor (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    file_id VARCHAR(20) NOT NULL COMMENT '文件级统计 ID',
    stat_date BIGINT NOT NULL COMMENT '统计日期（毫秒时间戳）',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    file_path VARCHAR(500) NOT NULL COMMENT '文件路径',
    contributor_id VARCHAR(20) NOT NULL COMMENT '贡献者 ID',
    contributor_name VARCHAR(100) NOT NULL COMMENT '贡献者名称',
    contributor_email VARCHAR(100) COMMENT '贡献者邮箱',
    ai_lines INT NOT NULL DEFAULT 0 COMMENT 'AI 代码行数',
    non_ai_lines INT NOT NULL DEFAULT 0 COMMENT '非 AI 代码行数',
    total_lines INT NOT NULL DEFAULT 0 COMMENT '总行数',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_blame_fc_branch_contributor (file_id, stat_date, branch, contributor_id),
    INDEX idx_blame_fc_file (repo_id, stat_date, file_path),
    INDEX idx_blame_fc_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='文件贡献者归因统计表';

-- APScheduler JobStore 表
CREATE TABLE IF NOT EXISTS apscheduler_jobs (
    id VARCHAR(191) NOT NULL PRIMARY KEY COMMENT '任务 ID',
    next_run_time DOUBLE COMMENT '下次运行时间',
    job_state LONGBLOB NOT NULL COMMENT '序列化任务状态',
    INDEX idx_apscheduler_jobs_next_run_time (next_run_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='APScheduler JobStore 表';


-- 任务执行表
CREATE TABLE IF NOT EXISTS task_running (
    job_id VARCHAR(100) PRIMARY KEY  COMMENT '调度任务 ID',
    started_at BIGINT COMMENT '开始执行时间（毫秒）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='任务执行表';


-- 任务执行记录表
CREATE TABLE IF NOT EXISTS task_executions (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    job_id VARCHAR(100) NOT NULL COMMENT '调度任务 ID',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '执行状态',
    started_at BIGINT COMMENT '开始执行时间（毫秒）',
    finished_at BIGINT COMMENT '完成时间（毫秒）',
    execution_time_ms INT COMMENT '执行耗时（毫秒）',
    error_message TEXT COMMENT '错误信息',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_task_executions_job (job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='任务执行记录表';

-- Codeup 合并 authorship 重算任务表
CREATE TABLE IF NOT EXISTS codeup_merge_authorship_tasks (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_url VARCHAR(400) NOT NULL COMMENT '仓库远程 URL',
    project_id VARCHAR(100) COMMENT 'Codeup 项目 ID',
    merge_request_id VARCHAR(100) NOT NULL COMMENT 'Merge Request ID',
    source_branch VARCHAR(255) NOT NULL COMMENT '源分支',
    target_branch VARCHAR(255) NOT NULL COMMENT '目标分支',
    merge_commit_sha VARCHAR(40) NOT NULL COMMENT '合并提交 SHA',
    source_commit_shas TEXT NOT NULL COMMENT '源提交 SHA 列表 JSON',
    payload TEXT NOT NULL COMMENT '原始 webhook payload JSON',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '任务状态',
    attempts INT NOT NULL DEFAULT 0 COMMENT '尝试次数',
    last_error TEXT COMMENT '最后错误信息',
    result_summary TEXT COMMENT '处理结果摘要 JSON',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_codeup_merge_authorship_task (repo_url(400), merge_request_id, merge_commit_sha),
    INDEX idx_codeup_merge_authorship_status_attempts (status, attempts),
    INDEX idx_codeup_merge_authorship_repo_url (repo_url(400)),
    INDEX idx_codeup_merge_authorship_commit (merge_commit_sha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Codeup 合并 authorship 重算任务表';

-- 系统管理表
CREATE TABLE IF NOT EXISTS sys_dept (
    id VARCHAR(20) PRIMARY KEY ,
    parent_id VARCHAR(20) NOT NULL DEFAULT 0,
    name VARCHAR(100) NOT NULL,
    sort INT NOT NULL DEFAULT 0,
    status INT NOT NULL DEFAULT 1,
    created_at BIGINT NOT NULL
)  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='部门表';

CREATE TABLE IF NOT EXISTS sys_menu (
    id VARCHAR(20) PRIMARY KEY ,
    parent_id VARCHAR(20) NOT NULL DEFAULT 0,
    title VARCHAR(100) NOT NULL,
    router_name VARCHAR(100) NOT NULL COMMENT '路由名称',
    path VARCHAR(200),
    component VARCHAR(200),
    icon VARCHAR(100),
    `rank` INT NOT NULL DEFAULT 0,
    menu_type INT NOT NULL DEFAULT 0,
    status INT NOT NULL DEFAULT 1,
    show_link INT NOT NULL DEFAULT 1,
    keep_alive INT NOT NULL DEFAULT 0,
    created_at BIGINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='菜单表';

CREATE TABLE IF NOT EXISTS sys_role (
    id VARCHAR(20) PRIMARY KEY ,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(100) NOT NULL UNIQUE,
    status INT NOT NULL DEFAULT 1,
    remark VARCHAR(500),
    created_at BIGINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='角色表';

CREATE TABLE IF NOT EXISTS sys_user (
    id VARCHAR(20) PRIMARY KEY ,
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(200) NOT NULL,
    nickname VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(200),
    dept_id VARCHAR(20),
    avatar VARCHAR(500),
    status INT NOT NULL DEFAULT 1,
    created_at BIGINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户表';

CREATE TABLE IF NOT EXISTS sys_user_role (
    id VARCHAR(20) PRIMARY KEY ,
    user_id VARCHAR(20) NOT NULL,
    role_id VARCHAR(20) NOT NULL,
    INDEX idx_user_role_user (user_id),
    INDEX idx_user_role_role (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户角色表';

CREATE TABLE IF NOT EXISTS sys_role_menu (
    id VARCHAR(20) PRIMARY KEY ,
    role_id VARCHAR(20) NOT NULL,
    menu_id VARCHAR(20) NOT NULL,
    INDEX idx_role_menu_role (role_id),
    INDEX idx_role_menu_menu (menu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='角色菜单表';
