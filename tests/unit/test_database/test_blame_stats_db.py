import os
import tempfile

import pytest

import core.config.loader as loader
from core.database.blame_stats_db import BlameStatsDatabase
from core.database.models import AuthorshipNotes


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def blame_stats_db(temp_db_path):
    loader.config_data = {
        "features": {"enabled": True},
        "git": {"type": "github"},
        "database": {"url": f"sqlite:///{temp_db_path}", "echo": False},
    }
    db = BlameStatsDatabase()
    db.init_db()
    return db


def test_get_git_notes_batch_empty(blame_stats_db):
    assert blame_stats_db.get_git_notes_batch([]) == {}


def test_get_git_notes_batch_returns_matching_notes(blame_stats_db):
    with blame_stats_db.session_scope() as session:
        session.add(
            AuthorshipNotes(
                id="noteabc1230000000001",
                repo_url="https://example.com/repo.git",
                branch="main",
                commit_sha="abc123",
                note_blob_oid=None,
                author_name="tester",
                author_email="tester@example.com",
                note_content="note-a",
            )
        )
        session.add(
            AuthorshipNotes(
                id="notedef4560000000002",
                repo_url="https://example.com/repo.git",
                branch="main",
                commit_sha="def456",
                note_blob_oid=None,
                author_name="tester",
                author_email="tester@example.com",
                note_content="note-b",
            )
        )

    result = blame_stats_db.get_git_notes_batch(["abc123", "missing"])

    assert result == {"abc123": "note-a"}
