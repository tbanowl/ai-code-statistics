-- Migration: Add commit_time column to authorship_notes table
-- Purpose: Enable incremental fetch by filtering notes based on commit timestamp

-- SQLite
ALTER TABLE authorship_notes ADD COLUMN commit_time BIGINT;
CREATE INDEX idx_authorship_notes_commit_time ON authorship_notes(repo_url, commit_time);

-- PostgreSQL / MySQL (same syntax)
-- ALTER TABLE authorship_notes ADD COLUMN commit_time BIGINT;
-- CREATE INDEX idx_authorship_notes_commit_time ON authorship_notes(repo_url, commit_time);
