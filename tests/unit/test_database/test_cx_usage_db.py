import os
import tempfile
from datetime import datetime

from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as db_base
from core.database.base import session_scope
from core.database.cx_usage_db import CxCommandUsageEvent, CxUsageDatabase


def test_insert_batch_derives_event_day_from_event_time():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        loader.config_data = {
            "features": {"enabled": True},
            "git": {"type": "github"},
            "database": {"url": f"sqlite:///{path}", "echo": False},
        }
        db_base.global_engine = create_engine(f"sqlite:///{path}")
        db = CxUsageDatabase()
        db_base.Base.metadata.create_all(db.engine)

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
        loader.config_data = {}
        db_base.global_engine = None
        if os.path.exists(path):
            os.unlink(path)
