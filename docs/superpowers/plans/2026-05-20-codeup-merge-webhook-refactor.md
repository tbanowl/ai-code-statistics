# Codeup Merge Webhook Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Codeup merge webhook processing so payload normalization, event classification, repository merge resolution, and authorship policy are separated and aligned with Git-AI Standard v3.0.0.

**Architecture:** The webhook route stays thin and delegates to `CodeupWebhookService`. `CodeupWebhookService` uses a payload normalizer and event classifier to decide whether to create or skip tasks. The scheduler worker uses a repository resolver to determine the real merge type, then dispatches to a merge authorship policy that performs standard/squash/rebase/fast-forward behavior before writing DB-backed authorship notes.

**Tech Stack:** Python 3.10+, Flask, SQLAlchemy 2.0, pytest, existing `core.scheduler`, existing `CodeupGitService`, existing `AuthorshipNotesDatabase` / `NotesRestService`.

---

## File Structure

- Create `core/services/codeup_payload_normalizer.py`: dataclasses and logic for converting old/new Codeup payloads into a stable internal event.
- Create `core/services/codeup_merge_event_classifier.py`: classifies normalized events as `merge_candidate`, `push_update`, `mr_update`, `invalid`, or `unknown`.
- Modify `core/services/codeup_webhook_service.py`: delegate parsing/classification to the new components and only create tasks for merge candidates.
- Modify `api/routes/codeup_webhook.py`: keep HTTP handling thin; preserve the current dependency accessor pattern.
- Modify `core/database/models.py`: extend `CodeupMergeAuthorshipTask` with event/normalization/merge/skipped fields.
- Modify `core/database/codeup_merge_authorship_db.py`: persist new fields and support skipped status.
- Modify `sql/metrics_schema_mysql.sql`: keep MySQL DDL aligned with the ORM.
- Create `core/services/repository_merge_resolver.py`: classify real Git result as standard/squash/rebase/fast-forward/unknown.
- Create `core/services/merge_authorship_policy.py`: dispatch authorship behavior by merge type.
- Modify `core/services/codeup_merge_authorship_service.py`: reduce to orchestration over DB, Git service, note provider, resolver, policy, and notes service.
- Modify `core/services/codeup_git_service.py`: add minimal Git helpers needed by the resolver if absent.
- Update tests under `tests/unit/test_services/`, `tests/unit/test_database/`, `tests/unit/test_scheduler/`, and `tests/integration/`.

---

## Task 1: Codeup Payload Normalizer

**Files:**
- Create: `core/services/codeup_payload_normalizer.py`
- Test: `tests/unit/test_services/test_codeup_payload_normalizer.py`

- [ ] **Step 1: Write the failing normalizer tests**

Create `tests/unit/test_services/test_codeup_payload_normalizer.py`:

