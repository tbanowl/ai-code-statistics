-- Git-AI 客户端发布文件迁移
--
-- 适用场景：已有 MySQL 数据库需要支持管理端上传 Git-AI Windows 发布文件，
-- 并将安装脚本、可执行文件与后端生成的 SHA256SUMS 保存到数据库。
-- 新库建表请使用 metrics_schema_mysql.sql。

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
    INDEX idx_git_ai_release_artifacts_release (release_id),
    CONSTRAINT fk_git_ai_release_artifacts_release
        FOREIGN KEY (release_id) REFERENCES git_ai_releases(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Git-AI 客户端发布文件表';
