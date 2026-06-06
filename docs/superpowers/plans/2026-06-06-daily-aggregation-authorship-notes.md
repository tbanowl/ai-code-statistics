# Daily Aggregation Authorship Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `daily_aggregation_task` optionally count only commits present in `authorship_notes`, derive `stat_date` from commit timestamps, and record the latest counted daily aggregation commit SHA on `stats_repositories`.

**Architecture:** Add one repository progress column and one `StatsDatabase` update method. Extend committed event queries with an optional authorship-notes `EXISTS` gate, then update `DailyAggregationTask` so grouping includes event-derived `stat_date` and repository progress is written after successful daily-stat upserts.

**Tech Stack:** Python 3, SQLAlchemy ORM, pytest, SQLite test databases, MySQL schema SQL.

---

## File Structure

- `core/database/models.py`: add ORM column to `StatsRepository` and import/use `AuthorshipNotes` in query code through the existing model module.
- `core/database/stats_db.py`: add `require_authorship_notes` query option, return `commit_sha` and `timestamp`, and add a repository progress update method.
- `core/scheduler/tasks/daily_aggregation_task.py`: read config/context gate, aggregate by event-derived `stat_date`, and update latest commit per repository.
- `config.yaml`: add default `scheduler.jobs.daily_aggregation.require_authorship_notes: false`.
- `sql/metrics_schema_mysql.sql`: add new column to fresh schema.
- `sql/daily_aggregation_commit_sha_migration_mysql.sql`: migration for existing MySQL databases.
- `tests/integration/test_dimensions_db.py`: add database-backed tests for committed-event filtering and progress update.
- `tests/unit/test_scheduler/test_stats_task.py`: add task orchestration tests for config/context, timestamp-derived `stat_date`, and latest commit update.

---

### Task 1: Add Database Model and Query Gate Tests

**Files:**
- Modify: `tests/integration/test_dimensions_db.py`
- Modify: `core/database/models.py`
- Modify: `core/database/stats_db.py`

- [ ] **Step 1: Write failing integration tests**

Append these imports to the existing import block in `tests/integration/test_dimensions_db.py`:

```python
from core.database.authorship_notes_db import compute_note_content_hash
from core.database.models import AuthorshipNotes
```

Append these tests after `test_query_committed_and_checkpoint_events`:

```python
def test_query_committed_events_can_require_authorship_notes(setup_dbs):
    metrics_db, stats_db = setup_dbs

    raw_id = metrics_db.save_metrics_raw(
        version=1,
        event_count=2,
        payload_json="{}",
        received_at=1710000000000,
    )

    with_note = MetricsEventsCommitted(
        raw_id=raw_id,
        timestamp=1710000000001,
        repo_url="example.com/org/repo",
        author="alice <alice@example.com>",
        commit_sha="abc123",
        human_additions=6,
        git_diff_added_lines=10,
        ai_additions=[3, 1],
        ai_accepted=[3, 1],
        total_ai_additions=[3, 1],
    )
    with_note.uid = gen_commited_uid(with_note)
    metrics_db.upsert_committed_event(with_note)

    without_note = MetricsEventsCommitted(
        raw_id=raw_id,
        timestamp=1710000000002,
        repo_url="example.com/org/repo",
        author="bob <bob@example.com>",
        commit_sha="def456",
        human_additions=4,
        git_diff_added_lines=8,
        ai_additions=[2, 1],
        ai_accepted=[2, 1],
        total_ai_additions=[2, 1],
    )
    without_note.uid = gen_commited_uid(without_note)
    metrics_db.upsert_committed_event(without_note)

    with session_scope(stats_db.engine) as session:
        session.add(
            AuthorshipNotes(
                repo_url="example.com/org/repo",
                branch="main",
                commit_sha="abc123",
                note_blob_oid=None,
                author_name="alice",
                author_email="alice@example.com",
                note_content="note-a",
                content_hash=compute_note_content_hash("note-a"),
                change_seq=1,
            )
        )

    unfiltered = stats_db.query_committed_events(
        1710000000000, 1710000000010, require_authorship_notes=False
    )
    filtered = stats_db.query_committed_events(
        1710000000000, 1710000000010, require_authorship_notes=True
    )

    assert {row["commit_sha"] for row in unfiltered} == {"abc123", "def456"}
    assert [row["commit_sha"] for row in filtered] == ["abc123"]
    assert filtered[0]["repo_url"] == "example.com/org/repo"
    assert filtered[0]["timestamp"] == 1710000000001


def test_update_repository_last_daily_aggregation_commit_sha(setup_dbs):
    _, stats_db = setup_dbs
    repo_id = stats_db.get_or_create_repository("https://example.com/org/repo.git")

    assert (
        stats_db.update_repository_last_daily_aggregation_commit_sha(
            repo_id, "abc123def456"
        )
        is True
    )

    with session_scope(stats_db.engine) as session:
        repo = (
            session.query(StatsRepository)
            .filter(StatsRepository.id == repo_id)
            .one()
        )
        assert repo.last_daily_aggregation_commit_sha == "abc123def456"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/integration/test_dimensions_db.py::test_query_committed_events_can_require_authorship_notes tests/integration/test_dimensions_db.py::test_update_repository_last_daily_aggregation_commit_sha -v
```

