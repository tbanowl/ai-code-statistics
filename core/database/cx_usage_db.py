from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import DateTime, JSON, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError

from .base import BaseDatabase, session_scope, Base
from .models import gen_xid


class CxCommandUsageEvent(Base):
    __tablename__ = "cx_command_usage_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True,)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    event_day: Mapped[int] = mapped_column(Integer, nullable=False)
    command_name: Mapped[str] = mapped_column(String(64), nullable=False)
    spec_id: Mapped[str] = mapped_column(String(128), nullable=False)
    spec_id_source: Mapped[str] = mapped_column(String(32), nullable=True)
    project_id: Mapped[str] = mapped_column(String(128), nullable=True)
    git_user_name: Mapped[str] = mapped_column(String(128), nullable=True)
    git_user_email: Mapped[str] = mapped_column(String(256), nullable=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=True)
    plugin_version: Mapped[str] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=True)
    warning: Mapped[str] = mapped_column(String(128), nullable=True)
    token_name: Mapped[str] = mapped_column(String(128), nullable=True)
    raw_event: Mapped[dict] = mapped_column(JSON, nullable=True)


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


class CxUsageDatabase(BaseDatabase):

    def insert_batch(self, events: List[Dict], token_name: Optional[str] = None) -> Dict:
        accepted, duplicated, failed = [], [], []

        with session_scope(self.engine) as session:
            for event in events:
                try:
                    record = CxCommandUsageEvent(
                        event_id=event["eventId"],
                        schema_version=event["schemaVersion"],
                        event_type=event["eventType"],
                        event_time=event["eventTime"],
                        event_day=int(event["eventTime"].strftime("%Y%m%d")),
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
