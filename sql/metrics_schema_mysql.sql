-- Metrics 原始事件表
CREATE TABLE IF NOT EXISTS metrics_events_raw (
    -- 主键，使用 XID (20字符字符串)
    id VARCHAR(20) PRIMARY KEY,
    -- 批次版本号
    version INT NOT NULL DEFAULT 1,
    -- 批次中的事件数量
    event_count INT NOT NULL,
    -- 原始 JSON 载荷数据
    payload_json TEXT NOT NULL,
    -- 提取标识：0-未提取、1-提取成功、2-提取中、3-提取失败
    extract INT NOT NULL DEFAULT 0,
    -- 提取失败原因
    extract_fail VARCHAR(100),
    -- 接收时间戳（毫秒）
    received_at BIGINT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    INDEX idx_metrics_raw_received_at (received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Metrics 原始事件表';

-- Committed 事件表
CREATE TABLE IF NOT EXISTS metrics_events_committed (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 事件唯一标识
    uid VARCHAR(100) NOT NULL,
    -- 关联的原始批次 ID
    raw_id VARCHAR(20),
    -- 事件类型 ID (1=Committed)
    event_id INT NOT NULL DEFAULT 1,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- 人类手动添加代码行数
    human_additions INT,
    -- Git diff 删除行数
    git_diff_deleted_lines INT,
    -- Git diff 新增行数
    git_diff_added_lines INT,
    -- 首次检查点时间戳
    first_checkpoint_ts BIGINT,
    -- 提交标题
    commit_subject VARCHAR(200),
    -- 提交正文
    commit_body VARCHAR(1000),
    -- 工具-模型配对 JSON
    tool_model_pairs JSON,
    -- 混合生成代码行数 JSON
    mixed_additions JSON,
    -- AI 生成代码行数 JSON
    ai_additions JSON,
    -- 被接受的 AI 代码行数 JSON
    ai_accepted JSON,
    -- 总 AI 新增代码行数 JSON
    total_ai_additions JSON,
    -- 总 AI 删除代码行数 JSON
    total_ai_deletions JSON,
    -- 等待 AI 响应时长 JSON
    time_waiting_for_ai JSON,
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(20),
    -- 仓库 URL
    repo_url VARCHAR(400),
    -- 提交作者
    author VARCHAR(100),
    -- 提交 SHA
    commit_sha VARCHAR(40),
    -- 基础提交 SHA
    base_commit_sha VARCHAR(40),
    -- 分支名称
    branch VARCHAR(50),
    -- 使用工具
    tool VARCHAR(1000),
    -- 使用模型
    model VARCHAR(50),
    -- 提示词 ID
    prompt_id VARCHAR(200),
    -- 外部提示词 ID
    external_prompt_id VARCHAR(200),
    -- 自定义属性 JSON
    custom_attributes JSON,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    INDEX idx_committed_timestamp (timestamp),
    INDEX idx_committed_repo_url (repo_url),
    INDEX idx_committed_author (author),
    INDEX idx_committed_commit_sha (commit_sha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Committed 事件表';

-- Checkpoint 事件表
CREATE TABLE IF NOT EXISTS metrics_events_checkpoint (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 事件唯一标识
    uid VARCHAR(100) NOT NULL,
    -- 关联的原始批次 ID
    raw_id VARCHAR(20),
    -- 事件类型 ID (4=Checkpoint)
    event_id INT NOT NULL DEFAULT 4,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- 检查点时间戳
    checkpoint_ts BIGINT,
    -- 检查点类型
    kind VARCHAR(100),
    -- 文件路径
    file_path VARCHAR(100),
    -- 新增行数
    lines_added INT,
    -- 删除行数
    lines_deleted INT,
    -- 新增源代码行数
    lines_added_sloc INT,
    -- 删除源代码行数
    lines_deleted_sloc INT,
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(20),
    -- 仓库 URL
    repo_url VARCHAR(400),
    -- 提交作者
    author VARCHAR(100),
    -- 提交 SHA
    commit_sha VARCHAR(40),
    -- 基础提交 SHA
    base_commit_sha VARCHAR(40),
    -- 分支名称
    branch VARCHAR(50),
    -- 使用工具
    tool VARCHAR(1000),
    -- 使用模型
    model VARCHAR(50),
    -- 提示词 ID
    prompt_id VARCHAR(200),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    INDEX idx_checkpoint_timestamp (timestamp),
    INDEX idx_checkpoint_file_path (file_path)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Checkpoint 事件表';

-- AgentUsage 事件表
CREATE TABLE IF NOT EXISTS metrics_events_agent_usage (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 事件唯一标识
    uid VARCHAR(100) NOT NULL,
    -- 关联的原始批次 ID
    raw_id VARCHAR(20),
    -- 事件类型 ID (2=AgentUsage)
    event_id INT NOT NULL DEFAULT 2,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(20),
    -- 仓库 URL
    repo_url VARCHAR(400),
    -- 提交作者
    author VARCHAR(100),
    -- 提交 SHA
    commit_sha VARCHAR(40),
    -- 基础提交 SHA
    base_commit_sha VARCHAR(40),
    -- 分支名称
    branch VARCHAR(50),
    -- 使用工具
    tool VARCHAR(1000),
    -- 使用模型
    model VARCHAR(50),
    -- 提示词 ID
    prompt_id VARCHAR(200),
    -- 外部提示词 ID
    external_prompt_id VARCHAR(200),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    INDEX idx_agent_usage_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AgentUsage 事件表';

-- InstallHooks 事件表
CREATE TABLE IF NOT EXISTS metrics_events_install_hooks (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 事件唯一标识
    uid VARCHAR(100) NOT NULL,
    -- 关联的原始批次 ID
    raw_id VARCHAR(20),
    -- 事件类型 ID (3=InstallHooks)
    event_id INT NOT NULL DEFAULT 3,
    -- 事件时间戳（毫秒）
    timestamp BIGINT NOT NULL,
    -- 工具 ID
    tool_id VARCHAR(100),
    -- 安装状态
    status VARCHAR(100),
    -- 安装消息
    message TEXT,
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(20),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='InstallHooks 事件表';

-- 事件解析错误记录表
CREATE TABLE IF NOT EXISTS metrics_event_errors (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 关联的原始批次 ID
    raw_id VARCHAR(20),
    -- 事件在批次中的索引
    event_index INT NOT NULL,
    -- 原始事件数据
    event_data_raw TEXT NOT NULL,
    -- 错误消息
    error_message TEXT NOT NULL,
    -- 载荷片段
    payload_snippet TEXT,
    -- 重试次数
    retry_count INT NOT NULL DEFAULT 0,
    -- 最后重试时间（毫秒）
    last_retry_at BIGINT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    INDEX idx_raw_event_index (raw_id, event_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件解析错误记录表';

-- CAS 对象表
CREATE TABLE IF NOT EXISTS cas_objects (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 内容哈希值
    hash VARCHAR(100) NOT NULL,
    -- 内容 JSON
    content_json JSON,
    -- 元数据 JSON
    metadata_json JSON,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    INDEX idx_cas_hash (hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='CAS 对象表';

-- 仓库表
CREATE TABLE IF NOT EXISTS stats_repositories (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库路径
    repo_path VARCHAR(200) NOT NULL,
    -- 仓库名称
    repo_name VARCHAR(100),
    -- 是否启用归因统计（0/1）
    repo_stats_flag INT DEFAULT 1,
    -- 关联的 SSH Key ID
    ssh_key_id VARCHAR(20),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    INDEX idx_stats_repositories_name (repo_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='仓库表';

-- 仓库分支表
CREATE TABLE IF NOT EXISTS stats_repo_branch_config (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    branch_pattern TEXT NOT NULL,
    pattern_type VARCHAR(20) NOT NULL DEFAULT 'exact' COMMENT "正则类型: exact, wildcard, special",
    enabled BOOLEAN DEFAULT TRUE,
    created_at BIGINT NULL,
    updated_at BIGINT NULL,
    INDEX idx_repo_branch_config_repo (repo_id),
    INDEX idx_repo_branch_config_enabled (repo_id, enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='仓库分支表';

-- 贡献者表
CREATE TABLE IF NOT EXISTS stats_contributors (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 贡献者唯一标识
    contributor_uid TEXT NOT NULL,
    -- 贡献者名称
    name VARCHAR(100) NOT NULL,
    -- 贡献者邮箱
    email VARCHAR(100),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    INDEX idx_stats_contributors_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='贡献者表';

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
    updated_at BIGINT NOT NULL,
    INDEX idx_stats_repo_contributors_repo (repo_id),
    INDEX idx_stats_repo_contributors_contributor (contributor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='仓库贡献者关联表';

-- 每日统计表
CREATE TABLE IF NOT EXISTS stats_daily_stats (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 统计日期（毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 仓库名称冗余字段
    repo_name VARCHAR(100),
    -- 贡献者 ID
    contributor_id VARCHAR(20) NOT NULL,
    -- 贡献者名称冗余字段
    contributor_name VARCHAR(100),
    -- AI 生成源代码行数
    ai_generated_lines INT DEFAULT 0,
    -- AI 生成总行数
    ai_generated_lines_total INT DEFAULT 0,
    -- 被接受的 AI 代码行数
    ai_accepted_lines INT DEFAULT 0,
    -- 人类代码行数
    human_lines INT DEFAULT 0,
    -- AI 占比
    ai_percentage DECIMAL(5, 2) DEFAULT 0.0,
    -- Git-AI 客户端版本号
    git_ai_version VARCHAR(50),
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    INDEX idx_stats_daily_stats_date (stat_date),
    INDEX idx_stats_daily_stats_repo (repo_id),
    INDEX idx_stats_daily_stats_contributor (contributor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日统计表';

-- 任务执行记录表
CREATE TABLE IF NOT EXISTS task_executions (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 调度任务 ID
    job_id VARCHAR(100) NOT NULL,
    -- 执行状态
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- 开始执行时间（毫秒）
    started_at BIGINT,
    -- 完成时间（毫秒）
    finished_at BIGINT,
    -- 执行耗时（毫秒）
    execution_time_ms INT,
    -- 错误信息
    error_message TEXT,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    INDEX idx_task_executions_job (job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务执行记录表';

-- GIT AI 数据收集表
CREATE TABLE IF NOT EXISTS telemetry_envelope (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 包络 JSON 数据
    envelope_data JSON NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='GIT AI 数据收集表';

-- 作者注释表
CREATE TABLE IF NOT EXISTS authorship_notes (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库 URL
    repo_url VARCHAR(200) NOT NULL,
    -- 分支名称
    branch VARCHAR(100) NOT NULL,
    -- 提交 SHA
    commit_sha VARCHAR(40) NOT NULL,
    -- Note Blob OID
    note_blob_oid VARCHAR(40),
    -- 作者名称
    author_name VARCHAR(100) NOT NULL,
    -- 作者邮箱
    author_email VARCHAR(100) NOT NULL,
    -- 注释内容
    note_content TEXT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 同一仓库同一提交唯一
    INDEX idx_authorship_notes_repo_url (repo_url),
    INDEX idx_authorship_notes_repo_commit (repo_url, commit_sha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='作者注释表';

-- SSH Key 表
CREATE TABLE IF NOT EXISTS stats_ssh_keys (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- Key 名称
    key_name VARCHAR(100) NOT NULL,
    -- 公钥内容
    public_key TEXT,
    -- 加密后的私钥内容
    private_key_encrypted TEXT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    INDEX idx_ssh_key_name (key_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='SSH Key 表';

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
    branch VARCHAR(100) NOT NULL,
    -- 总行数
    total_lines INT NOT NULL,
    -- AI 代码行数
    ai_lines INT NOT NULL,
    -- 非 AI 代码行数
    non_ai_lines INT NOT NULL,
    -- AI 代码占比
    ai_ratio DECIMAL(5, 2) NOT NULL,
    -- 文件总数
    total_files INT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 同一仓库同一日期唯一
    INDEX idx_blame_repo_date (repo_id, stat_date),
    INDEX idx_blame_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='仓库级归因统计表';

-- 文件级归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_file (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 分支名称
    branch VARCHAR(100) NOT NULL,
    -- 统计日期（毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 文件路径
    file_path VARCHAR(200) NOT NULL,
    -- 当前统计提交 SHA
    commit_sha VARCHAR(40) NOT NULL,
    -- 总行数
    total_lines INT NOT NULL,
    -- AI 代码行数
    ai_lines INT NOT NULL,
    -- 非 AI 代码行数
    non_ai_lines INT NOT NULL,
    -- AI 代码占比
    ai_ratio DECIMAL(5, 2) NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 同一仓库同一日期同一路径唯一
    INDEX idx_blame_file_repo (repo_id, stat_date),
    INDEX idx_blame_file_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文件级归因统计表';

-- 仓库贡献者归因统计表
CREATE TABLE IF NOT EXISTS stats_blame_repo_contributor (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 分支名称
    branch VARCHAR(100) NOT NULL,
    -- 统计日期（毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 贡献者 ID
    contributor_id VARCHAR(20) NOT NULL,
    -- 贡献者名称
    contributor_name VARCHAR(100) NOT NULL,
    -- 贡献者邮箱
    contributor_email VARCHAR(100),
    -- AI 代码行数
    ai_lines INT NOT NULL DEFAULT 0,
    -- 非 AI 代码行数
    non_ai_lines INT NOT NULL DEFAULT 0,
    -- 总行数
    total_lines INT NOT NULL DEFAULT 0,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 同一仓库同一日期同一贡献者唯一
    INDEX idx_blame_rc_repo (repo_id, stat_date),
    INDEX idx_blame_rc_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='仓库贡献者归因统计表';

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
    -- 分支名称
    branch VARCHAR(100) NOT NULL,
    -- 文件路径
    file_path VARCHAR(100) NOT NULL,
    -- 贡献者 ID
    contributor_id VARCHAR(20) NOT NULL,
    -- 贡献者名称
    contributor_name VARCHAR(100) NOT NULL,
    -- 贡献者邮箱
    contributor_email VARCHAR(100),
    -- AI 代码行数
    ai_lines INT NOT NULL DEFAULT 0,
    -- 非 AI 代码行数
    non_ai_lines INT NOT NULL DEFAULT 0,
    -- 总行数
    total_lines INT NOT NULL DEFAULT 0,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 同一文件同一日期同一贡献者唯一
    INDEX idx_blame_fc_file (repo_id, stat_date, file_path),
    INDEX idx_blame_fc_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文件贡献者归因统计表';

-- APScheduler JobStore 表
CREATE TABLE IF NOT EXISTS apscheduler_jobs (
    -- 任务 ID
    id VARCHAR(191) NOT NULL PRIMARY KEY,
    -- 下次运行时间
    next_run_time DOUBLE,
    -- 序列化任务状态
    job_state LONGBLOB NOT NULL,
    INDEX idx_apscheduler_jobs_next_run_time (next_run_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='APScheduler JobStore 表';

CREATE TABLE IF NOT EXISTS sys_dept (
    id INT PRIMARY KEY AUTO_INCREMENT,
    parent_id INT NOT NULL DEFAULT 0,
    name VARCHAR(100) NOT NULL,
    sort INT NOT NULL DEFAULT 0,
    status INT NOT NULL DEFAULT 1,
    created_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS sys_menu (
    id INT PRIMARY KEY AUTO_INCREMENT,
    parent_id INT NOT NULL DEFAULT 0,
    title VARCHAR(100) NOT NULL,
    path VARCHAR(200),
    component VARCHAR(200),
    icon VARCHAR(100),
    `rank` INT NOT NULL DEFAULT 0,
    menu_type INT NOT NULL DEFAULT 0,
    status INT NOT NULL DEFAULT 1,
    show_link INT NOT NULL DEFAULT 1,
    keep_alive INT NOT NULL DEFAULT 0,
    created_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS sys_role (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(100) NOT NULL UNIQUE,
    status INT NOT NULL DEFAULT 1,
    remark VARCHAR(500),
    created_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS sys_user (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(200) NOT NULL,
    nickname VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(200),
    dept_id INT,
    avatar VARCHAR(500),
    status INT NOT NULL DEFAULT 1,
    created_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS sys_user_role (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    INDEX idx_user_role_user (user_id),
    INDEX idx_user_role_role (role_id)
);

CREATE TABLE IF NOT EXISTS sys_role_menu (
    id INT PRIMARY KEY AUTO_INCREMENT,
    role_id INT NOT NULL,
    menu_id INT NOT NULL,
    INDEX idx_role_menu_role (role_id),
    INDEX idx_role_menu_menu (menu_id)
);
