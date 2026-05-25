-- Git Blame 统计仓库/分支状态迁移
--
-- 适用场景：已有 MySQL 数据库已经存在 stats_repositories 和
-- stats_repositories_branch 表，需要补齐最后统计提交 SHA 和分支软删除字段。
-- 新库建表请使用 metrics_schema_mysql.sql。

ALTER TABLE stats_repositories
    ADD COLUMN last_blame_commit_sha VARCHAR(40) NULL COMMENT '最近一次 Git Blame 统计成功的提交 SHA' AFTER ssh_key_id;

ALTER TABLE stats_repositories_branch
    ADD COLUMN is_deleted INT NOT NULL DEFAULT 0 COMMENT '是否已删除（0/1）' AFTER branch_name,
    ADD COLUMN deleted_at BIGINT NULL COMMENT '删除时间戳（毫秒）' AFTER is_deleted;
