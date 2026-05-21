import re
from datetime import datetime, timezone

TRACKED_COMMANDS = {
    "cx-spec", "cx-brainstorm", "cx-work",
    "cx-codereview", "cx-verify", "cx-test", "cx-debug"
}

VALID_EVENT_TYPES = {"cx_command_invoked", "cx_specid_update"}

FIELD_LIMITS = {
    "eventId": 80, "schemaVersion": 16, "eventType": 64, "command": 64,
    "specId": 128, "timestamp": 64, "specIdSource": 32, "projectId": 128,
    "gitUserName": 128, "gitUserEmail": 256, "sessionId": 128,
    "pluginVersion": 32, "source": 64, "warning": 128,
}

_EVENT_ID_RE = re.compile(r"^evt_[A-Za-z0-9._-]{8,76}$")

MAX_BATCH_SIZE = 100


def _read(event, key, errors, required=False):
    value = str(event.get(key) or "")
    if required and not value:
        errors.append(f"missing {key}")
    elif value and len(value) > FIELD_LIMITS[key]:
        errors.append(f"{key} too long")
    return value


def validate_event(event):
    if not isinstance(event, dict):
        return {"valid": False, "errors": ["event must be an object"]}

    errors = []
    event_id = _read(event, "eventId", errors)
    schema_version = _read(event, "schemaVersion", errors, required=True)
    event_type = _read(event, "eventType", errors)
    command = _read(event, "command", errors)
    spec_id = _read(event, "specId", errors, required=True)
    timestamp = _read(event, "timestamp", errors)

    if not _EVENT_ID_RE.match(event_id):
        errors.append("invalid eventId")
    if event_type not in VALID_EVENT_TYPES:
        errors.append("invalid eventType")
    if event_type == "cx_command_invoked" and command not in TRACKED_COMMANDS:
        errors.append("invalid command")

    event_time = None
    try:
        event_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        errors.append("invalid timestamp")

    spec_id_source = _read(event, "specIdSource", errors)
    project_id = _read(event, "projectId", errors)
    git_user_name = _read(event, "gitUserName", errors)
    git_user_email = _read(event, "gitUserEmail", errors).strip().lower()
    session_id = _read(event, "sessionId", errors)
    plugin_version = _read(event, "pluginVersion", errors)
    source = _read(event, "source", errors)
    warning = _read(event, "warning", errors)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "value": {
            "eventId": event_id,
            "schemaVersion": schema_version,
            "eventType": event_type,
            "eventTime": event_time,
            "command": command,
            "specId": spec_id,
            "specIdSource": spec_id_source,
            "projectId": project_id,
            "gitUserName": git_user_name,
            "gitUserEmail": git_user_email,
            "sessionId": session_id,
            "pluginVersion": plugin_version,
            "source": source,
            "warning": warning,
            "rawEvent": event,
        },
    }


def validate_batch(items):
    if not isinstance(items, list):
        return {"valid": False, "status_code": 400, "error": "body.items must be an array"}
    if len(items) > MAX_BATCH_SIZE:
        return {"valid": False, "status_code": 413, "error": f"batch size exceeds {MAX_BATCH_SIZE}"}
    return {"valid": True}
