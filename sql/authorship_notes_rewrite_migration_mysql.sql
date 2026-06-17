-- Authorship Notes 重写元数据迁移
--
-- 适用场景：已有 MySQL 数据库已经存在 authorship_notes 表，需要补齐
-- 重写状态字段、重写操作记录表与提交映射表。
-- 新库建表请使用 metrics_schema_mysql.sql。

ALTER TABLE authorship_notes
    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '注释状态' AFTER change_seq,
    ADD COLUMN superseded_by VARCHAR(40) NULL COMMENT '取代该注释的提交 SHA' AFTER status,
    ADD COLUMN superseded_at BIGINT NULL COMMENT '取代时间戳（毫秒）' AFTER superseded_by,
    ADD COLUMN superseded_rewrite_id VARCHAR(200) NULL COMMENT '取代该注释的重写操作 ID' AFTER superseded_at,
    ADD INDEX idx_authorship_notes_repo_status (repo_url, status),
    ADD INDEX idx_authorship_notes_superseded_rewrite (repo_url, superseded_rewrite_id);

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='作者注释重写操作记录表';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='作者注释重写提交映射表';
