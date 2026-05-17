import json
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace


CodeupMergeAuthorshipService = import_module(
    "core.services.codeup_merge_authorship_service"
).CodeupMergeAuthorshipService


MERGE_SHA = "a" * 40
SOURCE_SHA = "b" * 40
REPO_URL = "https://codeup.aliyun.com/org/repo.git"
OTHER_REPO_URL = "https://codeup.aliyun.com/org/other-repo.git"


def _split_note(content):
    body, metadata = content.split("\n---\n", 1)
    return body, json.loads(metadata)


class FakeTaskDatabase:
    def __init__(self, source_commit_shas=None):
        if source_commit_shas is None:
            source_commit_shas = [SOURCE_SHA]
        self.task = SimpleNamespace(
            id="task-1",
            repo_url=REPO_URL,
            source_branch="feature/a",
            target_branch="main",
            merge_commit_sha=MERGE_SHA,
            source_commit_shas=json.dumps(source_commit_shas),
        )
        self.claim_calls = []
        self.successes = []
        self.failures = []

    def claim_next_task(self, max_attempts):
        self.claim_calls.append(max_attempts)
        task = self.task
        self.task = None
        return task

    def mark_success(self, task_id, result_summary):
        self.successes.append((task_id, result_summary))

    def mark_failed(self, task_id, error):
        self.failures.append((task_id, error))


class FakeGitService:
    def __init__(self, fail_on_changed_files=False, derived_shas=None):
        if derived_shas is None:
            derived_shas = [SOURCE_SHA]
        self.ensure_repo_calls = []
        self.merge_base_calls = []
        self.rev_list_calls = []
        self.changed_file_calls = []
        self.show_file_calls = []
        self.metadata_calls = []
        self.fail_on_changed_files = fail_on_changed_files
        self.derived_shas = derived_shas

    def ensure_repo(
        self,
        repo_url,
        repo_dir,
        target_branch,
        source_branch,
        merge_commit_sha,
        source_commit_shas,
        clone_timeout,
        fetch_timeout,
    ):
        self.ensure_repo_calls.append(
            (
                repo_url,
                repo_dir,
                target_branch,
                source_branch,
                merge_commit_sha,
                source_commit_shas,
                clone_timeout,
                fetch_timeout,
            )
        )
        return repo_dir

    def merge_base(self, repo_path, source_ref, target_ref_or_merge_sha):
        self.merge_base_calls.append((repo_path, source_ref, target_ref_or_merge_sha))
        return "c" * 40

    def rev_list(self, repo_path, revision_range):
        self.rev_list_calls.append((repo_path, revision_range))
        return self.derived_shas

    def changed_files(self, repo_path, base_sha, head_sha):
        if self.fail_on_changed_files:
            raise RuntimeError("invalid git revision")
        self.changed_file_calls.append((repo_path, base_sha, head_sha))
        return ["app.py"]

    def show_file_lines(self, repo_path, commit_sha, file_path):
        self.show_file_calls.append((repo_path, commit_sha, file_path))
        return ["line 1", "line 2", "line 3"]

    def commit_metadata(self, repo_path, commit_sha):
        self.metadata_calls.append((repo_path, commit_sha))
        return {
            "author_name": f"Author {commit_sha[0]}",
            "author_email": f"{commit_sha[0]}@example.com",
            "commit_time": 1715555555,
        }


class FakeNoteProvider:
    def __init__(self):
        self.calls = []

    def batch_get_note_contents(self, repo_url, commit_shas):
        self.calls.append((repo_url, commit_shas))
        return {
            SOURCE_SHA: (
                "app.py\n"
                "  source_prompt 1-2\n"
                "---\n"
                '{"schema_version":"3","prompts":{"source_prompt":{}}}'
            )
        }


class FakeNotesService:
    def __init__(self):
        self.calls = []

    def batch_push_notes(self, repo_url, notes_data):
        self.calls.append((repo_url, notes_data))
        return {"created": len(notes_data), "updated": 0}


def test_process_next_task_upserts_merge_and_source_notes_then_marks_success():
    task_db = FakeTaskDatabase()
    git_service = FakeGitService()
    note_provider = FakeNoteProvider()
    notes_service = FakeNotesService()
    service = CodeupMergeAuthorshipService(
        task_db=task_db,
        git_service=git_service,
        note_provider=note_provider,
        notes_service=notes_service,
        config={"max_attempts": 5, "repo_path": "/repo"},
    )

    result = service.process_next_task()

    assert result == {"success": True, "processed": 1, "summary": {"created": 2, "updated": 0}}
    assert task_db.claim_calls == [5]
    assert git_service.ensure_repo_calls == [
        (REPO_URL, Path("/repo"), "main", "feature/a", MERGE_SHA, [SOURCE_SHA], 60, 60)
    ]
    assert note_provider.calls == [(REPO_URL, [MERGE_SHA, SOURCE_SHA])]
    assert git_service.changed_file_calls == [(Path("/repo"), "c" * 40, MERGE_SHA)]
    assert git_service.show_file_calls == [(Path("/repo"), MERGE_SHA, "app.py")]
    assert git_service.metadata_calls == [(Path("/repo"), MERGE_SHA), (Path("/repo"), SOURCE_SHA)]

    assert len(notes_service.calls) == 1
    repo_url, notes_data = notes_service.calls[0]
    assert repo_url == REPO_URL
    assert [note["commit_sha"] for note in notes_data] == [MERGE_SHA, SOURCE_SHA]
    assert [note["branch"] for note in notes_data] == ["main", "feature/a"]
    note_bodies = []
    note_prompts = []
    for note in notes_data:
        body, metadata = _split_note(note["content"])
        note_bodies.append(body)
        note_prompts.append(metadata["prompts"])
    assert note_bodies == ["app.py\n  source_prompt 1-2"] * 2
    assert note_prompts == [{"source_prompt": {}}] * 2
    assert notes_data[0]["author_name"] == "Author a"
    assert notes_data[1]["author_email"] == "b@example.com"
    assert [note["commit_time"] for note in notes_data] == [1715555555, 1715555555]
    assert task_db.successes == [("task-1", {"created": 2, "updated": 0})]
    assert task_db.failures == []


