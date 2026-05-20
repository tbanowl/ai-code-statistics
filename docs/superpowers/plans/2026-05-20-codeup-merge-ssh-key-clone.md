# Codeup Merge SSH Key Clone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Codeup merge AI authorship recalculation clone and fetch repositories through an SSH key, and requeue tasks without failing or consuming retry attempts when no SSH key is available.

**Architecture:** `CodeupMergeAuthorshipService` owns the business decision: acquire an SSH key before Git work, and release the claimed task back to `pending` if no key is available. `CodeupGitService` owns Git execution: when given a private key it creates a temporary key file, sets `GIT_SSH_COMMAND`, converts HTTP(S) Codeup URLs to SSH URLs consistently with `GitCloneService`, and uses that environment for both clone and fetch. `CodeupMergeAuthorshipDatabase` gets a focused method to release a claimed task without marking it failed/skipped/success.

**Tech Stack:** Python 3.10+, SQLAlchemy, pytest, subprocess Git CLI, existing `SshKeyService`, existing Codeup merge authorship services.

---

## File Structure

- Modify `core/database/codeup_merge_authorship_db.py`
  - Add `release_for_retry(task_id: str, reason: str) -> None` to change a `processing` task back to `pending`, decrement the claim attempt by one without going below zero, and record `last_error`.
- Modify `tests/unit/test_database/test_codeup_merge_authorship_db.py`
  - Add database tests proving missing-key release does not consume attempts and does not use terminal statuses.
- Modify `core/services/codeup_git_service.py`
  - Extend `GitRunner` to accept an optional environment mapping while preserving current test doubles as much as possible.
  - Add SSH helper methods for private key normalization/validation, temporary key file lifecycle, SSH command construction, and Codeup HTTP(S) to SSH URL conversion.
  - Extend `ensure_repo()` with optional `private_key: str | None = None`, and use SSH env for clone and fetch when present.
- Modify `tests/unit/test_services/test_codeup_git_service.py`
  - Add tests for clone/fetch using SSH env, existing repo fetch using SSH env, temporary key cleanup, and invalid private key rejection.
- Modify `core/services/codeup_merge_authorship_service.py`
  - Inject `SshKeyService`.
  - Fetch an SSH key before `ensure_repo()`.
  - Return a release result when key is missing, and call `task_db.release_for_retry()` in `process_next_task()`.
  - Pass the private key into `CodeupGitService.ensure_repo()`.
- Modify `tests/unit/test_services/test_codeup_merge_authorship_service.py`
  - Extend fakes and add tests for missing-key requeue behavior and private-key propagation.

---

### Task 1: Database Release Method

**Files:**
- Modify: `core/database/codeup_merge_authorship_db.py:265-327`
- Test: `tests/unit/test_database/test_codeup_merge_authorship_db.py`

- [ ] **Step 1: Write the failing database test for releasing a claimed task**

Append this test to `tests/unit/test_database/test_codeup_merge_authorship_db.py`:

```python
def test_release_for_retry_requeues_processing_task_without_consuming_attempt():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create(db)
    claimed = db.claim_next_task(max_attempts=3)
    assert claimed is not None
    assert claimed.status == "processing"
    assert claimed.attempts == 1

    db.release_for_retry(claimed.id, "missing ssh key for Codeup merge authorship")

    released = db.get_task(task.id)
    assert released is not None
    assert released.status == "pending"
    assert released.attempts == 0
    assert released.last_error == "missing ssh key for Codeup merge authorship"

    reclaimed = db.claim_next_task(max_attempts=3)
    assert reclaimed is not None
    assert reclaimed.id == task.id
    assert reclaimed.status == "processing"
    assert reclaimed.attempts == 1
```

- [ ] **Step 2: Run the new database test and verify it fails**

Run:

```bash
pytest tests/unit/test_database/test_codeup_merge_authorship_db.py::test_release_for_retry_requeues_processing_task_without_consuming_attempt -v
```

Expected: FAIL with `AttributeError: 'CodeupMergeAuthorshipDatabase' object has no attribute 'release_for_retry'`.

- [ ] **Step 3: Implement `release_for_retry()`**

In `core/database/codeup_merge_authorship_db.py`, add this method after `mark_failed()` and before `mark_skipped()`:

```python
    def release_for_retry(self, task_id: str, reason: str) -> None:
        """Release a claimed task back to pending without consuming an attempt."""
        with session_scope(self.engine) as session:
            task = session.execute(
                select(CodeupMergeAuthorshipTask).where(
                    CodeupMergeAuthorshipTask.id == task_id
                )
            ).scalar_one_or_none()
            if task is None:
                return

            task.status = "pending"
            task.attempts = max(int(task.attempts or 0) - 1, 0)
            task.last_error = reason
```

- [ ] **Step 4: Run database tests for task status behavior**

Run:

```bash
pytest tests/unit/test_database/test_codeup_merge_authorship_db.py -v
```

Expected: PASS.

---

### Task 2: CodeupGitService SSH Clone/Fetch Support

**Files:**
- Modify: `core/services/codeup_git_service.py:1-176`
- Test: `tests/unit/test_services/test_codeup_git_service.py`

- [ ] **Step 1: Update the Git service fake runner to record env**

In `tests/unit/test_services/test_codeup_git_service.py`, replace `FakeRunner` with:

```python
class FakeRunner:
    def __init__(self, stdout_by_args):
        self.stdout_by_args = stdout_by_args
        self.calls = []

    def __call__(self, args, cwd, timeout, env=None):
        self.calls.append((args, cwd, timeout, env))
        return self.stdout_by_args[tuple(args)]
```

Then update existing `runner.calls` assertions in this file by adding `None` as the fourth tuple item. For example:

```python
assert runner.calls == [(["git", "rev-list", "base..head"], Path("/repo"), 60, None)]
```

For multi-call assertions, each tuple should become `(args, cwd, timeout, None)`.

- [ ] **Step 2: Add failing tests for SSH clone and fetch env propagation**

Append these tests to `tests/unit/test_services/test_codeup_git_service.py`:

```python
VALID_PRIVATE_KEY = """-----BEGIN OPENSSH PRIVATE KEY-----
abc123
-----END OPENSSH PRIVATE KEY-----
"""


def test_ensure_repo_with_private_key_clones_and_fetches_with_git_ssh_command(tmp_path):
    ssh_repo_url = "ssh://git@codeup.aliyun.com/org/repo.git"
    runner = FakeRunner(
        {
            ("git", "clone", ssh_repo_url, str(tmp_path / "repo")): "",
            ("git", "fetch", "origin", "main", "feature/a", "a" * 40, "b" * 40): "",
        }
    )
    service = CodeupGitService(runner=runner)

    result = service.ensure_repo(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        repo_dir=tmp_path / "repo",
        target_branch="main",
        source_branch="feature/a",
        merge_commit_sha="a" * 40,
        source_commit_shas=["b" * 40],
        clone_timeout=12,
        fetch_timeout=34,
        private_key=VALID_PRIVATE_KEY,
    )

    assert result == tmp_path / "repo"
    assert len(runner.calls) == 2
    clone_call, fetch_call = runner.calls
    assert clone_call[0] == ["git", "clone", ssh_repo_url, str(tmp_path / "repo")]
    assert fetch_call[0] == ["git", "fetch", "origin", "main", "feature/a", "a" * 40, "b" * 40]
    for _, _, _, env in runner.calls:
        assert env is not None
        ssh_command = env["GIT_SSH_COMMAND"]
        assert "ssh -i" in ssh_command
        assert "StrictHostKeyChecking=no" in ssh_command
        assert "IdentitiesOnly=yes" in ssh_command


def test_existing_repo_fetches_with_private_key_env(tmp_path):
    repo_dir = tmp_path / "repo"
    (repo_dir / ".git").mkdir(parents=True)
    runner = FakeRunner(
        {
            ("git", "fetch", "origin", "main", "feature/a", "a" * 40): "",
        }
    )
    service = CodeupGitService(runner=runner)

    result = service.ensure_repo(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        repo_dir=repo_dir,
        target_branch="main",
        source_branch="feature/a",
        merge_commit_sha="a" * 40,
        source_commit_shas=[],
        clone_timeout=12,
        fetch_timeout=34,
        private_key=VALID_PRIVATE_KEY,
    )

    assert result == repo_dir
    assert len(runner.calls) == 1
    assert runner.calls[0][0] == ["git", "fetch", "origin", "main", "feature/a", "a" * 40]
    assert runner.calls[0][3] is not None
    assert "GIT_SSH_COMMAND" in runner.calls[0][3]


def test_ensure_repo_rejects_invalid_private_key(tmp_path):
    service = CodeupGitService(runner=FakeRunner({}))

    with pytest.raises(CodeupGitError, match="Invalid SSH private key"):
        service.ensure_repo(
            repo_url="https://codeup.aliyun.com/org/repo.git",
            repo_dir=tmp_path / "repo",
            target_branch="main",
            source_branch="feature/a",
            merge_commit_sha="a" * 40,
            source_commit_shas=[],
            clone_timeout=12,
            fetch_timeout=34,
            private_key="not a key",
        )
```