```python
from core.services.codeup_payload_normalizer import CodeupPayloadNormalizer


def test_normalizes_new_codeup_payload_with_stable_ids():
    payload = {
        "version": "new",
        "object_kind": "merge_request",
        "user": {"aliyun_pk": "u-1"},
        "repository": {"git_http_url": "https://codeup.aliyun.com/org/repo.git"},
        "object_attributes": {
            "biz_id": "mr-biz-42",
            "local_id": 7,
            "id": 99,
            "project_id": "project-1",
            "source_branch": "feature/a",
            "target_branch": "main",
            "merge_commit_sha": "a" * 40,
            "action": "merge",
            "state": "merged",
            "is_update_by_push": False,
        },
        "commits": [{"id": "b" * 40}, {"sha": "c" * 40}],
    }

    event = CodeupPayloadNormalizer().normalize(payload)

    assert event.repo_url == "https://codeup.aliyun.com/org/repo.git"
    assert event.project_id == "project-1"
    assert event.merge_request_id == "mr-biz-42"
    assert event.source_branch == "feature/a"
    assert event.target_branch == "main"
    assert event.merge_commit_sha == "a" * 40
    assert event.source_commit_shas == ["b" * 40, "c" * 40]
    assert event.event_action == "merge"
    assert event.payload_version_hint == "new"
    assert event.is_update_by_push is False


def test_normalizes_legacy_payload_with_fallbacks():
    payload = {
        "object_kind": "merge_request",
        "project": {"git_http_url": "https://codeup.aliyun.com/org/legacy.git", "id": 123},
        "object_attributes": {
            "iid": 12,
            "source_branch": "feature/legacy",
            "target_branch": "master",
            "merge_commit_sha": "d" * 40,
            "state": "merged_success",
        },
    }

    event = CodeupPayloadNormalizer().normalize(payload)

    assert event.repo_url == "https://codeup.aliyun.com/org/legacy.git"
    assert event.project_id == "123"
    assert event.merge_request_id == "12"
    assert event.event_action == "merged_success"
    assert event.payload_version_hint == "legacy"
    assert event.source_commit_shas == []


def test_missing_repo_url_is_recorded_without_guessing():
    payload = {
        "object_kind": "merge_request",
        "object_attributes": {"iid": 12, "state": "opened"},
    }

    event = CodeupPayloadNormalizer().normalize(payload)

    assert event.repo_url is None
    assert event.merge_request_id == "12"
    assert event.payload_version_hint == "unknown"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_services/test_codeup_payload_normalizer.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'core.services.codeup_payload_normalizer'`.

- [ ] **Step 3: Implement the normalizer**

Create `core/services/codeup_payload_normalizer.py`:

```python
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
```

- [ ] **Step 4: Run the normalizer tests**

Run: `pytest tests/unit/test_services/test_codeup_payload_normalizer.py -v`

Expected: PASS, 3 tests passed.

---

## Task 2: Codeup Merge Event Classifier

**Files:**
- Create: `core/services/codeup_merge_event_classifier.py`
- Test: `tests/unit/test_services/test_codeup_merge_event_classifier.py`

- [ ] **Step 1: Write the failing classifier tests**

Create `tests/unit/test_services/test_codeup_merge_event_classifier.py`:

```python
from core.services.codeup_merge_event_classifier import CodeupMergeEventClassifier
from core.services.codeup_payload_normalizer import NormalizedCodeupMergeEvent


def _event(**overrides):
    values = {
        "repo_url": "https://codeup.aliyun.com/org/repo.git",
        "project_id": "100",
        "merge_request_id": "42",
        "source_branch": "feature/a",
        "target_branch": "main",
        "merge_commit_sha": "a" * 40,
        "source_commit_shas": [],
        "event_action": "merged",
        "payload_version_hint": "new",
        "is_update_by_push": False,
        "raw_payload": {},
    }
    values.update(overrides)
    return NormalizedCodeupMergeEvent(**values)


def test_merged_event_is_merge_candidate():
    result = CodeupMergeEventClassifier().classify(_event())
    assert result.event_kind == "merge_candidate"
    assert result.should_enqueue is True
    assert result.http_status == 200


def test_push_update_is_skipped():
    result = CodeupMergeEventClassifier().classify(_event(event_action="update", is_update_by_push=True))
    assert result.event_kind == "push_update"
    assert result.should_enqueue is False
    assert result.skipped_reason == "push_update"


def test_open_event_is_skipped_as_mr_update():
    result = CodeupMergeEventClassifier().classify(_event(event_action="open", merge_commit_sha=None))
    assert result.event_kind == "mr_update"
    assert result.should_enqueue is False
    assert result.skipped_reason == "not_merge_completion"


def test_missing_repo_is_invalid():
    result = CodeupMergeEventClassifier().classify(_event(repo_url=None))
    assert result.event_kind == "invalid"
    assert result.should_enqueue is False
    assert result.http_status == 400
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_services/test_codeup_merge_event_classifier.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'core.services.codeup_merge_event_classifier'`.

- [ ] **Step 3: Implement the classifier**

Create `core/services/codeup_merge_event_classifier.py`:

```python
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
```

- [ ] **Step 4: Run the classifier tests**

