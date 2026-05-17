import pytest
from flask import Flask
from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as database_base
from core.database.base import Base
from api.routes.codeup_webhook import codeup_webhook_bp


@pytest.fixture
def client():
    loader.config_data = {"database": {"url": "sqlite:///:memory:", "echo": False}}
    database_base.global_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(database_base.global_engine)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(codeup_webhook_bp)

    yield app.test_client()


def _merged_payload():
    return {
        "object_attributes": {
            "state": "merged",
            "iid": 42,
            "source_branch": "feature/codeup",
            "target_branch": "main",
            "merge_commit_sha": "a" * 40,
        },
        "project": {
            "id": 1001,
            "git_http_url": "https://codeup.aliyun.com/org/repo.git",
        },
        "commits": [
            {"id": "b" * 40},
            {"sha": "c" * 40},
        ],
    }


def test_merge_webhook_enqueues_merged_payload(client):
    response = client.post("/webhook/codeup/merge", json=_merged_payload())

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["data"]["skipped"] is False
    assert data["data"]["task_id"]


def test_merge_webhook_skips_opened_payload(client):
    payload = _merged_payload()
    payload["object_attributes"]["state"] = "opened"

    response = client.post("/webhook/codeup/merge", json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["data"] == {"success": True, "skipped": True, "reason": "not_merged"}


def test_merge_webhook_rejects_missing_merge_commit_sha(client):
    payload = _merged_payload()
    del payload["object_attributes"]["merge_commit_sha"]

    response = client.post("/webhook/codeup/merge", json=payload)

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "merge_commit_sha" in data["error"]
