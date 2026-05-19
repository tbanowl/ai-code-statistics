"""Codeup payload 归一化：将原始 webhook payload 转为稳定的内部事件对象。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedCodeupMergeEvent:
    repo_url: str | None
    project_id: str | None
    merge_request_id: str | None
    source_branch: str | None
    target_branch: str | None
    merge_commit_sha: str | None
    source_commit_shas: list[str]
    event_action: str | None
    payload_version_hint: str
    is_update_by_push: bool | None
    raw_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_url": self.repo_url,
            "project_id": self.project_id,
            "merge_request_id": self.merge_request_id,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "merge_commit_sha": self.merge_commit_sha,
            "source_commit_shas": self.source_commit_shas,
            "event_action": self.event_action,
            "payload_version_hint": self.payload_version_hint,
            "is_update_by_push": self.is_update_by_push,
        }


class CodeupPayloadNormalizer:
    """将原始 Codeup payload 归一化为 NormalizedCodeupMergeEvent。"""

    def normalize(self, payload: dict[str, Any]) -> NormalizedCodeupMergeEvent:
        attrs = self._dict(payload.get("object_attributes"))
        project = self._dict(payload.get("project"))
        repository = self._dict(payload.get("repository"))
        project_repository = self._dict(project.get("repository"))

        action = self._first_string(attrs.get("action"), attrs.get("state"), payload.get("action"))
        version_hint = "new" if payload.get("version") == "new" else "legacy" if project or repository else "unknown"

        return NormalizedCodeupMergeEvent(
            repo_url=self._first_string(
                repository.get("git_http_url"),
                repository.get("http_url"),
                repository.get("url"),
                project_repository.get("git_http_url"),
                project_repository.get("http_url"),
                project_repository.get("url"),
                project.get("git_http_url"),
                project.get("git_ssh_url"),
            ),
            project_id=self._first_string(attrs.get("project_id"), project.get("id"), payload.get("project_id")),
            merge_request_id=self._first_string(
                attrs.get("biz_id"),
                attrs.get("local_id"),
                attrs.get("iid"),
                attrs.get("id"),
                payload.get("merge_request_id"),
            ),
            source_branch=self._first_string(attrs.get("source_branch"), payload.get("source_branch")),
            target_branch=self._first_string(attrs.get("target_branch"), payload.get("target_branch")),
            merge_commit_sha=self._first_string(
                attrs.get("merge_commit_sha"),
                attrs.get("last_commit", {}).get("id") if isinstance(attrs.get("last_commit"), dict) else None,
                payload.get("merge_commit_sha"),
            ),
            source_commit_shas=self._source_commit_shas(payload),
            event_action=action,
            payload_version_hint=version_hint,
            is_update_by_push=attrs.get("is_update_by_push") if isinstance(attrs.get("is_update_by_push"), bool) else None,
            raw_payload=payload,
        )

    def _source_commit_shas(self, payload: dict[str, Any]) -> list[str]:
        commits = payload.get("commits")
        if not isinstance(commits, list):
            return []
        shas: list[str] = []
        for commit in commits:
            if isinstance(commit, dict):
                sha = self._first_string(commit.get("id"), commit.get("sha"))
                if sha:
                    shas.append(sha)
        return shas

    def _dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _first_string(self, *values: Any) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None