- [ ] **Step 3: Run the Git service tests and verify the new tests fail**

Run:

```bash
pytest tests/unit/test_services/test_codeup_git_service.py -v
```

Expected: FAIL because `ensure_repo()` does not accept `private_key`, `_run()` does not accept `env`, and existing assertions may need the fourth `None` item fixed.

- [ ] **Step 4: Implement SSH helpers and env-aware runner**

In `core/services/codeup_git_service.py`, replace imports and type alias at the top with:

```python
import os
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Callable, Mapping


GitRunner = Callable[[list[str], Path, int, Mapping[str, str] | None], str]
```

Inside `CodeupGitService`, add these helper methods before `_run()`:

```python
    def _run_with_optional_ssh_key(
        self,
        args: list[str],
        cwd: Path,
        timeout: int,
        private_key: str | None,
    ) -> str:
        if private_key is None:
            return self._run(args, cwd, timeout)

        normalized_key = self._normalize_private_key(private_key)
        if not self._validate_private_key_format(normalized_key):
            raise CodeupGitError("Invalid SSH private key")

        temp_key_path = self._write_private_key_to_temp(normalized_key)
        try:
            env = os.environ.copy()
            env["GIT_SSH_COMMAND"] = self._create_ssh_command(temp_key_path)
            return self._run(args, cwd, timeout, env=env)
        finally:
            if os.path.exists(temp_key_path):
                os.unlink(temp_key_path)

    def _normalize_private_key(self, private_key: str) -> str:
        key_content = private_key.strip().replace("\\n", "\n").replace("\r\n", "\n")
        if not key_content.endswith("\n"):
            key_content += "\n"
        return key_content

    def _validate_private_key_format(self, private_key: str) -> bool:
        if not private_key or not private_key.strip():
            return False
        key_content = private_key.strip()
        headers = [
            "-----BEGIN RSA PRIVATE KEY-----",
            "-----BEGIN OPENSSH PRIVATE KEY-----",
            "-----BEGIN EC PRIVATE KEY-----",
            "-----BEGIN DSA PRIVATE KEY-----",
            "-----BEGIN PRIVATE KEY-----",
            "-----BEGIN ED25519 PRIVATE KEY-----",
        ]
        footers = [
            "-----END RSA PRIVATE KEY-----",
            "-----END OPENSSH PRIVATE KEY-----",
            "-----END EC PRIVATE KEY-----",
            "-----END DSA PRIVATE KEY-----",
            "-----END PRIVATE KEY-----",
            "-----END ED25519 PRIVATE KEY-----",
        ]
        return any(header in key_content for header in headers) and any(
            footer in key_content for footer in footers
        )

    def _write_private_key_to_temp(self, private_key: str) -> str:
        fd, temp_path = tempfile.mkstemp(prefix="codeup_ssh_key_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as key_file:
                key_file.write(private_key)
            os.chmod(temp_path, 0o600)
            return temp_path
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _create_ssh_command(self, key_file_path: str) -> str:
        return (
            f'ssh -i "{key_file_path}" '
            "-o StrictHostKeyChecking=no "
            "-o UserKnownHostsFile=/dev/null "
            "-o IdentitiesOnly=yes "
            "-o LogLevel=ERROR"
        )

    def _repo_url_for_auth(self, repo_url: str, private_key: str | None) -> str:
        if private_key is None or not repo_url.startswith(("http://", "https://")):
            return repo_url
        ssh_url = repo_url.replace("https://", "ssh://git@", 1).replace(
            "http://", "ssh://git@", 1
        )
        if not ssh_url.endswith(".git"):
            ssh_url += ".git"
        return ssh_url
```