Expected: FAIL because `query_committed_events()` does not accept `require_authorship_notes`, returned rows do not include `commit_sha`/`timestamp`, and the update method/column do not exist.

- [ ] **Step 3: Add ORM column and query support**

In `core/database/models.py`, add the column below in `class StatsRepository`, immediately after `last_blame_commit_sha`:

```python
    # 最近一次每日聚合成功统计到的提交 SHA
    last_daily_aggregation_commit_sha: Mapped[str] = mapped_column(String(40), nullable=True)
```

In `core/database/stats_db.py`, add `AuthorshipNotes` to the `.models` import list:

```python
    AuthorshipNotes,
```

Change `query_committed_events` signature to:

```python
    def query_committed_events(
        self,
        start_ts: int,
        end_ts: int,
        repo_url: Optional[str] = None,
        author: Optional[str] = None,
        require_authorship_notes: bool = False,
    ) -> List[Dict]:
```

Inside `query_committed_events`, normalize the optional repo filter once:

```python
            normalized_repo_url = normalize_repo_url(repo_url) if repo_url else None
```

Replace the existing `if repo_url:` block with:

```python
            if normalized_repo_url:
                query = query.filter(MetricsEventsCommitted.repo_url == normalized_repo_url)
```

Add this block after the author filter. Both committed events and authorship notes are already normalized before persistence by `MetricsService` and `NotesRestService`, so compare the stored columns directly to preserve the `(repo_url, commit_sha)` index path:

```python
            if require_authorship_notes:
                query = query.filter(MetricsEventsCommitted.commit_sha.isnot(None))
                query = query.filter(func.trim(MetricsEventsCommitted.commit_sha) != "")
                query = query.filter(
                    session.query(AuthorshipNotes.id)
                    .filter(AuthorshipNotes.repo_url == MetricsEventsCommitted.repo_url)
                    .filter(AuthorshipNotes.commit_sha == MetricsEventsCommitted.commit_sha)
                    .exists()
                )
```

In the `items.append({...})` dict, include normalized repo URL plus commit fields:

```python
                        "repo_url": normalize_repo_url(row.repo_url),
                        "commit_sha": (row.commit_sha or "").strip(),
                        "timestamp": int(row.timestamp or 0),
```

Remove the older `"repo_url": row.repo_url or "",` line from that same dict.

- [ ] **Step 4: Add repository progress update method**

In `core/database/stats_db.py`, add this method after `get_or_create_repository`:

```python
    def update_repository_last_daily_aggregation_commit_sha(
        self, repo_id: str, commit_sha: str
    ) -> bool:
        normalized_sha = (commit_sha or "").strip()
        if not normalized_sha:
            return False

        with session_scope(self.engine) as session:
            row = (
                session.query(StatsRepository)
                .filter(StatsRepository.id == repo_id)
                .first()
            )
            if row is None:
                return False

            row.last_daily_aggregation_commit_sha = normalized_sha
            row.updated_at = now_ts()
            session.flush()
            return True
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/integration/test_dimensions_db.py::test_query_committed_events_can_require_authorship_notes tests/integration/test_dimensions_db.py::test_update_repository_last_daily_aggregation_commit_sha -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add core/database/models.py core/database/stats_db.py tests/integration/test_dimensions_db.py
git commit -m "feat: add daily aggregation commit tracking query support"
```

---

### Task 2: Update DailyAggregationTask Behavior

**Files:**
- Modify: `tests/unit/test_scheduler/test_stats_task.py`
- Modify: `core/scheduler/tasks/daily_aggregation_task.py`

