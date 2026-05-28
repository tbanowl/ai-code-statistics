-- cx_command_usage_events event_day 字段迁移
--
-- 适用场景：已有 MySQL 数据库已经存在 cx_command_usage_events 表，
-- 需要补齐 event_time 对应的 yyyyMMdd 整数字段。
-- 新库建表请使用 metrics_schema_mysql.sql。

ALTER TABLE cx_command_usage_events
    ADD COLUMN event_day INT NULL AFTER event_time;

UPDATE cx_command_usage_events
SET event_day = CAST(DATE_FORMAT(event_time, '%Y%m%d') AS UNSIGNED)
WHERE event_day IS NULL;

ALTER TABLE cx_command_usage_events
    MODIFY COLUMN event_day INT NOT NULL;

CREATE INDEX idx_usage_event_day ON cx_command_usage_events(event_day);