Run: `pytest tests/unit/test_services/test_codeup_merge_event_classifier.py -v`

Expected: PASS, 4 tests passed.

---

## Task 3: Refactor Webhook Service and API Behavior

**Files:**
- Modify: `core/services/codeup_webhook_service.py`
- Modify: `api/routes/codeup_webhook.py`
- Test: `tests/unit/test_services/test_codeup_webhook_service.py`
- Test: `tests/integration/test_codeup_webhook_api.py`

- [ ] **Step 1: Update the failing service tests**

In `tests/unit/test_services/test_codeup_webhook_service.py`, add tests that assert skipped events do not create DB tasks and new payload fields are passed through as normalized data:

```python
def test_open_event_is_skipped_without_creating_task():
    db = FakeCodeupMergeAuthorshipDatabase()
    service = CodeupWebhookService(database=db)

    result = service.enqueue_merge_event({
        "object_kind": "merge_request",
        "repository": {"git_http_url": "https://codeup.aliyun.com/org/repo.git"},
        "object_attributes": {"biz_id": "mr-1", "action": "open"},
    })

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["reason"] == "not_merge_completion"
    assert db.created == []


def test_new_payload_creates_task_with_normalized_fields():
    db = FakeCodeupMergeAuthorshipDatabase()
    service = CodeupWebhookService(database=db)

    result = service.enqueue_merge_event({
        "version": "new",
        "object_kind": "merge_request",
        "repository": {"git_http_url": "https://codeup.aliyun.com/org/repo.git"},
        "object_attributes": {
            "biz_id": "mr-biz-1",
            "project_id": "project-1",
            "source_branch": "feature/a",
            "target_branch": "main",
            "merge_commit_sha": "a" * 40,
            "action": "merge",
        },
    })

    assert result["success"] is True
    assert result["skipped"] is False
    assert db.created[0]["merge_request_id"] == "mr-biz-1"
    assert db.created[0]["event_kind"] == "merge_candidate"
    assert db.created[0]["payload_version_hint"] == "new"
```

- [ ] **Step 2: Run the service test to verify failure**

Run: `pytest tests/unit/test_services/test_codeup_webhook_service.py -v`

Expected: FAIL because `create_or_update_task()` does not accept the new keyword arguments yet.

- [ ] **Step 3: Refactor the service to use normalizer/classifier**

Modify `core/services/codeup_webhook_service.py` so `CodeupWebhookService.__init__` accepts optional `normalizer` and `classifier`, and `enqueue_merge_event()` follows this shape:

```python
event = self.normalizer.normalize(payload)
classification = self.classifier.classify(event)
if not classification.should_enqueue:
    if classification.http_status == 400:
        raise InvalidCodeupPayload(classification.skipped_reason or "invalid_codeup_payload")
    return {
        "success": True,
        "skipped": True,
        "reason": classification.skipped_reason,
        "event_kind": classification.event_kind,
    }
task, created = self.database.create_or_update_task(
    repo_url=self._required(event.repo_url, "repo_url"),
    project_id=event.project_id,
    merge_request_id=self._required(event.merge_request_id, "merge_request_id"),
    source_branch=event.source_branch,
    target_branch=event.target_branch,
    merge_commit_sha=self._required(event.merge_commit_sha, "merge_commit_sha"),
    source_commit_shas=event.source_commit_shas,
    payload=payload,
    event_kind=classification.event_kind,
    payload_version_hint=event.payload_version_hint,
    normalized_payload=event.to_dict(),
    skipped_reason=None,
)
return {"success": True, "skipped": False, "task_id": task.id, "created": created}
```

- [ ] **Step 4: Update API integration tests**

In `tests/integration/test_codeup_webhook_api.py`, add coverage for a skipped open event:

```python
def test_open_event_returns_skipped(client):
    response = client.post("/webhook/codeup/merge", json={
        "object_kind": "merge_request",
        "repository": {"git_http_url": "https://codeup.aliyun.com/org/repo.git"},
        "object_attributes": {"biz_id": "mr-1", "action": "open"},
    })

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["skipped"] is True
```