- [ ] **Step 1: Write failing task tests**

In `tests/unit/test_scheduler/test_stats_task.py`, add this import:

```python
from datetime import datetime
```

Add a helper near the top of the file:

```python
def _millis(year, month, day, hour=0, minute=0, second=0):
    return int(datetime(year, month, day, hour, minute, second).timestamp() * 1000)
```

Update the existing `test_execute_calls_stats_db_methods` fixture event to include:

```python
            "commit_sha": "abc123",
            "timestamp": _millis(2026, 6, 5, 10, 30),
```

Add these assertions to the same test after `args = stats_db.upsert_daily_stat.call_args.args`:

```python
    assert args[0] == 20260605
    stats_db.update_repository_last_daily_aggregation_commit_sha.assert_called_once_with(
        "r1", "abc123"
    )
```

Append these new tests:

```python
@patch("core.scheduler.tasks.daily_aggregation_task.StatsDatabase")
def test_execute_passes_authorship_notes_gate_from_config(mock_stats_db_cls):
    stats_db = MagicMock()
    stats_db.query_committed_events.return_value = []
    stats_db.get_latest_stat_date.return_value = 0
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask(
        {
            "scheduler": {
                "jobs": {
                    "daily_aggregation": {
                        "require_authorship_notes": True,
                    }
                }
            }
        }
    )
    task.logger = MagicMock()

    result = task.execute(
        {
            "start_date": _millis(2026, 6, 5),
            "end_date": _millis(2026, 6, 5),
        }
    )

    assert result["success"] is True
    assert stats_db.query_committed_events.call_args.kwargs[
        "require_authorship_notes"
    ] is True


@patch("core.scheduler.tasks.daily_aggregation_task.StatsDatabase")
def test_execute_context_overrides_authorship_notes_gate(mock_stats_db_cls):
    stats_db = MagicMock()
    stats_db.query_committed_events.return_value = []
    stats_db.get_latest_stat_date.return_value = 0
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask(
        {
            "scheduler": {
                "jobs": {
                    "daily_aggregation": {
                        "require_authorship_notes": False,
                    }
                }
            }
        }
    )
    task.logger = MagicMock()

    task.execute(
        {
            "start_date": _millis(2026, 6, 5),
            "end_date": _millis(2026, 6, 5),
            "require_authorship_notes": True,
        }
    )

    assert stats_db.query_committed_events.call_args.kwargs[
        "require_authorship_notes"
    ] is True


@patch("core.scheduler.tasks.daily_aggregation_task.StatsDatabase")
def test_execute_groups_by_event_timestamp_stat_date(mock_stats_db_cls):
    stats_db = MagicMock()
    stats_db.query_committed_events.return_value = [
        {
            "repo_url": "repo/a",
            "author": "alice",
            "author_uid": "alice <a@example.com>",
            "author_email": "a@example.com",
            "human_additions": 5,
            "git_diff_added_lines": 15,
            "ai_additions": 4,
            "total_ai_additions_total": 6,
            "ai_accepted_lines": 10,
            "commit_sha": "abc123",
            "timestamp": _millis(2026, 6, 4, 23, 30),
        }
    ]
    stats_db.get_or_create_repository.return_value = "r1"
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask({})
    task.logger = MagicMock()
    result = task.execute(
        {
            "start_date": _millis(2026, 6, 5),
            "end_date": _millis(2026, 6, 5),
        }
    )

    assert result["success"] is True
    args = stats_db.upsert_daily_stat.call_args.args
    assert args[0] == 20260604
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_scheduler/test_stats_task.py -v
```

Expected: FAIL because task code still groups without `stat_date`, does not pass `require_authorship_notes`, and does not update the new repository progress field.

- [ ] **Step 3: Implement config helper and event-derived grouping**

In `core/scheduler/tasks/daily_aggregation_task.py`, change the typing import:

```python
from typing import Dict, List, Tuple
```

Add these methods inside `DailyAggregationTask`, before `_aggregate_by_repo_contributor`:

```python
    def _require_authorship_notes(self, context: Dict) -> bool:
        if "require_authorship_notes" in context:
            return bool(context.get("require_authorship_notes"))

        config = getattr(self, "config", None) or {}
        job_config = (
            config.get("scheduler", {})
            .get("jobs", {})
            .get("daily_aggregation", {})
        )
        return bool(job_config.get("require_authorship_notes", False))

    @staticmethod
    def _event_stat_date(event: Dict) -> int:
        timestamp = int(event.get("timestamp") or 0)
        if timestamp <= 0:
            return int(datetime.now().strftime("%Y%m%d"))
        return int(datetime.fromtimestamp(timestamp / 1000).strftime("%Y%m%d"))
```

