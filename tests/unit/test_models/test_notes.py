"""
Tests for AuthorshipNotes model
"""

from core.database.models import AuthorshipNotes


def test_authorship_notes_model_columns():
    """Test AuthorshipNotes has all required columns"""
    # Get the table columns
    columns = {c.name for c in AuthorshipNotes.__table__.columns}

    expected_columns = {
        'id', 'repo_url', 'branch', 'commit_sha', 'original_commit_sha',
        'author_name', 'author_email', 'note_content', 'created_at', 'updated_at'
    }

    assert expected_columns.issubset(columns), f"Missing columns: {expected_columns - columns}"


def test_authorship_notes_unique_constraint():
    """Test AuthorshipNotes has unique constraint on repo_url + commit_sha"""
    # Check for UniqueConstraint in table_args
    table_args = AuthorshipNotes.__table_args__

    # Check for UniqueConstraint
    unique_constraints = [c for c in table_args if hasattr(c, 'columns')]

    assert len(unique_constraints) > 0, "UniqueConstraint not found"

    # Verify the constraint includes repo_url and commit_sha
    constraint = unique_constraints[0]
    constraint_columns = {col.name for col in constraint.columns}
    assert constraint_columns == {'repo_url', 'commit_sha'}


def test_authorship_notes_indexes():
    """Test AuthorshipNotes has required indexes"""
    indexes = {i.name for i in AuthorshipNotes.__table__.indexes}

    assert 'idx_authorship_notes_repo_url' in indexes, "Missing repo_url index"
    assert 'idx_authorship_notes_repo_commit' in indexes, "Missing repo_commit index"


def test_authorship_notes_defaults():
    """Test AuthorshipNotes creates with proper defaults"""
    note = AuthorshipNotes(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="abc123def4567890123456789012345678901234",
        author_name="Test User",
        author_email="test@example.com",
        note_content="test content"
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
