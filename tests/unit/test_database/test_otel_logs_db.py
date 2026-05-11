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
    # Reload DB modules because core.database.base creates global_engine at
    # import time; we must reload after overriding loader.config_data so the
    # engine points at the temp SQLite database instead of the default DB.
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
