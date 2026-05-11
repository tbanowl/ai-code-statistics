"""Tests for OtelLogsService OTLP JSON Logs parsing."""

from unittest.mock import Mock

import pytest

from core.services.otel_logs_service import OtelLogsService


def _attr(key, value):
    """Build a single OTLP key-value attribute with stringValue."""
    return {"key": key, "value": {"stringValue": value}}


def _attr_typed(key, value, field):
    """Build an OTLP attribute with a specific AnyValue field."""
    return {"key": key, "value": {field: value}}


def _payload(
    log_attrs,
    resource_attrs=None,
    event_name="claude_code.skill_activated",
    time_unix_nano="1770000000000000000",
):
    """Build a minimal OTLP JSON Logs payload with one log record."""
    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": resource_attrs
                    or [
                        _attr("service.name", "claude-code"),
                        _attr("service.version", "2.1.126"),
                        _attr("org.user", "user-123"),
                    ]
                },
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "eventName": event_name,
                                "timeUnixNano": time_unix_nano,
                                "attributes": log_attrs,
                            }
                        ]
                    }
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# Core acceptance test
# ---------------------------------------------------------------------------


def test_process_logs_accepts_plugin_skill_activation():
    db = Mock()
    db.save_invocation_counts.return_value = 1
    service = OtelLogsService(database=db)

    result = service.process_logs(
        _payload(
            [
                _attr("event.name", "skill_activated"),
                _attr("skill.source", "plugin"),
                _attr("plugin.name", "superpowers"),
                _attr("skill.name", "brainstorming"),
                _attr("invocation_trigger", "user-slash"),
            ]
        )
    )

    assert result == {"success": True, "accepted": 1, "skipped": 0, "errors": []}
    saved = db.save_invocation_counts.call_args.args[0]
    assert len(saved) == 1
    assert saved[0].plugin_name == "superpowers"
    assert saved[0].skill_name == "brainstorming"
    assert saved[0].invocation_trigger == "user-slash"
    assert saved[0].org_user == "user-123"
    assert saved[0].service_name == "claude-code"
    assert saved[0].service_version == "2.1.126"
    assert saved[0].count == 1


# ---------------------------------------------------------------------------
# Event filtering
# ---------------------------------------------------------------------------


def test_process_logs_skips_non_skill_event():
    db = Mock()
    service = OtelLogsService(database=db)

    result = service.process_logs(
        _payload(
            [_attr("event.name", "user_prompt")],
            event_name="claude_code.user_prompt",
        )
    )

    assert result["success"] is True
    assert result["accepted"] == 0
    assert result["skipped"] == 1
    db.save_invocation_counts.assert_not_called()


def test_process_logs_skips_non_plugin_source():
    db = Mock()
    service = OtelLogsService(database=db)

    result = service.process_logs(
        _payload(
            [
                _attr("event.name", "skill_activated"),
                _attr("skill.source", "builtin"),
                _attr("plugin.name", "superpowers"),
                _attr("skill.name", "brainstorming"),
            ]
        )
    )

    assert result["accepted"] == 0
    db.save_invocation_counts.assert_not_called()


def test_process_logs_skips_custom_skill_placeholder():
    db = Mock()
    service = OtelLogsService(database=db)

    result = service.process_logs(
        _payload(
            [
                _attr("event.name", "skill_activated"),
                _attr("skill.source", "plugin"),
                _attr("plugin.name", "superpowers"),
                _attr("skill.name", "custom_skill"),
            ]
        )
    )

    assert result["accepted"] == 0
    assert result["skipped"] == 1
    assert "OTEL_LOG_TOOL_DETAILS=1" in result["errors"][0]["error"]
    db.save_invocation_counts.assert_not_called()


# ---------------------------------------------------------------------------
# eventName variants
# ---------------------------------------------------------------------------


def test_accepts_skill_activated_event_name():
    """ eventName == 'skill_activated' should also be accepted. """
    db = Mock()
    db.save_invocation_counts.return_value = 1
    service = OtelLogsService(database=db)

    result = service.process_logs(
        _payload(
            [
                _attr("event.name", "skill_activated"),
                _attr("skill.source", "plugin"),
                _attr("plugin.name", "superpowers"),
                _attr("skill.name", "brainstorming"),
            ],
            event_name="skill_activated",
        )
    )

    assert result["accepted"] == 1