- [ ] **Step 5: Run webhook tests**

Run: `pytest tests/unit/test_services/test_codeup_webhook_service.py tests/integration/test_codeup_webhook_api.py -v`

Expected: PASS after Task 4 updates DB signatures; if run before Task 4, expected failure is the new DB method signature.

---

## Task 4: Task Model, SQL, and Database State Expansion

**Files:**
- Modify: `core/database/models.py`
- Modify: `core/database/codeup_merge_authorship_db.py`
- Modify: `sql/metrics_schema_mysql.sql`
- Test: `tests/unit/test_database/test_codeup_merge_authorship_db.py`

- [ ] **Step 1: Update the failing DB tests**

Add tests to `tests/unit/test_database/test_codeup_merge_authorship_db.py`:

```python
def test_create_or_update_task_persists_normalized_event_fields():
    db = CodeupMergeAuthorshipDatabase()
    task, created = db.create_or_update_task(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        project_id="project-1",
        merge_request_id="mr-1",
        source_branch="feature/a",
        target_branch="main",
        merge_commit_sha="a" * 40,
        source_commit_shas=["b" * 40],
        payload={"raw": True},
        event_kind="merge_candidate",
        payload_version_hint="new",
        normalized_payload={"repo_url": "https://codeup.aliyun.com/org/repo.git"},
        skipped_reason=None,
    )

    assert created is True
    assert task.event_kind == "merge_candidate"
    assert task.payload_version_hint == "new"
    assert "repo_url" in task.normalized_payload
    assert task.skipped_reason is None


def test_mark_skipped_records_reason():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create(db)

    db.mark_skipped(task.id, "unknown_merge_type", merge_type="unknown")

    stored = db.get_task(task.id)
    assert stored.status == "skipped"
    assert stored.skipped_reason == "unknown_merge_type"
    assert stored.merge_type == "unknown"
```

- [ ] **Step 2: Run the DB test to verify failure**

Run: `pytest tests/unit/test_database/test_codeup_merge_authorship_db.py -v`

Expected: FAIL because model fields and DB method parameters do not exist.

- [ ] **Step 3: Extend the ORM model**

Modify `CodeupMergeAuthorshipTask` in `core/database/models.py` with nullable string/text columns:

```python
event_kind = Column(String(64), nullable=True, index=True)
payload_version_hint = Column(String(32), nullable=True)
normalized_payload = Column(Text, nullable=True)
merge_type = Column(String(64), nullable=True, index=True)
skipped_reason = Column(String(255), nullable=True)
```

- [ ] **Step 4: Extend the database adapter**

Modify `create_or_update_task()` in `core/database/codeup_merge_authorship_db.py` to accept `event_kind`, `payload_version_hint`, `normalized_payload`, and `skipped_reason`. Serialize `normalized_payload` with `json.dumps(..., ensure_ascii=False, sort_keys=True)`.

Add:

```python
def mark_skipped(self, task_id: str, reason: str, merge_type: str | None = None) -> None:
    with self.get_session() as session:
        task = session.query(CodeupMergeAuthorshipTask).filter_by(id=task_id).one_or_none()
        if not task:
            return
        task.status = "skipped"
        task.skipped_reason = reason
        task.merge_type = merge_type
        task.updated_at = int(time.time() * 1000)
        session.commit()
```

- [ ] **Step 5: Update the MySQL DDL**

Modify `sql/metrics_schema_mysql.sql` table `codeup_merge_authorship_tasks` to include:

```sql
event_kind VARCHAR(64) NULL,
payload_version_hint VARCHAR(32) NULL,
normalized_payload LONGTEXT NULL,
merge_type VARCHAR(64) NULL,
skipped_reason VARCHAR(255) NULL,
KEY idx_codeup_merge_authorship_event_kind (event_kind),
KEY idx_codeup_merge_authorship_merge_type (merge_type),
```

- [ ] **Step 6: Run the DB tests**

Run: `pytest tests/unit/test_database/test_codeup_merge_authorship_db.py -v`

