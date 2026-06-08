# CX Code Review Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one batch API that receives CX code review bypass and summary events, validates them, and stores them in the two new code review tables.

**Architecture:** Keep the existing `cx_usage` blueprint and database helper as the integration point. Add a focused schema module for code review event validation, add SQLAlchemy models and a batch insert method for the two new tables, then add a dedicated route that mirrors the current command usage batch response shape.

**Tech Stack:** Flask, SQLAlchemy 2.0, pytest, SQLite test databases, existing `py-xid` via `core.database.models.gen_xid()`.

---

## File Structure

- Create `api/schemas/cx_codereview_schema.py`: validation and normalization for `cx_codereview_issue_bypass` and `cx_codereview_push_summary`.
- Modify `api/routes/cx_usage.py`: import the code review validators and add `POST /api/v1/cx-aicode/codereview/events/batch`.
- Modify `core/database/cx_usage_db.py`: add ORM models for `cx_codereview_bypasses` and `cx_codereview_summaries`; add `insert_codereview_batch()`.
- Create `tests/unit/test_schemas/__init__.py`: package marker for schema tests.
- Create `tests/unit/test_schemas/test_cx_codereview_schema.py`: validator unit tests.
- Modify `tests/unit/test_database/test_cx_usage_db.py`: database insertion and duplicate tests.
- Create `tests/integration/test_cx_codereview_api.py`: route-level tests using an isolated Flask app and mocks.

## Task 1: Code Review Schema Validation

**Files:**
- Create: `tests/unit/test_schemas/__init__.py`
- Create: `tests/unit/test_schemas/test_cx_codereview_schema.py`
- Create: `api/schemas/cx_codereview_schema.py`

- [ ] **Step 1: Create the schema test package marker**

Create `tests/unit/test_schemas/__init__.py` as an empty file.

- [ ] **Step 2: Write failing schema tests**

Create `tests/unit/test_schemas/test_cx_codereview_schema.py`:

```python
from datetime import datetime
from decimal import Decimal

from api.schemas.cx_codereview_schema import (
    validate_batch,
    validate_codereview_event,
)


def _base_event(event_type="cx_codereview_issue_bypass"):
    return {
        "eventId": "evt_codereview_202606080001",
        "schemaVersion": "1.0",
        "eventType": event_type,
        "timestamp": "2026-06-08T10:20:30Z",
        "specId": "spec-1",
        "specIdSource": "file",
        "projectId": "project-1",
        "gitUserName": "Alice",
        "gitUserEmail": " Alice@Example.COM ",
        "sessionId": "session-1",
        "pluginVersion": "0.1.0",
        "source": "codex",
    }


def test_validate_bypass_event_normalizes_fields():
    event = _base_event()
    event.update(
        {
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
        }
    )

    result = validate_codereview_event(event)

    assert result["valid"] is True
    value = result["value"]
    assert value["eventId"] == "evt_codereview_202606080001"
    assert value["eventType"] == "cx_codereview_issue_bypass"
    assert value["eventTime"] == datetime(2026, 6, 8, 10, 20, 30)
    assert value["gitUserEmail"] == "alice@example.com"
    assert value["originalMarker"] == {"line": 10}
    assert value["bypassedMarker"] == {"line": 10, "bypassed": True}
    assert value["rawEvent"] is event


def test_validate_summary_event_normalizes_fields():
    event = _base_event("cx_codereview_push_summary")
    event.update(
        {
            "eventId": "evt_codereview_202606080002",
            "pushId": "push-1",
            "commitSha": "b" * 40,
            "commitShort": "bbbbbbb",
            "pushBranch": "main",
            "pushRemote": "origin",
            "reportPath": "reports/review.md",
            "reviewStatus": "passed",
            "bypassCount": "2",
            "finalScore": "93.50",
            "grade": "A",
            "issueCounts": {"high": 1, "low": 2},
            "submissionTime": "2026-06-08T10:30:00Z",
        }
    )

    result = validate_codereview_event(event)

    assert result["valid"] is True
    value = result["value"]
    assert value["eventType"] == "cx_codereview_push_summary"
    assert value["bypassCount"] == 2
    assert value["finalScore"] == Decimal("93.50")
    assert value["submissionTime"] == datetime(2026, 6, 8, 10, 30, 0)
    assert value["issueCounts"] == {"high": 1, "low": 2}


def test_validate_rejects_invalid_event_type():
    event = _base_event("cx_command_invoked")

    result = validate_codereview_event(event)

    assert result["valid"] is False
    assert "invalid eventType" in result["errors"]


def test_validate_rejects_invalid_timestamp():
    event = _base_event()
    event["timestamp"] = "not-a-time"

    result = validate_codereview_event(event)

    assert result["valid"] is False
    assert "invalid timestamp" in result["errors"]


def test_validate_rejects_non_json_marker():
    event = _base_event()
    event["originalMarker"] = "not-json"

    result = validate_codereview_event(event)

    assert result["valid"] is False
    assert "originalMarker must be an object or array" in result["errors"]


def test_validate_rejects_invalid_numeric_fields():
    event = _base_event("cx_codereview_push_summary")
    event["eventId"] = "evt_codereview_202606080003"
    event["bypassCount"] = "many"
    event["finalScore"] = "excellent"

    result = validate_codereview_event(event)

    assert result["valid"] is False
    assert "invalid bypassCount" in result["errors"]
    assert "invalid finalScore" in result["errors"]


def test_validate_batch_shape_and_size():
    assert validate_batch({"not": "a-list"}) == {
        "valid": False,
        "status_code": 400,
        "error": "body.items must be an array",
    }
    assert validate_batch([{}] * 101) == {
        "valid": False,
        "status_code": 413,
        "error": "batch size exceeds 100",
    }
    assert validate_batch([]) == {"valid": True}
```

