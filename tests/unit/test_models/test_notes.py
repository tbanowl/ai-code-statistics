"""
Tests for AuthorshipNotes model
"""

from core.database.models import (
    AuthorshipNoteRewrite,
    AuthorshipNoteRewriteMapping,
    AuthorshipNotes,
)


def test_authorship_notes_model_columns():
    """Test AuthorshipNotes has all required columns"""
    # Get the table columns
    columns = {c.name for c in AuthorshipNotes.__table__.columns}

    expected_columns = {
        "id",
        "repo_url",
        "branch",
        "commit_sha",
        "note_blob_oid",
        "author_name",
        "author_email",
        "note_content",
        "commit_time",
        "commit_date",
        "content_hash",
        "change_seq",
        "status",
        "superseded_by",
        "superseded_at",
        "superseded_rewrite_id",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(columns), (
        f"Missing columns: {expected_columns - columns}"
    )


def test_authorship_notes_unique_constraint():
    """Test AuthorshipNotes has unique constraint on repo_url + commit_sha"""
    # Check for UniqueConstraint in table_args
    table_args = AuthorshipNotes.__table_args__

    # Check for UniqueConstraint
    unique_constraints = [c for c in table_args if hasattr(c, "columns")]

    assert len(unique_constraints) > 0, "UniqueConstraint not found"

    # Verify the constraint includes repo_url and commit_sha
    constraint = unique_constraints[0]
    constraint_columns = {col.name for col in constraint.columns}
    assert constraint_columns == {"repo_url", "commit_sha"}


def test_authorship_notes_indexes():
    """Test AuthorshipNotes has required indexes"""
    indexes = {i.name for i in getattr(AuthorshipNotes.__table__, "indexes", set())}

    expected_indexes = {
        "idx_authorship_notes_repo_url",
        "idx_authorship_notes_repo_commit",
        "idx_authorship_notes_repo_change_seq",
        "idx_authorship_notes_repo_status",
        "idx_authorship_notes_superseded_rewrite",
    }

    assert expected_indexes.issubset(indexes), (
        f"Missing indexes: {expected_indexes - indexes}"
    )


def test_authorship_note_rewrite_model_columns():
    """Test AuthorshipNoteRewrite has all required columns"""
    columns = {c.name for c in AuthorshipNoteRewrite.__table__.columns}

    expected_columns = {
        "id",
        "rewrite_id",
        "repo_url",
        "operation",
        "branch",
        "original_head",
        "new_head",
        "request_hash",
        "created_at",
    }

    assert expected_columns.issubset(columns), (
        f"Missing columns: {expected_columns - columns}"
    )


def test_authorship_note_rewrite_mapping_model_columns():
    """Test AuthorshipNoteRewriteMapping has all required columns"""
    columns = {c.name for c in AuthorshipNoteRewriteMapping.__table__.columns}

    expected_columns = {
        "id",
        "rewrite_id",
        "repo_url",
        "source_commit",
        "target_commit",
        "source_note_blob_oid",
        "target_note_blob_oid",
        "target_content_hash",
        "disposition",
        "created_at",
    }

    assert expected_columns.issubset(columns), (
        f"Missing columns: {expected_columns - columns}"
    )


def test_authorship_notes_defaults():
    """Test AuthorshipNotes creates with proper defaults"""
    note = AuthorshipNotes(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="abc123def4567890123456789012345678901234",
        author_name="Test User",
        author_email="test@example.com",
        note_content="test content",
    )

    data = note.to_dict()
    assert data["repo_url"] == "https://github.com/test/repo.git"
    assert data["branch"] == "main"
    assert data["commit_sha"] == "abc123def4567890123456789012345678901234"
    assert data["author_name"] == "Test User"
    assert data["author_email"] == "test@example.com"
    assert data["note_content"] == "test content"
    # ID 可以是 None（在创建实例时），需要 save 后才会生成
    # created_at 和 updated_at 也是如此
    # 这些字段在数据库写入时通过 default 值生成
