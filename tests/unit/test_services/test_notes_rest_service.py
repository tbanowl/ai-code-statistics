"""
Tests for NotesRestService
"""

import pytest
import tempfile
import os
import hashlib
from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as database_base
from core.database.base import Base, session_scope
from core.database.models import AuthorshipNotes
from core.services.notes_service import NotesRestService


def expected_note_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def mark_note_superseded(service, commit_sha: str):
    with session_scope(service.database.engine) as session:
        note = (
            session.query(AuthorshipNotes)
            .filter(AuthorshipNotes.commit_sha == commit_sha)
            .one()
        )
        note.status = "superseded"
        note.superseded_by = f"{commit_sha}-target"
        note.superseded_rewrite_id = f"rewrite-{commit_sha}"
        note.superseded_at = 1710000000000


def test_initialization_reads_db_url_from_loader_config(temp_db):
    """Notes DB initialization must read database URL from loader config."""
    previous_config_data = loader.config_data
    previous_global_engine = database_base.global_engine
    sqlite_engine = create_engine(temp_db, echo=False)
    full_config = {
        "database": {"url": temp_db, "echo": False},
        "scheduler": {"enabled": True},
        "git_ai": {"api_key": "test-key"},
        "web": {"debug": True},
    }

    loader.config_data = full_config
    Base.metadata.create_all(sqlite_engine)

    try:
        service = NotesRestService()
        service.create_or_update_note(
            repo_url="https://github.com/test/repo.git",
            branch="main",
            commit_sha="config-db-url",
            original_commit_sha=None,
            content="from loader config",
            author_name="Test User",
            author_email="test@example.com",
        )
        assert loader.config_data is full_config
        assert loader.config_data["scheduler"] == {"enabled": True}
        assert loader.config_data["git_ai"] == {"api_key": "test-key"}
        service.close()
    finally:
        sqlite_engine.dispose()
        loader.config_data = previous_config_data
        database_base.global_engine = previous_global_engine


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
    previous_config_data = loader.config_data
    previous_global_engine = database_base.global_engine
    sqlite_engine = create_engine(temp_db, echo=False)

    loader.config_data = {"database": {"url": temp_db, "echo": False}}
    database_base.global_engine = sqlite_engine
    Base.metadata.create_all(sqlite_engine)

    try:
        yield NotesRestService()
    finally:
        sqlite_engine.dispose()
        loader.config_data = previous_config_data
        database_base.global_engine = previous_global_engine


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
    assert result.repo_url == "github.com/test/repo"
    assert result.branch == "main"
    assert result.commit_sha == "abc123def4567890123456789012345678901234"
    assert result.note_content == "test content"
    assert result.author_name == "Test User"
    assert result.author_email == "test@example.com"


def test_create_note_generates_content_hash_and_change_seq(service):
    note = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha-hash-1",
        original_commit_sha=None,
        content="stable content",
        author_name="Test User",
        author_email="test@example.com",
    )

    assert note.content_hash == expected_note_hash("stable content")
    assert note.change_seq > 0


def test_same_content_update_is_unchanged_and_keeps_change_seq(service):
    first = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha-idempotent",
        original_commit_sha=None,
        content="same content",
        author_name="Test User",
        author_email="test@example.com",
    )
    first_seq = first.change_seq

    second = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="develop",
        commit_sha="sha-idempotent",
        original_commit_sha="different-blob",
        content="same content",
        author_name="Other User",
        author_email="other@example.com",
    )

    assert second.change_seq == first_seq
    assert second.content_hash == expected_note_hash("same content")


def test_changed_content_advances_change_seq(service):
    first = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha-change",
        original_commit_sha=None,
        content="old content",
        author_name="Test User",
        author_email="test@example.com",
    )

    second = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha-change",
        original_commit_sha=None,
        content="new content",
        author_name="Test User",
        author_email="test@example.com",
    )

    assert second.change_seq > first.change_seq
    assert second.content_hash == expected_note_hash("new content")
    assert second.note_content == "new content"


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


def test_get_note_excludes_superseded_by_default(service):
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="source-sha",
        original_commit_sha=None,
        content="source note",
        author_name="Test User",
        author_email="test@example.com",
    )
    mark_note_superseded(service, "source-sha")

    assert (
        service.get_note(
            repo_url="https://github.com/test/repo.git",
            commit_sha="source-sha",
        )
        is None
    )

    note = service.get_note(
        repo_url="https://github.com/test/repo.git",
        commit_sha="source-sha",
        include_superseded=True,
    )

    assert note is not None
    assert note.status == "superseded"


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
    assert result["unchanged"] == 0


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
    assert result["unchanged"] == 0


