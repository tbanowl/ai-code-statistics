"""
Tests for NotesRestService
"""

import pytest
import tempfile
import os
from core.services.notes_service import NotesRestService


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield f"sqlite:///{path}"
    # Windows 需要先关闭数据库连接才能删除文件
    try:
        os.unlink(path)
    except (PermissionError, OSError):
        # 忽略删除错误（Windows 临时文件会在系统清理时删除）
        pass


@pytest.fixture
def service(temp_db):
    """Create service instance with temp database"""
    return NotesRestService()


def test_create_note(service):
    """Test creating a new note"""
    result = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="abc123def4567890123456789012345678901234",
        original_commit_sha=None,
        content="test content",
        author_name="Test User",
        author_email="test@example.com",
    )

    assert result.id is not None
    assert result.repo_url == "https://github.com/test/repo.git"
    assert result.branch == "main"
    assert result.commit_sha == "abc123def4567890123456789012345678901234"
    assert result.note_content == "test content"
    assert result.author_name == "Test User"
    assert result.author_email == "test@example.com"


def test_update_note(service):
    """Test updating an existing note"""
    # Create initial note
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="abc123def4567890123456789012345678901234",
        original_commit_sha=None,
        content="original content",
        author_name="Test User",
        author_email="test@example.com",
    )

    # Update the note
    result = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="abc123def4567890123456789012345678901234",
        original_commit_sha="original123",
        content="updated content",
        author_name="Updated User",
        author_email="updated@example.com",
    )

    assert result.note_content == "updated content"
    assert result.note_blob_oid == "original123"
    assert result.author_name == "Updated User"


def test_get_note(service):
    """Test getting a note"""
    # Create a note first
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="abc123def4567890123456789012345678901234",
        original_commit_sha=None,
        content="test content",
        author_name="Test User",
        author_email="test@example.com",
    )

    # Get the note
    result = service.get_note(
        repo_url="https://github.com/test/repo.git",
        commit_sha="abc123def4567890123456789012345678901234",
    )

    assert result is not None
    assert result.note_content == "test content"


def test_get_note_not_found(service):
    """Test getting a non-existent note"""
    result = service.get_note(
        repo_url="https://github.com/test/repo.git", commit_sha="nonexistent"
    )

    assert result is None


def test_batch_get_notes(service):
    """Test batch getting notes"""
    # Create notes
    for sha in ["sha1", "sha2", "sha3"]:
        service.create_or_update_note(
            repo_url="https://github.com/test/repo.git",
            branch="main",
            commit_sha=sha,
            original_commit_sha=None,
            content=f"content {sha}",
            author_name="Test",
            author_email="test@test.com",
        )

    # Batch get
    result = service.batch_get_notes(
        repo_url="https://github.com/test/repo.git",
        commit_shas=["sha1", "sha2", "nonexistent"],
    )

    assert len(result["notes"]) == 2
    assert "nonexistent" in result["missing"]
    assert result["notes"][0]["commit_sha"] == "sha1"


def test_batch_push_notes(service):
    """Test batch pushing notes"""
    result = service.batch_push_notes(
        repo_url="https://github.com/test/repo.git",
        notes_data=[
            {
                "branch": "main",
                "commit_sha": "sha1",
                "original_commit_sha": None,
                "author_name": "User1",
                "author_email": "user1@test.com",
                "content": "content1",
            },
            {
                "branch": "main",
                "commit_sha": "sha2",
                "original_commit_sha": None,
                "author_name": "User2",
                "author_email": "user2@test.com",
                "content": "content2",
            },
        ],
    )

    assert result["created"] == 2
    assert result["updated"] == 0


def test_batch_push_with_updates(service):
    """Test batch pushing with existing notes"""
    # Create one note first
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha1",
        original_commit_sha=None,
        content="old content",
        author_name="User1",
        author_email="user1@test.com",
    )

    # Batch push including the existing one and a new one
    result = service.batch_push_notes(
        repo_url="https://github.com/test/repo.git",
        notes_data=[
            {
                "branch": "main",
                "commit_sha": "sha1",
                "original_commit_sha": None,
                "author_name": "User1 Updated",
                "author_email": "user1@test.com",
                "content": "new content",
            },
            {
                "branch": "main",
                "commit_sha": "sha2",
                "original_commit_sha": None,
                "author_name": "User2",
                "author_email": "user2@test.com",
                "content": "content2",
            },
        ],
    )

    assert result["created"] == 1
    assert result["updated"] == 1


def test_list_notes(service):
    """Test listing notes"""
    # Create notes
    for sha in ["sha1", "sha2", "sha3"]:
        service.create_or_update_note(
            repo_url="https://github.com/test/repo.git",
            branch="main",
            commit_sha=sha,
            original_commit_sha=None,
            content="content",
            author_name="Test",
            author_email="test@test.com",
        )

    result = service.list_notes(repo_url="https://github.com/test/repo.git")

    assert len(result) == 3
    assert set(result) == {"sha1", "sha2", "sha3"}


def test_search_notes(service):
    """Test searching notes"""
    # Create notes
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha1",
        original_commit_sha=None,
        content="cursor position",
        author_name="Test",
        author_email="test@test.com",
    )

    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha2",
        original_commit_sha=None,
        content="buffer size",
        author_name="Test",
        author_email="test@test.com",
    )

    result = service.search_notes(
        repo_url="https://github.com/test/repo.git", pattern="cursor"
    )

    assert "sha1" in result
    assert "sha2" not in result
