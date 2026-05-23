import os
import pytest
import tempfile
from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as database_base
from core.database.base import Base
from core.services.codeup_note_provider import CodeupDatabaseNoteProvider
from core.services.notes_service import NotesRestService

@pytest.fixture(autouse=True)
def isolated_notes_database():
    original_config_data = loader.config_data
    original_engine = database_base.global_engine
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_db_url = f"sqlite:///{path}"
    test_engine = create_engine(test_db_url, echo=False)

    loader.config_data = {"database": {"url": test_db_url, "echo": False}}
    database_base.global_engine = test_engine
    Base.metadata.create_all(test_engine)

    try:
        yield
    finally:
        test_engine.dispose()
        database_base.global_engine = original_engine
        loader.config_data = original_config_data
        try:
            os.unlink(path)
        except (PermissionError, OSError):
            pass


def test_batch_get_note_contents_returns_existing_db_notes_only():
    repo_url = "https://codeup.aliyun.com/org/repo.git"
    existing = "a" * 40
    missing = "b" * 40
    content = "AI authorship log content"

    NotesRestService().create_or_update_note(
        repo_url=repo_url,
        branch="main",
        commit_sha=existing,
        original_commit_sha=None,
        content=content,
        author_name="Test User",
        author_email="test@example.com",
    )

    # Service normalizes repo_url, so DB stores "codeup.aliyun.com/org/repo"
    result = CodeupDatabaseNoteProvider().batch_get_note_contents(
        "codeup.aliyun.com/org/repo", [existing, missing]
    )

    assert result == {existing: content}
