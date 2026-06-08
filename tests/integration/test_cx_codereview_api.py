from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from flask import Flask

from api.routes.cx_usage import cx_usage_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(cx_usage_bp)
    return app.test_client()


def _bypass_event(event_id="evt_codereview_202606080201"):
    return {
        "eventId": event_id,
        "schemaVersion": "1.0",
        "eventType": "cx_codereview_issue_bypass",
        "timestamp": "2026-06-08T10:20:30Z",
        "specId": "spec-1",
        "pushId": "push-1",
        "issueId": "issue-1",
        "originalMarker": {"line": 10},
    }


def _summary_event(event_id="evt_codereview_202606080202"):
    return {
        "eventId": event_id,
        "schemaVersion": "1.0",
        "eventType": "cx_codereview_push_summary",
        "timestamp": "2026-06-08T10:30:00Z",
        "specId": "spec-1",
        "pushId": "push-1",
        "bypassCount": 1,
        "finalScore": "88.25",
        "issueCounts": {"high": 1},
    }


def test_codereview_events_batch_accepts_mixed_events(client):
    with patch("core.database.cx_usage_db.CxUsageDatabase") as db_cls:
        db = db_cls.return_value
        db.insert_codereview_batch.return_value = {
            "accepted": [
                "evt_codereview_202606080201",
                "evt_codereview_202606080202",
            ],
            "duplicated": [],
            "failed": [],
        }

        response = client.post(
            "/api/v1/cx-aicode/codereview/events/batch",
            json={"items": [_bypass_event(), _summary_event()]},
        )

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "accepted": [
            "evt_codereview_202606080201",
            "evt_codereview_202606080202",
        ],
        "duplicated": [],
        "failed": [],
    }

    inserted_events = db.insert_codereview_batch.call_args.args[0]
    assert [event["eventType"] for event in inserted_events] == [
        "cx_codereview_issue_bypass",
        "cx_codereview_push_summary",
    ]
    assert inserted_events[0]["eventTime"] == datetime(2026, 6, 8, 10, 20, 30)
    assert inserted_events[1]["finalScore"] == Decimal("88.25")


def test_codereview_events_batch_reports_validation_failures(client):
    valid = _bypass_event()
    invalid = _summary_event("evt_codereview_202606080203")
    invalid["timestamp"] = "bad-time"

    with patch("core.database.cx_usage_db.CxUsageDatabase") as db_cls:
        db = db_cls.return_value
        db.insert_codereview_batch.return_value = {
            "accepted": ["evt_codereview_202606080201"],
            "duplicated": [],
            "failed": [],
        }

        response = client.post(
            "/api/v1/cx-aicode/codereview/events/batch",
            json={"items": [valid, invalid]},
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is False
    assert data["accepted"] == ["evt_codereview_202606080201"]
    assert data["failed"] == ["evt_codereview_202606080203"]

    inserted_events = db.insert_codereview_batch.call_args.args[0]
    assert len(inserted_events) == 1
    assert inserted_events[0]["eventId"] == "evt_codereview_202606080201"


def test_codereview_events_batch_rejects_non_array(client):
    response = client.post(
        "/api/v1/cx-aicode/codereview/events/batch",
        json={"items": {"not": "array"}},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "body.items must be an array",
    }


def test_codereview_events_batch_rejects_large_batch(client):
    response = client.post(
        "/api/v1/cx-aicode/codereview/events/batch",
        json={"items": [_bypass_event(f"evt_codereview_{i:012d}") for i in range(101)]},
    )

    assert response.status_code == 413
    assert response.get_json() == {
        "success": False,
        "error": "batch size exceeds 100",
    }


def test_codereview_events_batch_returns_503_when_database_construction_fails(client):
    with patch("core.database.cx_usage_db.CxUsageDatabase") as db_cls:
        db_cls.side_effect = RuntimeError("database down")

        response = client.post(
            "/api/v1/cx-aicode/codereview/events/batch",
            json={"items": [_bypass_event()]},
        )

    assert response.status_code == 503
    assert response.get_json() == {
        "success": False,
        "error": "database unavailable",
        "accepted": [],
        "duplicated": [],
        "failed": ["evt_codereview_202606080201"],
    }


def test_codereview_events_batch_returns_503_when_insert_fails(client):
    with patch("core.database.cx_usage_db.CxUsageDatabase") as db_cls:
        db = db_cls.return_value
        db.insert_codereview_batch.side_effect = RuntimeError("insert failed")

        response = client.post(
            "/api/v1/cx-aicode/codereview/events/batch",
            json={"items": [_bypass_event(), _summary_event()]},
        )

    assert response.status_code == 503
    assert response.get_json() == {
        "success": False,
        "error": "database unavailable",
        "accepted": [],
        "duplicated": [],
        "failed": [
            "evt_codereview_202606080201",
            "evt_codereview_202606080202",
        ],
    }
