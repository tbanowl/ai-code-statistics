from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import CheckConstraint, DateTime, JSON, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

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
    __table_args__ = (
        CheckConstraint(
            "event_type = 'cx_codereview_issue_bypass'",
            name="chk_cr_bypass_event_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="cx_codereview_issue_bypass",
    )
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
    __table_args__ = (
        CheckConstraint(
            "event_type = 'cx_codereview_push_summary'",
            name="chk_cr_summary_event_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="cx_codereview_push_summary",
    )
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
        existing_event_ids = self._existing_codereview_event_ids(
            event["eventId"] for event in events if event.get("eventId")
        )
        seen_event_ids = set()

        for event in events:
            try:
                event_id = event["eventId"]
                if event_id in seen_event_ids or event_id in existing_event_ids:
                    duplicated.append(event_id)
                    continue

                common_fields = self._codereview_common_fields(event, token_name)
                if event["eventType"] == "cx_codereview_issue_bypass":
                    record = CxCodereviewBypass(
                        **common_fields,
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
                    )
                elif event["eventType"] == "cx_codereview_push_summary":
                    record = CxCodereviewSummary(
                        **common_fields,
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
                    )
                else:
                    failed.append(event.get("eventId", ""))
                    continue

                with session_scope(self.engine) as session:
                    session.add(record)
                    session.flush()
                accepted.append(event_id)
                seen_event_ids.add(event_id)
            except IntegrityError:
                duplicated.append(event["eventId"])
            except SQLAlchemyError:
                raise
            except Exception:
                failed.append(event["eventId"])

        return {"accepted": accepted, "duplicated": duplicated, "failed": failed}

    def _existing_codereview_event_ids(self, event_ids) -> set:
        event_ids = set(event_ids)
        if not event_ids:
            return set()

        with session_scope(self.engine) as session:
            bypass_event_ids = (
                event_id
                for event_id, in session.query(CxCodereviewBypass.event_id)
                .filter(CxCodereviewBypass.event_id.in_(event_ids))
                .all()
            )
            summary_event_ids = (
                event_id
                for event_id, in session.query(CxCodereviewSummary.event_id)
                .filter(CxCodereviewSummary.event_id.in_(event_ids))
                .all()
            )
            return set(bypass_event_ids) | set(summary_event_ids)

    def _codereview_common_fields(self, event: Dict, token_name: Optional[str]) -> Dict:
        return {
            "event_id": event["eventId"],
            "schema_version": event["schemaVersion"],
            "event_type": event["eventType"],
            "event_time": event["eventTime"],
            "spec_id": event.get("specId") or None,
            "spec_id_source": event.get("specIdSource") or None,
            "project_id": event.get("projectId") or None,
            "git_user_name": event.get("gitUserName") or None,
            "git_user_email": event.get("gitUserEmail") or None,
            "session_id": event.get("sessionId") or None,
            "plugin_version": event.get("pluginVersion") or None,
            "source": event.get("source") or None,
            "push_id": event.get("pushId") or None,
            "commit_sha": event.get("commitSha") or None,
            "token_name": token_name,
            "raw_event": event.get("rawEvent"),
        }
