-- Daily aggregation ID cursor and commit_date migration
--
-- 适用场景：已有 MySQL 数据库已经存在 committed、authorship_notes、
-- stats_repositories 和 stats_commit_daily 表，需要补齐每日聚合 ID 游标、
-- UTC commit_date 与新的每日统计字段。
-- 新库建表请使用 metrics_schema_mysql.sql。
--
-- UTC 说明：commit_date 使用
-- DATE_ADD('1970-01-01 00:00:00', INTERVAL <seconds> SECOND)
-- 计算 UTC 时间，不依赖 MySQL session/server 时区，也不需要时区表。
-- 本迁移暂不删除 stats_repositories.last_daily_aggregation_commit_sha。

ALTER TABLE metrics_events_committed
    ADD COLUMN commit_date BIGINT NULL COMMENT '提交日期 yyyyMMdd' AFTER timestamp,
    ADD COLUMN mixed_additions_total INT NOT NULL DEFAULT 0 COMMENT '混合生成代码行数首值' AFTER time_waiting_for_ai,
    ADD COLUMN ai_additions_total INT NOT NULL DEFAULT 0 COMMENT 'AI 生成代码行数首值' AFTER mixed_additions_total,
    ADD COLUMN ai_accepted_total INT NOT NULL DEFAULT 0 COMMENT '被接受 AI 代码行数首值' AFTER ai_additions_total,
    ADD COLUMN total_ai_additions_total INT NOT NULL DEFAULT 0 COMMENT '总 AI 新增代码行数首值' AFTER ai_accepted_total,
    ADD COLUMN total_ai_deletions_total INT NOT NULL DEFAULT 0 COMMENT '总 AI 删除代码行数首值' AFTER total_ai_additions_total,
    ADD COLUMN time_waiting_for_ai_total BIGINT NOT NULL DEFAULT 0 COMMENT '等待 AI 响应时长首值' AFTER total_ai_deletions_total;

UPDATE metrics_events_committed
SET timestamp = FLOOR(timestamp / 1000)
WHERE timestamp > 9999999999;

UPDATE metrics_events_committed
SET commit_date = CAST(
    DATE_FORMAT(
        DATE_ADD('1970-01-01 00:00:00', INTERVAL timestamp SECOND),
        '%Y%m%d'
    ) AS UNSIGNED
)
WHERE timestamp > 0;

UPDATE metrics_events_committed
SET
    mixed_additions_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(mixed_additions, '$[0]')) AS UNSIGNED), 0),
    ai_additions_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(ai_additions, '$[0]')) AS UNSIGNED), 0),
    ai_accepted_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(ai_accepted, '$[0]')) AS UNSIGNED), 0),
    total_ai_additions_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(total_ai_additions, '$[0]')) AS UNSIGNED), 0),
    total_ai_deletions_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(total_ai_deletions, '$[0]')) AS UNSIGNED), 0),
    time_waiting_for_ai_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(time_waiting_for_ai, '$[0]')) AS UNSIGNED), 0);

ALTER TABLE metrics_events_committed
    ADD INDEX idx_committed_repo_id (repo_url, id),
    ADD INDEX idx_committed_repo_commit_date (repo_url, commit_date);

ALTER TABLE authorship_notes
    ADD COLUMN commit_date BIGINT NULL COMMENT '提交日期 yyyyMMdd' AFTER commit_time;

UPDATE authorship_notes
SET commit_date = CAST(
    DATE_FORMAT(
        DATE_ADD('1970-01-01 00:00:00', INTERVAL commit_time SECOND),
        '%Y%m%d'
    ) AS UNSIGNED
)
WHERE commit_time > 0;

ALTER TABLE authorship_notes
    ADD INDEX idx_authorship_notes_repo_commit_date (repo_url, commit_date);

ALTER TABLE stats_repositories
    ADD COLUMN last_daily_aggregation_id VARCHAR(20) NULL COMMENT '最近一次每日聚合成功统计到的 committed 事件 ID' AFTER last_blame_commit_sha;

ALTER TABLE stats_commit_daily
    ADD COLUMN human_additions INT DEFAULT 0 COMMENT '人类手动添加代码行数' AFTER contributor_email,
    ADD COLUMN unknown_additions INT DEFAULT 0 COMMENT '未知来源新增代码行数' AFTER human_additions,
    ADD COLUMN git_diff_deleted_lines INT DEFAULT 0 COMMENT 'Git diff 删除行数' AFTER unknown_additions,
    ADD COLUMN git_diff_added_lines INT DEFAULT 0 COMMENT 'Git diff 新增行数' AFTER git_diff_deleted_lines,
    ADD COLUMN mixed_additions INT DEFAULT 0 COMMENT '混合生成代码行数' AFTER git_diff_added_lines,
    ADD COLUMN ai_additions INT DEFAULT 0 COMMENT 'AI 生成代码行数' AFTER mixed_additions,
    ADD COLUMN ai_accepted INT DEFAULT 0 COMMENT '被接受 AI 代码行数' AFTER ai_additions,
    ADD COLUMN total_ai_additions INT DEFAULT 0 COMMENT '总 AI 新增代码行数' AFTER ai_accepted,
    ADD COLUMN total_ai_deletions INT DEFAULT 0 COMMENT '总 AI 删除代码行数' AFTER total_ai_additions;

UPDATE stats_commit_daily
SET
    human_additions = COALESCE(human_lines, 0),
    git_diff_added_lines = COALESCE(total_lines, 0),
    ai_additions = COALESCE(ai_lines, 0),
    ai_accepted = COALESCE(ai_accepted_lines, 0),
    total_ai_additions = COALESCE(ai_total_lines, 0);

ALTER TABLE stats_commit_daily
    DROP COLUMN ai_lines,
    DROP COLUMN ai_total_lines,
    DROP COLUMN ai_accepted_lines,
    DROP COLUMN human_lines,
    DROP COLUMN total_lines;
