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


def test_admin_list_does_not_include_content_blob(client):
    response = client.get(
        "/worker/releases/admin/list",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert "content_blob" not in response.get_data(as_text=True)
