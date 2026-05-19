"""Conservative policy for Codeup merge authorship rewrites."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.services.merge_authorship_calculator import MergeAuthorshipCalculator


@dataclass(frozen=True)
class PolicyNoteUpsert:
    commit_sha: str
    content: str


@dataclass(frozen=True)
class MergeAuthorshipPolicyResult:
    notes_to_upsert: list[PolicyNoteUpsert] = field(default_factory=list)
    skipped_reason: str | None = None


class MergeAuthorshipPolicy:
    def __init__(self, calculator: MergeAuthorshipCalculator | None = None):
        self.calculator = calculator or MergeAuthorshipCalculator()

    def apply(
        self,
        resolution,
        target_note: str | None,
        source_notes: list[str | None],
        final_files: dict[str, list[str]],
        output_commit_sha: str | None = None,
    ) -> MergeAuthorshipPolicyResult:
        merge_type = resolution.merge_type

        if merge_type == "standard_merge":
            return MergeAuthorshipPolicyResult()

        if merge_type == "fast_forward":
            return MergeAuthorshipPolicyResult(
                skipped_reason="fast_forward_no_merge_authorship_rewrite",
            )

        if merge_type == "unknown":
            return MergeAuthorshipPolicyResult(
                skipped_reason="unknown_merge_type",
            )

        if merge_type in {"squash_merge", "rebase_merge"}:
            if not output_commit_sha:
                return MergeAuthorshipPolicyResult(
                    skipped_reason="missing_output_commit_sha",
                )
            content = self.calculator.merge_notes(
                target_note=target_note,
                source_notes=source_notes,
                final_files=final_files,
            )
            return MergeAuthorshipPolicyResult(
                notes_to_upsert=[PolicyNoteUpsert(output_commit_sha, content)],
            )

        return MergeAuthorshipPolicyResult(
            skipped_reason="unsupported_merge_type",
        )
