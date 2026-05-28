-- stats_repositories 仓库路径层级字段迁移
--
-- 适用场景：已有 MySQL 数据库已经存在 stats_repositories 表，
-- 需要补齐按 repo_path 拆分得到的层级名称字段。
-- 新库建表请使用 metrics_schema_mysql.sql。

ALTER TABLE stats_repositories
    ADD COLUMN name_level1 VARCHAR(50) NULL COMMENT '仓库路径一级名称' AFTER repo_name,
    ADD COLUMN name_level2 VARCHAR(50) NULL COMMENT '仓库路径二级名称' AFTER name_level1,
    ADD COLUMN name_level3 VARCHAR(50) NULL COMMENT '仓库路径三级名称' AFTER name_level2,
    ADD COLUMN name_level4 VARCHAR(50) NULL COMMENT '仓库路径四级名称' AFTER name_level3,
    ADD COLUMN name_level5 VARCHAR(50) NULL COMMENT '仓库路径五级名称' AFTER name_level4,
    ADD COLUMN repo_short_name VARCHAR(50) NULL COMMENT '仓库短名称' AFTER name_level5;

UPDATE stats_repositories AS repo
JOIN (
    SELECT
        id,
        path_no_host,
        CASE
            WHEN path_no_host IS NULL OR path_no_host = '' THEN 0
            ELSE LENGTH(path_no_host) - LENGTH(REPLACE(path_no_host, '/', '')) + 1
        END AS segment_count
    FROM (
        SELECT
            id,
            CASE
                WHEN repo_path IS NULL OR TRIM(repo_path) = '' THEN NULL
                WHEN LOCATE('/', TRIM(repo_path)) > 0
                    AND (
                        LOCATE('.', SUBSTRING_INDEX(TRIM(repo_path), '/', 1)) > 0
                        OR LOCATE(':', SUBSTRING_INDEX(TRIM(repo_path), '/', 1)) > 0
                    )
                    THEN SUBSTRING(TRIM(repo_path), LOCATE('/', TRIM(repo_path)) + 1)
                ELSE TRIM(repo_path)
            END AS path_no_host
        FROM stats_repositories
    ) AS normalized
) AS parsed ON parsed.id = repo.id
SET
    name_level1 = CASE
        WHEN parsed.segment_count >= 5 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(parsed.path_no_host, '/', 5), '/', -1)
        WHEN parsed.segment_count >= 2 THEN SUBSTRING_INDEX(parsed.path_no_host, '/', 1)
        ELSE NULL
    END,
    name_level2 = CASE
        WHEN parsed.segment_count >= 5 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(parsed.path_no_host, '/', 4), '/', -1)
        WHEN parsed.segment_count >= 3 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(parsed.path_no_host, '/', 2), '/', -1)
        ELSE NULL
    END,
    name_level3 = CASE
        WHEN parsed.segment_count >= 5 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(parsed.path_no_host, '/', 3), '/', -1)
        WHEN parsed.segment_count >= 4 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(parsed.path_no_host, '/', 3), '/', -1)
        ELSE NULL
    END,
    name_level4 = CASE
        WHEN parsed.segment_count >= 5 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(parsed.path_no_host, '/', 2), '/', -1)
        ELSE NULL
    END,
    name_level5 = CASE
        WHEN parsed.segment_count >= 5 THEN SUBSTRING_INDEX(parsed.path_no_host, '/', 1)
        ELSE NULL
    END,
    repo_short_name = CASE
        WHEN parsed.segment_count > 5 THEN SUBSTRING(parsed.path_no_host, LENGTH(SUBSTRING_INDEX(parsed.path_no_host, '/', 5)) + 2)
        WHEN parsed.segment_count = 5 THEN NULL
        WHEN parsed.segment_count >= 1 THEN SUBSTRING_INDEX(parsed.path_no_host, '/', -1)
        ELSE NULL
    END;