- [ ] **Step 3: Run schema tests and confirm they fail**

Run:

```bash
pytest tests/unit/test_schemas/test_cx_codereview_schema.py -v
```

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'api.schemas.cx_codereview_schema'`.

- [ ] **Step 4: Implement the schema module**

Create `api/schemas/cx_codereview_schema.py`:

```python
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


VALID_EVENT_TYPES = {
    "cx_codereview_issue_bypass",
    "cx_codereview_push_summary",
}

FIELD_LIMITS = {
    "eventId": 80,
    "schemaVersion": 16,
    "eventType": 64,
    "timestamp": 64,
    "specId": 128,
    "specIdSource": 32,
    "projectId": 128,
    "gitUserName": 128,
    "gitUserEmail": 256,
    "sessionId": 128,
    "pluginVersion": 32,
    "source": 64,
    "pushId": 80,
    "commitSha": 64,
    "issueId": 128,
    "issueTitle": 512,
    "severity": 16,
    "lineRange": 64,
    "ruleRef": 256,
    "response": 16,
    "reason": 512,
    "commitShort": 16,
    "pushBranch": 256,
    "pushRemote": 64,
    "reviewStatus": 32,
    "grade": 8,
    "submissionTime": 64,
}

COMMON_FIELDS = [
    "specId",
    "specIdSource",
    "projectId",
    "gitUserName",
    "gitUserEmail",
    "sessionId",
    "pluginVersion",
    "source",
]

BYPASS_FIELDS = [
    "pushId",
    "commitSha",
    "issueId",
    "issueTitle",
    "issueDescription",
    "severity",
    "filePath",
    "lineRange",
    "codeSnippet",
    "impact",
    "suggestion",
    "ruleRef",
    "response",
    "reason",
]

BYPASS_JSON_FIELDS = ["originalMarker", "bypassedMarker"]

SUMMARY_FIELDS = [
    "pushId",
    "commitSha",
    "commitShort",
    "pushBranch",
    "pushRemote",
    "reportPath",
    "reviewStatus",
    "grade",
]

SUMMARY_JSON_FIELDS = ["issueCounts"]

MAX_BATCH_SIZE = 100

_EVENT_ID_RE = re.compile(r"^evt_[A-Za-z0-9._-]{8,76}$")


def _read(event, key, errors, required=False):
    value = str(event.get(key) or "")
    if required and not value:
        errors.append(f"missing {key}")
    elif value and key in FIELD_LIMITS and len(value) > FIELD_LIMITS[key]:
        errors.append(f"{key} too long")
    return value


def _parse_datetime(value, errors, field_name):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+08:00"))
        return parsed.replace(tzinfo=None)
    except (ValueError, AttributeError):
        errors.append(f"invalid {field_name}")
        return None


