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


def test_validate_rejects_non_integral_bypass_count_values():
    for invalid_value in (True, 1.9, "1.9", "many"):
        event = _base_event("cx_codereview_push_summary")
        event["eventId"] = f"evt_codereview_count_{str(invalid_value).replace('.', '_')}"
        event["bypassCount"] = invalid_value

        result = validate_codereview_event(event)

        assert result["valid"] is False
        assert "invalid bypassCount" in result["errors"]


def test_validate_rejects_oversized_bypass_count_without_raising():
    event = _base_event("cx_codereview_push_summary")
    event["eventId"] = "evt_codereview_count_oversized"
    event["bypassCount"] = "1" * 5000

    result = validate_codereview_event(event)

    assert result["valid"] is False
    assert "invalid bypassCount" in result["errors"]


def test_validate_rejects_invalid_final_score_shape():
    for invalid_value in ("NaN", "Infinity", "1000.00", "1.234"):
        event = _base_event("cx_codereview_push_summary")
        event["eventId"] = f"evt_codereview_score_{invalid_value.replace('.', '_')}"
        event["finalScore"] = invalid_value

        result = validate_codereview_event(event)

        assert result["valid"] is False
        assert "invalid finalScore" in result["errors"]


def test_validate_summary_json_fields_allow_lists():
    event = _base_event("cx_codereview_push_summary")
    event.update(
        {
            "eventId": "evt_codereview_202606080004",
            "issueCounts": [{"severity": "high", "count": 1}],
        }
    )

    result = validate_codereview_event(event)

    assert result["valid"] is True
    assert result["value"]["issueCounts"] == [{"severity": "high", "count": 1}]


def test_validate_rejects_fixed_string_limit_violations():
    event = _base_event("cx_codereview_push_summary")
    event["gitUserEmail"] = "a" * 257
    event["pushBranch"] = "b" * 257

    result = validate_codereview_event(event)

    assert result["valid"] is False
    assert "gitUserEmail too long" in result["errors"]
    assert "pushBranch too long" in result["errors"]


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