def test_process_next_task_derives_empty_source_shas_and_upserts_notes():
    task_db = FakeTaskDatabase(source_commit_shas=[])
    git_service = FakeGitService(derived_shas=[SOURCE_SHA])
    note_provider = FakeNoteProvider()
    notes_service = FakeNotesService()
    service = CodeupMergeAuthorshipService(
        task_db=task_db,
        git_service=git_service,
        note_provider=note_provider,
        notes_service=notes_service,
        config={
            "repo_path": "/repo",
            "clone_timeout_seconds": 11,
            "fetch_timeout_seconds": 22,
        },
    )

    result = service.process_next_task()

    assert result == {"success": True, "processed": 1, "summary": {"created": 2, "updated": 0}}
    assert git_service.ensure_repo_calls == [
        (REPO_URL, Path("/repo"), "main", "feature/a", MERGE_SHA, [], 11, 22)
    ]
    assert git_service.merge_base_calls == [(Path("/repo"), "feature/a", MERGE_SHA)]
    assert git_service.rev_list_calls == [(Path("/repo"), "c" * 40 + "..feature/a")]
    assert git_service.changed_file_calls == [(Path("/repo"), "c" * 40, MERGE_SHA)]
    assert note_provider.calls == [(REPO_URL, [MERGE_SHA, SOURCE_SHA])]
    assert [note["commit_sha"] for note in notes_service.calls[0][1]] == [MERGE_SHA, SOURCE_SHA]
    assert task_db.successes == [("task-1", {"created": 2, "updated": 0})]
    assert task_db.failures == []


def test_process_next_task_fails_empty_source_shas_when_derivation_returns_no_commits():
    task_db = FakeTaskDatabase(source_commit_shas=[])
    notes_service = FakeNotesService()
    service = CodeupMergeAuthorshipService(
        task_db=task_db,
        git_service=FakeGitService(derived_shas=[]),
        note_provider=FakeNoteProvider(),
        notes_service=notes_service,
        config={"repo_path": "/repo"},
    )

    result = service.process_next_task()

    assert result["success"] is False
    assert result["processed"] == 1
    assert "source_commit_shas" in result["error"]
    assert task_db.successes == []
    assert len(task_db.failures) == 1
    assert task_db.failures[0][0] == "task-1"
    assert "source_commit_shas" in task_db.failures[0][1]
    assert notes_service.calls == []


def test_process_next_task_marks_failed_when_git_service_raises_without_upsert():
    task_db = FakeTaskDatabase()
    notes_service = FakeNotesService()
    service = CodeupMergeAuthorshipService(
        task_db=task_db,
        git_service=FakeGitService(fail_on_changed_files=True),
        note_provider=FakeNoteProvider(),
        notes_service=notes_service,
        config={"repo_path": "/repo"},
    )

    result = service.process_next_task()

    assert result == {"success": False, "processed": 1, "error": "invalid git revision"}
    assert task_db.successes == []
    assert task_db.failures == [("task-1", "invalid git revision")]
    assert notes_service.calls == []


def test_repo_path_defaults_to_distinct_cache_child_per_repo_url():
    service = CodeupMergeAuthorshipService(config={"repo_cache_dir": "/cache/codeup_repos"})
    first_task = SimpleNamespace(repo_url=REPO_URL)
    second_task = SimpleNamespace(repo_url=OTHER_REPO_URL)

    first_path = service._repo_path(first_task)
    second_path = service._repo_path(second_task)

    assert first_path.parent == Path("/cache/codeup_repos")
    assert second_path.parent == Path("/cache/codeup_repos")
    assert first_path != Path("/cache/codeup_repos")
    assert second_path != Path("/cache/codeup_repos")
    assert first_path != second_path


def test_process_next_task_passes_cache_child_path_to_ensure_repo():
    task_db = FakeTaskDatabase()
    git_service = FakeGitService()
    service = CodeupMergeAuthorshipService(
        task_db=task_db,
        git_service=git_service,
        note_provider=FakeNoteProvider(),
        notes_service=FakeNotesService(),
        config={"repo_cache_dir": "/cache/codeup_repos"},
    )

    service.process_next_task()

    repo_dir = git_service.ensure_repo_calls[0][1]
    assert repo_dir.parent == Path("/cache/codeup_repos")
    assert repo_dir != Path("/cache/codeup_repos")


def test_repo_path_preserves_explicit_repo_path_override():
    service = CodeupMergeAuthorshipService(
        config={"repo_cache_dir": "/cache/codeup_repos", "repo_path": "/explicit/repo"}
    )

    repo_path = service._repo_path(SimpleNamespace(repo_url=REPO_URL))

    assert repo_path == Path("/explicit/repo")


def test_repo_path_preserves_repo_paths_mapping_override_for_repo_url():
    service = CodeupMergeAuthorshipService(
        config={
            "repo_cache_dir": "/cache/codeup_repos",
            "repo_paths": {REPO_URL: "/mapped/repo"},
        }
    )

    repo_path = service._repo_path(SimpleNamespace(repo_url=REPO_URL))

    assert repo_path == Path("/mapped/repo")