def _read_json(event, key, errors):
    value = event.get(key)
    if value is None:
        return None
    if not isinstance(value, (dict, list)):
        errors.append(f"{key} must be an object or array")
        return None
    return value


def _read_int(event, key, errors):
    value = event.get(key)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(f"invalid {key}")
        return None


def _read_decimal(event, key, errors):
    value = event.get(key)
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        errors.append(f"invalid {key}")
        return None


def validate_codereview_event(event):
    if not isinstance(event, dict):
        return {"valid": False, "errors": ["event must be an object"]}

    errors = []
    event_id = _read(event, "eventId", errors, required=True)
    schema_version = _read(event, "schemaVersion", errors, required=True)
    event_type = _read(event, "eventType", errors, required=True)
    timestamp = _read(event, "timestamp", errors, required=True)

    if event_id and not _EVENT_ID_RE.match(event_id):
        errors.append("invalid eventId")
    if event_type not in VALID_EVENT_TYPES:
        errors.append("invalid eventType")

    value = {
        "eventId": event_id,
        "schemaVersion": schema_version,
        "eventType": event_type,
        "eventTime": _parse_datetime(timestamp, errors, "timestamp"),
        "rawEvent": event,
    }

    for field in COMMON_FIELDS:
        value[field] = _read(event, field, errors)
    value["gitUserEmail"] = value["gitUserEmail"].strip().lower()

    if event_type == "cx_codereview_issue_bypass":
        for field in BYPASS_FIELDS:
            value[field] = _read(event, field, errors)
        for field in BYPASS_JSON_FIELDS:
            value[field] = _read_json(event, field, errors)

    if event_type == "cx_codereview_push_summary":
        for field in SUMMARY_FIELDS:
            value[field] = _read(event, field, errors)
        value["bypassCount"] = _read_int(event, "bypassCount", errors)
        value["finalScore"] = _read_decimal(event, "finalScore", errors)
        value["issueCounts"] = _read_json(event, "issueCounts", errors)
        submission_time = _read(event, "submissionTime", errors)
        value["submissionTime"] = _parse_datetime(
            submission_time, errors, "submissionTime"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "value": value,
    }


def validate_batch(items):
    if not isinstance(items, list):
        return {
            "valid": False,
            "status_code": 400,
            "error": "body.items must be an array",
        }
    if len(items) > MAX_BATCH_SIZE:
        return {
            "valid": False,
            "status_code": 413,
            "error": f"batch size exceeds {MAX_BATCH_SIZE}",
        }
    return {"valid": True}
```

- [ ] **Step 5: Run schema tests and confirm they pass**

Run:

```bash
pytest tests/unit/test_schemas/test_cx_codereview_schema.py -v
```

Expected: PASS for all 7 tests.

- [ ] **Step 6: Commit schema validation**

Run:

```bash
git add api/schemas/cx_codereview_schema.py tests/unit/test_schemas/__init__.py tests/unit/test_schemas/test_cx_codereview_schema.py
git commit -m "feat: validate cx codereview events"
```

Expected: commit succeeds.

## Task 2: Code Review Database Persistence

**Files:**
- Modify: `tests/unit/test_database/test_cx_usage_db.py`
- Modify: `core/database/cx_usage_db.py`

- [ ] **Step 1: Write failing database tests**

Append this code to `tests/unit/test_database/test_cx_usage_db.py` and update the import line to include the new models:

```python
from decimal import Decimal
```

Change:

```python
from core.database.cx_usage_db import CxCommandUsageEvent, CxUsageDatabase
```

To:

```python
from core.database.cx_usage_db import (
    CxCodereviewBypass,
    CxCodereviewSummary,
    CxCommandUsageEvent,
    CxUsageDatabase,
)
```

Append:

```python

def _codereview_db():
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


def _cleanup_codereview_db(path):
    loader.config_data = {}
    db_base.global_engine = None
    if os.path.exists(path):
        os.unlink(path)


def test_insert_codereview_batch_splits_bypass_and_summary():
    db, path = _codereview_db()
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

        result = db.insert_codereview_batch([bypass_event, summary_event])

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
            assert summary.push_branch == "main"
            assert summary.bypass_count == 2
            assert summary.issue_counts == {"high": 1}
    finally:
        _cleanup_codereview_db(path)


