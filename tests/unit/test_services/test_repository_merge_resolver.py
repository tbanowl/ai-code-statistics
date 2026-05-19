"""Tests for RepositoryMergeResolver — resolve() merge-type classification."""

from importlib import import_module
from pathlib import Path

import pytest


_resolver = import_module("core.services.repository_merge_resolver")
RepositoryMergeResolver = _resolver.RepositoryMergeResolver
RepositoryMergeResolution = _resolver.RepositoryMergeResolution

_git_svc = import_module("core.services.codeup_git_service")
CodeupGitService = _git_svc.CodeupGitService
CodeupGitError = _git_svc.CodeupGitError


class FakeGitService:
    def __init__(self, parents_by_sha=None):
        self.parents_by_sha = parents_by_sha or {}
        self.calls = []

    def commit_parents(self, repo_path, commit_sha):
        self.calls.append(("commit_parents", repo_path, commit_sha))
        return self.parents_by_sha[commit_sha]


REPO = Path("/repo")
MERGE_SHA = "a" * 40
SOURCE_SHA = "b" * 40
TARGET_SHA = "c" * 40


def test_resolve_fast_forward_when_no_merge_commit_sha():
    git = FakeGitService()
    resolver = RepositoryMergeResolver(git_service=git)

    result = resolver.resolve(REPO, None, [SOURCE_SHA])

    assert result.merge_type == "fast_forward"
    assert result.reason == "no_merge_commit_sha"
    assert result.source_commit_shas == [SOURCE_SHA]
    assert git.calls == []


def test_resolve_fast_forward_when_empty_merge_commit_sha():
    git = FakeGitService()
    resolver = RepositoryMergeResolver(git_service=git)

    result = resolver.resolve(REPO, "", [SOURCE_SHA])

    assert result.merge_type == "fast_forward"
    assert result.reason == "no_merge_commit_sha"
    assert result.source_commit_shas == [SOURCE_SHA]
    assert git.calls == []


def test_resolve_standard_merge_two_parents():
    git = FakeGitService(parents_by_sha={MERGE_SHA: [TARGET_SHA, SOURCE_SHA]})
    resolver = RepositoryMergeResolver(git_service=git)

    result = resolver.resolve(REPO, MERGE_SHA, [SOURCE_SHA])

    assert result.merge_type == "standard_merge"
    assert result.reason == "merge_commit_has_multiple_parents"
    assert result.source_commit_shas == [SOURCE_SHA]


def test_resolve_standard_merge_three_parents():
    git = FakeGitService(
        parents_by_sha={MERGE_SHA: [TARGET_SHA, SOURCE_SHA, "e" * 40]}
    )
    resolver = RepositoryMergeResolver(git_service=git)

    result = resolver.resolve(REPO, MERGE_SHA, [SOURCE_SHA])

    assert result.merge_type == "standard_merge"
    assert result.reason == "merge_commit_has_multiple_parents"


def test_resolve_squash_merge_single_parent_multiple_source_commits():
    git = FakeGitService(parents_by_sha={MERGE_SHA: [TARGET_SHA]})
    resolver = RepositoryMergeResolver(git_service=git)

    result = resolver.resolve(REPO, MERGE_SHA, ["s1", "s2", "s3"])

    assert result.merge_type == "squash_merge"
    assert result.reason == "single_parent_commit_with_multiple_source_commits"
    assert result.source_commit_shas == ["s1", "s2", "s3"]


def test_resolve_rebase_merge_single_parent_one_rewritten_source():
    git = FakeGitService(parents_by_sha={MERGE_SHA: [TARGET_SHA]})
    resolver = RepositoryMergeResolver(git_service=git)

    result = resolver.resolve(REPO, MERGE_SHA, [SOURCE_SHA])

    assert result.merge_type == "rebase_merge"
    assert result.reason == "single_parent_commit_with_rewritten_source_commit"
    assert result.source_commit_shas == [SOURCE_SHA]


def test_resolve_unknown_when_source_sha_equals_merge_sha():
    git = FakeGitService(parents_by_sha={MERGE_SHA: [TARGET_SHA]})
    resolver = RepositoryMergeResolver(git_service=git)

    result = resolver.resolve(REPO, MERGE_SHA, [MERGE_SHA])

    assert result.merge_type == "unknown"
    assert result.reason == "insufficient_commit_graph"


def test_resolve_unknown_when_single_parent_empty_source_commits():
    git = FakeGitService(parents_by_sha={MERGE_SHA: [TARGET_SHA]})
    resolver = RepositoryMergeResolver(git_service=git)

    result = resolver.resolve(REPO, MERGE_SHA, [])

    assert result.merge_type == "unknown"
    assert result.reason == "insufficient_commit_graph"


def test_resolve_unknown_when_zero_parents_and_source_commits():
    git = FakeGitService(parents_by_sha={MERGE_SHA: []})
    resolver = RepositoryMergeResolver(git_service=git)

    result = resolver.resolve(REPO, MERGE_SHA, [SOURCE_SHA])

    assert result.merge_type == "unknown"
    assert result.reason == "insufficient_commit_graph"


def test_resolve_rejects_invalid_merge_commit_sha_via_git_service():
    resolver = RepositoryMergeResolver()

    with pytest.raises(CodeupGitError, match="commit_sha"):
        resolver.resolve(REPO, "not-a-sha", [SOURCE_SHA])


def test_resolve_defaults_to_real_codeup_git_service():
    resolver = RepositoryMergeResolver()
    assert isinstance(resolver.git_service, CodeupGitService)
