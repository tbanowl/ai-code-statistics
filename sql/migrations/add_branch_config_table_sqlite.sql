-- sql/migrations/add_branch_config_table_sqlite.sql
CREATE TABLE IF NOT EXISTS stats_repo_branch_config (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    branch_pattern TEXT NOT NULL,
    pattern_type VARCHAR(20) NOT NULL DEFAULT 'exact',
    enabled INTEGER DEFAULT 1,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES stats_repositories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_repo_branch_config_repo ON stats_repo_branch_config(repo_id);
CREATE INDEX IF NOT EXISTS idx_repo_branch_config_enabled ON stats_repo_branch_config(repo_id, enabled);