def test_batch_push_reports_unchanged(service):
    service.batch_push_notes(
        repo_url="https://github.com/test/repo.git",
        notes_data=[
            {
                "branch": "main",
                "commit_sha": "sha-same",
                "original_commit_sha": None,
                "author_name": "User1",
                "author_email": "user1@test.com",
                "content": "same content",
            }
        ],
    )

    result = service.batch_push_notes(
        repo_url="https://github.com/test/repo.git",
        notes_data=[
            {
                "branch": "main",
                "commit_sha": "sha-same",
                "original_commit_sha": "different-blob",
                "author_name": "User1",
                "author_email": "user1@test.com",
                "content": "same content",
            }
        ],
    )

    assert result == {"created": 0, "updated": 0, "unchanged": 1}


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

    assert len(result["commit_shas"]) == 3
    assert set(result["commit_shas"]) == {"sha1", "sha2", "sha3"}
    assert len(result["items"]) == 3
    assert result["has_more"] is False


def test_list_notes_summary_paginates_by_change_seq(service):
    for idx, sha in enumerate(["sha1", "sha2", "sha3"], start=1):
        service.create_or_update_note(
            repo_url="https://github.com/test/repo.git",
            branch="main",
            commit_sha=sha,
            original_commit_sha=None,
            content=f"content {idx}",
            author_name="Test",
            author_email="test@test.com",
        )

    first_page = service.list_notes(
        repo_url="https://github.com/test/repo.git",
        since_change_seq=0,
        limit=2,
    )

    assert first_page["commit_shas"] == ["sha1", "sha2"]
    assert [item["commit_sha"] for item in first_page["items"]] == ["sha1", "sha2"]
    assert first_page["items"][0]["content_hash"] == expected_note_hash("content 1")
    assert first_page["has_more"] is True
    assert first_page["next_change_seq"] == first_page["items"][-1]["change_seq"]

    second_page = service.list_notes(
        repo_url="https://github.com/test/repo.git",
        since_change_seq=first_page["next_change_seq"],
        limit=2,
    )

    assert second_page["commit_shas"] == ["sha3"]
    assert second_page["has_more"] is False


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


def test_batch_list_and_search_exclude_superseded_by_default(service):
    for sha in ["active-sha", "superseded-sha"]:
        service.create_or_update_note(
            repo_url="https://github.com/test/repo.git",
            branch="main",
            commit_sha=sha,
            original_commit_sha=None,
            content=f"shared search content {sha}",
            author_name="Test",
            author_email="test@test.com",
        )
    mark_note_superseded(service, "superseded-sha")

    batch = service.batch_get_notes(
        repo_url="https://github.com/test/repo.git",
        commit_shas=["active-sha", "superseded-sha"],
    )
    assert [note["commit_sha"] for note in batch["notes"]] == ["active-sha"]
    assert batch["missing"] == ["superseded-sha"]

    audit_batch = service.batch_get_notes(
        repo_url="https://github.com/test/repo.git",
        commit_shas=["active-sha", "superseded-sha"],
        include_superseded=True,
    )
    assert {note["commit_sha"] for note in audit_batch["notes"]} == {
        "active-sha",
        "superseded-sha",
    }
    audit_batch_superseded = next(
        note for note in audit_batch["notes"] if note["commit_sha"] == "superseded-sha"
    )
    assert audit_batch_superseded["superseded_at"] == 1710000000000

    listed = service.list_notes(repo_url="https://github.com/test/repo.git")
    assert listed["commit_shas"] == ["active-sha"]

    audit_listed = service.list_notes(
        repo_url="https://github.com/test/repo.git",
        include_superseded=True,
    )
    assert set(audit_listed["commit_shas"]) == {"active-sha", "superseded-sha"}
    audit_listed_superseded = next(
        item for item in audit_listed["items"] if item["commit_sha"] == "superseded-sha"
    )
    assert audit_listed_superseded["superseded_at"] == 1710000000000

    search = service.search_notes(
        repo_url="https://github.com/test/repo.git",
        pattern="shared search content",
    )
    assert search == ["active-sha"]

    audit_search = service.search_notes(
        repo_url="https://github.com/test/repo.git",
        pattern="shared search content",
        include_superseded=True,
    )
    assert set(audit_search) == {"active-sha", "superseded-sha"}