def test_insert_codereview_batch_reports_duplicate_event_id():
    db, path = _codereview_db()
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
        _cleanup_codereview_db(path)
```

- [ ] **Step 2: Run database tests and confirm they fail**

Run:

```bash
pytest tests/unit/test_database/test_cx_usage_db.py -v
```

Expected: FAIL during collection with `ImportError` for `CxCodereviewBypass` or `CxCodereviewSummary`.

- [ ] **Step 3: Implement database models and insert method**

Modify imports in `core/database/cx_usage_db.py`:

```python
from decimal import Decimal
from sqlalchemy import String, BigInteger, DateTime, JSON, Integer, Text, Numeric, func
```

Add:

```python
from .models import gen_xid
```

Add the two model classes after `CxCommandUsageEvent`:

```python

class CxCodereviewBypass(Base):
    __tablename__ = "cx_codereview_bypasses"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    spec_id: Mapped[str] = mapped_column(String(128), nullable=True)
    spec_id_source: Mapped[str] = mapped_column(String(32), nullable=True)
    project_id: Mapped[str] = mapped_column(String(128), nullable=True)
    git_user_name: Mapped[str] = mapped_column(String(128), nullable=True)
    git_user_email: Mapped[str] = mapped_column(String(256), nullable=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=True)
    plugin_version: Mapped[str] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=True)
    push_id: Mapped[str] = mapped_column(String(80), nullable=True)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=True)
    issue_id: Mapped[str] = mapped_column(String(128), nullable=True)
    issue_title: Mapped[str] = mapped_column(String(512), nullable=True)
    issue_description: Mapped[str] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=True)
    line_range: Mapped[str] = mapped_column(String(64), nullable=True)
    code_snippet: Mapped[str] = mapped_column(Text, nullable=True)
    impact: Mapped[str] = mapped_column(Text, nullable=True)
    suggestion: Mapped[str] = mapped_column(Text, nullable=True)
    rule_ref: Mapped[str] = mapped_column(String(256), nullable=True)
    response: Mapped[str] = mapped_column(String(16), nullable=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=True)
    original_marker: Mapped[dict] = mapped_column(JSON, nullable=True)
    bypassed_marker: Mapped[dict] = mapped_column(JSON, nullable=True)
    token_name: Mapped[str] = mapped_column(String(128), nullable=True)
    raw_event: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=func.now()
    )


class CxCodereviewSummary(Base):
    __tablename__ = "cx_codereview_summaries"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    spec_id: Mapped[str] = mapped_column(String(128), nullable=True)
    spec_id_source: Mapped[str] = mapped_column(String(32), nullable=True)
    project_id: Mapped[str] = mapped_column(String(128), nullable=True)
    git_user_name: Mapped[str] = mapped_column(String(128), nullable=True)
    git_user_email: Mapped[str] = mapped_column(String(256), nullable=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=True)
    plugin_version: Mapped[str] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=True)
    push_id: Mapped[str] = mapped_column(String(80), nullable=True)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=True)
    commit_short: Mapped[str] = mapped_column(String(16), nullable=True)
    push_branch: Mapped[str] = mapped_column(String(256), nullable=True)
    push_remote: Mapped[str] = mapped_column(String(64), nullable=True)
    report_path: Mapped[str] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=True)
    bypass_count: Mapped[int] = mapped_column(Integer, nullable=True)
    final_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=True)
    grade: Mapped[str] = mapped_column(String(8), nullable=True)
    issue_counts: Mapped[dict] = mapped_column(JSON, nullable=True)
    submission_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=True)
    token_name: Mapped[str] = mapped_column(String(128), nullable=True)
    raw_event: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=True, server_default=func.now()
    )