Expected: PASS.

---

## Task 5: Repository Merge Resolver

**Files:**
- Create: `core/services/repository_merge_resolver.py`
- Modify: `core/services/codeup_git_service.py`
- Test: `tests/unit/test_services/test_repository_merge_resolver.py`
- Test: `tests/unit/test_services/test_codeup_git_service.py`

- [ ] **Step 1: Write the failing resolver tests**

Create `tests/unit/test_services/test_repository_merge_resolver.py`:

```python
from core.services.repository_merge_resolver import RepositoryMergeResolver


class FakeGitService:
    def __init__(self, parents, rev_lists=None):
        self.parents = parents
        self.rev_lists = rev_lists or {}

    def commit_parents(self, repo_path, commit_sha):
        return self.parents.get(commit_sha, [])

    def rev_list(self, repo_path, revision_range):
        return self.rev_lists.get(revision_range, [])


def test_resolves_standard_merge_from_multiple_parents():
    resolver = RepositoryMergeResolver(git_service=FakeGitService({"m": ["p1", "p2"]}))
    result = resolver.resolve(repo_path="/tmp/repo", merge_commit_sha="m", source_commit_shas=[])

    assert result.merge_type == "standard_merge"
    assert result.reason == "merge_commit_has_multiple_parents"


def test_resolves_squash_when_single_parent_and_multiple_source_commits():
    resolver = RepositoryMergeResolver(git_service=FakeGitService({"s": ["p1"]}))
    result = resolver.resolve(repo_path="/tmp/repo", merge_commit_sha="s", source_commit_shas=["a", "b"])

    assert result.merge_type == "squash_merge"


def test_resolves_fast_forward_without_merge_commit():
    resolver = RepositoryMergeResolver(git_service=FakeGitService({}))
    result = resolver.resolve(repo_path="/tmp/repo", merge_commit_sha=None, source_commit_shas=["a"])

    assert result.merge_type == "fast_forward"


def test_resolves_unknown_when_commit_shape_is_not_enough():
    resolver = RepositoryMergeResolver(git_service=FakeGitService({"x": []}))
    result = resolver.resolve(repo_path="/tmp/repo", merge_commit_sha="x", source_commit_shas=[])

    assert result.merge_type == "unknown"
```

- [ ] **Step 2: Run the resolver test to verify failure**

Run: `pytest tests/unit/test_services/test_repository_merge_resolver.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Add the Git helper if absent**

Modify `core/services/codeup_git_service.py` to add:

```python
def commit_parents(self, repo_path: str, commit_sha: str) -> list[str]:
    output = self._run_git(repo_path, ["show", "-s", "--format=%P", commit_sha])
    return [parent for parent in output.strip().split() if parent]
```

Add a unit test in `tests/unit/test_services/test_codeup_git_service.py` using the existing fake runner style to assert the command is `git show -s --format=%P <sha>`.

- [ ] **Step 4: Implement the resolver**

Create `core/services/repository_merge_resolver.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from core.services.codeup_git_service import CodeupGitService


@dataclass(frozen=True)
class RepositoryMergeResolution:
    merge_type: str
    reason: str
    source_commit_shas: list[str]


class RepositoryMergeResolver:
    def __init__(self, git_service: CodeupGitService | None = None):
        self.git_service = git_service or CodeupGitService()

    def resolve(
        self,
        repo_path: str,
        merge_commit_sha: str | None,
        source_commit_shas: list[str],
    ) -> RepositoryMergeResolution:
        if not merge_commit_sha:
            return RepositoryMergeResolution("fast_forward", "no_merge_commit_sha", source_commit_shas)

        parents = self.git_service.commit_parents(repo_path, merge_commit_sha)
        if len(parents) > 1:
            return RepositoryMergeResolution("standard_merge", "merge_commit_has_multiple_parents", source_commit_shas)
        if len(parents) == 1 and len(source_commit_shas) > 1:
            return RepositoryMergeResolution("squash_merge", "single_parent_commit_with_multiple_source_commits", source_commit_shas)
        if len(parents) == 1 and len(source_commit_shas) == 1 and source_commit_shas[0] != merge_commit_sha:
            return RepositoryMergeResolution("rebase_merge", "single_parent_commit_with_rewritten_source_commit", source_commit_shas)
        return RepositoryMergeResolution("unknown", "insufficient_commit_graph", source_commit_shas)
