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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Metrics 原始事件表';

-- Committed 事件表
CREATE TABLE IF NOT EXISTS metrics_events_committed (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    uid VARCHAR(100) NOT NULL COMMENT '事件唯一标识',
    raw_id VARCHAR(20) COMMENT '关联的原始批次 ID',
    event_id INT NOT NULL DEFAULT 1 COMMENT '事件类型 ID (1=Committed)',
    timestamp BIGINT NOT NULL COMMENT '事件时间戳（秒）',
    commit_date BIGINT COMMENT '提交日期 yyyyMMdd',
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
    mixed_additions_total INT NOT NULL DEFAULT 0 COMMENT '混合生成代码行数首值',
    ai_additions_total INT NOT NULL DEFAULT 0 COMMENT 'AI 生成代码行数首值',
    ai_accepted_total INT NOT NULL DEFAULT 0 COMMENT '被接受 AI 代码行数首值',
    total_ai_additions_total INT NOT NULL DEFAULT 0 COMMENT '总 AI 新增代码行数首值',
    total_ai_deletions_total INT NOT NULL DEFAULT 0 COMMENT '总 AI 删除代码行数首值',
    time_waiting_for_ai_total BIGINT NOT NULL DEFAULT 0 COMMENT '等待 AI 响应时长首值',
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
    INDEX idx_committed_commit_sha (commit_sha),
    INDEX idx_committed_repo_id (repo_url, id),
    INDEX idx_committed_repo_commit_date (repo_url, commit_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Committed 事件表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Checkpoint 事件表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AgentUsage 事件表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='InstallHooks 事件表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='事件解析错误记录表';

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
    INDEX idx_otel_invocation_org_plugin_skill (org_user, plugin_name, skill_name),
    INDEX idx_otel_log_date_plugin_skill_user (otel_log_date, plugin_name, skill_name, org_user)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Claude Code OTLP Logs Skill 调用计数表';

-- CAS 对象表
CREATE TABLE IF NOT EXISTS cas_objects (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    hash VARCHAR(100) NOT NULL COMMENT '内容哈希值',
    content_json JSON COMMENT '内容 JSON',
    metadata_json JSON COMMENT '元数据 JSON',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_cas_hash (hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='CAS 对象表';

-- 仓库表
CREATE TABLE IF NOT EXISTS stats_repositories (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_path VARCHAR(200) NOT NULL COMMENT '仓库路径',
    repo_name VARCHAR(100) COMMENT '仓库名称',
    name_level1 VARCHAR(50) COMMENT '仓库路径一级名称',
    name_level2 VARCHAR(50) COMMENT '仓库路径二级名称',
    name_level3 VARCHAR(50) COMMENT '仓库路径三级名称',
    name_level4 VARCHAR(50) COMMENT '仓库路径四级名称',
    name_level5 VARCHAR(50) COMMENT '仓库路径五级名称',
    repo_short_name VARCHAR(50) COMMENT '仓库短名称',
    repo_stats_flag INT DEFAULT 1 COMMENT '是否启用归因统计（0/1）',
    ssh_key_id VARCHAR(20) COMMENT '关联的 SSH Key ID',
    last_blame_commit_sha VARCHAR(40) COMMENT '最近一次 Git Blame 统计成功的提交 SHA',
    last_daily_aggregation_id VARCHAR(20) COMMENT '最近一次每日聚合成功统计到的 committed 事件 ID',
    last_stat_date BIGINT COMMENT '最后统计日期，格式 yyyyMMdd',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_stats_repositories_name (repo_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓库表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓库分支表';

-- 仓库实际分支表
CREATE TABLE IF NOT EXISTS stats_repositories_branch (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    branch_name VARCHAR(255) NOT NULL COMMENT '分支名称',
    is_deleted INT NOT NULL DEFAULT 0 COMMENT '是否已删除（0/1）',
    deleted_at BIGINT COMMENT '删除时间戳（毫秒）',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_repositories_branch_repo_name (repo_id, branch_name),
    INDEX idx_repositories_branch_repo (repo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓库实际分支表';

-- 贡献者表
CREATE TABLE IF NOT EXISTS stats_contributors (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    name VARCHAR(100) NOT NULL COMMENT '贡献者名称',
    email VARCHAR(100) COMMENT '贡献者邮箱',
    display_name VARCHAR(50) COMMENT '显示名称',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_stats_contributors_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='贡献者表';

-- 仓库贡献者关联表
CREATE TABLE IF NOT EXISTS stats_repo_contributors (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    contributor_id VARCHAR(20) NOT NULL COMMENT '贡献者 ID',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_stats_repo_contributors_repo (repo_id),
    INDEX idx_stats_repo_contributors_contributor (contributor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓库贡献者关联表';

-- Commit 每日统计表
CREATE TABLE IF NOT EXISTS stats_commit_daily (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    stat_date BIGINT NOT NULL COMMENT '统计日期（年月日 yyyyMMdd）',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    repo_name VARCHAR(100) COMMENT '仓库名称冗余字段',
    contributor_name VARCHAR(100) COMMENT '贡献者名称冗余字段',
    contributor_email VARCHAR(255) COMMENT '贡献者邮箱',
    human_additions INT DEFAULT 0 COMMENT '人类手动添加代码行数',
    unknown_additions INT DEFAULT 0 COMMENT '未知来源新增代码行数',
    git_diff_deleted_lines INT DEFAULT 0 COMMENT 'Git diff 删除行数',
    git_diff_added_lines INT DEFAULT 0 COMMENT 'Git diff 新增行数',
    mixed_additions INT DEFAULT 0 COMMENT '混合生成代码行数',
    ai_additions INT DEFAULT 0 COMMENT 'AI 生成代码行数',
    ai_accepted INT DEFAULT 0 COMMENT '被接受 AI 代码行数',
    total_ai_additions INT DEFAULT 0 COMMENT '总 AI 新增代码行数',
    total_ai_deletions INT DEFAULT 0 COMMENT '总 AI 删除代码行数',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_stats_commit_daily_date (stat_date),
    INDEX idx_stats_commit_daily_repo (repo_id),
    INDEX idx_stats_commit_daily_contributor_email (contributor_email),
    UNIQUE KEY uk_stats_commit_daily_identity (stat_date, repo_id, contributor_name, contributor_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Commit 每日统计表';

-- GIT AI 数据收集表
CREATE TABLE IF NOT EXISTS telemetry_envelope (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    envelope_data JSON NOT NULL COMMENT '包络 JSON 数据',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='GIT AI 数据收集表';

-- Git-AI 客户端发布版本表
CREATE TABLE IF NOT EXISTS git_ai_releases (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    tag VARCHAR(100) NOT NULL COMMENT '发布标签',
    version VARCHAR(100) NOT NULL COMMENT '版本号',
    channel VARCHAR(50) NOT NULL COMMENT '发布通道',
    status VARCHAR(20) NOT NULL DEFAULT 'inactive' COMMENT '发布状态：active/inactive',
    active_channel VARCHAR(50) GENERATED ALWAYS AS (CASE WHEN status = 'active' THEN channel ELSE NULL END) STORED COMMENT '激活状态唯一约束辅助列',
    sha256sums_checksum VARCHAR(64) NOT NULL COMMENT 'SHA256SUMS 文件的 SHA-256',
    description TEXT COMMENT '发布说明',
    created_by VARCHAR(100) COMMENT '创建人',
    published_at BIGINT COMMENT '激活发布时间戳（毫秒）',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_git_ai_releases_channel_tag (channel, tag),
    UNIQUE KEY uk_git_ai_releases_active_channel (active_channel),
    INDEX idx_git_ai_releases_channel_status (channel, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Git-AI 客户端发布版本表';

-- Git-AI 客户端发布文件表
CREATE TABLE IF NOT EXISTS git_ai_release_artifacts (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    release_id VARCHAR(20) NOT NULL COMMENT '发布版本 ID',
    filename VARCHAR(255) NOT NULL COMMENT '文件名',
    artifact_type VARCHAR(30) NOT NULL COMMENT '文件类型：installer/executable/checksums',
    platform VARCHAR(50) COMMENT '目标平台',
    sha256 VARCHAR(64) NOT NULL COMMENT '文件内容 SHA-256',
    size_bytes BIGINT NOT NULL COMMENT '文件大小（字节）',
    content_type VARCHAR(100) NOT NULL COMMENT 'MIME 类型',
    content_blob LONGBLOB NOT NULL COMMENT '文件内容',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    UNIQUE KEY uk_git_ai_release_artifacts_release_filename (release_id, filename),
    INDEX idx_git_ai_release_artifacts_release (release_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Git-AI 客户端发布文件表';

-- 作者注释表
CREATE TABLE IF NOT EXISTS authorship_notes (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_url VARCHAR(400) NOT NULL COMMENT '仓库 URL',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    commit_sha VARCHAR(40) NOT NULL COMMENT '提交 SHA',
    commit_time BIGINT NOT NULL DEFAULT 0 COMMENT '提交时间戳（秒）',
    commit_date BIGINT COMMENT '提交日期 yyyyMMdd',
    note_blob_oid VARCHAR(40) COMMENT 'Note Blob OID',
    author_name VARCHAR(100) NOT NULL COMMENT '作者名称',
    author_email VARCHAR(100) NOT NULL COMMENT '作者邮箱',
    note_content TEXT NOT NULL COMMENT '注释内容',
    content_hash VARCHAR(71) NOT NULL COMMENT 'note_content 的 SHA-256 摘要',
    change_seq BIGINT NOT NULL COMMENT '服务端单调递增变更序号',
    status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '注释状态',
    superseded_by VARCHAR(40) COMMENT '取代该注释的提交 SHA',
    superseded_at BIGINT COMMENT '取代时间戳（毫秒）',
    superseded_rewrite_id VARCHAR(200) COMMENT '取代该注释的重写操作 ID',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_authorship_notes_repo_commit (repo_url, commit_sha),
    INDEX idx_authorship_notes_repo_url (repo_url),
    INDEX idx_authorship_notes_repo_commit (repo_url, commit_sha),
    INDEX idx_authorship_notes_repo_change_seq (repo_url, change_seq),
    INDEX idx_authorship_notes_repo_status (repo_url, status),
    INDEX idx_authorship_notes_superseded_rewrite (repo_url, superseded_rewrite_id),
    INDEX idx_authorship_notes_repo_commit_date (repo_url, commit_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='作者注释表';

CREATE TABLE IF NOT EXISTS authorship_notes_seq (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '全局 authorship_notes change_seq',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Authorship Notes 变更序列表';

CREATE TABLE IF NOT EXISTS authorship_note_rewrites (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    rewrite_id VARCHAR(200) NOT NULL COMMENT '重写操作 ID',
    repo_url VARCHAR(400) NOT NULL COMMENT '仓库 URL',
    operation VARCHAR(50) NOT NULL COMMENT '重写操作类型',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    original_head VARCHAR(40) COMMENT '重写前 HEAD',
    new_head VARCHAR(40) COMMENT '重写后 HEAD',
    request_hash VARCHAR(71) NOT NULL COMMENT '请求内容哈希',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    UNIQUE KEY uk_authorship_note_rewrites_rewrite_id (rewrite_id),
    INDEX idx_authorship_note_rewrites_repo (repo_url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='作者注释重写操作记录表';

CREATE TABLE IF NOT EXISTS authorship_note_rewrite_mappings (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    rewrite_id VARCHAR(200) NOT NULL COMMENT '重写操作 ID',
    repo_url VARCHAR(400) NOT NULL COMMENT '仓库 URL',
    source_commit VARCHAR(40) NOT NULL COMMENT '源提交 SHA',
    target_commit VARCHAR(40) NOT NULL COMMENT '目标提交 SHA',
    source_note_blob_oid VARCHAR(40) COMMENT '源 Note Blob OID',
    target_note_blob_oid VARCHAR(40) COMMENT '目标 Note Blob OID',
    target_content_hash VARCHAR(71) NOT NULL COMMENT '目标注释内容哈希',
    disposition VARCHAR(50) NOT NULL COMMENT '映射处理结果',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    UNIQUE KEY uk_authorship_note_rewrite_mapping (repo_url, source_commit, target_commit, rewrite_id),
    INDEX idx_authorship_note_rewrite_source (repo_url, source_commit),
    INDEX idx_authorship_note_rewrite_target (repo_url, target_commit)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='作者注释重写提交映射表';

-- SSH Key 表
CREATE TABLE IF NOT EXISTS stats_ssh_keys (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    key_name VARCHAR(100) NOT NULL COMMENT 'Key 名称',
    public_key TEXT COMMENT '公钥内容',
    private_key_encrypted TEXT NOT NULL COMMENT '加密后的私钥内容',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    INDEX idx_ssh_key_name (key_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SSH Key 表';

-- 仓库级归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_repo (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    stat_date BIGINT NOT NULL COMMENT '统计日期（年月日 yyyyMMdd）',
    commit_sha VARCHAR(40) NOT NULL COMMENT '当前统计提交 SHA',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    total_lines INT NOT NULL COMMENT '总行数',
    ai_lines INT NOT NULL COMMENT 'AI 代码行数',
    non_ai_lines INT NOT NULL COMMENT '非 AI 代码行数',
    total_files INT NOT NULL COMMENT '文件总数',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_blame_repo_date_branch (repo_id, stat_date, branch),
    INDEX idx_blame_repo_date (repo_id, stat_date),
    INDEX idx_blame_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓库级归因统计表';

-- 仓库贡献者归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_repo_contributor (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_id VARCHAR(20) NOT NULL COMMENT '仓库 ID',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    stat_date BIGINT NOT NULL COMMENT '统计日期（年月日 yyyyMMdd）',
    contributor_name VARCHAR(100) NOT NULL COMMENT '贡献者名称',
    contributor_email VARCHAR(100) NOT NULL DEFAULT '' COMMENT '贡献者邮箱',
    ai_lines INT NOT NULL DEFAULT 0 COMMENT 'AI 代码行数',
    non_ai_lines INT NOT NULL DEFAULT 0 COMMENT '非 AI 代码行数',
    total_lines INT NOT NULL DEFAULT 0 COMMENT '总行数',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_blame_rc_branch_contributor_identity (repo_id, stat_date, branch, contributor_name, contributor_email),
    INDEX idx_blame_rc_repo (repo_id, stat_date),
    INDEX idx_blame_rc_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓库贡献者归因统计表';

-- APScheduler JobStore 表
CREATE TABLE IF NOT EXISTS apscheduler_jobs (
    id VARCHAR(191) NOT NULL PRIMARY KEY COMMENT '任务 ID',
    next_run_time DOUBLE COMMENT '下次运行时间',
    job_state LONGBLOB NOT NULL COMMENT '序列化任务状态',
    INDEX idx_apscheduler_jobs_next_run_time (next_run_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='APScheduler JobStore 表';


-- 任务执行表
CREATE TABLE IF NOT EXISTS task_running (
    job_id VARCHAR(100) PRIMARY KEY  COMMENT '调度任务 ID',
    started_at BIGINT COMMENT '开始执行时间（毫秒）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务执行表';


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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务执行记录表';

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
    event_kind VARCHAR(64) COMMENT '事件类型标识',
    payload_version_hint VARCHAR(32) COMMENT 'payload 版本提示',
    normalized_payload LONGTEXT COMMENT '标准化后的 payload JSON',
    merge_type VARCHAR(64) COMMENT '合并类型: squash, normal, merge-commit 等',
    skipped_reason VARCHAR(255) COMMENT '跳过处理的原因',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '任务状态',
    attempts INT NOT NULL DEFAULT 0 COMMENT '尝试次数',
    last_error TEXT COMMENT '最后错误信息',
    result_summary TEXT COMMENT '处理结果摘要 JSON',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_codeup_merge_authorship_task (repo_url(400), merge_request_id, merge_commit_sha),
    INDEX idx_codeup_merge_authorship_status_attempts (status, attempts),
    INDEX idx_codeup_merge_authorship_repo_url (repo_url(400)),
    INDEX idx_codeup_merge_authorship_commit (merge_commit_sha),
    INDEX idx_codeup_merge_authorship_event_kind (event_kind),
    INDEX idx_codeup_merge_authorship_merge_type (merge_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Codeup 合并 authorship 重算任务表';

-- 系统管理表
CREATE TABLE IF NOT EXISTS sys_dept (
    id VARCHAR(20) PRIMARY KEY ,
    parent_id VARCHAR(20) NOT NULL DEFAULT 0,
    name VARCHAR(100) NOT NULL,
    sort INT NOT NULL DEFAULT 0,
    status INT NOT NULL DEFAULT 1,
    created_at BIGINT NOT NULL
)  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='菜单表';

CREATE TABLE IF NOT EXISTS sys_role (
    id VARCHAR(20) PRIMARY KEY ,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(100) NOT NULL UNIQUE,
    status INT NOT NULL DEFAULT 1,
    remark VARCHAR(500),
    created_at BIGINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

CREATE TABLE IF NOT EXISTS sys_user_role (
    id VARCHAR(20) PRIMARY KEY ,
    user_id VARCHAR(20) NOT NULL,
    role_id VARCHAR(20) NOT NULL,
    INDEX idx_user_role_user (user_id),
    INDEX idx_user_role_role (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户角色表';

CREATE TABLE IF NOT EXISTS sys_role_menu (
    id VARCHAR(20) PRIMARY KEY ,
    role_id VARCHAR(20) NOT NULL,
    menu_id VARCHAR(20) NOT NULL,
    INDEX idx_role_menu_role (role_id),
    INDEX idx_role_menu_menu (menu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色菜单表';

CREATE TABLE IF NOT EXISTS cx_command_usage_events (
   id BIGINT AUTO_INCREMENT PRIMARY KEY,
   event_id VARCHAR(80) NOT NULL UNIQUE,
   schema_version VARCHAR(16) NOT NULL,
   event_type VARCHAR(64) NOT NULL,
   event_time TIMESTAMP(3) NOT NULL,
   event_day INT NOT NULL,
   command_name VARCHAR(64) NOT NULL,
   spec_id VARCHAR(128) NOT NULL,
   spec_id_source VARCHAR(32),
   project_id VARCHAR(128),
   git_user_name VARCHAR(128),
   git_user_email VARCHAR(256),
   session_id VARCHAR(128),
   plugin_version VARCHAR(32),
   source VARCHAR(64),
   warning VARCHAR(128),
   token_name VARCHAR(128),
   raw_event JSON,
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_usage_spec_command ON cx_command_usage_events(spec_id, command_name);
CREATE INDEX idx_usage_project_time ON cx_command_usage_events(project_id, event_time);
CREATE INDEX idx_usage_user_time ON cx_command_usage_events(git_user_email, event_time);
CREATE INDEX idx_usage_event_time ON cx_command_usage_events(event_time);
CREATE INDEX idx_usage_event_day ON cx_command_usage_events(event_day);

CREATE TABLE IF NOT EXISTS cx_codereview_bypasses (
  id VARCHAR(20) PRIMARY KEY ,
  event_id VARCHAR(80) NOT NULL UNIQUE,
  schema_version VARCHAR(16) NOT NULL,
  event_type VARCHAR(64) NOT NULL DEFAULT 'cx_codereview_issue_bypass',
  event_time DATETIME(3) NOT NULL,
  spec_id VARCHAR(128) NULL,
  spec_id_source VARCHAR(32) NULL,
  project_id VARCHAR(128) NULL,
  git_user_name VARCHAR(128) NULL,
  git_user_email VARCHAR(256) NULL,
  session_id VARCHAR(128) NULL,
  plugin_version VARCHAR(32) NULL,
  source VARCHAR(64) NULL,
  push_id          VARCHAR(80) NULL,
  commit_sha       VARCHAR(64) NULL,
  issue_id         VARCHAR(128) NULL,
  issue_title      VARCHAR(512) NULL,
  issue_description TEXT NULL,
  severity         VARCHAR(16) NULL,
  file_path        TEXT NULL,
  line_range       VARCHAR(64) NULL,
  code_snippet     TEXT NULL,
  impact           TEXT NULL,
  suggestion       TEXT NULL,
  rule_ref         VARCHAR(256) NULL,
  response         VARCHAR(16) NULL,
  reason           VARCHAR(512) NULL,
  original_marker  JSON NULL,
  bypassed_marker  JSON NULL,
  token_name       VARCHAR(128) NULL,
  raw_event        JSON NULL,
  created_at       DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  CONSTRAINT chk_cr_bypass_event_type CHECK (event_type = 'cx_codereview_issue_bypass')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_cr_bypass_push_id
  ON cx_codereview_bypasses(push_id);

CREATE INDEX idx_cr_bypass_commit_tm
  ON cx_codereview_bypasses(commit_sha, event_time);

CREATE INDEX idx_cr_bypass_severity
  ON cx_codereview_bypasses(severity);

CREATE INDEX idx_cr_bypass_user_tm
  ON cx_codereview_bypasses(git_user_email, event_time);

CREATE INDEX idx_cr_bypass_event_tm
  ON cx_codereview_bypasses(event_time);

CREATE TABLE IF NOT EXISTS cx_codereview_summaries (
  id VARCHAR(20) PRIMARY KEY ,
  event_id VARCHAR(80) NOT NULL UNIQUE,
  schema_version VARCHAR(16) NOT NULL,
  event_type VARCHAR(64) NOT NULL DEFAULT 'cx_codereview_push_summary',
  event_time DATETIME(3) NOT NULL,
  spec_id VARCHAR(128) NULL,
  spec_id_source VARCHAR(32) NULL,
  project_id VARCHAR(128) NULL,
  git_user_name VARCHAR(128) NULL,
  git_user_email VARCHAR(256) NULL,
  session_id VARCHAR(128) NULL,
  plugin_version VARCHAR(32) NULL,
  source VARCHAR(64) NULL,
  push_id          VARCHAR(80) NULL,
  commit_sha       VARCHAR(64) NULL,
  commit_short     VARCHAR(16) NULL,
  push_branch      VARCHAR(256) NULL,
  push_remote      VARCHAR(64) NULL,
  report_path      TEXT NULL,
  review_status    VARCHAR(32) NULL,
  bypass_count     INT NULL,
  final_score      DECIMAL(5,2) NULL,
  grade            VARCHAR(8) NULL,
  issue_counts     JSON NULL,
  submission_time  DATETIME(3) NULL,
  token_name       VARCHAR(128) NULL,
  raw_event        JSON NULL,
  created_at       DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  CONSTRAINT chk_cr_summary_event_type CHECK (event_type = 'cx_codereview_push_summary')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_cr_summary_push_id
  ON cx_codereview_summaries(push_id);

CREATE INDEX idx_cr_summary_commit_tm
  ON cx_codereview_summaries(commit_sha, event_time);

CREATE INDEX idx_cr_summary_branch_tm
  ON cx_codereview_summaries(push_branch, event_time);

CREATE INDEX idx_cr_summary_user_tm
  ON cx_codereview_summaries(git_user_email, event_time);

CREATE INDEX idx_cr_summary_event_tm
  ON cx_codereview_summaries(event_time);
