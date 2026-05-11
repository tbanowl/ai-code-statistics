# Claude Code OTLP Logs Invocation Counts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent OTLP JSON Logs receiver that records Claude Code plugin Skill activation counts with `plugin_name`, `skill_name`, `invocation_trigger`, and custom `org.user` resource metadata.

**Architecture:** Add a new `/v1/logs` Flask route that delegates OTLP JSON parsing to a focused service and persists normalized invocation rows through a small database access class. The new flow is intentionally separate from the existing `/worker/metrics/upload` Git-AI Metrics pipeline, and existing metrics route/service/task files must not be modified.

**Tech Stack:** Python 3.10+, Flask, SQLAlchemy 2.0 ORM, SQLite-backed pytest tests, OTLP HTTP JSON Logs shape, YAML config.

---

## File Structure

### Create

- `core/database/otel_logs_db.py`
  - Owns writes for OTLP-derived invocation records.
  - Uses existing `BaseDatabase` and `session_scope` conventions.
- `core/services/otel_logs_service.py`
  - Parses OTLP JSON Logs requests.
  - Extracts resource attributes and `skill_activated` log record attributes.
  - Validates `plugin.name`, `skill.name`, `invocation_trigger`, and `org.user`.
- `api/routes/otel_receiver.py`
  - Defines `otel_receiver_bp` and routes `POST /v1/logs` plus `POST /worker/otel/v1/logs`.
  - Returns `{"success": true, "accepted": N, "skipped": N, "errors": []}` style responses.
- `tests/unit/test_database/test_otel_logs_db.py`
  - Verifies DB insert and query behavior for `OtelInvocationCount`.
- `tests/unit/test_services/test_otel_logs_service.py`
  - Verifies OTLP logs parsing and validation rules.
- `tests/integration/test_otel_receiver_api.py`
  - Verifies both HTTP endpoints and error behavior.

### Modify

- `core/database/models.py`
  - Add `OtelInvocationCount` ORM model.
- `core/database/__init__.py`
  - Export `OtelLogsDatabase`.
- `app.py`
  - Register the new OTLP receiver blueprint.
- `config.yaml`
  - Add `otel.receiver.logs` configuration defaults.
- `sql/metrics_schema_mysql.sql`
  - Add MySQL DDL for `otel_invocation_counts`.

### Must Not Modify

- `api/routes/git_ai_worker.py`
- `core/services/metrics_service.py`
- `core/scheduler/tasks/metrics_event_processor_task.py`

---

## Task 1: Model and SQL schema for OTLP invocation counts

**Files:**
- Modify: `core/database/models.py`
- Modify: `sql/metrics_schema_mysql.sql`
- Test: `tests/unit/test_models/test_metrics.py`

- [ ] **Step 1: Write failing model tests**

Append these tests to `tests/unit/test_models/test_metrics.py`:

```python
from core.database.models import OtelInvocationCount


def test_otel_invocation_count_fields():
    columns = {c.name for c in OtelInvocationCount.__table__.columns}

    expected_columns = {
        "id",
        "source",
        "category",
        "plugin_name",
        "skill_name",
        "invocation_trigger",
        "org_user",
        "service_name",
        "service_version",
        "count",
        "time_unix_nano",
        "received_at",
        "created_at",
    }

    assert expected_columns.issubset(columns), (
        f"Missing columns: {expected_columns - columns}"
    )


def test_otel_invocation_count_indexes():
    indexes = {i.name for i in getattr(OtelInvocationCount.__table__, "indexes", set())}

    assert "idx_otel_invocation_received_at" in indexes
    assert "idx_otel_invocation_org_plugin_skill" in indexes
```

- [ ] **Step 2: Run model tests and verify failure**

Run:

```bash
pytest tests/unit/test_models/test_metrics.py -v
```

Expected: FAIL with `ImportError` or `NameError` because `OtelInvocationCount` does not exist.

- [ ] **Step 3: Add the ORM model**

Add this model in `core/database/models.py` near the Metrics event models, after `MetricsEventErrors` and before the CAS model section:

