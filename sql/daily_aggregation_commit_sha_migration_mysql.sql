-- Daily aggregation commit SHA migration
--
-- 适用场景：已有 MySQL 数据库已经存在 stats_repositories 表，
-- 需要补齐每日聚合任务专用的最后统计提交 SHA。
-- 新库建表请使用 metrics_schema_mysql.sql。

ALTER TABLE stats_repositories
    ADD COLUMN last_daily_aggregation_commit_sha VARCHAR(40) NULL COMMENT '最近一次每日聚合成功统计到的提交 SHA' AFTER last_blame_commit_sha;
