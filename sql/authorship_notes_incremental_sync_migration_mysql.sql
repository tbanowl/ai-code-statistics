-- Authorship Notes 强增量同步存量表迁移
--
-- 适用场景：已有 MySQL 数据库已经存在 authorship_notes 表，需要补齐
-- content_hash、change_seq、authorship_notes_seq 与按 repo/change_seq 分页索引。
-- 新库建表请使用 metrics_schema_mysql.sql。

CREATE TABLE IF NOT EXISTS authorship_notes_seq (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '全局 authorship_notes change_seq',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Authorship Notes 变更序列表';

ALTER TABLE authorship_notes
    ADD COLUMN content_hash VARCHAR(71) NULL COMMENT 'note_content 的 SHA-256 摘要' AFTER note_content,
    ADD COLUMN change_seq BIGINT NULL COMMENT '服务端单调递增变更序号' AFTER content_hash;

SET @authorship_notes_row_number := 0;

UPDATE authorship_notes
JOIN (
    SELECT
        id,
        (@authorship_notes_row_number := @authorship_notes_row_number + 1) AS new_change_seq
    FROM authorship_notes
    ORDER BY updated_at, id
) AS ordered_notes ON ordered_notes.id = authorship_notes.id
SET
    authorship_notes.content_hash = CONCAT('sha256:', SHA2(authorship_notes.note_content, 256)),
    authorship_notes.change_seq = ordered_notes.new_change_seq
WHERE authorship_notes.content_hash IS NULL
   OR authorship_notes.change_seq IS NULL;

SET @max_authorship_notes_change_seq := COALESCE(
    (SELECT MAX(change_seq) FROM authorship_notes),
    0
);

SET @authorship_notes_seq_next := @max_authorship_notes_change_seq + 1;
SET @authorship_notes_seq_sql := CONCAT(
    'ALTER TABLE authorship_notes_seq AUTO_INCREMENT = ',
    @authorship_notes_seq_next
);
PREPARE authorship_notes_seq_stmt FROM @authorship_notes_seq_sql;
EXECUTE authorship_notes_seq_stmt;
DEALLOCATE PREPARE authorship_notes_seq_stmt;

ALTER TABLE authorship_notes
    MODIFY COLUMN content_hash VARCHAR(71) NOT NULL COMMENT 'note_content 的 SHA-256 摘要',
    MODIFY COLUMN change_seq BIGINT NOT NULL COMMENT '服务端单调递增变更序号';

ALTER TABLE authorship_notes
    ADD UNIQUE KEY uk_authorship_notes_repo_commit (repo_url, commit_sha),
    ADD INDEX idx_authorship_notes_repo_change_seq (repo_url, change_seq);
