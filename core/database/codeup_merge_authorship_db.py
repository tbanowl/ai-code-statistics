"""
Codeup 合并 authorship 重算任务数据库操作类。

负责 codeup_merge_authorship_tasks 表的创建、幂等更新、领取和状态标记。
"""

import json
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .base import BaseDatabase, session_scope
from .models import CodeupMergeAuthorshipTask, gen_xid


class CodeupMergeAuthorshipDatabase(BaseDatabase):
    """Codeup 合并 authorship 重算任务数据库操作类"""

    def create_or_update_task(
        self,
        repo_url: str,
        project_id: str | None,
        merge_request_id: str,
        source_branch: str,
        target_branch: str,
        merge_commit_sha: str,
        source_commit_shas: list[str],
        payload: dict[str, Any],
    ) -> tuple[CodeupMergeAuthorshipTask, bool]:
        """创建或幂等更新 Codeup 合并重算任务。"""
        source_commit_shas_json = json.dumps(
            source_commit_shas, ensure_ascii=False, sort_keys=True
        )
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        with session_scope(self.engine) as session:
            stmt = select(CodeupMergeAuthorshipTask).where(
                CodeupMergeAuthorshipTask.repo_url == repo_url,
                CodeupMergeAuthorshipTask.merge_request_id == merge_request_id,
                CodeupMergeAuthorshipTask.merge_commit_sha == merge_commit_sha,
            )
            task = session.execute(stmt).scalar_one_or_none()

            if task is not None:
                self._apply_duplicate_payload_update(
                    task=task,
                    project_id=project_id,
                    source_branch=source_branch,
                    target_branch=target_branch,
                    source_commit_shas_json=source_commit_shas_json,
                    payload_json=payload_json,
                )
                return session.execute(stmt).scalar_one(), False

        try:
            return self._insert_new_task(
                repo_url=repo_url,
                project_id=project_id,
                merge_request_id=merge_request_id,
                source_branch=source_branch,
                target_branch=target_branch,
                merge_commit_sha=merge_commit_sha,
                source_commit_shas_json=source_commit_shas_json,
                payload_json=payload_json,
            ), True
        except IntegrityError:
            return self._update_existing_task_after_duplicate_insert(
                repo_url=repo_url,
                project_id=project_id,
                merge_request_id=merge_request_id,
                source_branch=source_branch,
                target_branch=target_branch,
                merge_commit_sha=merge_commit_sha,
                source_commit_shas_json=source_commit_shas_json,
                payload_json=payload_json,
            ), False

    def _insert_new_task(
        self,
        repo_url: str,
        project_id: str | None,
        merge_request_id: str,
        source_branch: str,
        target_branch: str,
        merge_commit_sha: str,
        source_commit_shas_json: str,
        payload_json: str,
    ) -> CodeupMergeAuthorshipTask:
        with session_scope(self.engine) as session:
            stmt = select(CodeupMergeAuthorshipTask).where(
                CodeupMergeAuthorshipTask.repo_url == repo_url,
                CodeupMergeAuthorshipTask.merge_request_id == merge_request_id,
                CodeupMergeAuthorshipTask.merge_commit_sha == merge_commit_sha,
            )
            task = CodeupMergeAuthorshipTask(
                id=gen_xid(),
                repo_url=repo_url,
                project_id=project_id,
                merge_request_id=merge_request_id,
                source_branch=source_branch,
                target_branch=target_branch,
                merge_commit_sha=merge_commit_sha,
                source_commit_shas=source_commit_shas_json,
                payload=payload_json,
                status="pending",
                attempts=0,
            )
            session.add(task)
            session.flush()
            return session.execute(stmt).scalar_one()

    def _apply_duplicate_payload_update(
        self,
        task: CodeupMergeAuthorshipTask,
        project_id: str | None,
        source_branch: str,
        target_branch: str,
        source_commit_shas_json: str,
        payload_json: str,
    ) -> None:
        task.project_id = project_id
        task.source_branch = source_branch
        task.target_branch = target_branch
        task.source_commit_shas = source_commit_shas_json
        task.payload = payload_json
        if task.status in {"pending", "failed"}:
            task.status = "pending"
            task.attempts = 0
            task.last_error = None

    def _update_existing_task_after_duplicate_insert(
        self,
        repo_url: str,
        project_id: str | None,
        merge_request_id: str,
        source_branch: str,
        target_branch: str,
        merge_commit_sha: str,
        source_commit_shas_json: str,
        payload_json: str,
    ) -> CodeupMergeAuthorshipTask:
        with session_scope(self.engine) as session:
            stmt = select(CodeupMergeAuthorshipTask).where(
                CodeupMergeAuthorshipTask.repo_url == repo_url,
                CodeupMergeAuthorshipTask.merge_request_id == merge_request_id,
                CodeupMergeAuthorshipTask.merge_commit_sha == merge_commit_sha,
            )
            task = session.execute(stmt).scalar_one()
            self._apply_duplicate_payload_update(
                task=task,
                project_id=project_id,
                source_branch=source_branch,
                target_branch=target_branch,
                source_commit_shas_json=source_commit_shas_json,
                payload_json=payload_json,
            )
            session.flush()
            return session.execute(stmt).scalar_one()

    def get_task(self, task_id: str) -> CodeupMergeAuthorshipTask | None:
        """按任务 ID 获取任务。"""
        with session_scope(self.engine) as session:
            stmt = select(CodeupMergeAuthorshipTask).where(
                CodeupMergeAuthorshipTask.id == task_id
            )
            return session.execute(stmt).scalar_one_or_none()

    def claim_next_task(self, max_attempts: int) -> CodeupMergeAuthorshipTask | None:
        """领取下一条可处理任务，并标记为 processing。"""
        with session_scope(self.engine) as session:
            candidate_stmt = (
                select(CodeupMergeAuthorshipTask.id)
                .where(
                    CodeupMergeAuthorshipTask.status.in_({"pending", "failed"}),
                    CodeupMergeAuthorshipTask.attempts < max_attempts,
                )
                .order_by(CodeupMergeAuthorshipTask.created_at)
                .limit(1)
            )
            task_id = session.execute(candidate_stmt).scalar_one_or_none()
            if task_id is None:
                return None

            claim_stmt = (
                update(CodeupMergeAuthorshipTask)
                .where(
                    CodeupMergeAuthorshipTask.id == task_id,
                    CodeupMergeAuthorshipTask.status.in_({"pending", "failed"}),
                    CodeupMergeAuthorshipTask.attempts < max_attempts,
                )
                .values(
                    status="processing",
                    attempts=CodeupMergeAuthorshipTask.attempts + 1,
                )
            )
            result = session.execute(claim_stmt)
            if result.rowcount != 1:
                return None

            session.flush()
            return session.execute(
                select(CodeupMergeAuthorshipTask).where(
                    CodeupMergeAuthorshipTask.id == task_id
                )
            ).scalar_one()

    def mark_success(self, task_id: str, result_summary: dict[str, Any]) -> None:
        """标记任务成功并保存结果摘要。"""
        result_summary_json = json.dumps(
            result_summary, ensure_ascii=False, sort_keys=True
        )
        with session_scope(self.engine) as session:
            task = session.execute(
                select(CodeupMergeAuthorshipTask).where(
                    CodeupMergeAuthorshipTask.id == task_id
                )
            ).scalar_one_or_none()
            if task is None:
                return

            task.status = "success"
            task.last_error = None
            task.result_summary = result_summary_json

    def mark_failed(self, task_id: str, error: str) -> None:
        """标记任务失败并保存错误信息。"""
        with session_scope(self.engine) as session:
            task = session.execute(
                select(CodeupMergeAuthorshipTask).where(
                    CodeupMergeAuthorshipTask.id == task_id
                )
            ).scalar_one_or_none()
            if task is None:
                return

            task.status = "failed"
            task.last_error = error