```python
class OtelInvocationCount(ModelBase):
    """Claude Code OTLP Logs Skill 调用计数表。"""

    __tablename__ = "otel_invocation_counts"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="claude_code")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="skill")
    plugin_name: Mapped[str] = mapped_column(String(200), nullable=False)
    skill_name: Mapped[str] = mapped_column(String(200), nullable=False)
    invocation_trigger: Mapped[str] = mapped_column(String(50), nullable=True)
    org_user: Mapped[str] = mapped_column(String(200), nullable=False)
    service_name: Mapped[str] = mapped_column(String(200), nullable=True)
    service_version: Mapped[str] = mapped_column(String(100), nullable=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    time_unix_nano: Mapped[str] = mapped_column(String(30), nullable=True)
    received_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)

    __table_args__ = (
        Index("idx_otel_invocation_received_at", "received_at"),
        Index(
            "idx_otel_invocation_org_plugin_skill",
            "org_user",
            "plugin_name",
            "skill_name",
        ),
    )
```

- [ ] **Step 4: Add MySQL DDL**

Append this DDL to `sql/metrics_schema_mysql.sql` after the existing metrics event tables and before unrelated domain tables:

```sql
-- Claude Code OTLP Logs Skill 调用计数表
CREATE TABLE IF NOT EXISTS otel_invocation_counts (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    source VARCHAR(50) NOT NULL DEFAULT 'claude_code' COMMENT '遥测来源',
    category VARCHAR(50) NOT NULL DEFAULT 'skill' COMMENT '调用类型，第一阶段固定为 skill',
    plugin_name VARCHAR(200) NOT NULL COMMENT '插件名称，例如 superpowers',
    skill_name VARCHAR(200) NOT NULL COMMENT 'Skill 名称，例如 brainstorming',
    invocation_trigger VARCHAR(50) COMMENT '触发方式，例如 user-slash',
    org_user VARCHAR(200) NOT NULL COMMENT '自定义用户 ID，来自 OTEL_RESOURCE_ATTRIBUTES org.user',
    service_name VARCHAR(200) COMMENT 'OTEL resource service.name',
    service_version VARCHAR(100) COMMENT 'OTEL resource service.version',
    count INT NOT NULL DEFAULT 1 COMMENT '调用次数，按 log record 逐条保存时固定为 1',
    time_unix_nano VARCHAR(30) COMMENT 'OTLP log record timeUnixNano',
    received_at BIGINT NOT NULL COMMENT '服务端接收时间戳（毫秒）',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    INDEX idx_otel_invocation_received_at (received_at),
    INDEX idx_otel_invocation_org_plugin_skill (org_user, plugin_name, skill_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Claude Code OTLP Logs Skill 调用计数表';
```

- [ ] **Step 5: Run model tests and verify pass**

Run:

```bash
pytest tests/unit/test_models/test_metrics.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Only commit if the user explicitly requested commits during execution. If commits are allowed, run:

```bash
git add core/database/models.py sql/metrics_schema_mysql.sql tests/unit/test_models/test_metrics.py
git commit -m "feat: add otlp invocation count schema"
```

---

## Task 2: Database access for OTLP invocation counts

**Files:**
- Create: `core/database/otel_logs_db.py`
- Modify: `core/database/__init__.py`
- Test: `tests/unit/test_database/test_otel_logs_db.py`

- [ ] **Step 1: Write failing database tests**

Create `tests/unit/test_database/test_otel_logs_db.py`:

```python
import importlib
import os
import tempfile
import time

import pytest

import core.config.loader as loader


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    time.sleep(0.1)
    for _ in range(5):
        try:
            if os.path.exists(path):
                os.unlink(path)
            break
        except PermissionError:
            time.sleep(0.2)


@pytest.fixture
def otel_db(temp_db_path):
    loader.config_data = {
        "features": {"enabled": True},
        "git": {"type": "github"},
        "database": {"url": f"sqlite:///{temp_db_path}", "echo": False},
    }
    import core.database.base as db_base
    import core.database.models as db_models
    import core.database.otel_logs_db as otel_logs_db_module

    importlib.reload(db_base)
    importlib.reload(db_models)
    importlib.reload(otel_logs_db_module)

    db = otel_logs_db_module.OtelLogsDatabase()
    db_base.Base.metadata.create_all(db.engine)
    return db


