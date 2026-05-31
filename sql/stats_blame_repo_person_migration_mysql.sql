ALTER TABLE stats_repositories
    ADD COLUMN last_stat_date BIGINT COMMENT '最后统计日期，格式 yyyyMMdd';

ALTER TABLE stats_blame_repo
    DROP COLUMN ai_ratio;

ALTER TABLE stats_blame_repo_contributor
    DROP INDEX uk_blame_rc_branch_contributor;

UPDATE stats_blame_repo_contributor
SET contributor_email = ''
WHERE contributor_email IS NULL;

ALTER TABLE stats_blame_repo_contributor
    MODIFY contributor_email VARCHAR(100) NOT NULL DEFAULT '' COMMENT '贡献者邮箱';

ALTER TABLE stats_blame_repo_contributor
    DROP COLUMN contributor_id;

ALTER TABLE stats_blame_repo_contributor
    ADD UNIQUE KEY uk_blame_rc_branch_contributor_identity (
        repo_id,
        stat_date,
        branch,
        contributor_name,
        contributor_email
    );
