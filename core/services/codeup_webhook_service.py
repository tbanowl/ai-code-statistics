"""Codeup 合并 webhook payload 解析与任务入队服务。"""

from typing import Any

from core.database.codeup_merge_authorship_db import CodeupMergeAuthorshipDatabase
from core.services.codeup_merge_event_classifier import CodeupMergeEventClassifier
from core.services.codeup_payload_normalizer import CodeupPayloadNormalizer


class InvalidCodeupPayload(ValueError):
    """Codeup webhook payload 缺少必要字段。"""


class CodeupWebhookService:
    """解析 Codeup merge webhook 并创建 authorship 重算任务。

    通过 normalizer 归一化原始 payload，再由 classifier 判断事件类型，
    仅对 merge_candidate 类型入队创建任务。
    """

    def __init__(
        self,
        database: CodeupMergeAuthorshipDatabase | None = None,
        normalizer: CodeupPayloadNormalizer | None = None,
        classifier: CodeupMergeEventClassifier | None = None,
    ):
        self.database = database or CodeupMergeAuthorshipDatabase()
        self.normalizer = normalizer or CodeupPayloadNormalizer()
        self.classifier = classifier or CodeupMergeEventClassifier()

    def enqueue_merge_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = self.normalizer.normalize(payload)
        classification = self.classifier.classify(event)

        if classification.event_kind == "invalid":
            raise InvalidCodeupPayload(
                f"Invalid Codeup payload: {classification.skipped_reason}"
            )

        if not classification.should_enqueue:
            return {
                "success": True,
                "skipped": True,
                "reason": classification.skipped_reason,
                "event_kind": classification.event_kind,
            }

        source_branch = self._string_required(event.source_branch, "source_branch")
        target_branch = self._string_required(event.target_branch, "target_branch")

        assert event.repo_url is not None
        assert event.merge_request_id is not None
        assert event.merge_commit_sha is not None

        task, created = self.database.create_or_update_task(
            repo_url=event.repo_url,
            project_id=event.project_id,
            merge_request_id=event.merge_request_id,
            source_branch=source_branch,
            target_branch=target_branch,
            merge_commit_sha=event.merge_commit_sha,
            source_commit_shas=event.source_commit_shas,
            payload=payload,
            event_kind=classification.event_kind,
            payload_version_hint=event.payload_version_hint,
            normalized_payload=event.to_dict(),
            skipped_reason=None,
        )

        return {
            "success": True,
            "skipped": False,
            "created": created,
            "task_id": task.id,
            "status": task.status,
        }

    def _string_required(self, value: Any, field_name: str) -> str:
        if value is None or str(value).strip() == "":
            raise InvalidCodeupPayload(f"Missing required Codeup field: {field_name}")
        return str(value)