```

- [ ] **Step 5: Run the resolver and Git service tests**

Run: `pytest tests/unit/test_services/test_repository_merge_resolver.py tests/unit/test_services/test_codeup_git_service.py -v`

Expected: PASS.

---

## Task 6: Merge Authorship Policy

**Files:**
- Create: `core/services/merge_authorship_policy.py`
- Modify: `core/services/merge_authorship_calculator.py`
- Test: `tests/unit/test_services/test_merge_authorship_policy.py`
- Test: `tests/unit/test_services/test_merge_authorship_calculator.py`

- [ ] **Step 1: Write the failing policy tests**

Create `tests/unit/test_services/test_merge_authorship_policy.py`:

```python
from core.services.merge_authorship_policy import MergeAuthorshipPolicy
from core.services.repository_merge_resolver import RepositoryMergeResolution


def test_standard_merge_does_not_copy_source_notes_to_merge_commit():
    result = MergeAuthorshipPolicy().apply(
        resolution=RepositoryMergeResolution("standard_merge", "multiple_parents", ["s1"]),
        target_note=None,
        source_notes={"s1": "app.py\n  p1 1-2\n---\n{\"schema_version\":\"authorship/3.0.0\",\"prompts\":{\"p1\":{}}}"},
        final_files={"app.py": ["one", "two"]},
    )

    assert result.notes_to_upsert == {}
    assert result.skipped_reason is None


def test_fast_forward_writes_no_notes():
    result = MergeAuthorshipPolicy().apply(
        resolution=RepositoryMergeResolution("fast_forward", "no_merge_commit", ["s1"]),
        target_note=None,
        source_notes={"s1": "note"},
        final_files={},
    )

    assert result.notes_to_upsert == {}
    assert result.skipped_reason == "fast_forward_no_new_note"


def test_unknown_writes_no_guessed_attribution():
    result = MergeAuthorshipPolicy().apply(
        resolution=RepositoryMergeResolution("unknown", "insufficient_commit_graph", []),
        target_note=None,
        source_notes={},
        final_files={},
    )

    assert result.notes_to_upsert == {}
    assert result.skipped_reason == "unknown_merge_type"
```

- [ ] **Step 2: Run the policy test to verify failure**

Run: `pytest tests/unit/test_services/test_merge_authorship_policy.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the policy result and conservative policies**

Create `core/services/merge_authorship_policy.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from core.services.merge_authorship_calculator import MergeAuthorshipCalculator
from core.services.repository_merge_resolver import RepositoryMergeResolution


@dataclass(frozen=True)
class MergeAuthorshipPolicyResult:
    notes_to_upsert: dict[str, str]
    skipped_reason: str | None


class MergeAuthorshipPolicy:
    def __init__(self, calculator: MergeAuthorshipCalculator | None = None):
        self.calculator = calculator or MergeAuthorshipCalculator()

    def apply(
        self,
        resolution: RepositoryMergeResolution,
        target_note: str | None,
        source_notes: dict[str, str],
        final_files: dict[str, list[str]],
        output_commit_sha: str | None = None,
    ) -> MergeAuthorshipPolicyResult:
        if resolution.merge_type == "standard_merge":
            return MergeAuthorshipPolicyResult({}, None)
        if resolution.merge_type == "fast_forward":
            return MergeAuthorshipPolicyResult({}, "fast_forward_no_new_note")
        if resolution.merge_type == "unknown":
            return MergeAuthorshipPolicyResult({}, "unknown_merge_type")
        if resolution.merge_type in {"squash_merge", "rebase_merge"} and output_commit_sha:
            merged_note = self.calculator.merge_notes(target_note, list(source_notes.values()), final_files)
            return MergeAuthorshipPolicyResult({output_commit_sha: merged_note}, None)
        return MergeAuthorshipPolicyResult({}, "missing_output_commit")
```

