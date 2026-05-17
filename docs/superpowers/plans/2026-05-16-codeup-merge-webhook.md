# Codeup Merge Webhook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增阿里 Codeup 合并完成 webhook，异步重算 Merge Request 全部相关提交的 AI authorship，并只从 `authorship_notes` 表读取/写回 notes。

**Architecture:** Webhook 路由只做 payload 校验和任务入队；scheduler task 异步领取任务；服务层拉取仓库、读取 DB-backed notes、执行 target 优先归因合并并批量 upsert notes。Codeup 路径禁止读写 Git Notes。

**Tech Stack:** Python 3.10+、Flask、SQLAlchemy 2.0、pytest、现有 `core.scheduler`、系统 `git` CLI。

---

## 文件结构

- Modify `core/database/models.py`: 新增 `CodeupMergeAuthorshipTask` ORM。
- Create `core/database/codeup_merge_authorship_db.py`: 任务 upsert、claim、mark success/failed。
- Create `core/services/codeup_webhook_service.py`: Codeup payload 解析与入队。
- Create `api/routes/codeup_webhook.py`: `POST /webhook/codeup/merge`。
- Modify `app.py`, `api/routes/__init__.py`: 注册/导出蓝图。
- Create `core/services/codeup_note_provider.py`: 只从 `authorship_notes` 表批量读取 note content。
- Create `core/services/merge_authorship_calculator.py`: authorship log 解析、target 优先合并、序列化。
- Create `core/services/codeup_git_service.py`: Git CLI 封装。
- Create `core/services/codeup_merge_authorship_service.py`: 后台任务编排。
- Create `core/scheduler/tasks/codeup_merge_authorship_task.py`: scheduler 入口。
- Modify `config.yaml`, `sql/metrics_schema_mysql.sql`: 配置与 DDL。

---

## Task 1: 任务模型与 DB 层

**Files:**
- Modify: `core/database/models.py`
- Create: `core/database/codeup_merge_authorship_db.py`
- Modify: `sql/metrics_schema_mysql.sql`
- Test: `tests/unit/test_database/test_codeup_merge_authorship_db.py`

- [ ] **Step 1: 写失败测试**

Create `tests/unit/test_database/test_codeup_merge_authorship_db.py`:

```python
import json
import core.config.loader as loader
from core.database.base import Base, get_engine
from core.database.codeup_merge_authorship_db import CodeupMergeAuthorshipDatabase


def setup_function():
    loader.config_data = {"database": {"url": "sqlite:///:memory:", "echo": False}}
    Base.metadata.create_all(get_engine())


def _create(db):
    return db.create_or_update_task(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        project_id="1001",
        merge_request_id="42",
        source_branch="feature/a",
        target_branch="main",
        merge_commit_sha="a" * 40,
        source_commit_shas=["b" * 40, "c" * 40],
        payload={"object_attributes": {"iid": 42}},
    )


def test_create_or_update_task_creates_pending_task():
    task, created = _create(CodeupMergeAuthorshipDatabase())
    assert created is True
    assert task.status == "pending"
    assert task.attempts == 0
    assert json.loads(task.source_commit_shas) == ["b" * 40, "c" * 40]


def test_create_or_update_task_is_idempotent_for_same_merge():
    db = CodeupMergeAuthorshipDatabase()
    first, first_created = _create(db)
    second, second_created = _create(db)
    assert first_created is True
    assert second_created is False
    assert second.id == first.id


def test_claim_next_task_marks_processing_and_increments_attempts():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create(db)
    claimed = db.claim_next_task(max_attempts=3)
    assert claimed.id == task.id
    assert claimed.status == "processing"
    assert claimed.attempts == 1
    assert db.claim_next_task(max_attempts=3) is None


def test_mark_success_and_failure_updates_status_fields():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create(db)
    db.mark_failed(task.id, "fetch failed")
    assert db.get_task(task.id).status == "failed"
    assert db.get_task(task.id).last_error == "fetch failed"
    db.mark_success(task.id, {"created": 1, "updated": 2})
    assert db.get_task(task.id).status == "success"
    assert json.loads(db.get_task(task.id).result_summary) == {"created": 1, "updated": 2}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_database/test_codeup_merge_authorship_db.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: 实现 ORM 与 DB 类**

Add `CodeupMergeAuthorshipTask` after `AuthorshipNotes` in `core/database/models.py`, using fields from the spec: `repo_url`, `project_id`, `merge_request_id`, `source_branch`, `target_branch`, `merge_commit_sha`, `source_commit_shas`, `payload`, `status`, `attempts`, `last_error`, `result_summary`, `created_at`, `updated_at`; add unique constraint `(repo_url, merge_request_id, merge_commit_sha)` and indexes for status/repo/commit.

Create `core/database/codeup_merge_authorship_db.py` with methods:

```python
class CodeupMergeAuthorshipDatabase(BaseDatabase):
    def create_or_update_task(...) -> tuple[CodeupMergeAuthorshipTask, bool]: ...
    def get_task(self, task_id: str) -> CodeupMergeAuthorshipTask | None: ...
    def claim_next_task(self, max_attempts: int) -> CodeupMergeAuthorshipTask | None: ...
    def mark_success(self, task_id: str, result_summary: dict[str, Any]) -> None: ...
    def mark_failed(self, task_id: str, error: str) -> None: ...