- [ ] **Step 5: Extend `ensure_repo()` and `_run()`**

In `core/services/codeup_git_service.py`, update `ensure_repo()` signature to include `private_key`:

```python
    def ensure_repo(
        self,
        repo_url: str,
        repo_dir: Path,
        target_branch: str,
        source_branch: str,
        merge_commit_sha: str,
        source_commit_shas: list[str],
        clone_timeout: int,
        fetch_timeout: int,
        private_key: str | None = None,
    ) -> Path:
```

Inside `ensure_repo()`, replace the existing clone call:

```python
        self._run(["git", "clone", repo_url, str(repo_dir)], repo_dir.parent, clone_timeout)
```

with:

```python
        clone_url = self._repo_url_for_auth(repo_url, private_key)
        self._run_with_optional_ssh_key(
            ["git", "clone", clone_url, str(repo_dir)],
            repo_dir.parent,
            clone_timeout,
            private_key,
        )
```

Update both `_fetch_required_refs()` calls in `ensure_repo()` to pass `private_key=private_key`.

Update `_fetch_required_refs()` signature to:

```python
    def _fetch_required_refs(
        self,
        repo_dir: Path,
        target_branch: str,
        source_branch: str,
        merge_commit_sha: str,
        source_commit_shas: list[str],
        timeout: int,
        private_key: str | None = None,
    ) -> None:
```

Replace its `_run()` call with:

```python
        self._run_with_optional_ssh_key(
            ["git", "fetch", "origin", *refs], repo_dir, timeout, private_key
        )
```

Update `_run()` signature and body:

```python
    def _run(
        self,
        args: list[str],
        cwd: Path,
        timeout: int = 60,
        env: Mapping[str, str] | None = None,
    ) -> str:
        if self.runner is not None:
            return self.runner(args, cwd, timeout, env)

        if not cwd.exists() or not cwd.is_dir():
            raise CodeupGitError(f"Invalid git working directory: {cwd}")

        try:
            result = subprocess.run(
                args=args,
                cwd=cwd,
                timeout=timeout,
                text=True,
                capture_output=True,
                check=True,
                env=env,
            )
            return result.stdout
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr or exc.stdout or str(exc)
            raise CodeupGitError(f"git command failed: {detail}") from exc
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            raise CodeupGitError(f"git command failed: {exc}") from exc
```

- [ ] **Step 6: Update subprocess kwargs test for `env=None`**

In `tests/unit/test_services/test_codeup_git_service.py::test_run_uses_expected_subprocess_kwargs_without_shell`, update expected kwargs to include:

```python
                "env": None,
```

- [ ] **Step 7: Run Git service tests**

Run:

```bash
pytest tests/unit/test_services/test_codeup_git_service.py -v
```

Expected: PASS.

---

### Task 3: Merge Authorship Service SSH Key Decision

**Files:**
- Modify: `core/services/codeup_merge_authorship_service.py:1-205`
- Test: `tests/unit/test_services/test_codeup_merge_authorship_service.py`

- [ ] **Step 1: Extend service tests with fake SSH key service and release tracking**

In `tests/unit/test_services/test_codeup_merge_authorship_service.py`, add this fake after `FakeTaskDatabase`:

```python
class FakeSshKeyService:
    def __init__(self, ssh_key_info=None):
        self.ssh_key_info = ssh_key_info
        self.calls = []

    def get_ssh_key_for_repo(self, repo_ssh_key_id):
        self.calls.append(repo_ssh_key_id)
        return self.ssh_key_info
```

Add this method to `FakeTaskDatabase`:

```python
    def release_for_retry(self, task_id, reason):
        self.releases.append((task_id, reason))
```

Add this field in `FakeTaskDatabase.__init__()` after `self.skips = []`:

```python
        self.releases = []
```

Update `FakeTaskDatabase.task` to include an SSH key id field:

```python
            ssh_key_id="ssh-key-1",
```

- [ ] **Step 2: Update fake Git service to accept `private_key`**

In `FakeGitService.ensure_repo()`, add a defaulted parameter after `fetch_timeout`:

```python
        private_key=None,
```

Update `self.ensure_repo_calls.append(...)` to include `private_key` as the final tuple item:

```python
                private_key,
```

Update existing assertions of `git_service.ensure_repo_calls` to include `None` as the final item when no `ssh_key_service` is injected. For example:

```python
assert git_service.ensure_repo_calls == [
    (REPO_URL, Path("/repo"), "main", "feature/a", MERGE_SHA, [SOURCE_SHA], 60, 60, None)
]
```

- [ ] **Step 3: Add failing test for missing SSH key release**

Append this test to `tests/unit/test_services/test_codeup_merge_authorship_service.py`:

```python
def test_process_next_task_releases_task_without_failure_when_ssh_key_missing():
    task_db = FakeTaskDatabase()
    git_service = FakeGitService()
    ssh_key_service = FakeSshKeyService(ssh_key_info=None)
    service = CodeupMergeAuthorshipService(
        task_db=task_db,
        git_service=git_service,
        ssh_key_service=ssh_key_service,
        note_provider=FakeNoteProvider(),
        notes_service=FakeNotesService(),
        merge_resolver=FakeMergeResolver(),
        merge_policy=FakeMergePolicy(),
        config={"repo_path": "/repo"},
    )

    result = service.process_next_task()

    assert result == {
        "success": True,
        "processed": 1,
        "released": True,
        "reason": "missing ssh key for Codeup merge authorship",
    }
    assert ssh_key_service.calls == ["ssh-key-1"]
    assert task_db.releases == [
        ("task-1", "missing ssh key for Codeup merge authorship")
    ]
    assert task_db.failures == []
    assert task_db.skips == []
    assert task_db.successes == []
    assert git_service.ensure_repo_calls == []
```

- [ ] **Step 4: Add failing test for private key propagation**

Append this test to `tests/unit/test_services/test_codeup_merge_authorship_service.py`:

```python
def test_process_next_task_passes_ssh_private_key_to_git_service():
    task_db = FakeTaskDatabase()
    git_service = FakeGitService()
    ssh_key_service = FakeSshKeyService(
        ssh_key_info={
            "id": "ssh-key-1",
            "key_name": "default",
            "public_key": "ssh-ed25519 AAAA",
            "private_key": "private-key-content",
        }
    )
    service = CodeupMergeAuthorshipService(
        task_db=task_db,
        git_service=git_service,
        ssh_key_service=ssh_key_service,
        note_provider=FakeNoteProvider(),
        notes_service=FakeNotesService(),
        merge_resolver=FakeMergeResolver(),
        merge_policy=FakeMergePolicy(),
        config={"repo_path": "/repo"},
    )

    result = service.process_next_task()

    assert result["success"] is True
    assert ssh_key_service.calls == ["ssh-key-1"]
    assert git_service.ensure_repo_calls == [
        (
            REPO_URL,
            Path("/repo"),
            "main",
            "feature/a",
            MERGE_SHA,
            [SOURCE_SHA],
            60,
            60,
            "private-key-content",
        )
    ]
    assert task_db.releases == []
    assert task_db.failures == []
```

- [ ] **Step 5: Run merge service tests and verify new tests fail**

Run:

```bash
pytest tests/unit/test_services/test_codeup_merge_authorship_service.py -v
```

Expected: FAIL because `CodeupMergeAuthorshipService.__init__()` does not accept `ssh_key_service`, missing-key release branch does not exist, and `ensure_repo()` is not called with `private_key`.

- [ ] **Step 6: Implement SSH key service injection and release branch**

In `core/services/codeup_merge_authorship_service.py`, add this import:

```python
from core.services.ssh_key_service import SshKeyService
```

Update `__init__()` signature after `notes_service`:

```python
        ssh_key_service: SshKeyService | None = None,
```

Set the instance field after `self.notes_service`:

```python
        self.ssh_key_service = ssh_key_service
```

Update `process_next_task()` after the skipped branch and before `mark_success()`:

```python
            if summary.get("release_reason"):
                reason = str(summary["release_reason"])
                self.task_db.release_for_retry(task.id, reason)
                return {
                    "success": True,
                    "processed": 1,
                    "released": True,
                    "reason": reason,
                }
```

At the top of `_process_task()` after `source_shas = ...`, add:

```python
        ssh_key_info = self._ssh_key_info(task)
        if ssh_key_info is None:
            return {"release_reason": "missing ssh key for Codeup merge authorship"}
        private_key = str(ssh_key_info["private_key"])
```

Update `ensure_repo()` call to pass the private key:

```python
            private_key=private_key,
```

Add this helper before `_repo_path()`:

```python
    def _ssh_key_info(self, task) -> dict[str, Any] | None:
        if self.ssh_key_service is None:
            return None
        return self.ssh_key_service.get_ssh_key_for_repo(getattr(task, "ssh_key_id", None))
```

- [ ] **Step 7: Preserve tests that do not inject SSH key service**

If existing tests now release every task because `ssh_key_service` defaults to `None`, change the helper to preserve backward-compatible no-SSH test behavior by returning a sentinel only when a service is injected:

```python
    def _ssh_key_info(self, task) -> dict[str, Any] | None:
        if self.ssh_key_service is None:
            return {"private_key": None}
        return self.ssh_key_service.get_ssh_key_for_repo(getattr(task, "ssh_key_id", None))
```

Then set `private_key = ssh_key_info.get("private_key")` instead of `str(...)`:

```python
        private_key = ssh_key_info.get("private_key")
```

This keeps old unit tests working while production will inject `SshKeyService` in the next task.

- [ ] **Step 8: Run merge service tests**

Run:

```bash
pytest tests/unit/test_services/test_codeup_merge_authorship_service.py -v
```

Expected: PASS.

---

### Task 4: Production Wiring for SshKeyService

**Files:**
- Modify: `core/services/codeup_merge_authorship_service.py:14-31`
- Test: `tests/unit/test_services/test_codeup_merge_authorship_service.py`

- [ ] **Step 1: Add a test that the default service constructs SshKeyService**

Append this test to `tests/unit/test_services/test_codeup_merge_authorship_service.py`:

```python
def test_default_service_constructs_ssh_key_service():
    service = CodeupMergeAuthorshipService(
        task_db=FakeTaskDatabase(),
        git_service=FakeGitService(),
        note_provider=FakeNoteProvider(),
        notes_service=FakeNotesService(),
        merge_resolver=FakeMergeResolver(),
        merge_policy=FakeMergePolicy(),
        config={"repo_path": "/repo"},
    )

    assert service.ssh_key_service is not None
```

- [ ] **Step 2: Run the new default wiring test and verify it fails if Task 3 used backward-compatible `None` default**

Run:

```bash
pytest tests/unit/test_services/test_codeup_merge_authorship_service.py::test_default_service_constructs_ssh_key_service -v
```

Expected: FAIL if `self.ssh_key_service = ssh_key_service`; PASS if already wired to a concrete default.

- [ ] **Step 3: Wire the default `SshKeyService`**

In `core/services/codeup_merge_authorship_service.py`, set the field to construct the real service by default:

```python
        self.ssh_key_service = ssh_key_service or SshKeyService()
```

Then simplify `_ssh_key_info()` to always call the service:

```python
    def _ssh_key_info(self, task) -> dict[str, Any] | None:
        return self.ssh_key_service.get_ssh_key_for_repo(getattr(task, "ssh_key_id", None))
```

Because default production behavior now enforces SSH keys, update older tests that do not care about SSH by injecting `ssh_key_service=FakeSshKeyService({"private_key": None})` or a helper factory. Prefer a helper:

```python
def _available_ssh_key_service(private_key=None):
    return FakeSshKeyService({"private_key": private_key})
```

Use `ssh_key_service=_available_ssh_key_service()` in existing `CodeupMergeAuthorshipService(...)` test setup calls, and use `ssh_key_service=FakeSshKeyService(ssh_key_info=None)` only in the missing-key test.

- [ ] **Step 4: Run merge service tests**

Run:

```bash
pytest tests/unit/test_services/test_codeup_merge_authorship_service.py -v
```

Expected: PASS.

---

### Task 5: Scheduler Summary for Released Tasks

**Files:**
- Modify: `core/scheduler/tasks/codeup_merge_authorship_task.py:37-70`
- Test: `tests/unit/test_scheduler/test_codeup_merge_authorship_task.py`

- [ ] **Step 1: Read current scheduler tests**

Run no command for this step. Open `tests/unit/test_scheduler/test_codeup_merge_authorship_task.py` and identify the fake service factory pattern used by scheduler tests.

- [ ] **Step 2: Add failing scheduler test for released tasks**

Add a test to `tests/unit/test_scheduler/test_codeup_merge_authorship_task.py` following the file's existing fake service style:

```python
def test_codeup_merge_authorship_task_counts_released_results_separately():
    module = import_module("core.scheduler.tasks.codeup_merge_authorship_task")
    task = module.CodeupMergeAuthorshipTask(
        config={
            "scheduler": {"jobs": {"codeup_merge_authorship": {"batch_size": 1}}},
            "codeup_webhook": {},
        },
        service_factory=lambda config: SimpleNamespace(
            process_next_task=lambda: {
                "success": True,
                "processed": 1,
                "released": True,
                "reason": "missing ssh key for Codeup merge authorship",
            }
        ),
    )

    result = task.execute()

    assert result == {"success": True, "processed": 1, "failed": 0, "released": 1}
```

If the file already imports `import_module` and `SimpleNamespace`, reuse those imports; otherwise add:

```python
from importlib import import_module
from types import SimpleNamespace
```

- [ ] **Step 3: Run scheduler test and verify it fails**

Run:

```bash
pytest tests/unit/test_scheduler/test_codeup_merge_authorship_task.py::test_codeup_merge_authorship_task_counts_released_results_separately -v
```

Expected: FAIL because `released` is not counted in the summary.

- [ ] **Step 4: Implement released count**

In `core/scheduler/tasks/codeup_merge_authorship_task.py`, initialize `released = 0` after `skipped = 0`:

```python
        released = 0
```

Inside the loop after skipped handling:

```python
            if result.get("released"):
                released += processed
```

Before logging, add `released` to summary only when non-zero:

```python
        if released:
            summary["released"] = released
```

Update the logger call to include released:

```python
            "Codeup Merge AI归属重算完成: processed=%s, failed=%s, skipped=%s, released=%s",
            total_processed,
            failures,
            skipped,
            released,
```

- [ ] **Step 5: Run scheduler tests**

Run:

```bash
pytest tests/unit/test_scheduler/test_codeup_merge_authorship_task.py -v
```

Expected: PASS.

---

### Task 6: Final Verification

**Files:**
- Verify modified files only.

- [ ] **Step 1: Run LSP diagnostics**

Run diagnostics on these files:

```text
core/database/codeup_merge_authorship_db.py
core/services/codeup_git_service.py
core/services/codeup_merge_authorship_service.py
core/scheduler/tasks/codeup_merge_authorship_task.py
tests/unit/test_database/test_codeup_merge_authorship_db.py
tests/unit/test_services/test_codeup_git_service.py
tests/unit/test_services/test_codeup_merge_authorship_service.py
tests/unit/test_scheduler/test_codeup_merge_authorship_task.py
```

Expected: zero errors.

- [ ] **Step 2: Run targeted unit tests**

Run:

```bash
pytest \
  tests/unit/test_database/test_codeup_merge_authorship_db.py \
  tests/unit/test_services/test_codeup_git_service.py \
  tests/unit/test_services/test_codeup_merge_authorship_service.py \
  tests/unit/test_scheduler/test_codeup_merge_authorship_task.py \
  -v
```

Expected: PASS.

- [ ] **Step 3: Run broader relevant tests**

Run:

```bash
pytest tests/unit/test_services/test_repository_merge_resolver.py tests/unit/test_services/test_codeup_webhook_service.py tests/integration/test_codeup_webhook_api.py -v
```

Expected: PASS.

- [ ] **Step 4: Run full Python test suite if targeted tests pass**

Run:

```bash
pytest
```

Expected: PASS. If unrelated pre-existing failures appear, capture exact failing tests and verify the four targeted files still pass.

---

## Self-Review

**Spec coverage:**
- SSH key acquisition before clone: Task 3 and Task 4.
- Missing SSH key does not fail, skip, or consume retry: Task 1 and Task 3.
- Clone and fetch both use SSH key: Task 2.
- Scheduler reports released tasks distinctly: Task 5.
- Verification: Task 6.

**Placeholder scan:** No TBD/TODO/placeholders remain. Each task has exact files, code snippets, commands, and expected outcomes.

**Type consistency:** `release_for_retry(task_id: str, reason: str) -> None`, `private_key: str | None = None`, `ssh_key_service.get_ssh_key_for_repo(repo_ssh_key_id)` and `ensure_repo(..., private_key=private_key)` are used consistently across plan tasks and tests.