```

Add this method inside `CxUsageDatabase`:

```python
    def insert_codereview_batch(self, events: List[Dict], token_name: Optional[str] = None) -> Dict:
        accepted, duplicated, failed = [], [], []

        with session_scope(self.engine) as session:
            for event in events:
                try:
                    if event["eventType"] == "cx_codereview_issue_bypass":
                        record = CxCodereviewBypass(
                            event_id=event["eventId"],
                            schema_version=event["schemaVersion"],
                            event_type=event["eventType"],
                            event_time=event["eventTime"],
                            spec_id=event.get("specId") or None,
                            spec_id_source=event.get("specIdSource") or None,
                            project_id=event.get("projectId") or None,
                            git_user_name=event.get("gitUserName") or None,
                            git_user_email=event.get("gitUserEmail") or None,
                            session_id=event.get("sessionId") or None,
                            plugin_version=event.get("pluginVersion") or None,
                            source=event.get("source") or None,
                            push_id=event.get("pushId") or None,
                            commit_sha=event.get("commitSha") or None,
                            issue_id=event.get("issueId") or None,
                            issue_title=event.get("issueTitle") or None,
                            issue_description=event.get("issueDescription") or None,
                            severity=event.get("severity") or None,
                            file_path=event.get("filePath") or None,
                            line_range=event.get("lineRange") or None,
                            code_snippet=event.get("codeSnippet") or None,
                            impact=event.get("impact") or None,
                            suggestion=event.get("suggestion") or None,
                            rule_ref=event.get("ruleRef") or None,
                            response=event.get("response") or None,
                            reason=event.get("reason") or None,
                            original_marker=event.get("originalMarker"),
                            bypassed_marker=event.get("bypassedMarker"),
                            token_name=token_name,
                            raw_event=event.get("rawEvent"),
                        )
                    elif event["eventType"] == "cx_codereview_push_summary":
                        record = CxCodereviewSummary(
                            event_id=event["eventId"],
                            schema_version=event["schemaVersion"],
                            event_type=event["eventType"],
                            event_time=event["eventTime"],
                            spec_id=event.get("specId") or None,
                            spec_id_source=event.get("specIdSource") or None,
                            project_id=event.get("projectId") or None,
                            git_user_name=event.get("gitUserName") or None,
                            git_user_email=event.get("gitUserEmail") or None,
                            session_id=event.get("sessionId") or None,
                            plugin_version=event.get("pluginVersion") or None,
                            source=event.get("source") or None,
                            push_id=event.get("pushId") or None,
                            commit_sha=event.get("commitSha") or None,
                            commit_short=event.get("commitShort") or None,
                            push_branch=event.get("pushBranch") or None,
                            push_remote=event.get("pushRemote") or None,
                            report_path=event.get("reportPath") or None,
                            review_status=event.get("reviewStatus") or None,
                            bypass_count=event.get("bypassCount"),
                            final_score=event.get("finalScore"),
                            grade=event.get("grade") or None,
                            issue_counts=event.get("issueCounts"),
                            submission_time=event.get("submissionTime"),
                            token_name=token_name,
                            raw_event=event.get("rawEvent"),
                        )
                    else:
                        failed.append(event.get("eventId", ""))
                        continue

                    session.add(record)
                    session.flush()
                    accepted.append(event["eventId"])
                except IntegrityError:
                    session.rollback()
                    duplicated.append(event["eventId"])
                except Exception:
                    session.rollback()
                    failed.append(event["eventId"])

        return {"accepted": accepted, "duplicated": duplicated, "failed": failed}