- [ ] **Step 4: Add squash/rebase preservation tests**

Extend `tests/unit/test_services/test_merge_authorship_policy.py` with a squash test that passes `output_commit_sha="squash"`, one source note, final files, and asserts `notes_to_upsert["squash"]` contains the source prompt id.

- [ ] **Step 5: Run the policy tests**

Run: `pytest tests/unit/test_services/test_merge_authorship_policy.py tests/unit/test_services/test_merge_authorship_calculator.py -v`

Expected: PASS.

---

## Task 7: Refactor Worker Orchestration

**Files:**
- Modify: `core/services/codeup_merge_authorship_service.py`
- Modify: `core/scheduler/tasks/codeup_merge_authorship_task.py`
- Test: `tests/unit/test_services/test_codeup_merge_authorship_service.py`
- Test: `tests/unit/test_scheduler/test_codeup_merge_authorship_task.py`

- [ ] **Step 1: Update the failing worker tests**

In `tests/unit/test_services/test_codeup_merge_authorship_service.py`, add fake resolver/policy tests:

```python
def test_process_task_marks_skipped_for_unknown_merge_type():
    task = FakeTask(merge_commit_sha="a" * 40, source_commit_shas="[]")
    db = FakeTaskDatabase(task)
    resolver = FakeResolver(merge_type="unknown")
    policy = FakePolicy(notes_to_upsert={}, skipped_reason="unknown_merge_type")
    service = CodeupMergeAuthorshipService(database=db, resolver=resolver, authorship_policy=policy)

    result = service.process_next_task()

    assert result["processed"] is True
    assert db.skipped == [(task.id, "unknown_merge_type", "unknown")]


def test_process_task_upserts_policy_notes_for_squash():
    task = FakeTask(merge_commit_sha="a" * 40, source_commit_shas='["b"]')
    db = FakeTaskDatabase(task)
    resolver = FakeResolver(merge_type="squash_merge")
    policy = FakePolicy(notes_to_upsert={"a" * 40: "note"}, skipped_reason=None)
    notes = FakeNotesService()
    service = CodeupMergeAuthorshipService(database=db, resolver=resolver, authorship_policy=policy, notes_service=notes)

    result = service.process_next_task()

    assert result["processed"] is True
    assert notes.pushed[0]["notes"][0]["commit_sha"] == "a" * 40
    assert db.successes == [task.id]
```

- [ ] **Step 2: Run the worker test to verify failure**

Run: `pytest tests/unit/test_services/test_codeup_merge_authorship_service.py -v`

Expected: FAIL because constructor does not accept resolver/policy and DB has no `mark_skipped()`.

- [ ] **Step 3: Refactor service dependencies**

Modify `CodeupMergeAuthorshipService.__init__()` to accept optional `resolver` and `authorship_policy`. Default them to `RepositoryMergeResolver()` and `MergeAuthorshipPolicy()`.

- [ ] **Step 4: Refactor `_process_task()` orchestration**

Restructure `_process_task()` to follow:

```python
repo_path = self.git_service.ensure_repo(task.repo_url, self.repo_cache_dir)
source_commit_shas = self._source_commit_shas(task)
resolution = self.resolver.resolve(repo_path, task.merge_commit_sha, source_commit_shas)
self.database.update_merge_type(task.id, resolution.merge_type)
if resolution.merge_type in {"unknown", "fast_forward"}:
    self.database.mark_skipped(task.id, resolution.reason, merge_type=resolution.merge_type)
    return {"processed": True, "status": "skipped", "merge_type": resolution.merge_type}
notes = self.note_provider.batch_get_note_contents(task.repo_url, [task.merge_commit_sha, *source_commit_shas])
final_files = self._final_files(repo_path, task.merge_commit_sha)
policy_result = self.authorship_policy.apply(
    resolution=resolution,
    target_note=notes.get(task.merge_commit_sha),
    source_notes={sha: notes[sha] for sha in source_commit_shas if sha in notes},
    final_files=final_files,
    output_commit_sha=task.merge_commit_sha,
)
if policy_result.skipped_reason:
    self.database.mark_skipped(task.id, policy_result.skipped_reason, merge_type=resolution.merge_type)
    return {"processed": True, "status": "skipped", "merge_type": resolution.merge_type}
self.notes_service.batch_push_notes(task.repo_url, [
    {"commit_sha": commit_sha, "note_content": note_content}
    for commit_sha, note_content in policy_result.notes_to_upsert.items()
])
self.database.mark_success(task.id, {"merge_type": resolution.merge_type, "upserted": len(policy_result.notes_to_upsert)})
```

