-- sql/migrations/add_branch_config_table_postgresql.sql
CREATE TABLE IF NOT EXISTS stats_repo_branch_config (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    branch_pattern TEXT NOT NULL,
    pattern_type VARCHAR(20) NOT NULL DEFAULT 'exact',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES stats_repositories(id) ON DELETE CASCADE,
    UNIQUE(repo_id, branch_pattern),
    CHECK (pattern_type IN ('exact', 'wildcard', 'special'))
);

CREATE INDEX IF NOT EXISTS idx_repo_branch_config_repo ON stats_repo_branch_config(repo_id);
CREATE INDEX IF NOT EXISTS idx_repo_branch_config_enabled ON stats_repo_branch_config(repo_id, enabled);
