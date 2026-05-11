"""OTLP Logs Receiver API 集成测试。"""

from unittest.mock import patch

import pytest
from flask import Flask

from api.routes.otel_receiver import otel_receiver_bp


def _attr(key, value):
    return {"key": key, "value": {"stringValue": value}}


def _valid_payload():
    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        _attr("service.name", "claude-code"),
                        _attr("org.user", "user-123"),
                    ]
                },
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "eventName": "claude_code.skill_activated",
                                "attributes": [
                                    _attr("event.name", "skill_activated"),
                                    _attr("skill.source", "plugin"),
                                    _attr("plugin.name", "superpowers"),
                                    _attr("skill.name", "brainstorming"),
                                    _attr("invocation_trigger", "user-slash"),
                                ],
                            }
                        ]
                    }
                ],
            }
        ]
    }


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(otel_receiver_bp)
    return app.test_client()


def test_v1_logs_accepts_valid_payload(client):
    with patch("core.services.otel_logs_service.OtelLogsService.process_logs") as process:
        process.return_value = {"success": True, "accepted": 1, "skipped": 0, "errors": []}

        response = client.post("/v1/logs", json=_valid_payload())

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["accepted"] == 1


def test_worker_alias_accepts_valid_payload(client):
    with patch("core.services.otel_logs_service.OtelLogsService.process_logs") as process:
        process.return_value = {"success": True, "accepted": 1, "skipped": 0, "errors": []}

        response = client.post("/worker/otel/v1/logs", json=_valid_payload())

    assert response.status_code == 200
    assert response.get_json()["accepted"] == 1


def test_logs_rejects_invalid_json(client):
    response = client.post(
        "/v1/logs",
        data="not-json",
        content_type="application/json",
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Invalid JSON" in data["error"]


def test_v1_logs_persists_invocation_record():
    import importlib
    import os
    import tempfile
    import time

    import core.config.loader as loader

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_base = db = None
    try:
        loader.config_data = {
            "database": {"url": f"sqlite:///{path}", "echo": False},
            "otel": {
                "receiver": {
                    "logs": {
                        "enabled": True,
                        "accept_json": True,
                        "accept_protobuf": False,
                        "max_log_records_per_request": 1000,
                        "require_org_user": True,
                    }
                }
            },
        }
        import core.database.base as db_base
        import core.database.models as db_models
        import core.database.otel_logs_db as otel_logs_db_module

        importlib.reload(db_base)
        importlib.reload(db_models)
        importlib.reload(otel_logs_db_module)

        db = otel_logs_db_module.OtelLogsDatabase()
        db_base.Base.metadata.create_all(db.engine)

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(otel_receiver_bp)
        client = app.test_client()

        response = client.post("/v1/logs", json=_valid_payload())

        assert response.status_code == 200
        assert response.get_json()["accepted"] == 1

        with db_base.session_scope(db.engine) as session:
            stored = session.query(db_models.OtelInvocationCount).one()
            assert stored.plugin_name == "superpowers"
            assert stored.skill_name == "brainstorming"
            assert stored.org_user == "user-123"
    finally:
        loader.config_data = {}
        if db is not None:
            db.engine.dispose()
        elif db_base is not None:
            db_base.engine.dispose()
        time.sleep(0.1)
        if os.path.exists(path):
            os.unlink(path)
