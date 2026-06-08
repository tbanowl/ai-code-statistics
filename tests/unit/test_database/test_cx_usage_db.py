import os
import tempfile
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as db_base
from core.database.base import session_scope
from core.database.cx_usage_db import (
    CxCodereviewBypass,
    CxCodereviewSummary,
    CxCommandUsageEvent,
    CxUsageDatabase,
)


def _cx_usage_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    loader.config_data = {
        "features": {"enabled": True},
        "git": {"type": "github"},
        "database": {"url": f"sqlite:///{path}", "echo": False},
    }
    db_base.global_engine = create_engine(f"sqlite:///{path}")
    db = CxUsageDatabase()
    db_base.Base.metadata.create_all(db.engine)
    return db, path


def _cleanup_cx_usage_db(db, path):
    if db and db.engine:
        db.engine.dispose()
    loader.config_data = {}
    db_base.global_engine = None
    if os.path.exists(path):
        os.unlink(path)


def test_insert_batch_derives_event_day_from_event_time():
    db, path = _cx_usage_db()
    try:
        result = db.insert_batch(
            [
                {
                    "eventId": "evt_test_202605280001",
                    "schemaVersion": "1.0",
                    "eventType": "cx_command_invoked",
                    "eventTime": datetime(2026, 5, 28, 9, 30, 45),
                    "command": "cx-spec",
                    "specId": "spec-1",
                }
            ]
        )

        assert result == {
            "accepted": ["evt_test_202605280001"],
            "duplicated": [],
            "failed": [],
        }
        with session_scope(db.engine) as session:
            row = session.query(CxCommandUsageEvent).one()
            assert row.event_day == 20260528
    finally:
        _cleanup_cx_usage_db(db, path)


def test_insert_codereview_batch_splits_bypass_and_summary():
    db, path = _cx_usage_db()
    try:
        bypass_event = {
            "eventId": "evt_codereview_202606080101",
            "schemaVersion": "1.0",
            "eventType": "cx_codereview_issue_bypass",
            "eventTime": datetime(2026, 6, 8, 10, 20, 30),
            "specId": "spec-1",
            "specIdSource": "file",
            "projectId": "project-1",
            "gitUserName": "Alice",
            "gitUserEmail": "alice@example.com",
            "sessionId": "session-1",
            "pluginVersion": "0.1.0",
            "source": "codex",
            "pushId": "push-1",
            "commitSha": "a" * 40,
            "issueId": "issue-1",
            "issueTitle": "Unchecked error",
            "issueDescription": "The error is ignored.",
            "severity": "high",
            "filePath": "src/app.py",
            "lineRange": "10-12",
            "codeSnippet": "call()",
            "impact": "Runtime failure",
            "suggestion": "Handle the error",
            "ruleRef": "CR001",
            "response": "bypass",
            "reason": "False positive",
            "originalMarker": {"line": 10},
            "bypassedMarker": {"line": 10, "bypassed": True},
            "rawEvent": {"eventId": "evt_codereview_202606080101"},
        }
        summary_event = {
            "eventId": "evt_codereview_202606080102",
            "schemaVersion": "1.0",
            "eventType": "cx_codereview_push_summary",
            "eventTime": datetime(2026, 6, 8, 10, 30, 0),
            "specId": "spec-1",
            "specIdSource": "file",
            "projectId": "project-1",
            "gitUserName": "Alice",
            "gitUserEmail": "alice@example.com",
            "sessionId": "session-1",
            "pluginVersion": "0.1.0",
            "source": "codex",
            "pushId": "push-1",
            "commitSha": "b" * 40,
            "commitShort": "bbbbbbb",
            "pushBranch": "main",
            "pushRemote": "origin",
            "reportPath": "reports/review.md",
            "reviewStatus": "passed",
            "bypassCount": 2,
            "finalScore": Decimal("93.50"),
            "grade": "A",
            "issueCounts": {"high": 1},
            "submissionTime": datetime(2026, 6, 8, 10, 31, 0),
            "rawEvent": {"eventId": "evt_codereview_202606080102"},
        }

        result = db.insert_codereview_batch(
            [bypass_event, summary_event], token_name="token-1"
        )

        assert result == {
            "accepted": [
                "evt_codereview_202606080101",
                "evt_codereview_202606080102",
            ],
            "duplicated": [],
            "failed": [],
        }
        with session_scope(db.engine) as session:
            bypass = session.query(CxCodereviewBypass).one()
            summary = session.query(CxCodereviewSummary).one()
            assert len(bypass.id) == 20
            assert bypass.issue_id == "issue-1"
            assert bypass.original_marker == {"line": 10}
            assert bypass.raw_event == {"eventId": "evt_codereview_202606080101"}
            assert bypass.token_name == "token-1"
            assert len(summary.id) == 20
            assert summary.push_branch == "main"
            assert summary.bypass_count == 2
            assert summary.final_score == Decimal("93.50")
            assert summary.issue_counts == {"high": 1}
            assert summary.raw_event == {"eventId": "evt_codereview_202606080102"}
            assert summary.token_name == "token-1"
    finally:
        _cleanup_cx_usage_db(db, path)


def test_insert_codereview_batch_reports_duplicate_event_id():
    db, path = _cx_usage_db()
    try:
        event = {
            "eventId": "evt_codereview_202606080103",
            "schemaVersion": "1.0",
            "eventType": "cx_codereview_issue_bypass",
            "eventTime": datetime(2026, 6, 8, 10, 20, 30),
            "specId": "spec-1",
            "pushId": "push-1",
            "rawEvent": {"eventId": "evt_codereview_202606080103"},
        }

        first = db.insert_codereview_batch([event])
        second = db.insert_codereview_batch([event])

        assert first["accepted"] == ["evt_codereview_202606080103"]
        assert second == {
            "accepted": [],
            "duplicated": ["evt_codereview_202606080103"],
            "failed": [],
        }
    finally:
        _cleanup_cx_usage_db(db, path)
