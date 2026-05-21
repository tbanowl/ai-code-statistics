import json
from datetime import datetime
from typing import Dict, List

from sqlalchemy import String, BigInteger, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError

from .base import BaseDatabase, session_scope, Base


class CxCommandUsageEvent(Base):
    __tablename__ = "cx_command_usage_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    command_name: Mapped[str] = mapped_column(String(64), nullable=False)
    spec_id: Mapped[str] = mapped_column(String(128), nullable=False)
    spec_id_source: Mapped[str | None] = mapped_column(String(32))
    project_id: Mapped[str | None] = mapped_column(String(128))
    git_user_name: Mapped[str | None] = mapped_column(String(128))
    git_user_email: Mapped[str | None] = mapped_column(String(256))
    session_id: Mapped[str | None] = mapped_column(String(128))
    plugin_version: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str | None] = mapped_column(String(64))
    warning: Mapped[str | None] = mapped_column(String(128))
    token_name: Mapped[str | None] = mapped_column(String(128))
    raw_event: Mapped[dict | None] = mapped_column(JSON)


class CxUsageDatabase(BaseDatabase):

    def insert_batch(self, events: List[Dict], token_name: str | None = None) -> Dict:
        accepted, duplicated, failed = [], [], []

        with session_scope(self.engine) as session:
            for event in events:
                try:
                    record = CxCommandUsageEvent(
                        event_id=event["eventId"],
                        schema_version=event["schemaVersion"],
                        event_type=event["eventType"],
                        event_time=event["eventTime"],
                        command_name=event["command"],
                        spec_id=event["specId"],
                        spec_id_source=event.get("specIdSource") or None,
                        project_id=event.get("projectId") or None,
                        git_user_name=event.get("gitUserName") or None,
                        git_user_email=event.get("gitUserEmail") or None,
                        session_id=event.get("sessionId") or None,
                        plugin_version=event.get("pluginVersion") or None,
                        source=event.get("source") or None,
                        warning=event.get("warning") or None,
                        token_name=token_name,
                        raw_event=event.get("rawEvent"),
                    )
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
