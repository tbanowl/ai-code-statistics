from collections.abc import Iterable
from typing import Any

from core.config import load_config
from core.config.logging import Logger
from core.database.models import OtelInvocationCount, now_ts
from core.database.otel_logs_db import OtelLogsDatabase

MAX_FIELD_LENGTH = 200
MAX_TIME_UNIX_NANO_LENGTH = 30
SKILL_ACTIVATED_EVENT_NAMES = frozenset(
    {"claude_code.skill_activated", "skill_activated"}
)


class OtelLogsService:

    def __init__(
        self,
        database: OtelLogsDatabase | None = None,
        require_org_user: bool | None = None,
    ):
        self.logger = Logger.get_logger("services.otel_logs")
        self.database = database or OtelLogsDatabase()
        config = load_config().get("otel", {}).get("receiver", {}).get("logs", {})
        self.require_org_user = (
            bool(config.get("require_org_user", True))
            if require_org_user is None
            else require_org_user
        )
        self.max_log_records = int(config.get("max_log_records_per_request", 1000))

    def process_logs(self, payload: dict[str, Any]) -> dict[str, Any]:
        records: list[OtelInvocationCount] = []
        errors: list[dict[str, Any]] = []
        skipped = 0
        seen = 0
        received_at = now_ts()

        for resource_log in self._iter_list(payload.get("resourceLogs")):
            resource_attrs = self._attrs_to_dict(
                resource_log.get("resource", {}).get("attributes", [])
            )
            for scope_log in self._iter_list(resource_log.get("scopeLogs")):
                for log_record in self._iter_list(scope_log.get("logRecords")):
                    seen += 1
                    if seen > self.max_log_records:
                        skipped += 1
                        errors.append(
                            {
                                "index": seen - 1,
                                "error": "max_log_records_per_request exceeded",
                            }
                        )
                        continue

                    normalized = self._normalize_log_record(
                        log_record,
                        resource_attrs,
                        received_at,
                    )
                    if isinstance(normalized, OtelInvocationCount):
                        records.append(normalized)
                    else:
                        skipped += 1
                        if normalized:
                            errors.append({"index": seen - 1, "error": normalized})

        accepted = self.database.save_invocation_counts(records) if records else 0
        return {
            "success": True,
            "accepted": accepted,
            "skipped": skipped,
            "errors": errors,
        }

    def _normalize_log_record(
        self,
        log_record: dict[str, Any],
        resource_attrs: dict[str, Any],
        received_at: int,
    ) -> OtelInvocationCount | str | None:
        attrs = self._attrs_to_dict(log_record.get("attributes", []))
        event_name = log_record.get("eventName") or attrs.get("event.name")
        if event_name not in SKILL_ACTIVATED_EVENT_NAMES:
            return None

        attrs_event_name = attrs.get("event.name")
        if attrs_event_name is not None and attrs_event_name != "skill_activated":
            return None

        skill_source = attrs.get("skill.source")
        if skill_source != "plugin":
            return None

        plugin_name = self._clean_string(attrs.get("plugin.name"))
        skill_name = self._clean_string(attrs.get("skill.name"))
        org_user = self._clean_string(resource_attrs.get("org.user"))

        if not plugin_name:
            return "missing plugin.name for plugin skill activation"
        if not skill_name:
            return "missing skill.name for plugin skill activation"
        if skill_name == "custom_skill":
            return (
                "skill.name is custom_skill; set OTEL_LOG_TOOL_DETAILS=1 in Claude Code"
            )
        if self.require_org_user and not org_user:
            return "missing required resource attribute org.user"

        return OtelInvocationCount(
            source="claude_code",
            category="skill",
            plugin_name=plugin_name,
            skill_name=skill_name,
            invocation_trigger=self._clean_string(attrs.get("invocation_trigger")),
            org_user=org_user or "unknown",
            service_name=self._clean_string(resource_attrs.get("service.name")),
            service_version=self._clean_string(resource_attrs.get("service.version")),
            count=1,
            time_unix_nano=self._clean_string(
                log_record.get("timeUnixNano"),
                max_length=MAX_TIME_UNIX_NANO_LENGTH,
            ),
            received_at=received_at,
        )

    @staticmethod
    def _iter_list(value: Any) -> Iterable[dict[str, Any]]:
        if isinstance(value, list):
            return (item for item in value if isinstance(item, dict))
        return iter(())

    @classmethod
    def _attrs_to_dict(cls, attrs: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if not isinstance(attrs, list):
            return result

        for attr in attrs:
            if not isinstance(attr, dict):
                continue
            key = attr.get("key")
            if not isinstance(key, str):
                continue
            result[key] = cls._decode_any_value(attr.get("value", {}))
        return result

    @staticmethod
    def _decode_any_value(value: Any) -> Any:
        if not isinstance(value, dict):
            return None
        for field in (
            "stringValue",
            "boolValue",
            "intValue",
            "doubleValue",
            "bytesValue",
        ):
            if field in value:
                return value[field]
        return None

    @staticmethod
    def _clean_string(value: Any, max_length: int = MAX_FIELD_LENGTH) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text[:max_length]
