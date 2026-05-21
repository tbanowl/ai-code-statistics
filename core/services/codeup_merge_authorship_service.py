import hashlib
import json
from importlib import import_module
from pathlib import Path
from typing import Any

from core.database.codeup_merge_authorship_db import CodeupMergeAuthorshipDatabase
from core.services.codeup_git_service import CodeupGitService
from core.services.codeup_note_provider import CodeupDatabaseNoteProvider
from core.services.notes_service import NotesRestService
from core.services.ssh_key_service import SshKeyService


class CodeupMergeAuthorshipService:
    def __init__(
        self,
        task_db: CodeupMergeAuthorshipDatabase | None = None,
        git_service: CodeupGitService | None = None,
        note_provider: CodeupDatabaseNoteProvider | None = None,
        notes_service: NotesRestService | None = None,
        merge_resolver: Any | None = None,
        merge_policy: Any | None = None,
        ssh_key_service: Any | None = None,
        config: dict[str, Any] | None = None,
    ):
        self.task_db = task_db or CodeupMergeAuthorshipDatabase()
        self.git_service = git_service or CodeupGitService()
        self.note_provider = note_provider or CodeupDatabaseNoteProvider()
        self.notes_service = notes_service or NotesRestService()
        self.merge_resolver = merge_resolver or self._default_merge_resolver()
        self.merge_policy = merge_policy or self._default_merge_policy()
        self.ssh_key_service = ssh_key_service or SshKeyService()
        self.config = config or {}

    def _default_merge_resolver(self) -> Any:
        resolver_module = import_module("core.services.repository_merge_resolver")
        return resolver_module.RepositoryMergeResolver(self.git_service)

    def _default_merge_policy(self) -> Any:
        policy_module = import_module("core.services.merge_authorship_policy")
        return policy_module.MergeAuthorshipPolicy()

    def process_next_task(self) -> dict[str, Any]:
        max_attempts = int(self.config.get("max_attempts", 3))
        task = self.task_db.claim_next_task(max_attempts=max_attempts)
        if task is None:
            return {"success": True, "processed": 0}

        try:
            ssh_key_info = self._ssh_key_info(task)
            if ssh_key_info is None:
                reason = "missing ssh key for Codeup merge authorship"
                self.task_db.release_for_retry(task.id, reason)
                return {
                    "success": True,
                    "processed": 1,
                    "released": True,
                    "reason": reason,
                }
            private_key = ssh_key_info.get("private_key")
            summary = self._process_task(task, private_key=private_key)
            if summary.get("skipped_reason"):
                reason = str(summary["skipped_reason"])
                merge_type = summary.get("merge_type")
                self.task_db.mark_skipped(task.id, reason, merge_type=merge_type)
                return {
                    "success": True,
                    "processed": 1,
                    "skipped": True,
                    "reason": reason,
                }
            self.task_db.mark_success(task.id, summary)
            return {"success": True, "processed": 1, "summary": summary}
        except Exception as exc:
            self.task_db.mark_failed(task.id, str(exc))
            return {"success": False, "processed": 1, "error": str(exc)}

    def _ssh_key_info(self, task) -> dict[str, Any] | None:
        return self.ssh_key_service.get_ssh_key_for_repo(
            getattr(task, "ssh_key_id", None)
        )

    def _process_task(self, task, private_key: str | None = None) -> dict[str, Any]:
        source_shas = json.loads(task.source_commit_shas or "[]")
        repo_path = self._repo_path(task)
        repo_path = self.git_service.ensure_repo(
            repo_url=task.repo_url,
            repo_dir=repo_path,
            target_branch=task.target_branch,
            source_branch=task.source_branch,
            merge_commit_sha=task.merge_commit_sha,
            source_commit_shas=source_shas,
            clone_timeout=int(self.config.get("clone_timeout_seconds", 60)),
            fetch_timeout=int(self.config.get("fetch_timeout_seconds", 60)),
            private_key=private_key,
        )
        merge_base_sha = self._merge_base(repo_path, task) if task.merge_commit_sha else None

        if not source_shas and merge_base_sha:
            source_shas = self._source_shas_from_range(
                repo_path, merge_base_sha, task.source_branch
            )

        if not source_shas:
            raise ValueError("source_commit_shas must include at least one source commit")

        resolution = self.merge_resolver.resolve(
            repo_path, task.merge_commit_sha, source_shas
        )
        self.task_db.update_merge_type(task.id, resolution.merge_type)
        source_shas = resolution.source_commit_shas
        related_shas = self._unique_shas([task.merge_commit_sha, *source_shas])
        note_map = self.note_provider.batch_get_note_contents(task.repo_url, related_shas)
        final_files = self._final_files(
            repo_path, task.merge_commit_sha, source_shas, merge_base_sha
        )

        target_note = note_map.get(task.merge_commit_sha)
        source_notes = [note_map.get(source_sha) for source_sha in source_shas]
        policy_result = self.merge_policy.apply(
            resolution=resolution,
            target_note=target_note,
            source_notes=source_notes,
            final_files=final_files,
            output_commit_sha=task.merge_commit_sha,
        )

        if policy_result.skipped_reason:
            return {
                "skipped_reason": policy_result.skipped_reason,
                "merge_type": resolution.merge_type,
            }

        if not policy_result.notes_to_upsert:
            return {"merge_type": resolution.merge_type, "upserted": 0}

        notes_data = [
            self._note_payload(
                task=task,
                repo_path=repo_path,
                commit_sha=note.commit_sha,
                branch=task.target_branch,
                content=note.content,
            )
            for note in policy_result.notes_to_upsert
        ]
        upsert_summary = self.notes_service.batch_push_notes(task.repo_url, notes_data)
        return {
            "merge_type": resolution.merge_type,
            "upserted": len(policy_result.notes_to_upsert),
            **upsert_summary,
        }

    def _repo_path(self, task) -> Path:
        if "repo_path" in self.config:
            return Path(self.config["repo_path"])
        repo_paths = self.config.get("repo_paths", {})
        if task.repo_url in repo_paths:
            return Path(repo_paths[task.repo_url])
        repo_hash = hashlib.sha256(task.repo_url.encode("utf-8")).hexdigest()[:16]
        return Path(self.config.get("repo_cache_dir", ".cache/codeup_repos")) / repo_hash

    def _final_files(
        self,
        repo_path: Path,
        merge_sha: str,
        source_shas: list[str],
        merge_base_sha: str | None = None,
    ) -> dict[str, list[str]]:
        changed_files = self._changed_files(
            repo_path, merge_sha, source_shas, merge_base_sha
        )
        return {
            file_path: self.git_service.show_file_lines(repo_path, merge_sha, file_path)
            for file_path in changed_files
        }

    def _changed_files(
        self,
        repo_path: Path,
        merge_sha: str,
        source_shas: list[str],
        merge_base_sha: str | None = None,
    ) -> list[str]:
        if merge_base_sha:
            return self.git_service.changed_files(repo_path, merge_base_sha, merge_sha)
        if source_shas:
            return self.git_service.changed_files(repo_path, source_shas[0], merge_sha)
        return []

    def _merge_base(self, repo_path: Path, task) -> str:
        return self.git_service.merge_base(
            repo_path, task.source_branch, task.merge_commit_sha
        )

    def _source_shas_from_range(
        self, repo_path: Path, merge_base_sha: str, source_branch: str
    ) -> list[str]:
        return self.git_service.rev_list(repo_path, f"{merge_base_sha}..{source_branch}")

    def _note_payload(
        self,
        task,
        repo_path: Path,
        commit_sha: str,
        branch: str,
        content: str,
    ) -> dict[str, Any]:
        metadata = self.git_service.commit_metadata(repo_path, commit_sha)
        return {
            "branch": branch,
            "commit_sha": commit_sha,
            "original_commit_sha": None,
            "content": content,
            "author_name": metadata["author_name"],
            "author_email": metadata["author_email"],
            "commit_time": metadata["commit_time"],
        }

    def _unique_shas(self, shas: list[str]) -> list[str]:
        unique = []
        for sha in shas:
            if sha and sha not in unique:
                unique.append(sha)
        return unique