```

Implementation requirements: serialize `payload`, `source_commit_shas`, and `result_summary` with `json.dumps(..., ensure_ascii=False, sort_keys=True)` where applicable; duplicate pending/failed tasks become `pending`; duplicate success/processing tasks keep their status.

- [ ] **Step 4: 更新 MySQL DDL**

Add `CREATE TABLE IF NOT EXISTS codeup_merge_authorship_tasks (...)` to `sql/metrics_schema_mysql.sql` with the same fields and unique key as the ORM.

- [ ] **Step 5: 验证**

Run: `pytest tests/unit/test_database/test_codeup_merge_authorship_db.py -v`

Expected: PASS, 4 tests passed.

---

## Task 2: Webhook payload 解析与入队服务

**Files:**
- Create: `core/services/codeup_webhook_service.py`
- Test: `tests/unit/test_services/test_codeup_webhook_service.py`

- [ ] **Step 1: 写失败测试**

Create tests for: merged payload creates task; non-merged returns `{"success": True, "skipped": True, "reason": "not_merged"}`; missing `merge_commit_sha` raises `InvalidCodeupPayload`; duplicate payload returns same task id and `created=False`.

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_services/test_codeup_webhook_service.py -v`

Expected: FAIL with missing module.

- [ ] **Step 3: 实现服务**

Create `core/services/codeup_webhook_service.py`:

```python
class InvalidCodeupPayload(ValueError):
    pass


class CodeupWebhookService:
    def __init__(self, database: CodeupMergeAuthorshipDatabase | None = None): ...
    def enqueue_merge_event(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def _repo_url(self, payload: dict[str, Any]) -> str: ...
    def _source_commit_shas(self, payload: dict[str, Any]) -> list[str]: ...
    def _string_required(self, value: Any, field_name: str) -> str: ...
```

Merged detection: accept `state in {"merged", "merged_success"}` or `action in {"merge", "merged"}`. Extract repo URL from `project.git_http_url`, `project.git_ssh_url`, `repository.git_http_url`, or `repository.url`. Extract MR id from `object_attributes.iid`, `object_attributes.id`, or top-level `merge_request_id`.

- [ ] **Step 4: 验证**

Run: `pytest tests/unit/test_services/test_codeup_webhook_service.py -v`

Expected: PASS.

---

## Task 3: Flask 路由

**Files:**
- Create: `api/routes/codeup_webhook.py`
- Modify: `app.py`
- Modify: `api/routes/__init__.py`
- Test: `tests/integration/test_codeup_webhook_api.py`

- [ ] **Step 1: 写失败集成测试**