def test_save_invocation_counts_persists_records(otel_db):
    from core.database.base import session_scope
    from core.database.models import OtelInvocationCount

    records = [
        OtelInvocationCount(
            source="claude_code",
            category="skill",
            plugin_name="superpowers",
            skill_name="brainstorming",
            invocation_trigger="user-slash",
            org_user="user-123",
            service_name="claude-code",
            service_version="2.1.126",
            count=1,
            time_unix_nano="1770000000000000000",
            received_at=1770000000000,
        )
    ]

    saved = otel_db.save_invocation_counts(records)

    assert saved == 1
    with session_scope(otel_db.engine) as session:
        stored = session.query(OtelInvocationCount).one()
        assert stored.plugin_name == "superpowers"
        assert stored.skill_name == "brainstorming"
        assert stored.org_user == "user-123"
        assert stored.count == 1
```

- [ ] **Step 2: Run database tests and verify failure**

Run:

```bash
pytest tests/unit/test_database/test_otel_logs_db.py -v
```

Expected: FAIL because `core.database.otel_logs_db` does not exist.

- [ ] **Step 3: Implement database access class**

Create `core/database/otel_logs_db.py`:

```python
"""OTLP Logs 调用计数数据库操作。"""

from typing import Iterable

from .base import BaseDatabase, session_scope
from .models import OtelInvocationCount


class OtelLogsDatabase(BaseDatabase):
    """Claude Code OTLP Logs 调用计数数据库访问类。"""

    def save_invocation_counts(self, records: Iterable[OtelInvocationCount]) -> int:
        """批量保存调用计数记录，返回保存条数。"""
        records_list = list(records)
        if not records_list:
            return 0

        with session_scope(self.engine) as session:
            session.add_all(records_list)
            session.flush()
            return len(records_list)
```

- [ ] **Step 4: Export the database class**

Modify `core/database/__init__.py`:

```python
from .otel_logs_db import OtelLogsDatabase
```

Add `"OtelLogsDatabase"` to `__all__`:

```python
__all__ = [
    "Base",
    "session_scope",
    "BaseDatabase",
    "MetricsDatabase",
    "StatsDatabase",
    "SchedulerDatabase",
    "BlameStatsDatabase",
    "AuthorshipNotesDatabase",
    "OtelLogsDatabase",
]
```

- [ ] **Step 5: Run database tests and verify pass**

Run:

```bash
pytest tests/unit/test_database/test_otel_logs_db.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Only commit if the user explicitly requested commits during execution. If commits are allowed, run:

```bash
git add core/database/otel_logs_db.py core/database/__init__.py tests/unit/test_database/test_otel_logs_db.py
git commit -m "feat: add otlp logs invocation database access"
```

---

## Task 3: OTLP JSON Logs parsing service

**Files:**
- Create: `core/services/otel_logs_service.py`
- Test: `tests/unit/test_services/test_otel_logs_service.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/unit/test_services/test_otel_logs_service.py`:

```python
from unittest.mock import Mock

from core.services.otel_logs_service import OtelLogsService


def _attr(key, value):
    return {"key": key, "value": {"stringValue": value}}


def _payload(log_attrs, resource_attrs=None, event_name="claude_code.skill_activated"):
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
                                "timeUnixNano": "1770000000000000000",
                                "attributes": log_attrs,
                            }
                        ]
                    }
                ],
            }
        ]
    }


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


def test_process_logs_skips_non_skill_event():
    db = Mock()
    service = OtelLogsService(database=db)

    result = service.process_logs(
        _payload([_attr("event.name", "user_prompt")], event_name="claude_code.user_prompt")
    )

    assert result["success"] is True
    assert result["accepted"] == 0
    assert result["skipped"] == 1
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
```

- [ ] **Step 2: Run service tests and verify failure**

Run:

```bash
pytest tests/unit/test_services/test_otel_logs_service.py -v
```

Expected: FAIL because `core.services.otel_logs_service` does not exist.

- [ ] **Step 3: Implement the service**

Create `core/services/otel_logs_service.py`:

