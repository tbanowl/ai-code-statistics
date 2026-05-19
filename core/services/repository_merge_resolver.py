"""Repository merge resolver — classifies merge type from git history."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.services.codeup_git_service import CodeupGitService


@dataclass(frozen=True)
class RepositoryMergeResolution:
    merge_type: str
    reason: str
    source_commit_shas: list[str] = field(default_factory=list)


class RepositoryMergeResolver:
    def __init__(self, git_service: CodeupGitService | None = None):
        self.git_service = git_service or CodeupGitService()

    def resolve(
        self,
        repo_path: str | Path,
        merge_commit_sha: str | None,
        source_commit_shas: list[str],
    ) -> RepositoryMergeResolution:
        if not merge_commit_sha:
            return RepositoryMergeResolution(
                merge_type="fast_forward",
                reason="no_merge_commit_sha",
                source_commit_shas=source_commit_shas,
            )

        repo_path = Path(repo_path)
        parents = self.git_service.commit_parents(repo_path, merge_commit_sha)

        if len(parents) > 1:
            return RepositoryMergeResolution(
                merge_type="standard_merge",
                reason="merge_commit_has_multiple_parents",
                source_commit_shas=source_commit_shas,
            )

        if len(parents) == 1 and len(source_commit_shas) > 1:
            return RepositoryMergeResolution(
                merge_type="squash_merge",
                reason="single_parent_commit_with_multiple_source_commits",
                source_commit_shas=source_commit_shas,
            )

        if (
            len(parents) == 1
            and len(source_commit_shas) == 1
            and source_commit_shas[0] != merge_commit_sha
        ):
            return RepositoryMergeResolution(
                merge_type="rebase_merge",
                reason="single_parent_commit_with_rewritten_source_commit",
                source_commit_shas=source_commit_shas,
            )

        return RepositoryMergeResolution(
            merge_type="unknown",
            reason="insufficient_commit_graph",
            source_commit_shas=source_commit_shas,
        )
