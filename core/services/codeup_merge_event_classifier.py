"""Codeup 合并事件分类：判断归一化后的事件是否应该入队。"""

from __future__ import annotations

from dataclasses import dataclass

from core.services.codeup_payload_normalizer import NormalizedCodeupMergeEvent


@dataclass(frozen=True)
class CodeupMergeEventClassification:
    event_kind: str
    should_enqueue: bool
    skipped_reason: str | None
    http_status: int


class CodeupMergeEventClassifier:
    """将归一化事件分类为 merge_candidate / push_update / mr_update / invalid / unknown。"""

    MERGED_ACTIONS = {"merge", "merged", "merged_success"}
    UPDATE_ACTIONS = {"open", "update", "reopen", "reopened", "close", "closed"}

    def classify(self, event: NormalizedCodeupMergeEvent) -> CodeupMergeEventClassification:
        if not event.repo_url or not event.merge_request_id:
            return CodeupMergeEventClassification("invalid", False, "missing_required_identity", 400)

        action = (event.event_action or "").lower()
        if event.is_update_by_push:
            return CodeupMergeEventClassification("push_update", False, "push_update", 200)

        if action in self.MERGED_ACTIONS and event.merge_commit_sha:
            return CodeupMergeEventClassification("merge_candidate", True, None, 200)

        if action in {"closed", "close"}:
            return CodeupMergeEventClassification("closed", False, "not_merge_completion", 200)

        if action in {"reopen", "reopened"}:
            return CodeupMergeEventClassification("reopened", False, "not_merge_completion", 200)

        if action in self.UPDATE_ACTIONS or not event.merge_commit_sha:
            return CodeupMergeEventClassification("mr_update", False, "not_merge_completion", 200)

        return CodeupMergeEventClassification("unknown", False, "unknown_event_kind", 200)
