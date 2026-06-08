import os
import tempfile
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, create_engine
from sqlalchemy.exc import SQLAlchemyError

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
    previous_config_data = loader.config_data
    previous_global_engine = db_base.global_engine
    loader.config_data = {
        "features": {"enabled": True},
        "git": {"type": "github"},
        "database": {"url": f"sqlite:///{path}", "echo": False},
    }
    db_base.global_engine = create_engine(f"sqlite:///{path}")
    db = CxUsageDatabase()
    db_base.Base.metadata.create_all(db.engine)
    return db, path, previous_config_data, previous_global_engine


def _cleanup_cx_usage_db(db, path, previous_config_data, previous_global_engine):
    if db and db.engine:
        db.engine.dispose()
    loader.config_data = previous_config_data
    db_base.global_engine = previous_global_engine
    if os.path.exists(path):
        os.unlink(path)


def _bypass_event(event_id, **overrides):
    event = {
        "eventId": event_id,
        "schemaVersion": "1.0",
        "eventType": "cx_codereview_issue_bypass",
        "eventTime": datetime(2026, 6, 8, 10, 20, 30),
        "specId": "spec-1",
        "pushId": "push-1",
        "rawEvent": {"eventId": event_id},
    }
    event.update(overrides)
    return event


def _summary_event(event_id, **overrides):
    event = {
        "eventId": event_id,
        "schemaVersion": "1.0",
        "eventType": "cx_codereview_push_summary",
        "eventTime": datetime(2026, 6, 8, 10, 30, 0),
        "specId": "spec-1",
        "pushId": "push-1",
        "commitSha": "b" * 40,
        "rawEvent": {"eventId": event_id},
    }
    event.update(overrides)
    return event


def _constraint_sql(model, constraint_name):
    constraints = [
        constraint
        for constraint in model.__table__.constraints
        if constraint.name == constraint_name
    ]
    assert len(constraints) == 1
    constraint = constraints[0]
    assert isinstance(constraint, CheckConstraint)
    return str(constraint.sqltext)


def test_insert_batch_derives_event_day_from_event_time():
    db, path, previous_config_data, previous_global_engine = _cx_usage_db()
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
        _cleanup_cx_usage_db(db, path, previous_config_data, previous_global_engine)


def test_codereview_models_match_event_type_defaults_and_constraints():
    bypass_event_type = CxCodereviewBypass.__table__.c.event_type
    summary_event_type = CxCodereviewSummary.__table__.c.event_type

    assert bypass_event_type.server_default is not None
    assert str(bypass_event_type.server_default.arg) == "cx_codereview_issue_bypass"
    assert summary_event_type.server_default is not None
    assert str(summary_event_type.server_default.arg) == "cx_codereview_push_summary"
    assert (
        _constraint_sql(CxCodereviewBypass, "chk_cr_bypass_event_type")
        == "event_type = 'cx_codereview_issue_bypass'"
    )
    assert (
        _constraint_sql(CxCodereviewSummary, "chk_cr_summary_event_type")
        == "event_type = 'cx_codereview_push_summary'"
    )


def test_insert_codereview_batch_splits_bypass_and_summary():
    db, path, previous_config_data, previous_global_engine = _cx_usage_db()
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
        _cleanup_cx_usage_db(db, path, previous_config_data, previous_global_engine)


def test_insert_codereview_batch_reports_duplicate_event_id():
    db, path, previous_config_data, previous_global_engine = _cx_usage_db()
    try:
        event = _bypass_event("evt_codereview_202606080103")

        first = db.insert_codereview_batch([event])
        second = db.insert_codereview_batch([event])

        assert first["accepted"] == ["evt_codereview_202606080103"]
        assert second == {
            "accepted": [],
            "duplicated": ["evt_codereview_202606080103"],
            "failed": [],
        }
    finally:
        _cleanup_cx_usage_db(db, path, previous_config_data, previous_global_engine)


def test_insert_codereview_batch_persists_accepted_event_before_same_batch_duplicate():
    db, path, previous_config_data, previous_global_engine = _cx_usage_db()
    try:
        duplicate_event = _bypass_event("evt_codereview_202606080104")
        first = db.insert_codereview_batch([duplicate_event])
        assert first["accepted"] == ["evt_codereview_202606080104"]

        new_event = _bypass_event("evt_codereview_202606080105")
        second = db.insert_codereview_batch([new_event, duplicate_event])

        assert second == {
            "accepted": ["evt_codereview_202606080105"],
            "duplicated": ["evt_codereview_202606080104"],
            "failed": [],
        }
        with session_scope(db.engine) as session:
            persisted = (
                session.query(CxCodereviewBypass)
                .filter_by(event_id="evt_codereview_202606080105")
                .one_or_none()
            )
            assert persisted is not None
    finally:
        _cleanup_cx_usage_db(db, path, previous_config_data, previous_global_engine)


def test_insert_codereview_batch_reports_cross_type_duplicate_in_same_batch():
    db, path, previous_config_data, previous_global_engine = _cx_usage_db()
    try:
        event_id = "evt_codereview_202606080106"
        bypass_event = _bypass_event(event_id)
        summary_event = _summary_event(event_id)

        result = db.insert_codereview_batch([bypass_event, summary_event])

        assert result == {
            "accepted": [event_id],
            "duplicated": [event_id],
            "failed": [],
        }
        with session_scope(db.engine) as session:
            assert session.query(CxCodereviewBypass).filter_by(event_id=event_id).one()
            assert (
                session.query(CxCodereviewSummary)
                .filter_by(event_id=event_id)
                .one_or_none()
                is None
            )
    finally:
        _cleanup_cx_usage_db(db, path, previous_config_data, previous_global_engine)


def test_insert_codereview_batch_reports_cross_table_duplicate_from_existing_event():
    db, path, previous_config_data, previous_global_engine = _cx_usage_db()
    try:
        event_id = "evt_codereview_202606080107"
        first = db.insert_codereview_batch([_summary_event(event_id)])
        second = db.insert_codereview_batch([_bypass_event(event_id)])

        assert first["accepted"] == [event_id]
        assert second == {
            "accepted": [],
            "duplicated": [event_id],
            "failed": [],
        }
        with session_scope(db.engine) as session:
            assert session.query(CxCodereviewSummary).filter_by(event_id=event_id).one()
            assert (
                session.query(CxCodereviewBypass)
                .filter_by(event_id=event_id)
                .one_or_none()
                is None
            )
    finally:
        _cleanup_cx_usage_db(db, path, previous_config_data, previous_global_engine)


def test_insert_codereview_batch_propagates_database_write_errors(monkeypatch):
    db, path, previous_config_data, previous_global_engine = _cx_usage_db()
    try:
        event = _bypass_event("evt_codereview_202606080108")

        def fail_flush(self, *args, **kwargs):
            raise SQLAlchemyError("database down")

        monkeypatch.setattr("sqlalchemy.orm.Session.flush", fail_flush)

        try:
            db.insert_codereview_batch([event])
        except SQLAlchemyError as exc:
            assert "database down" in str(exc)
        else:
            raise AssertionError("expected SQLAlchemyError to propagate")
    finally:
        _cleanup_cx_usage_db(db, path, previous_config_data, previous_global_engine)