Create tests for `POST /webhook/codeup/merge`: merged returns 200 with `success=True` and `data.task_id`; opened returns 200 with skipped; missing `merge_commit_sha` returns 400.

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/integration/test_codeup_webhook_api.py -v`

Expected: FAIL with 404 or import error.

- [ ] **Step 3: 实现并注册路由**

Create `api/routes/codeup_webhook.py` with `codeup_webhook_bp = Blueprint("codeup_webhook", __name__, url_prefix="/webhook/codeup")` and route `@codeup_webhook_bp.route("/merge", methods=["POST"])`. Empty body returns 400. `InvalidCodeupPayload` returns 400. Unexpected exception returns 500.

Modify `app.py` to import and register `codeup_webhook_bp`. Modify `api/routes/__init__.py` to export it.

- [ ] **Step 4: 验证**

Run: `pytest tests/integration/test_codeup_webhook_api.py -v`

Expected: PASS.

---

## Task 4: DB-backed note provider

**Files:**
- Create: `core/services/codeup_note_provider.py`
- Test: `tests/unit/test_services/test_codeup_note_provider.py`

- [ ] **Step 1: 写失败测试**

Seed `authorship_notes` using `NotesRestService.create_or_update_note()`. Assert `CodeupDatabaseNoteProvider().batch_get_note_contents(repo_url, [existing, missing])` returns only `{existing: content}`.

- [ ] **Step 2: 实现 provider**

Create:

```python
class CodeupDatabaseNoteProvider:
    def __init__(self, database: AuthorshipNotesDatabase | None = None): ...
    def batch_get_note_contents(self, repo_url: str, commit_shas: list[str]) -> dict[str, str]: ...
```

It must call `AuthorshipNotesDatabase.batch_get_notes(repo_url, commit_shas)` and must not call any `git notes` command.

- [ ] **Step 3: 验证**

Run: `pytest tests/unit/test_services/test_codeup_note_provider.py -v`

Expected: PASS.

---

## Task 5: Authorship log 解析与 target 优先合并

**Files:**
- Create: `core/services/merge_authorship_calculator.py`
- Test: `tests/unit/test_services/test_merge_authorship_calculator.py`

- [ ] **Step 1: 写失败测试**

Use target note `app.py\n  target_prompt 1-2\n---\n{"schema_version":"3","prompts":{"target_prompt":{}}}` and source note `app.py\n  source_prompt 2-3\n---\n{"schema_version":"3","prompts":{"source_prompt":{}}}`. Assert output keeps target line 2, includes source line 3, preserves both prompt ids, and missing source notes do not fail.

- [ ] **Step 2: 实现 calculator**

Create `MergeAuthorshipCalculator` with `merge_notes(target_note, source_notes, final_files)`, `parse_note(content)`, and `serialize_note(attestations, prompts)`. Parse `---` separated metadata JSON, expand ranges like `1-3,5`, compact ranges on output, and use `dict.setdefault()` so source attribution never overrides target attribution.

- [ ] **Step 3: 验证**

Run: `pytest tests/unit/test_services/test_merge_authorship_calculator.py -v`

Expected: PASS.

---

## Task 6: Git 服务封装

**Files:**
- Create: `core/services/codeup_git_service.py`
- Test: `tests/unit/test_services/test_codeup_git_service.py`

- [ ] **Step 1: 写失败测试**

Inject fake runner. Assert `rev_list(Path("/repo"), "base..head")` calls `git rev-list base..head` and splits stdout lines. Assert `commit_metadata()` parses `%an%x00%ae%x00%ct` into author name/email/time.

- [ ] **Step 2: 实现 Git service**

Create `CodeupGitService` with methods `rev_list`, `show_file_lines`, `changed_files`, `commit_metadata`, and private `_run` using `subprocess.run(..., text=True, capture_output=True, check=True)`.

- [ ] **Step 3: 验证**

Run: `pytest tests/unit/test_services/test_codeup_git_service.py -v`

Expected: PASS.

---

## Task 7: 后台 worker 服务

**Files:**
- Create: `core/services/codeup_merge_authorship_service.py`
- Test: `tests/unit/test_services/test_codeup_merge_authorship_service.py`

- [ ] **Step 1: 写失败测试**

Use fake task DB with one task, fake git returning changed file `app.py`, fake note provider returning one source note, and fake notes service capturing `batch_push_notes`. Assert `process_next_task()` upserts notes for merge commit and source commit, then marks task success.

- [ ] **Step 2: 实现 worker service**

Create `CodeupMergeAuthorshipService` with constructor-injected `task_db`, `git_service`, `note_provider`, `notes_service`, `config`. Implement `process_next_task()` to claim a task, call `_process_task()`, mark success/failure. `_process_task()` loads source shas, builds related shas including merge commit, reads note map from DB provider, reads changed file contents through Git service, generates note content through calculator, and writes via `NotesRestService.batch_push_notes()`.

- [ ] **Step 3: 验证**

Run: `pytest tests/unit/test_services/test_codeup_merge_authorship_service.py -v`

Expected: PASS.

---

## Task 8: Scheduler 与配置

**Files:**
- Create: `core/scheduler/tasks/codeup_merge_authorship_task.py`
- Modify: `config.yaml`

- [ ] **Step 1: 新增 scheduler task**

Create scheduled task with `@scheduled(cron="*/2 * * * *", job_id="codeup_merge_authorship", name="Codeup Merge AI归属重算")`. It reads `codeup_webhook` config, returns skipped when disabled, processes up to `batch_size` tasks, and returns `{success, processed, failed}`.

- [ ] **Step 2: 新增配置块**

Add:

```yaml
codeup_webhook:
  enabled: true
  repo_cache_dir: .cache/codeup_repos
  max_attempts: 3
  batch_size: 10
  clone_timeout_seconds: 300
  fetch_timeout_seconds: 120