- [ ] **Step 5: Add DB helper for merge type**

Add `update_merge_type(task_id: str, merge_type: str) -> None` to `CodeupMergeAuthorshipDatabase` and cover it in DB tests.

- [ ] **Step 6: Run the worker and scheduler tests**

Run: `pytest tests/unit/test_services/test_codeup_merge_authorship_service.py tests/unit/test_scheduler/test_codeup_merge_authorship_task.py -v`

Expected: PASS.

---

## Task 8: End-to-End Regression and Documentation Alignment

**Files:**
- Modify: `tests/integration/test_codeup_webhook_api.py`
- Modify: `tests/unit/test_services/test_codeup_webhook_service.py`
- Modify: `docs/superpowers/plans/2026-05-20-codeup-merge-webhook-refactor.md` only if implementation discovers plan corrections

- [ ] **Step 1: Add integration regression for new payload**

Add an integration test that posts a `version: "new"` merged payload and asserts the API returns `success=True`, `skipped=False`, and a task id.

- [ ] **Step 2: Add regression for non-merge event**

Add an integration test that posts a Codeup MR update payload and asserts `success=True`, `skipped=True`, and no DB task is created.

- [ ] **Step 3: Run the focused Codeup test suite**

Run:

```bash
pytest \
  tests/unit/test_services/test_codeup_payload_normalizer.py \
  tests/unit/test_services/test_codeup_merge_event_classifier.py \
  tests/unit/test_services/test_repository_merge_resolver.py \
  tests/unit/test_services/test_merge_authorship_policy.py \
  tests/unit/test_services/test_codeup_webhook_service.py \
  tests/unit/test_services/test_codeup_merge_authorship_service.py \
  tests/unit/test_database/test_codeup_merge_authorship_db.py \
  tests/unit/test_scheduler/test_codeup_merge_authorship_task.py \
  tests/integration/test_codeup_webhook_api.py \
  -v
```

Expected: PASS.

- [ ] **Step 4: Run diagnostics on modified Python files**

Run LSP diagnostics on:

```text
core/services/codeup_payload_normalizer.py
core/services/codeup_merge_event_classifier.py
core/services/repository_merge_resolver.py
core/services/merge_authorship_policy.py
core/services/codeup_webhook_service.py
core/services/codeup_merge_authorship_service.py
core/services/codeup_git_service.py
core/database/models.py
core/database/codeup_merge_authorship_db.py
api/routes/codeup_webhook.py
```

Expected: no errors.

- [ ] **Step 5: Run broader backend verification**

Run: `pytest tests/unit/test_services tests/unit/test_database tests/unit/test_scheduler tests/integration/test_codeup_webhook_api.py -v`

Expected: PASS. If unrelated pre-existing tests fail, record exact failures and keep the Codeup-focused suite passing.

---

## Self-Review Checklist

- Design goal covered by Task 1 through Task 8.
- Payload normalization covered by Task 1.
- Event classification covered by Task 2.
- Task model and SQL extension covered by Task 4.
- Repository merge resolver covered by Task 5.
- Merge authorship policy covered by Task 6.
- Worker orchestration covered by Task 7.
- Integration and verification covered by Task 8.
- This plan intentionally omits commit commands because committing requires explicit user request.