```

- [ ] **Step 4: Run database tests and confirm they pass**

Run:

```bash
pytest tests/unit/test_database/test_cx_usage_db.py -v
```

Expected: PASS for all tests in the file.

- [ ] **Step 5: Commit database persistence**

Run:

```bash
git add core/database/cx_usage_db.py tests/unit/test_database/test_cx_usage_db.py
git commit -m "feat: persist cx codereview events"
```

Expected: commit succeeds.

## Task 3: Code Review Batch Route

**Files:**
- Create: `tests/integration/test_cx_codereview_api.py`
- Modify: `api/routes/cx_usage.py`

- [ ] **Step 1: Write failing route tests**

Create `tests/integration/test_cx_codereview_api.py`:

```python
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
    data = response.get_json()
    assert data == {
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
    assert len(db.insert_codereview_batch.call_args.args[0]) == 1


def test_codereview_events_batch_rejects_non_array(client):
    response = client.post(
        "/api/v1/cx-aicode/codereview/events/batch",
        json={"items": {"not": "array"}},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["error"] == "body.items must be an array"


def test_codereview_events_batch_rejects_large_batch(client):
    response = client.post(
        "/api/v1/cx-aicode/codereview/events/batch",
        json={"items": [_bypass_event(f"evt_codereview_{i:012d}") for i in range(101)]},
    )

    assert response.status_code == 413
    data = response.get_json()
    assert data["success"] is False
    assert data["error"] == "batch size exceeds 100"


def test_codereview_events_batch_returns_503_when_database_unavailable(client):
    with patch("core.database.cx_usage_db.CxUsageDatabase") as db_cls:
        db_cls.side_effect = RuntimeError("database down")

        response = client.post(
            "/api/v1/cx-aicode/codereview/events/batch",
            json={"items": [_bypass_event()]},
        )

    assert response.status_code == 503
    data = response.get_json()
    assert data["success"] is False
    assert data["error"] == "database unavailable"
    assert data["failed"] == ["evt_codereview_202606080201"]
```

- [ ] **Step 2: Run route tests and confirm they fail**

Run:

```bash
pytest tests/integration/test_cx_codereview_api.py -v
```

Expected: FAIL with `404 NOT FOUND` for `/api/v1/cx-aicode/codereview/events/batch`.

- [ ] **Step 3: Implement the route**

Modify the import in `api/routes/cx_usage.py`:

```python
from api.schemas.cx_usage_schema import validate_batch, validate_event
from api.schemas.cx_codereview_schema import (
    validate_batch as validate_codereview_batch,
    validate_codereview_event,
)
```

Append this route below `events_batch()`:

```python

@cx_usage_bp.route("/codereview/events/batch", methods=["POST"])
def codereview_events_batch():
    body = request.get_json(silent=True) or {}
    items = body.get("items", [])

    batch_result = validate_codereview_batch(items)
    if not batch_result["valid"]:
        return jsonify({"success": False, "error": batch_result["error"]}), batch_result["status_code"]

    valid_events, failed = [], []
    for i, item in enumerate(items):
        result = validate_codereview_event(item)
        if result["valid"]:
            valid_events.append(result["value"])
        else:
            event_id = item.get("eventId") if isinstance(item, dict) else None
            failed.append(str(event_id) if event_id else f"invalid:{i}")

    try:
        from core.database.cx_usage_db import CxUsageDatabase

        db = CxUsageDatabase()
        inserted = db.insert_codereview_batch(valid_events)
        all_failed = inserted["failed"] + failed
        return jsonify({
            "success": len(all_failed) == 0,
            "accepted": inserted["accepted"],
            "duplicated": inserted["duplicated"],
            "failed": all_failed,
        })
    except Exception as e:
        logger.error(f"cx_usage codereview/events/batch error: {e}", exc_info=True)
        all_failed = [ev["eventId"] for ev in valid_events] + failed
        return jsonify({
            "success": False,
            "error": "database unavailable",
            "accepted": [],
            "duplicated": [],
            "failed": all_failed,
        }), 503
```

- [ ] **Step 4: Run route tests and confirm they pass**

Run:

```bash
pytest tests/integration/test_cx_codereview_api.py -v
```

Expected: PASS for all 5 tests.

- [ ] **Step 5: Commit route implementation**

Run:

```bash
git add api/routes/cx_usage.py tests/integration/test_cx_codereview_api.py
git commit -m "feat: add cx codereview batch endpoint"
```

Expected: commit succeeds.

## Task 4: Full Verification

**Files:**
- Verify only; no file edits.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
pytest tests/unit/test_schemas/test_cx_codereview_schema.py tests/unit/test_database/test_cx_usage_db.py tests/integration/test_cx_codereview_api.py -v
```

Expected: PASS for all focused tests.

- [ ] **Step 2: Run broader existing API/database tests**

Run:

```bash
pytest tests/unit/test_database/test_cx_usage_db.py tests/integration/test_api.py tests/integration/test_cx_codereview_api.py -v
```

Expected: PASS for all selected tests.

- [ ] **Step 3: Check git status**

Run:

```bash
git status --short
```

Expected: no uncommitted changes.

- [ ] **Step 4: Report completion**

Summarize:

- Endpoint added: `POST /api/v1/cx-aicode/codereview/events/batch`.
- Event routing: `cx_codereview_issue_bypass` to `cx_codereview_bypasses`; `cx_codereview_push_summary` to `cx_codereview_summaries`.
- Verification commands and results.