```

---

## Task 9: 最终验证

**Files:** All files touched above.

- [ ] **Step 1: 运行新增测试集**

Run:

```bash
pytest \
  tests/unit/test_database/test_codeup_merge_authorship_db.py \
  tests/unit/test_services/test_codeup_webhook_service.py \
  tests/unit/test_services/test_codeup_note_provider.py \
  tests/unit/test_services/test_merge_authorship_calculator.py \
  tests/unit/test_services/test_codeup_git_service.py \
  tests/unit/test_services/test_codeup_merge_authorship_service.py \
  tests/integration/test_codeup_webhook_api.py -v
```

Expected: PASS.

- [ ] **Step 2: 运行 notes 回归测试**

Run: `pytest tests/unit/test_services/test_notes_rest_service.py tests/integration/test_notes_rest_api.py -v`

Expected: PASS.

- [ ] **Step 3: 语法检查**

Run: `python -m py_compile api/routes/codeup_webhook.py core/database/codeup_merge_authorship_db.py core/services/codeup_webhook_service.py core/services/codeup_note_provider.py core/services/codeup_git_service.py core/services/merge_authorship_calculator.py core/services/codeup_merge_authorship_service.py core/scheduler/tasks/codeup_merge_authorship_task.py`

Expected: exit code 0.

- [ ] **Step 4: 检查 Codeup 路径不调用 Git Notes**

Run: `python -c "from pathlib import Path; files=['core/services/codeup_note_provider.py','core/services/codeup_merge_authorship_service.py','core/services/merge_authorship_calculator.py']; [(_ for _ in ()).throw(AssertionError(p)) for p in files if 'git notes' in Path(p).read_text().lower()]; print('Codeup path does not call git notes')"`

Expected: prints `Codeup path does not call git notes`.

---

## Self-Review

- Spec coverage: webhook 入队由 Tasks 2-3 覆盖；任务持久化由 Task 1 覆盖；DB-backed notes 由 Task 4 覆盖；target 优先归因由 Task 5 覆盖；后台异步处理由 Tasks 7-8 覆盖；配置和验证由 Tasks 8-9 覆盖。
- Placeholder scan: 计划没有占位章节；每个任务都有明确文件、测试、实现要求和验证命令。
- Type consistency: `CodeupMergeAuthorshipDatabase`、`CodeupWebhookService`、`CodeupDatabaseNoteProvider`、`MergeAuthorshipCalculator`、`CodeupGitService`、`CodeupMergeAuthorshipService` 命名一致。