In `execute`, after reading `contributor`, add:

```python
        require_authorship_notes = self._require_authorship_notes(context)
```

Change the `query_committed_events` call to:

```python
            committed_events = stats_db.query_committed_events(
                day_start_ts,
                day_end_ts,
                repo_url=repo_url,
                author=contributor,
                require_authorship_notes=require_authorship_notes,
            )
```

Replace the aggregation/upsert loop in `execute`:

```python
            aggregated = self._aggregate_by_repo_contributor(committed_events)

            for key, stats in aggregated.items():
                repo_path, author_name, author_email = key

                repo_id = stats_db.get_or_create_repository(repo_path)
                stats_db.upsert_daily_stat(
                    stat_date, repo_id, author_name, author_email, stats
                )
```

with:

```python
            aggregated, latest_commits = self._aggregate_by_repo_contributor(
                committed_events
            )
            repo_ids: Dict[str, str] = {}

            for key, stats in aggregated.items():
                stat_date, repo_path, author_name, author_email = key

                repo_id = repo_ids.get(repo_path)
                if repo_id is None:
                    repo_id = stats_db.get_or_create_repository(repo_path)
                    repo_ids[repo_path] = repo_id

                stats_db.upsert_daily_stat(
                    stat_date, repo_id, author_name, author_email, stats
                )

            for repo_path, latest in latest_commits.items():
                commit_sha = latest.get("commit_sha")
                if not commit_sha:
                    continue

                repo_id = repo_ids.get(repo_path)
                if repo_id is None:
                    repo_id = stats_db.get_or_create_repository(repo_path)
                    repo_ids[repo_path] = repo_id

                stats_db.update_repository_last_daily_aggregation_commit_sha(
                    repo_id, commit_sha
                )
```

- [ ] **Step 4: Update aggregate return shape**

Replace `_aggregate_by_repo_contributor` with:

```python
    def _aggregate_by_repo_contributor(
        self, committed_events: List[Dict]
    ) -> Tuple[Dict, Dict]:
        aggregated = {}
        latest_commits = {}

        for event in committed_events:
            stat_date = self._event_stat_date(event)
            repo_path = normalize_repo_url(event.get("repo_url"))
            author_name = event.get("author", "")
            author_email = event.get("author_email")
            key = (stat_date, repo_path, author_name, author_email)

            if key not in aggregated:
                aggregated[key] = {
                    "repo_name": StatsDatabase._extract_repo_name(repo_path),
                    "contributor_name": author_name or "unknown",
                    "contributor_email": author_email,
                    "ai_lines": 0,
                    "ai_total_lines": 0,
                    "ai_accepted_lines": 0,
                    "human_lines": 0,
                    "total_lines": 0,
                }

            stats = aggregated[key]
            stats["ai_total_lines"] += int(event.get("total_ai_additions_total", 0))
            stats["ai_lines"] += int(event.get("ai_additions", 0))
            stats["ai_accepted_lines"] += int(event.get("ai_accepted_lines", 0))
            stats["human_lines"] += int(event.get("human_additions", 0))
            stats["total_lines"] += int(event.get("git_diff_added_lines", 0))

            commit_sha = (event.get("commit_sha") or "").strip()
            timestamp = int(event.get("timestamp") or 0)
            if commit_sha:
                current = latest_commits.get(repo_path)
                if current is None or timestamp >= int(current.get("timestamp") or 0):
                    latest_commits[repo_path] = {
                        "commit_sha": commit_sha,
                        "timestamp": timestamp,
                    }

        return aggregated, latest_commits
```

- [ ] **Step 5: Update existing aggregate tests for new key shape**

In `test_aggregate_by_repo_contributor`, add `"timestamp": _millis(2026, 6, 5),` to both committed events and change:

```python
    data = task._aggregate_by_repo_contributor(committed)
    key = ("repo/a", "alice", "a@example.com")
```

to:

```python
    data, latest_commits = task._aggregate_by_repo_contributor(committed)
    key = (20260605, "repo/a", "alice", "a@example.com")
```

Add:

```python
    assert latest_commits == {}
```

For `test_aggregate_normalizes_none_and_missing_repo_url_to_unknown`, add `"timestamp": _millis(2026, 6, 5),` to each event, change:

```python
    data = task._aggregate_by_repo_contributor(committed)
```

to:

```python
    data, _latest_commits = task._aggregate_by_repo_contributor(committed)
```

and change the key to:

```python
    key = (20260605, UNKNOWN_REPO, "bob", "b@b.com")
```

For `test_aggregate_normalizes_different_url_formats_to_same_key`, add `"timestamp": _millis(2026, 6, 5),` to both events, change:

```python
    data = task._aggregate_by_repo_contributor(committed)
```

to:

```python
    data, _latest_commits = task._aggregate_by_repo_contributor(committed)
```

and change the key to:

```python
    key = (20260605, expected_repo_path, "carol", "c@c.com")
```

- [ ] **Step 6: Run task tests to verify they pass**

Run:

```bash
python -m pytest tests/unit/test_scheduler/test_stats_task.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add core/scheduler/tasks/daily_aggregation_task.py tests/unit/test_scheduler/test_stats_task.py
git commit -m "feat: update daily aggregation task commit tracking"
```

---

### Task 3: Add Configuration and SQL Schema Updates

**Files:**
- Modify: `config.yaml`
- Modify: `sql/metrics_schema_mysql.sql`
- Create: `sql/daily_aggregation_commit_sha_migration_mysql.sql`

- [ ] **Step 1: Update default config**

In `config.yaml`, under `scheduler.jobs.daily_aggregation`, change:

```yaml
    daily_aggregation:
      enabled: true
      cron: "*/10 * * * *"
```

to:

```yaml
    daily_aggregation:
      enabled: true
      cron: "*/10 * * * *"
      require_authorship_notes: false
```

- [ ] **Step 2: Update fresh MySQL schema**

In `sql/metrics_schema_mysql.sql`, inside `CREATE TABLE IF NOT EXISTS stats_repositories`, add this line immediately after `last_blame_commit_sha`:

```sql
    last_daily_aggregation_commit_sha VARCHAR(40) COMMENT '最近一次每日聚合成功统计到的提交 SHA',
```

- [ ] **Step 3: Add migration SQL**

Create `sql/daily_aggregation_commit_sha_migration_mysql.sql`:

```sql
-- Daily aggregation commit SHA migration
--
-- 适用场景：已有 MySQL 数据库已经存在 stats_repositories 表，
-- 需要补齐每日聚合任务专用的最后统计提交 SHA。
-- 新库建表请使用 metrics_schema_mysql.sql。

ALTER TABLE stats_repositories
    ADD COLUMN last_daily_aggregation_commit_sha VARCHAR(40) NULL COMMENT '最近一次每日聚合成功统计到的提交 SHA' AFTER last_blame_commit_sha;
```

- [ ] **Step 4: Verify SQL/config diff**

Run:

```bash
git diff -- config.yaml sql/metrics_schema_mysql.sql sql/daily_aggregation_commit_sha_migration_mysql.sql
```

Expected: diff only shows the new config key, the fresh schema column, and the migration file.

- [ ] **Step 5: Commit**

Run:

```bash
git add config.yaml sql/metrics_schema_mysql.sql sql/daily_aggregation_commit_sha_migration_mysql.sql
git commit -m "chore: add daily aggregation commit schema config"
```

---

### Task 4: Full Verification and Cleanup

**Files:**
- Read: all touched files

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/unit/test_scheduler/test_stats_task.py tests/integration/test_dimensions_db.py -v
```

Expected: PASS.

- [ ] **Step 2: Run Python syntax verification**

Run:

```bash
python -m py_compile core/database/models.py core/database/stats_db.py core/scheduler/tasks/daily_aggregation_task.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Inspect final diff**

Run:

```bash
git status --short
git diff --stat HEAD
```

Expected: clean working tree if every task committed. If there are uncommitted changes, inspect them and either commit intended changes or explain why they remain.

- [ ] **Step 4: Optional all-test smoke**

Run:

```bash
python -m pytest tests/unit/test_database/test_metrics_db.py tests/unit/test_database/test_blame_stats_db.py tests/unit/test_scheduler/test_stats_task.py tests/integration/test_dimensions_db.py -v
```

Expected: PASS. If unrelated legacy tests fail, capture the failing test names and error summaries.