```python
"""Claude Code OTLP JSON Logs 解析服务。"""

from collections.abc import Iterable
from typing import Any

from core.config import load_config
from core.config.logging import Logger
from core.database.models import OtelInvocationCount, now_ts
from core.database.otel_logs_db import OtelLogsDatabase


MAX_FIELD_LENGTH = 200


class OtelLogsService:
    """解析 OTLP JSON Logs 并保存 Claude Code Skill 调用记录。"""

    def __init__(self, database: OtelLogsDatabase | None = None, require_org_user: bool | None = None):
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
        """处理 OTLP JSON Logs payload。"""
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
                        errors.append({"index": seen - 1, "error": "max_log_records_per_request exceeded"})
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
        if event_name not in {"claude_code.skill_activated", "skill_activated"}:
            return None

        if attrs.get("event.name") not in {None, "skill_activated"}:
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
            return "skill.name is custom_skill; set OTEL_LOG_TOOL_DETAILS=1 in Claude Code"
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
            time_unix_nano=self._clean_string(log_record.get("timeUnixNano"), max_length=30),
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
```

- [ ] **Step 4: Run service tests and verify pass**

Run:

```bash
pytest tests/unit/test_services/test_otel_logs_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only commit if the user explicitly requested commits during execution. If commits are allowed, run:

```bash
git add core/services/otel_logs_service.py tests/unit/test_services/test_otel_logs_service.py
git commit -m "feat: parse claude code otlp skill activation logs"
```

---

## Task 4: OTLP Logs receiver routes and app registration

**Files:**
- Create: `api/routes/otel_receiver.py`
- Modify: `app.py`
- Test: `tests/integration/test_otel_receiver_api.py`

- [ ] **Step 1: Write failing route tests**

Create `tests/integration/test_otel_receiver_api.py`:

```python
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
```

- [ ] **Step 2: Run route tests and verify failure**

Run:

```bash
pytest tests/integration/test_otel_receiver_api.py -v
```

Expected: FAIL because `api.routes.otel_receiver` does not exist.

- [ ] **Step 3: Implement the receiver routes**

Create `api/routes/otel_receiver.py`:

```python
"""OTLP Logs Receiver API 路由。"""

from flask import Blueprint, jsonify, request

from core.config.logging import Logger


otel_receiver_bp = Blueprint("otel_receiver", __name__)
logger = Logger.get_logger("api.otel_receiver")


