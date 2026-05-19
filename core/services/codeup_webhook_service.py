"""Codeup 合并 webhook payload 解析与任务入队服务。"""

from typing import Any

from core.database.codeup_merge_authorship_db import CodeupMergeAuthorshipDatabase


class InvalidCodeupPayload(ValueError):
    """Codeup webhook payload 缺少必要字段。"""


class CodeupWebhookService:
    """解析 Codeup merge webhook 并创建 authorship 重算任务。"""

    def __init__(self, database: CodeupMergeAuthorshipDatabase | None = None):
        self.database = database or CodeupMergeAuthorshipDatabase()

    def enqueue_merge_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        object_attributes = payload.get("object_attributes") or {}
        if not self._is_merged(object_attributes):
            return {"success": True, "skipped": True, "reason": "not_merged"}

        task, created = self.database.create_or_update_task(
            repo_url=self._repo_url(payload),
            project_id=self._project_id(payload),
            merge_request_id=self._merge_request_id(payload),
            source_branch=self._string_required(
                object_attributes.get("source_branch"), "source_branch"
            ),
            target_branch=self._string_required(
                object_attributes.get("target_branch"), "target_branch"
            ),
            merge_commit_sha=self._string_required(
                object_attributes.get("merge_commit_sha"), "merge_commit_sha"
            ),
            source_commit_shas=self._source_commit_shas(payload),
            payload=payload,
        )

        return {
            "success": True,
            "skipped": False,
            "created": created,
            "task_id": task.id,
            "status": task.status,
        }

    def _repo_url(self, payload: dict[str, Any]) -> str:
        project = payload.get("project") or {}
        repository = payload.get("repository") or {}
        return self._string_required(
            project.get("git_http_url")
            or project.get("git_ssh_url")
            or repository.get("git_http_url")
            or repository.get("url"),
            "repo_url",
        )

    def _source_commit_shas(self, payload: dict[str, Any]) -> list[str]:
        commits = payload.get("commits") or []
        source_commit_shas: list[str] = []
        for commit in commits:
            if not isinstance(commit, dict):
                continue
            commit_sha = commit.get("id") or commit.get("sha")
            if commit_sha:
                source_commit_shas.append(str(commit_sha))
        return source_commit_shas

    def _string_required(self, value: Any, field_name: str) -> str:
        if value is None or str(value).strip() == "":
            raise InvalidCodeupPayload(f"Missing required Codeup field: {field_name}")
        return str(value)

    def _is_merged(self, object_attributes: dict[str, Any]) -> bool:
        state = object_attributes.get("state")
        action = object_attributes.get("action")
        return state in {"merged", "merged_success"} or action in {"merge", "merged"}

    def _project_id(self, payload: dict[str, Any]) -> str | None:
        project = payload.get("project") or {}
        project_id = project.get("id") or payload.get("project_id")
        if project_id is None or str(project_id).strip() == "":
            return None
        return str(project_id)

    def _merge_request_id(self, payload: dict[str, Any]) -> str:
        object_attributes = payload.get("object_attributes") or {}
        return self._string_required(
            object_attributes.get("iid")
            or object_attributes.get("id")
            or object_attributes.get("biz_id")
            or payload.get("merge_request_id"),
            "merge_request_id",
        )
