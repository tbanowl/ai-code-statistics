-- ============================================================================
-- Git Blame 统计功能数据库迁移脚本 (SQLite)
-- ============================================================================
-- 版本: 1.0
-- 日期: 2026-03-31
-- 说明: 为 StatsRepository 表添加 blame 统计相关字段
--       创建 SSH Keys 表和 4 个归因统计表
--       用于跟踪仓库中 AI 代码归因统计
-- ============================================================================

-- ============================================================================
-- 扩展 stats_repositories 表
-- ============================================================================

-- 添加 repo_stats_flag：是否启用 AI 代码归因统计
ALTER TABLE stats_repositories ADD COLUMN repo_stats_flag INTEGER DEFAULT 0;

-- 添加 ssh_key_id：关联的 SSH Key ID（为空时使用配置文件默认 Key）
ALTER TABLE stats_repositories ADD COLUMN ssh_key_id VARCHAR(20);

-- ============================================================================
-- SSH Keys 表
-- ============================================================================

-- ssh_keys (SSH Key 存储表)
CREATE TABLE IF NOT EXISTS ssh_keys (
    -- 主键，使用 XID (20字符字符串)
    id VARCHAR(20) PRIMARY KEY,
    -- Key 名称（唯一标识）
    key_name TEXT NOT NULL UNIQUE,
    -- 公钥内容
    public_key TEXT NOT NULL,
    -- 加密的私钥内容
    private_key_encrypted TEXT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL
);

-- 索引：按 key_name 查询
CREATE INDEX IF NOT EXISTS idx_ssh_key_name ON ssh_keys(key_name);

-- ============================================================================
-- 归因统计表 (stats_blame_ 前缀)
-- ============================================================================

-- stats_blame_repo (仓库级归因统计表)
CREATE TABLE IF NOT EXISTS stats_blame_repo (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 关联的仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 统计日期（当天 00:00:00 的毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 当前统计时的提交 SHA
    commit_sha VARCHAR(40) NOT NULL,
    -- 分支名称
    branch TEXT NOT NULL,
    -- 仓库总行数
    total_lines INTEGER NOT NULL,
    -- AI 代码行数
    ai_lines INTEGER NOT NULL,
    -- 非 AI 代码行数
    non_ai_lines INTEGER NOT NULL,
    -- AI 代码占比 (ai_lines/total_lines*100)
    ai_ratio DECIMAL(5, 2) NOT NULL,
    -- 文件数量
    total_files INTEGER NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 唯一约束：同一仓库同一日期只能有一条记录
    UNIQUE(repo_id, stat_date)
);

-- 索引：按仓库 ID 和日期查询
CREATE INDEX IF NOT EXISTS idx_blame_repo_date ON stats_blame_repo(repo_id, stat_date);
-- 索引：按日期查询
CREATE INDEX IF NOT EXISTS idx_blame_stat_date ON stats_blame_repo(stat_date);

-- stats_blame_file (文件级归因统计表)
CREATE TABLE IF NOT EXISTS stats_blame_file (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 关联的仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 统计日期（当天 00:00:00 的毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 文件路径
    file_path TEXT NOT NULL,
    -- 当前统计时的提交 SHA
    commit_sha VARCHAR(40) NOT NULL,
    -- 文件总行数
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
    -- 唯一约束：同一仓库同一日期同一文件只能有一条记录
    UNIQUE(repo_id, stat_date, file_path)
);

-- 索引：按仓库 ID 和日期查询
CREATE INDEX IF NOT EXISTS idx_blame_file_repo ON stats_blame_file(repo_id, stat_date);
-- 索引：按日期查询
CREATE INDEX IF NOT EXISTS idx_blame_file_date ON stats_blame_file(stat_date);

-- stats_blame_repo_contributor (仓库贡献者归因统计表)
CREATE TABLE IF NOT EXISTS stats_blame_repo_contributor (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 关联的仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 统计日期（当天 00:00:00 的毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 关联的贡献者 ID
    contributor_id VARCHAR(20) NOT NULL,
    -- 贡献者名称（冗余字段，用于查询优化）
    contributor_name TEXT NOT NULL,
    -- 贡献者邮箱
    contributor_email TEXT,
    -- 该贡献者的 AI 代码行数
    ai_lines INTEGER NOT NULL DEFAULT 0,
    -- 该贡献者的非 AI 代码行数
    non_ai_lines INTEGER NOT NULL DEFAULT 0,
    -- 该贡献者的总行数
    total_lines INTEGER NOT NULL DEFAULT 0,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 唯一约束：同一仓库同一日期同一贡献者只能有一条记录
    UNIQUE(repo_id, stat_date, contributor_id)
);

-- 索引：按仓库 ID 和日期查询
CREATE INDEX IF NOT EXISTS idx_blame_rc_repo ON stats_blame_repo_contributor(repo_id, stat_date);
-- 索引：按日期查询
CREATE INDEX IF NOT EXISTS idx_blame_rc_date ON stats_blame_repo_contributor(stat_date);

-- stats_blame_file_contributor (文件贡献者归因统计表)
CREATE TABLE IF NOT EXISTS stats_blame_file_contributor (
    -- 主键，使用 XID
    id VARCHAR(20) PRIMARY KEY,
    -- 关联的文件 ID（来自 stats_blame_file）
    file_id VARCHAR(20) NOT NULL,
    -- 统计日期（当天 00:00:00 的毫秒时间戳）
    stat_date BIGINT NOT NULL,
    -- 关联的仓库 ID（冗余字段，用于查询优化）
    repo_id VARCHAR(20) NOT NULL,
    -- 文件路径（冗余字段，用于查询优化）
    file_path TEXT NOT NULL,
    -- 关联的贡献者 ID
    contributor_id VARCHAR(20) NOT NULL,
    -- 贡献者名称（冗余字段，用于查询优化）
    contributor_name TEXT NOT NULL,
    -- 贡献者邮箱
    contributor_email TEXT,
    -- 该贡献者在该文件的 AI 代码行数
    ai_lines INTEGER NOT NULL DEFAULT 0,
    -- 该贡献者在该文件的非 AI 代码行数
    non_ai_lines INTEGER NOT NULL DEFAULT 0,
    -- 该贡献者在该文件的总行数
    total_lines INTEGER NOT NULL DEFAULT 0,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 唯一约束：同一文件同一日期同一贡献者只能有一条记录
    UNIQUE(file_id, stat_date, contributor_id)
);

-- 索引：按仓库、日期、文件路径查询
CREATE INDEX IF NOT EXISTS idx_blame_fc_file ON stats_blame_file_contributor(repo_id, stat_date, file_path);
-- 索引：按日期查询
CREATE INDEX IF NOT EXISTS idx_blame_fc_date ON stats_blame_file_contributor(stat_date);

-- ============================================================================
-- 完成
-- ============================================================================