def _handle_logs_request():
    try:
        data = request.get_json(force=False, silent=False)
    except Exception as exc:
        return jsonify({"success": False, "error": f"Invalid JSON: {exc}"}), 400

    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid JSON: object payload required"}), 400

    try:
        from core.services.otel_logs_service import OtelLogsService

        result = OtelLogsService().process_logs(data)
        return jsonify(result), 200
    except Exception as exc:
        logger.error(f"OTLP logs receive error: {exc}", exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@otel_receiver_bp.route("/v1/logs", methods=["POST"])
def receive_v1_logs():
    """接收标准 OTLP HTTP JSON Logs。"""
    return _handle_logs_request()


@otel_receiver_bp.route("/worker/otel/v1/logs", methods=["POST"])
def receive_worker_otel_logs():
    """接收项目 worker 命名空间下的 OTLP HTTP JSON Logs。"""
    return _handle_logs_request()
```

- [ ] **Step 4: Register the blueprint in app.py**

Modify `app.py` imports near the existing route imports:

```python
from api.routes.otel_receiver import otel_receiver_bp
```

Register after existing REST/system blueprints:

```python
app.register_blueprint(otel_receiver_bp)
```

- [ ] **Step 5: Run route tests and verify pass**

Run:

```bash
pytest tests/integration/test_otel_receiver_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Only commit if the user explicitly requested commits during execution. If commits are allowed, run:

```bash
git add api/routes/otel_receiver.py app.py tests/integration/test_otel_receiver_api.py
git commit -m "feat: add otlp logs receiver routes"
```

---

## Task 5: Configuration defaults and end-to-end persistence test

**Files:**
- Modify: `config.yaml`
- Test: `tests/integration/test_otel_receiver_api.py`

- [ ] **Step 1: Add an end-to-end route persistence test**

Append this test to `tests/integration/test_otel_receiver_api.py`:

```python
import importlib
import os
import tempfile
import time

import core.config.loader as loader


def test_v1_logs_persists_invocation_record():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
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
        time.sleep(0.1)
        if os.path.exists(path):
            os.unlink(path)
```

- [ ] **Step 2: Run the end-to-end test and verify current behavior**

Run:

```bash
pytest tests/integration/test_otel_receiver_api.py::test_v1_logs_persists_invocation_record -v
```

Expected: PASS if Tasks 1-4 are complete. If it fails because configuration keys are missing from `config.yaml`, continue to Step 3.

- [ ] **Step 3: Add config defaults**

Add this section to `config.yaml` after `git_ai:` and before `logging:`:

```yaml
# OTEL 接收配置
otel:
  receiver:
    enabled: true
    logs:
      enabled: true
      accept_json: true
      accept_protobuf: false
      max_log_records_per_request: 1000
      require_org_user: true
```

- [ ] **Step 4: Run integration test file**

Run:

```bash
pytest tests/integration/test_otel_receiver_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only commit if the user explicitly requested commits during execution. If commits are allowed, run:

```bash
git add config.yaml tests/integration/test_otel_receiver_api.py
git commit -m "test: verify otlp logs receiver persistence"
```

---

## Task 6: Verification and regression checks

**Files:**
- Verify only; no planned edits.

- [ ] **Step 1: Run all new focused tests**

Run:

```bash
pytest \
  tests/unit/test_models/test_metrics.py \
  tests/unit/test_database/test_otel_logs_db.py \
  tests/unit/test_services/test_otel_logs_service.py \
  tests/integration/test_otel_receiver_api.py \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run existing metrics upload regression tests**

Run:

```bash
pytest tests/test_metrics_event_processor_task.py tests/unit/test_database/test_metrics_db.py -v
```

Expected: PASS or only pre-existing unrelated failures. If failures occur, inspect whether any touched file caused them; do not modify `api/routes/git_ai_worker.py`, `core/services/metrics_service.py`, or `core/scheduler/tasks/metrics_event_processor_task.py`.

- [ ] **Step 3: Run Python syntax compile check for changed modules**

Run:

```bash
python -m py_compile \
  api/routes/otel_receiver.py \
  core/database/otel_logs_db.py \
  core/services/otel_logs_service.py \
  core/database/models.py \
  app.py
```

Expected: exit code 0.

- [ ] **Step 4: Verify forbidden files were not modified**

Run:

```bash
git diff -- api/routes/git_ai_worker.py core/services/metrics_service.py core/scheduler/tasks/metrics_event_processor_task.py
```

Expected: no output.

- [ ] **Step 5: Review full diff**

Run:

```bash
git diff --stat
git diff -- docs/superpowers/specs/2026-05-11-claude-code-otlp-invocation-counts-design.md docs/superpowers/plans/2026-05-11-claude-code-otlp-logs-invocation-counts-plan.md
```

Expected: plan/spec docs are present; implementation changes are limited to new OTLP logs receiver, service, DB, model, config, tests, and app blueprint registration.

- [ ] **Step 6: Final commit**

Only commit if the user explicitly requested commits during execution. If commits are allowed and previous task commits were skipped, run:

```bash
git add \
  api/routes/otel_receiver.py \
  app.py \
  config.yaml \
  core/database/__init__.py \
  core/database/models.py \
  core/database/otel_logs_db.py \
  core/services/otel_logs_service.py \
  sql/metrics_schema_mysql.sql \
  tests/unit/test_models/test_metrics.py \
  tests/unit/test_database/test_otel_logs_db.py \
  tests/unit/test_services/test_otel_logs_service.py \
  tests/integration/test_otel_receiver_api.py
git commit -m "feat: receive claude code otlp skill activation logs"
```

---

## Claude Code OTEL logs configuration for manual validation

Use these environment variables when manually testing Claude Code against this receiver:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8888
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://localhost:8888/v1/logs
export OTEL_LOG_TOOL_DETAILS=1
export OTEL_SERVICE_NAME=claude-code
export OTEL_RESOURCE_ATTRIBUTES=org.user=userId
```

Then invoke a plugin Skill such as `/superpowers:brainstorming`. The receiver should persist one row where `plugin_name="superpowers"`, `skill_name="brainstorming"`, `invocation_trigger="user-slash"`, and `org_user="userId"`.