def test_accepts_via_attr_event_name():
    """ When eventName is missing but attrs contain event.name == 'skill_activated'. """
    db = Mock()
    db.save_invocation_counts.return_value = 1
    service = OtelLogsService(database=db)

    payload = _payload(
        [
            _attr("event.name", "skill_activated"),
            _attr("skill.source", "plugin"),
            _attr("plugin.name", "superpowers"),
            _attr("skill.name", "brainstorming"),
        ],
        event_name="skill_activated",
    )
    # Remove top-level eventName to force attr fallback
    del payload["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]["eventName"]

    result = service.process_logs(payload)

    assert result["accepted"] == 1


# ---------------------------------------------------------------------------
# require_org_user enforcement
# ---------------------------------------------------------------------------


def test_process_logs_requires_org_user_when_configured():
    db = Mock()
    service = OtelLogsService(database=db, require_org_user=True)

    result = service.process_logs(
        _payload(
            [
                _attr("event.name", "skill_activated"),
                _attr("skill.source", "plugin"),
                _attr("plugin.name", "superpowers"),
                _attr("skill.name", "brainstorming"),
            ],
            resource_attrs=[_attr("service.name", "claude-code")],
        )
    )

    assert result["accepted"] == 0
    assert result["skipped"] == 1
    assert "org.user" in result["errors"][0]["error"]
    db.save_invocation_counts.assert_not_called()


def test_process_logs_accepts_missing_org_user_when_not_required():
    db = Mock()
    db.save_invocation_counts.return_value = 1
    service = OtelLogsService(database=db, require_org_user=False)

    result = service.process_logs(
        _payload(
            [
                _attr("event.name", "skill_activated"),
                _attr("skill.source", "plugin"),
                _attr("plugin.name", "superpowers"),
                _attr("skill.name", "brainstorming"),
            ],
            resource_attrs=[_attr("service.name", "claude-code")],
        )
    )

    assert result["accepted"] == 1
    saved = db.save_invocation_counts.call_args.args[0]
    assert saved[0].org_user == "unknown"


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------


def test_skips_missing_plugin_name():
    db = Mock()
    service = OtelLogsService(database=db)

    result = service.process_logs(
        _payload(
            [
                _attr("event.name", "skill_activated"),
                _attr("skill.source", "plugin"),
                _attr("skill.name", "brainstorming"),
            ]
        )
    )

    assert result["accepted"] == 0
    assert "plugin.name" in result["errors"][0]["error"]


def test_skips_missing_skill_name():
    db = Mock()
    service = OtelLogsService(database=db)

    result = service.process_logs(
        _payload(
            [
                _attr("event.name", "skill_activated"),
                _attr("skill.source", "plugin"),
                _attr("plugin.name", "superpowers"),
            ]
        )
    )

    assert result["accepted"] == 0
    assert "skill.name" in result["errors"][0]["error"]


# ---------------------------------------------------------------------------
# AnyValue decoding
# ---------------------------------------------------------------------------


def test_decodes_bool_value():
    db = Mock()
    db.save_invocation_counts.return_value = 1
    service = OtelLogsService(database=db)

    attrs = [
        _attr_typed("event.name", True, "boolValue"),
        _attr("skill.source", "plugin"),
        _attr("plugin.name", "superpowers"),
        _attr("skill.name", "brainstorming"),
    ]
    result = service.process_logs(_payload(attrs))

    # event.name should be True (bool), not matching "skill_activated" string
    # so it should be skipped
    assert result["accepted"] == 0
    assert result["skipped"] == 1


def test_decodes_int_value():
    assert OtelLogsService._decode_any_value({"intValue": 42}) == 42


def test_decodes_double_value():
    assert OtelLogsService._decode_any_value({"doubleValue": 3.14}) == 3.14


def test_decodes_string_value():
    assert OtelLogsService._decode_any_value({"stringValue": "hello"}) == "hello"


def test_decode_returns_none_for_empty():
    assert OtelLogsService._decode_any_value({}) is None
    assert OtelLogsService._decode_any_value("not a dict") is None


# ---------------------------------------------------------------------------
# Field length limits
# ---------------------------------------------------------------------------


def test_truncates_long_field_values():
    db = Mock()
    db.save_invocation_counts.return_value = 1
    service = OtelLogsService(database=db)

    long_name = "x" * 300
    result = service.process_logs(
        _payload(
            [
                _attr("event.name", "skill_activated"),
                _attr("skill.source", "plugin"),
                _attr("plugin.name", long_name),
                _attr("skill.name", "brainstorming"),
            ]
        )
    )

    assert result["accepted"] == 1
    saved = db.save_invocation_counts.call_args.args[0]
    assert saved[0].plugin_name is not None
    assert len(saved[0].plugin_name) == 200


def test_truncates_time_unix_nano():
    db = Mock()
    db.save_invocation_counts.return_value = 1
    service = OtelLogsService(database=db)

    long_nano = "1" * 50
    result = service.process_logs(
        _payload(
            [
                _attr("event.name", "skill_activated"),
                _attr("skill.source", "plugin"),
                _attr("plugin.name", "superpowers"),
                _attr("skill.name", "brainstorming"),
            ],
            time_unix_nano=long_nano,
        )
    )

    assert result["accepted"] == 1
    saved = db.save_invocation_counts.call_args.args[0]
    assert saved[0].time_unix_nano is not None
    assert len(saved[0].time_unix_nano) == 30


# ---------------------------------------------------------------------------
# Empty / malformed payloads
# ---------------------------------------------------------------------------


def test_empty_payload():
    db = Mock()
    service = OtelLogsService(database=db)

    result = service.process_logs({})

    assert result == {"success": True, "accepted": 0, "skipped": 0, "errors": []}
    db.save_invocation_counts.assert_not_called()


def test_empty_resource_logs():
    db = Mock()
    service = OtelLogsService(database=db)

    result = service.process_logs({"resourceLogs": []})

    assert result["accepted"] == 0
    assert result["skipped"] == 0


def test_null_resource_logs():
    db = Mock()
    service = OtelLogsService(database=db)

    result = service.process_logs({"resourceLogs": None})

    assert result["accepted"] == 0


def test_multiple_log_records():
    db = Mock()
    db.save_invocation_counts.return_value = 2
    service = OtelLogsService(database=db)

    payload = {
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
                                "timeUnixNano": "1770000000000000000",
                                "attributes": [
                                    _attr("event.name", "skill_activated"),
                                    _attr("skill.source", "plugin"),
                                    _attr("plugin.name", "superpowers"),
                                    _attr("skill.name", "brainstorming"),
                                ],
                            },
                            {
                                "eventName": "claude_code.skill_activated",
                                "timeUnixNano": "1770000000000000001",
                                "attributes": [
                                    _attr("event.name", "skill_activated"),
                                    _attr("skill.source", "plugin"),
                                    _attr("plugin.name", "superpowers"),
                                    _attr("skill.name", "verification-before-completion"),
                                ],
                            },
                        ]
                    }
                ],
            }
        ]
    }

    result = service.process_logs(payload)

    assert result["accepted"] == 2
    assert result["skipped"] == 0


# ---------------------------------------------------------------------------
# attrs_to_dict
# ---------------------------------------------------------------------------


def test_attrs_to_dict_handles_malformed():
    result = OtelLogsService._attrs_to_dict("not a list")
    assert result == {}

    result = OtelLogsService._attrs_to_dict([{"no_key": "value"}])
    assert result == {}

    result = OtelLogsService._attrs_to_dict([123, None])
    assert result == {}


# ---------------------------------------------------------------------------
# _clean_string
# ---------------------------------------------------------------------------


def test_clean_string_truncates_to_max():
    long = "a" * 300
    result = OtelLogsService._clean_string(long, max_length=200)
    assert result is not None
    assert len(result) == 200


def test_clean_string_returns_none_for_none():
    assert OtelLogsService._clean_string(None) is None


def test_clean_string_returns_none_for_empty():
    assert OtelLogsService._clean_string("") is None
    assert OtelLogsService._clean_string("   ") is None


def test_clean_string_strips_whitespace():
    assert OtelLogsService._clean_string("  hello  ") == "hello"
