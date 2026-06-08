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
    if isinstance(value, bool):
        errors.append(f"invalid {key}")
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            try:
                return int(stripped)
            except ValueError:
                errors.append(f"invalid {key}")
                return None
        errors.append(f"invalid {key}")
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        decimal_value = None
    is_integral_decimal = (
        decimal_value is not None
        and decimal_value.is_finite()
        and decimal_value == decimal_value.to_integral_value()
    )
    if is_integral_decimal:
        return int(decimal_value)
    errors.append(f"invalid {key}")
    return None


def _read_decimal(event, key, errors):
    value = event.get(key)
    if value in (None, ""):
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        errors.append(f"invalid {key}")
        return None
    if (
        not decimal_value.is_finite()
        or abs(decimal_value) > Decimal("999.99")
        or decimal_value.as_tuple().exponent < -2
    ):
        errors.append(f"invalid {key}")
        return None
    return decimal_value


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
        for field in SUMMARY_JSON_FIELDS:
            value[field] = _read_json(event, field, errors)
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
