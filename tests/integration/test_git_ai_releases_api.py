import io
import os
import tempfile

import core.config.loader as loader
import core.database.base as database_base
import pytest
from flask import Flask
from sqlalchemy import create_engine

from core.database.base import Base


@pytest.fixture
def app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    temp_db_url = f"sqlite:///{path}"
    previous_config_data = loader.config_data
    previous_global_engine = database_base.global_engine
    engine = create_engine(temp_db_url, echo=False)
    loader.config_data = {
        "database": {"url": temp_db_url, "echo": False},
        "git_ai": {
            "api_key": "test-key",
            "releases": {
                "max_file_size_mb": 200,
                "max_files_per_release": 12,
                "allowed_channels": ["latest", "next", "enterprise-latest", "enterprise-next"],
            },
        },
    }
    database_base.global_engine = engine
    Base.metadata.create_all(engine)

    from api.routes.git_ai_worker import releases_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(releases_bp)

    yield app

    engine.dispose()
    loader.config_data = previous_config_data
    database_base.global_engine = previous_global_engine
    os.unlink(path)


@pytest.fixture
def client(app):
    return app.test_client()


def _bytes_file(content: bytes, filename: str):
    return io.BytesIO(content), filename


def test_upload_activate_and_download_release_files(client):
    response = client.post(
        "/worker/releases/admin/upload",
        data={
            "tag": "v1.0.0",
            "version": "1.0.0",
            "channel": "latest",
            "files": [
                _bytes_file(b"ps", "install.ps1"),
                _bytes_file(b"exe", "git-ai-windows-x64.exe"),
            ],
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    release_id = response.get_json()["release"]["id"]

    active = client.post(
        f"/worker/releases/admin/{release_id}/activate",
        headers={"X-API-Key": "test-key"},
    )
    assert active.status_code == 200

    channels = client.get("/worker/releases/").get_json()["channels"]
    assert channels["latest"]["tag"] == "v1.0.0"
    assert channels["latest"]["version"] == "1.0.0"
    assert channels["latest"]["platforms"] == ["windows-x64"]

    download = client.get("/worker/releases/latest/download/install.ps1")
    assert download.status_code == 200
    assert download.data == b"ps"


def test_download_release_artifact_by_version(client):
    response = client.post(
        "/worker/releases/admin/upload",
        data={
            "tag": "v2.3.4",
            "version": "2.3.4",
            "channel": "latest",
            "files": [
                _bytes_file(b"ps", "install.ps1"),
                _bytes_file(b"exe", "git-ai-windows-x64.exe"),
            ],
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200

    download = client.get("/worker/releases/download/2.3.4/install.ps1")
    assert download.status_code == 200
    assert download.data == b"ps"
    assert download.headers["X-Git-AI-SHA256"]
    assert download.headers["ETag"].startswith('"sha256:')

    missing = client.get("/worker/releases/download/9.9.9/install.ps1")
    assert missing.status_code == 404


def test_admin_list_does_not_include_content_blob(client):
    response = client.get(
        "/worker/releases/admin/list",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert "content_blob" not in response.get_data(as_text=True)


def _upload_release(client, tag="v1.0.0", version="1.0.0"):
    response = client.post(
        "/worker/releases/admin/upload",
        data={
            "tag": tag,
            "version": version,
            "channel": "latest",
            "files": [
                _bytes_file(b"ps", "install.ps1"),
                _bytes_file(b"exe", "git-ai-windows-x64.exe"),
            ],
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    return response.get_json()["release"]["id"]


def test_update_active_release_metadata_updates_channel_response(client):
    release_id = _upload_release(client)
    active = client.post(
        f"/worker/releases/admin/{release_id}/activate",
        headers={"X-API-Key": "test-key"},
    )
    assert active.status_code == 200

    response = client.put(
        f"/worker/releases/admin/{release_id}",
        data={"tag": "v1.0.1", "version": "1.0.1", "channel": "latest", "description": "edited"},
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    channels = client.get("/worker/releases/").get_json()["channels"]
    assert channels["latest"]["tag"] == "v1.0.1"
    assert channels["latest"]["version"] == "1.0.1"
    download = client.get("/worker/releases/latest/download/install.ps1")
    assert download.status_code == 200
    assert download.data == b"ps"


def test_update_active_release_files_updates_download(client):
    release_id = _upload_release(client)
    active = client.post(
        f"/worker/releases/admin/{release_id}/activate",
        headers={"X-API-Key": "test-key"},
    )
    assert active.status_code == 200

    previous_checksum = client.get("/worker/releases/").get_json()["channels"]["latest"]["checksum"]

    response = client.put(
        f"/worker/releases/admin/{release_id}",
        data={
            "tag": "v1.0.0",
            "version": "1.0.0",
            "channel": "latest",
            "files": [
                _bytes_file(b"ps-new", "install.ps1"),
                _bytes_file(b"exe-new", "git-ai-windows-x64.exe"),
            ],
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    download = client.get("/worker/releases/latest/download/install.ps1")
    assert download.status_code == 200
    assert download.data == b"ps-new"
    new_checksum = client.get("/worker/releases/").get_json()["channels"]["latest"]["checksum"]
    assert new_checksum != ""
    assert new_checksum != previous_checksum


def test_update_missing_release_returns_404(client):
    response = client.put(
        "/worker/releases/admin/missing",
        data={"tag": "v1.0.1", "version": "1.0.1", "channel": "latest"},
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 404


def test_update_release_files_requires_required_files(client):
    release_id = _upload_release(client)
    response = client.put(
        f"/worker/releases/admin/{release_id}",
        data={
            "tag": "v1.0.0",
            "version": "1.0.0",
            "channel": "latest",
            "files": [_bytes_file(b"ps", "install.ps1")],
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 400
    assert "git-ai-windows-x64.exe" in response.get_json()["error"]


def test_update_release_rejects_invalid_fields(client):
    release_id = _upload_release(client)

    empty_tag = client.put(
        f"/worker/releases/admin/{release_id}",
        data={"tag": "   ", "version": "1.0.0", "channel": "latest"},
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert empty_tag.status_code == 400
    assert "tag" in empty_tag.get_json()["error"].lower()

    invalid_channel = client.put(
        f"/worker/releases/admin/{release_id}",
        data={"tag": "v1.0.1", "version": "1.0.1", "channel": "bogus"},
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert invalid_channel.status_code == 400
    assert "bogus" in invalid_channel.get_json()["error"]
