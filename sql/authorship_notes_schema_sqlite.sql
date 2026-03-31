-- ============================================================================
-- Authorship Notes 数据库表结构
-- 版本: 1.0
-- 日期: 2026-03-30
-- 用于 REST Notes Store API
-- ============================================================================

CREATE TABLE IF NOT EXISTS authorship_notes (
    -- 主键，使用 XID (20字符字符串)
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库远程 URL
    repo_url TEXT NOT NULL,
    -- 分支名称
    branch TEXT NOT NULL,
    -- 当前提交 SHA（40 字符）
    commit_sha VARCHAR(40) NOT NULL,
    -- rebase/cherry-pick 之前的原始提交 SHA
    original_commit_sha VARCHAR(40),
    -- 提交者名称
    author_name TEXT NOT NULL,
    -- 提交者邮箱
    author_email TEXT NOT NULL,
    -- AuthorshipLog 原始内容
    note_content TEXT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 唯一约束：同一仓库同一提交只能有一条记录
    UNIQUE(repo_url, commit_sha)
);

-- 索引：按仓库 URL 查询
CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_url ON authorship_notes(repo_url);
-- 索引：按仓库 URL 和提交 SHA 联合查询
CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_commit ON authorship_notes(repo_url, commit_sha);
