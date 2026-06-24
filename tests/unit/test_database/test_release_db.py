import os
import tempfile

import core.config.loader as loader
import core.database.base as database_base
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from core.database.base import Base, session_scope


@pytest.fixture
def sqlite_release_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    temp_db_url = f"sqlite:///{path}"
    previous_config_data = loader.config_data
    previous_global_engine = database_base.global_engine
    engine = create_engine(temp_db_url, echo=False)
    loader.config_data = {"database": {"url": temp_db_url, "echo": False}}
    database_base.global_engine = engine
    try:
        Base.metadata.create_all(engine)
        from core.database.release_db import ReleaseDatabase

        yield ReleaseDatabase()
    finally:
        engine.dispose()
        loader.config_data = previous_config_data
        database_base.global_engine = previous_global_engine
        os.unlink(path)


def test_release_models_can_persist_blob_artifact():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    temp_db_url = f"sqlite:///{path}"
    previous_config_data = loader.config_data
    previous_global_engine = database_base.global_engine
    engine = create_engine(temp_db_url, echo=False)
    loader.config_data = {"database": {"url": temp_db_url, "echo": False}}
    database_base.global_engine = engine
    try:
        Base.metadata.create_all(engine)
        from core.database.models import GitAiRelease, GitAiReleaseArtifact

        with session_scope(engine) as session:
            release = GitAiRelease(
                tag="v1.2.3",
                version="v1.2.3",
                channel="latest",
                status="inactive",
                sha256sums_checksum="abc123",
            )
            session.add(release)
            session.flush()
            session.add(
                GitAiReleaseArtifact(
                    release_id=release.id,
                    filename="install.ps1",
                    artifact_type="installer",
                    platform="windows-x64",
                    sha256="def456",
                    size_bytes=8,
                    content_type="text/plain",
                    content_blob=b"Write-Ok",
                )
            )

        with session_scope(engine) as session:
            artifact = session.query(GitAiReleaseArtifact).filter_by(filename="install.ps1").one()
            assert artifact.content_blob == b"Write-Ok"
    finally:
        engine.dispose()
        loader.config_data = previous_config_data
        database_base.global_engine = previous_global_engine
        os.unlink(path)


def test_activate_release_deactivates_previous_release(sqlite_release_db):
    db = sqlite_release_db
    first = db.create_release(
        tag="v1.0.0",
        version="v1.0.0",
        channel="latest",
        sha256sums_checksum="a" * 64,
        artifacts=[],
        description=None,
        created_by="tester",
    )
    second = db.create_release(
        tag="v1.0.1",
        version="v1.0.1",
        channel="latest",
        sha256sums_checksum="b" * 64,
        artifacts=[],
        description=None,
        created_by="tester",
    )

    db.activate_release(first["id"])
    db.activate_release(second["id"])

    assert db.get_release(first["id"])["status"] == "inactive"
    assert db.get_release(second["id"])["status"] == "active"
    assert db.get_active_release("latest")["tag"] == "v1.0.1"


def test_get_artifact_returns_content(sqlite_release_db):
    db = sqlite_release_db
    release = db.create_release(
        tag="v1.0.0",
        version="v1.0.0",
        channel="latest",
        sha256sums_checksum="a" * 64,
        artifacts=[
            {
                "filename": "install.ps1",
                "artifact_type": "installer",
                "platform": "windows-x64",
                "sha256": "b" * 64,
                "size_bytes": 8,
                "content_type": "text/plain",
                "content_blob": b"Write-Ok",
            }
        ],
        description=None,
        created_by="tester",
    )

    artifact = db.get_artifact(release["id"], "install.ps1")
    assert artifact["content_blob"] == b"Write-Ok"


def test_release_model_rejects_two_active_releases_in_same_channel(sqlite_release_db):
    db = sqlite_release_db
    first = db.create_release(
        tag="v1.0.0",
        version="v1.0.0",
        channel="latest",
        sha256sums_checksum="a" * 64,
        artifacts=[],
        description=None,
        created_by="tester",
    )
    second = db.create_release(
        tag="v1.0.1",
        version="v1.0.1",
        channel="latest",
        sha256sums_checksum="b" * 64,
        artifacts=[],
        description=None,
        created_by="tester",
    )

    with pytest.raises(IntegrityError):
        with session_scope(db.engine) as session:
            from core.database.models import GitAiRelease

            session.query(GitAiRelease).filter(GitAiRelease.id == first["id"]).update(
                {"status": "active"}
            )
            session.query(GitAiRelease).filter(GitAiRelease.id == second["id"]).update(
                {"status": "active"}
            )
