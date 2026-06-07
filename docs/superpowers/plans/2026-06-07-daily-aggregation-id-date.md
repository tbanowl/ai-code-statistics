# Daily Aggregation ID Date Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement second-level committed timestamps, `commit_date`, SQL daily aggregation by affected dates, and `last_daily_aggregation_id` progress tracking.

**Architecture:** Keep extraction in `MetricsService`, schema declarations in `core/database/models.py` and SQL files, and SQL aggregation in `StatsDatabase`. `DailyAggregationTask` becomes an orchestration layer that loops repositories, asks `StatsDatabase` for affected dates and SQL aggregates, writes daily stats, then advances the repository ID cursor only after successful writes.

**Tech Stack:** Python, SQLAlchemy ORM/Core, MySQL DDL, SQLite-backed tests, pytest, Flask route tests.

---

## File Map

- Modify `core/database/models.py`: add ORM columns for `commit_date`, `_total` snapshots, `last_daily_aggregation_id`, and new daily stat fields; remove ORM use of deleted daily stat fields and commit SHA progress marker.
- Modify `core/services/metrics_service.py`: store committed event timestamp in seconds, compute `commit_date`, and populate `_total` snapshot fields.
- Modify `core/database/stats_db.py`: add repository listing, affected-date discovery, SQL aggregate query, ID cursor update, new daily stat upsert fields, and updated API aggregate fields.
- Modify `core/scheduler/tasks/daily_aggregation_task.py`: replace Python event aggregation with repository loop plus database aggregation methods.
- Modify `api/routes/stats.py`: update summaries and compatibility aggregate endpoint to use new daily/committed field names.
- Modify `sql/metrics_schema_mysql.sql`: update base schema for new installs.
- Create `sql/daily_aggregation_id_date_migration_mysql.sql`: migration/backfill for existing MySQL databases.
- Modify tests:
  - `tests/unit/test_models/test_metrics.py`
  - `tests/unit/test_models/test_stats.py`
  - `tests/unit/test_scheduler/test_stats_task.py`
  - `tests/unit/test_database/test_sqlite.py`
  - `tests/integration/test_dimensions_db.py`
  - `tests/integration/test_dimensions_api.py`
  - `tests/test_metrics_event_processor_task.py`

## Task 1: ORM Schema Fields

**Files:**
- Modify: `core/database/models.py`
- Test: `tests/unit/test_models/test_metrics.py`
- Test: `tests/unit/test_models/test_stats.py`

- [ ] **Step 1: Write failing metrics model test**

Add this test to `tests/unit/test_models/test_metrics.py`:

```python
def test_metrics_committed_commit_date_and_total_columns():
    columns = {c.name for c in MetricsEventsCommitted.__table__.columns}
    expected = {
        "commit_date",
        "mixed_additions_total",
        "ai_additions_total",
        "ai_accepted_total",
        "total_ai_additions_total",
        "total_ai_deletions_total",
        "time_waiting_for_ai_total",
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    row = MetricsEventsCommitted(
        raw_id="raw-1",
        timestamp=1710000000,
        commit_date=20240309,
        mixed_additions_total=1,
        ai_additions_total=2,
        ai_accepted_total=3,
        total_ai_additions_total=4,
        total_ai_deletions_total=5,
        time_waiting_for_ai_total=6,
    )
    data = row.to_dict()
    assert data["commit_date"] == 20240309
    assert data["mixed_additions_total"] == 1
    assert data["ai_additions_total"] == 2
    assert data["ai_accepted_total"] == 3
    assert data["total_ai_additions_total"] == 4
    assert data["total_ai_deletions_total"] == 5
    assert data["time_waiting_for_ai_total"] == 6
```

- [ ] **Step 2: Write failing stats model test**

Replace the old daily stat default assertions in `tests/unit/test_models/test_stats.py` with:

```python
def test_stats_daily_stat_new_metric_columns():
    columns = {c.name for c in StatsDailyStat.__table__.columns}
    expected = {
        "human_additions",
        "unknown_additions",
        "git_diff_deleted_lines",
        "git_diff_added_lines",
        "mixed_additions",
        "ai_additions",
        "ai_accepted",
        "total_ai_additions",
        "total_ai_deletions",
    }
    removed = {
        "ai_lines",
        "ai_total_lines",
        "ai_accepted_lines",
        "human_lines",
        "total_lines",
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"
    assert not removed.intersection(columns)

    daily = StatsDailyStat(stat_date=20260605, repo_id="r1")
    assert daily.human_additions in (None, 0)
    assert daily.ai_additions in (None, 0)
    assert daily.total_ai_additions in (None, 0)
```

Add a repository cursor assertion:

```python
def test_stats_repository_daily_aggregation_id_column():
    columns = {c.name for c in StatsRepository.__table__.columns}
    assert "last_daily_aggregation_id" in columns
    assert "last_daily_aggregation_commit_sha" not in columns
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_models/test_metrics.py tests/unit/test_models/test_stats.py -v
```

Expected: FAIL with missing `commit_date`, `_total`, new daily stat, and `last_daily_aggregation_id` columns.

- [ ] **Step 4: Implement ORM fields**

In `core/database/models.py`:

```python
class MetricsEventsCommitted(ModelBase):
    ...
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    commit_date: Mapped[int] = mapped_column(BigInteger, nullable=True, index=True)
    ...
    mixed_additions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_additions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_accepted_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_ai_additions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_ai_deletions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_waiting_for_ai_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
```

In `StatsRepository`, replace the old daily aggregation commit SHA field:

```python
last_daily_aggregation_id: Mapped[str] = mapped_column(String(20), nullable=True)
```

In `StatsDailyStat`, replace the old metric columns with:

```python
human_additions: Mapped[int] = mapped_column(Integer, default=0)
unknown_additions: Mapped[int] = mapped_column(Integer, default=0)
git_diff_deleted_lines: Mapped[int] = mapped_column(Integer, default=0)
git_diff_added_lines: Mapped[int] = mapped_column(Integer, default=0)
mixed_additions: Mapped[int] = mapped_column(Integer, default=0)
ai_additions: Mapped[int] = mapped_column(Integer, default=0)
ai_accepted: Mapped[int] = mapped_column(Integer, default=0)
total_ai_additions: Mapped[int] = mapped_column(Integer, default=0)
total_ai_deletions: Mapped[int] = mapped_column(Integer, default=0)
```

In `AuthorshipNotes`, add:

```python
commit_date: Mapped[int] = mapped_column(BigInteger, nullable=True, index=True)
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
pytest tests/unit/test_models/test_metrics.py tests/unit/test_models/test_stats.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/database/models.py tests/unit/test_models/test_metrics.py tests/unit/test_models/test_stats.py
git commit -m "feat: add daily aggregation schema fields"
```

## Task 2: Metrics Processor Timestamp and Snapshot Fields

**Files:**
- Modify: `core/services/metrics_service.py`
- Test: `tests/integration/test_dimensions_db.py`

- [ ] **Step 1: Write failing service extraction test**

Add this test to `tests/integration/test_dimensions_db.py`, which already has the `setup_dbs` SQLite fixture. The test processes a raw committed event with `t=1710000000` and arrays:

```python
from core.services.metrics_service import MetricsService


def test_metrics_processor_committed_seconds_commit_date_and_totals(setup_dbs):
    metrics_db, _stats_db = setup_dbs
    service = MetricsService()
    raw_id = metrics_db.save_metrics_raw(
        version=1,
        event_count=1,
        payload_json="{}",
        received_at=1710000000000,
    )
    event = {
        "e": 1,
        "t": 1710000000,
        "v": {
            "0": 11,
            "1": 2,
            "2": 13,
            "4": [3, 30],
            "5": [4, 40],
            "6": [5, 50],
            "7": [6, 60],
            "8": [7, 70],
            "9": [8000, 9000],
        },
        "a": {
            "1": "https://example.com/org/repo.git",
            "2": "Alice <alice@example.com>",
            "3": "abc123",
        },
    }

    service._process_single_event(event, raw_id)

    rows = metrics_db.get_committed_events_by_repo("example.com/org/repo")
    assert len(rows) == 1
    row = rows[0]
    assert row["timestamp"] == 1710000000
    assert row["commit_date"] == 20240309
    assert row["mixed_additions_total"] == 3
    assert row["ai_additions_total"] == 4
    assert row["ai_accepted_total"] == 5
    assert row["total_ai_additions_total"] == 6
    assert row["total_ai_deletions_total"] == 7
    assert row["time_waiting_for_ai_total"] == 8000
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/integration/test_dimensions_db.py::test_metrics_processor_committed_seconds_commit_date_and_totals -v
```

Expected: FAIL because timestamp is still milliseconds and columns are not populated.

- [ ] **Step 3: Implement timestamp and snapshot helpers**

In `core/services/metrics_service.py`, keep the existing `datetime` import:

```python
from datetime import datetime
```

Add helpers inside `MetricsService`:

```python
    @staticmethod
    def _event_timestamp_seconds(event: Dict) -> int:
        raw = event.get("t", 0)
        if isinstance(raw, (int, float)):
            return int(raw)
        return 0

    @staticmethod
    def _commit_date_from_seconds(timestamp: int) -> Optional[int]:
        if timestamp <= 0:
            return None
        return int(datetime.fromtimestamp(timestamp).strftime("%Y%m%d"))

    @staticmethod
    def _first_array_int(arr: Dict, pos: str) -> int:
        values = MetricsService._get_array(arr, pos)
        if not values:
            return 0
        first = values[0]
        if isinstance(first, (int, float)):
            return int(first)
        return 0
```

At the start of `_process_single_event`, change timestamp calculation:

```python
timestamp = self._event_timestamp_seconds(event)
commit_date = self._commit_date_from_seconds(timestamp)
```

For `event_id == 1`, set:

```python
timestamp=timestamp,
commit_date=commit_date,
mixed_additions_total=self._first_array_int(values, "4"),
ai_additions_total=self._first_array_int(values, "5"),
ai_accepted_total=self._first_array_int(values, "6"),
total_ai_additions_total=self._first_array_int(values, "7"),
total_ai_deletions_total=self._first_array_int(values, "8"),
time_waiting_for_ai_total=self._first_array_int(values, "9"),
```

For event IDs 2, 3, and 4, keep using `timestamp=timestamp`. For checkpoint, keep converting `checkpoint_ts` to milliseconds as the existing code does.

- [ ] **Step 4: Update committed query test expectations**

In `tests/integration/test_dimensions_db.py`, update committed test rows to use second-level `timestamp` and `commit_date`, and update `query_committed_events` ranges to second-level values for committed events. Example:

```python
committed = MetricsEventsCommitted(
    raw_id=raw_id,
    uid="uid-committed-1",
    timestamp=1710000000,
    commit_date=20240309,
    repo_url="repo/a",
    author="alice <alice@example.com>",
    human_additions=6,
    git_diff_added_lines=10,
    git_diff_deleted_lines=2,
    ai_additions_total=3,
    ai_accepted_total=3,
    total_ai_additions_total=3,
)
```

Query with:

```python
committed = stats_db.query_committed_events(1710000000, 1710000010)
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/integration/test_dimensions_db.py::test_metrics_processor_committed_seconds_commit_date_and_totals tests/integration/test_dimensions_db.py::test_query_committed_and_checkpoint_events -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/services/metrics_service.py tests/integration/test_dimensions_db.py
git commit -m "feat: store committed event dates and totals"
```

## Task 3: StatsDatabase Daily Stat Upsert and Cursor Methods

**Files:**
- Modify: `core/database/stats_db.py`
- Test: `tests/unit/test_database/test_sqlite.py`
- Test: `tests/integration/test_dimensions_db.py`

- [ ] **Step 1: Write failing upsert/query daily stat test**

In `tests/unit/test_database/test_sqlite.py`, replace old `upsert_daily_stat` assertions with:

```python
def test_upsert_and_query_daily_stats(stats_db):
    repo_id = stats_db.get_or_create_repository("https://example.com/org/repo.git")
    stats_db.upsert_daily_stat(
        20260605,
        repo_id,
        "alice",
        "alice@example.com",
        {
            "repo_name": "org/repo",
            "contributor_name": "alice",
            "contributor_email": "alice@example.com",
            "human_additions": 40,
            "unknown_additions": 1,
            "git_diff_deleted_lines": 3,
            "git_diff_added_lines": 120,
            "mixed_additions": 2,
            "ai_additions": 20,
            "ai_accepted": 18,
            "total_ai_additions": 24,
            "total_ai_deletions": 5,
        },
    )

    rows = stats_db.query_daily_stats(
        start_date=20260601,
        end_date=20260630,
        repo_id=repo_id,
        contributor_email="alice@example.com",
        limit=10,
        offset=0,
    )

    assert rows[0]["human_additions"] == 40
    assert rows[0]["unknown_additions"] == 1
    assert rows[0]["git_diff_deleted_lines"] == 3
    assert rows[0]["git_diff_added_lines"] == 120
    assert rows[0]["mixed_additions"] == 2
    assert rows[0]["ai_additions"] == 20
    assert rows[0]["ai_accepted"] == 18
    assert rows[0]["total_ai_additions"] == 24
    assert rows[0]["total_ai_deletions"] == 5
```

- [ ] **Step 2: Write failing cursor update test**

In `tests/integration/test_dimensions_db.py`, replace the old commit SHA cursor test with:

```python
def test_update_repository_last_daily_aggregation_id(setup_dbs):
    _, stats_db = setup_dbs
    repo_id = stats_db.get_or_create_repository("https://example.com/org/repo.git")

    assert stats_db.update_repository_last_daily_aggregation_id(repo_id, "czabc123") is True

    with session_scope(stats_db.engine) as session:
        repo = session.query(StatsRepository).filter(StatsRepository.id == repo_id).one()
        assert repo.last_daily_aggregation_id == "czabc123"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_database/test_sqlite.py::test_upsert_and_query_daily_stats tests/integration/test_dimensions_db.py::test_update_repository_last_daily_aggregation_id -v
```

Expected: FAIL because `upsert_daily_stat` and cursor method still use old fields.

- [ ] **Step 4: Implement new upsert and cursor method**

In `core/database/stats_db.py`, update `upsert_daily_stat` assignments:

```python
row.human_additions = int(stats.get("human_additions", 0))
row.unknown_additions = int(stats.get("unknown_additions", 0))
row.git_diff_deleted_lines = int(stats.get("git_diff_deleted_lines", 0))
row.git_diff_added_lines = int(stats.get("git_diff_added_lines", 0))
row.mixed_additions = int(stats.get("mixed_additions", 0))
row.ai_additions = int(stats.get("ai_additions", 0))
row.ai_accepted = int(stats.get("ai_accepted", 0))
row.total_ai_additions = int(stats.get("total_ai_additions", 0))
row.total_ai_deletions = int(stats.get("total_ai_deletions", 0))
```

Replace `update_repository_last_daily_aggregation_commit_sha` with:

```python
def update_repository_last_daily_aggregation_id(self, repo_id: str, committed_id: str) -> bool:
    normalized_id = (committed_id or "").strip()
    if not normalized_id:
        return False

    with session_scope(self.engine) as session:
        row = session.query(StatsRepository).filter(StatsRepository.id == repo_id).first()
        if row is None:
            return False
        row.last_daily_aggregation_id = normalized_id
        row.updated_at = now_ts()
        session.flush()
        return True
```

Update `consolidate_unknown_repositories` to merge the new daily stat fields:

```python
for field in (
    "human_additions",
    "unknown_additions",
    "git_diff_deleted_lines",
    "git_diff_added_lines",
    "mixed_additions",
    "ai_additions",
    "ai_accepted",
    "total_ai_additions",
    "total_ai_deletions",
):
    setattr(target, field, int(getattr(target, field) or 0) + int(getattr(daily, field) or 0))
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/unit/test_database/test_sqlite.py::test_upsert_and_query_daily_stats tests/integration/test_dimensions_db.py::test_update_repository_last_daily_aggregation_id -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/database/stats_db.py tests/unit/test_database/test_sqlite.py tests/integration/test_dimensions_db.py
git commit -m "feat: update daily stat storage fields"
```

## Task 4: StatsDatabase SQL Aggregation Methods

**Files:**
- Modify: `core/database/stats_db.py`
- Test: `tests/integration/test_dimensions_db.py`

- [ ] **Step 1: Write failing affected-date discovery test**

Add to `tests/integration/test_dimensions_db.py`:

```python
def test_find_daily_aggregation_affected_dates_uses_id_cursor(setup_dbs):
    metrics_db, stats_db = setup_dbs
    raw_id = metrics_db.save_metrics_raw(1, 3, "{}", 1710000000)
    repo_id = stats_db.get_or_create_repository("example.com/org/repo")

    rows = [
        MetricsEventsCommitted(
            id="c001",
            uid="uid-c001",
            raw_id=raw_id,
            timestamp=1710000000,
            commit_date=20240309,
            repo_url="example.com/org/repo",
            author="alice <alice@example.com>",
            commit_sha="a1",
        ),
        MetricsEventsCommitted(
            id="c002",
            uid="uid-c002",
            raw_id=raw_id,
            timestamp=1710003600,
            commit_date=20240309,
            repo_url="example.com/org/repo",
            author="bob <bob@example.com>",
            commit_sha="b1",
        ),
        MetricsEventsCommitted(
            id="c003",
            uid="uid-c003",
            raw_id=raw_id,
            timestamp=1710090000,
            commit_date=20240310,
            repo_url="example.com/org/repo",
            author="alice <alice@example.com>",
            commit_sha="a2",
        ),
    ]
    with session_scope(stats_db.engine) as session:
        session.add_all(rows)

    result = stats_db.find_daily_aggregation_affected_dates(
        repo_url="example.com/org/repo",
        last_aggregation_id="c001",
        require_authorship_notes=False,
    )

    assert result == {"commit_dates": [20240309, 20240310], "last_id": "c003"}
```

If the test file does not already import a symbol used in these tests, add the missing import at the top of `tests/integration/test_dimensions_db.py`. Required symbols are `MetricsService`, `AuthorshipNotes`, `MetricsEventsCommitted`, `compute_note_content_hash`, and `session_scope`.

- [ ] **Step 2: Write failing SQL aggregate test**

Add:

```python
def test_aggregate_committed_daily_stats_recomputes_full_dates(setup_dbs):
    metrics_db, stats_db = setup_dbs
    raw_id = metrics_db.save_metrics_raw(1, 3, "{}", 1710000000)
    with session_scope(stats_db.engine) as session:
        session.add_all(
            [
                MetricsEventsCommitted(
                    id="c001",
                    uid="uid-c001",
                    raw_id=raw_id,
                    timestamp=1710000000,
                    commit_date=20240309,
                    repo_url="example.com/org/repo",
                    author="alice <alice@example.com>",
                    human_additions=5,
                    git_diff_deleted_lines=1,
                    git_diff_added_lines=10,
                    mixed_additions_total=2,
                    ai_additions_total=3,
                    ai_accepted_total=4,
                    total_ai_additions_total=6,
                    total_ai_deletions_total=1,
                ),
                MetricsEventsCommitted(
                    id="c002",
                    uid="uid-c002",
                    raw_id=raw_id,
                    timestamp=1710003600,
                    commit_date=20240309,
                    repo_url="example.com/org/repo",
                    author="alice <alice@example.com>",
                    human_additions=7,
                    git_diff_deleted_lines=2,
                    git_diff_added_lines=11,
                    mixed_additions_total=3,
                    ai_additions_total=4,
                    ai_accepted_total=5,
                    total_ai_additions_total=8,
                    total_ai_deletions_total=2,
                ),
            ]
        )

    rows = stats_db.aggregate_committed_daily_stats(
        repo_url="example.com/org/repo",
        commit_dates=[20240309],
        require_authorship_notes=False,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["stat_date"] == 20240309
    assert row["contributor_name"] == "alice"
    assert row["contributor_email"] == "alice@example.com"
    assert row["human_additions"] == 12
    assert row["git_diff_deleted_lines"] == 3
    assert row["git_diff_added_lines"] == 21
    assert row["mixed_additions"] == 5
    assert row["ai_additions"] == 7
    assert row["ai_accepted"] == 9
    assert row["total_ai_additions"] == 14
    assert row["total_ai_deletions"] == 3
```

- [ ] **Step 3: Write failing authorship join test**

Add:

```python
def test_aggregate_committed_daily_stats_requires_authorship_notes(setup_dbs):
    metrics_db, stats_db = setup_dbs
    raw_id = metrics_db.save_metrics_raw(1, 2, "{}", 1710000000)
    with session_scope(stats_db.engine) as session:
        session.add_all(
            [
                MetricsEventsCommitted(
                    id="c001",
                    uid="uid-c001",
                    raw_id=raw_id,
                    timestamp=1710000000,
                    commit_date=20240309,
                    repo_url="example.com/org/repo",
                    author="alice <alice@example.com>",
                    commit_sha="with-note",
                    ai_accepted_total=5,
                ),
                MetricsEventsCommitted(
                    id="c002",
                    uid="uid-c002",
                    raw_id=raw_id,
                    timestamp=1710000100,
                    commit_date=20240309,
                    repo_url="example.com/org/repo",
                    author="alice <alice@example.com>",
                    commit_sha="without-note",
                    ai_accepted_total=7,
                ),
                AuthorshipNotes(
                    repo_url="example.com/org/repo",
                    branch="main",
                    commit_sha="with-note",
                    commit_date=20240309,
                    note_blob_oid=None,
                    author_name="alice",
                    author_email="alice@example.com",
                    note_content="note",
                    content_hash=compute_note_content_hash("note"),
                    change_seq=1,
                ),
            ]
        )

    rows = stats_db.aggregate_committed_daily_stats(
        repo_url="example.com/org/repo",
        commit_dates=[20240309],
        require_authorship_notes=True,
    )

    assert len(rows) == 1
    assert rows[0]["ai_accepted"] == 5
```

- [ ] **Step 4: Run tests to verify fail**

Run:

```bash
pytest tests/integration/test_dimensions_db.py::test_find_daily_aggregation_affected_dates_uses_id_cursor tests/integration/test_dimensions_db.py::test_aggregate_committed_daily_stats_recomputes_full_dates tests/integration/test_dimensions_db.py::test_aggregate_committed_daily_stats_requires_authorship_notes -v
```

Expected: FAIL because methods do not exist.

- [ ] **Step 5: Implement discovery and aggregate methods**

In `core/database/stats_db.py`, add:

```python
def list_repositories_for_daily_aggregation(self, repo_url: Optional[str] = None) -> List[Dict]:
    self.consolidate_unknown_repositories()
    with session_scope(self.engine) as session:
        query = session.query(StatsRepository).order_by(StatsRepository.repo_path.asc())
        if repo_url:
            query = query.filter(StatsRepository.repo_path == normalize_repo_url(repo_url))
        return [row.to_dict() for row in query.all()]
```

Add:

```python
def find_daily_aggregation_affected_dates(
    self,
    repo_url: str,
    last_aggregation_id: Optional[str] = None,
    require_authorship_notes: bool = False,
) -> Dict:
    normalized_repo_url = normalize_repo_url(repo_url)
    with session_scope(self.engine) as session:
        query = session.query(
            MetricsEventsCommitted.id,
            MetricsEventsCommitted.commit_date,
        ).filter(MetricsEventsCommitted.repo_url == normalized_repo_url)
        if last_aggregation_id:
            query = query.filter(MetricsEventsCommitted.id > last_aggregation_id)
        if require_authorship_notes:
            query = query.join(
                AuthorshipNotes,
                (MetricsEventsCommitted.repo_url == AuthorshipNotes.repo_url)
                & (MetricsEventsCommitted.commit_sha == AuthorshipNotes.commit_sha),
            )
        rows = query.order_by(MetricsEventsCommitted.id.asc()).all()

    commit_dates = sorted({int(row.commit_date) for row in rows if row.commit_date})
    last_id = rows[-1].id if rows else None
    return {"commit_dates": commit_dates, "last_id": last_id}
```

Add:

```python
def aggregate_committed_daily_stats(
    self,
    repo_url: str,
    commit_dates: List[int],
    require_authorship_notes: bool = False,
) -> List[Dict]:
    if not commit_dates:
        return []

    normalized_repo_url = normalize_repo_url(repo_url)
    with session_scope(self.engine) as session:
        query = session.query(
            MetricsEventsCommitted.commit_date.label("stat_date"),
            MetricsEventsCommitted.repo_url.label("repo_url"),
            MetricsEventsCommitted.author.label("author"),
            func.sum(func.coalesce(MetricsEventsCommitted.human_additions, 0)).label("human_additions"),
            func.sum(0).label("unknown_additions"),
            func.sum(func.coalesce(MetricsEventsCommitted.git_diff_deleted_lines, 0)).label("git_diff_deleted_lines"),
            func.sum(func.coalesce(MetricsEventsCommitted.git_diff_added_lines, 0)).label("git_diff_added_lines"),
            func.sum(func.coalesce(MetricsEventsCommitted.mixed_additions_total, 0)).label("mixed_additions"),
            func.sum(func.coalesce(MetricsEventsCommitted.ai_additions_total, 0)).label("ai_additions"),
            func.sum(func.coalesce(MetricsEventsCommitted.ai_accepted_total, 0)).label("ai_accepted"),
            func.sum(func.coalesce(MetricsEventsCommitted.total_ai_additions_total, 0)).label("total_ai_additions"),
            func.sum(func.coalesce(MetricsEventsCommitted.total_ai_deletions_total, 0)).label("total_ai_deletions"),
        ).filter(MetricsEventsCommitted.repo_url == normalized_repo_url)
        query = query.filter(MetricsEventsCommitted.commit_date.in_(commit_dates))
        if require_authorship_notes:
            query = query.join(
                AuthorshipNotes,
                (MetricsEventsCommitted.repo_url == AuthorshipNotes.repo_url)
                & (MetricsEventsCommitted.commit_sha == AuthorshipNotes.commit_sha),
            )
        rows = (
            query.group_by(
                MetricsEventsCommitted.commit_date,
                MetricsEventsCommitted.repo_url,
                MetricsEventsCommitted.author,
            )
            .order_by(MetricsEventsCommitted.commit_date.asc(), MetricsEventsCommitted.author.asc())
            .all()
        )

    items = []
    for row in rows:
        contributor_name, contributor_email = self._parse_author(row.author)
        repo_path = normalize_repo_url(row.repo_url)
        items.append(
            {
                "stat_date": int(row.stat_date),
                "repo_url": repo_path,
                "repo_name": self._extract_repo_name(repo_path),
                "contributor_name": contributor_name,
                "contributor_email": contributor_email,
                "human_additions": int(row.human_additions or 0),
                "unknown_additions": int(row.unknown_additions or 0),
                "git_diff_deleted_lines": int(row.git_diff_deleted_lines or 0),
                "git_diff_added_lines": int(row.git_diff_added_lines or 0),
                "mixed_additions": int(row.mixed_additions or 0),
                "ai_additions": int(row.ai_additions or 0),
                "ai_accepted": int(row.ai_accepted or 0),
                "total_ai_additions": int(row.total_ai_additions or 0),
                "total_ai_deletions": int(row.total_ai_deletions or 0),
            }
        )
    return items
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/integration/test_dimensions_db.py::test_find_daily_aggregation_affected_dates_uses_id_cursor tests/integration/test_dimensions_db.py::test_aggregate_committed_daily_stats_recomputes_full_dates tests/integration/test_dimensions_db.py::test_aggregate_committed_daily_stats_requires_authorship_notes -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/database/stats_db.py tests/integration/test_dimensions_db.py
git commit -m "feat: aggregate committed daily stats in sql"
```

## Task 5: DailyAggregationTask Orchestration

**Files:**
- Modify: `core/scheduler/tasks/daily_aggregation_task.py`
- Test: `tests/unit/test_scheduler/test_stats_task.py`

- [ ] **Step 1: Replace old aggregation tests with orchestration tests**

In `tests/unit/test_scheduler/test_stats_task.py`, remove tests for `_aggregate_by_repo_contributor` and `update_repository_last_daily_aggregation_commit_sha`. Add:

```python
@patch("core.scheduler.tasks.daily_aggregation_task.StatsDatabase")
def test_execute_discovers_dates_recomputes_and_updates_id(mock_stats_db_cls):
    stats_db = MagicMock()
    stats_db.list_repositories_for_daily_aggregation.return_value = [
        {
            "id": "r1",
            "repo_path": "repo/a",
            "last_daily_aggregation_id": "c001",
        }
    ]
    stats_db.find_daily_aggregation_affected_dates.return_value = {
        "commit_dates": [20260605],
        "last_id": "c003",
    }
    stats_db.aggregate_committed_daily_stats.return_value = [
        {
            "stat_date": 20260605,
            "repo_url": "repo/a",
            "repo_name": "repo/a",
            "contributor_name": "alice",
            "contributor_email": "a@example.com",
            "human_additions": 12,
            "unknown_additions": 0,
            "git_diff_deleted_lines": 1,
            "git_diff_added_lines": 31,
            "mixed_additions": 2,
            "ai_additions": 7,
            "ai_accepted": 12,
            "total_ai_additions": 11,
            "total_ai_deletions": 1,
        }
    ]
    stats_db.update_repository_last_daily_aggregation_id.return_value = True
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask.__new__(DailyAggregationTask)
    task.config = {}
    task.logger = MagicMock()
    result = task.execute()

    assert result == {"success": True, "records": 1}
    stats_db.find_daily_aggregation_affected_dates.assert_called_once_with(
        repo_url="repo/a",
        last_aggregation_id="c001",
        require_authorship_notes=False,
    )
    stats_db.aggregate_committed_daily_stats.assert_called_once_with(
        repo_url="repo/a",
        commit_dates=[20260605],
        require_authorship_notes=False,
    )
    stats_db.upsert_daily_stat.assert_called_once()
    assert stats_db.upsert_daily_stat.call_args.args[:4] == (
        20260605,
        "r1",
        "alice",
        "a@example.com",
    )
    stats_db.update_repository_last_daily_aggregation_id.assert_called_once_with("r1", "c003")
```

Add authorship config test:

```python
@patch("core.scheduler.tasks.daily_aggregation_task.StatsDatabase")
def test_execute_passes_authorship_notes_gate_to_discovery_and_aggregation(mock_stats_db_cls):
    stats_db = MagicMock()
    stats_db.list_repositories_for_daily_aggregation.return_value = [
        {"id": "r1", "repo_path": "repo/a", "last_daily_aggregation_id": None}
    ]
    stats_db.find_daily_aggregation_affected_dates.return_value = {
        "commit_dates": [],
        "last_id": None,
    }
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask.__new__(DailyAggregationTask)
    task.config = {"scheduler": {"jobs": {"daily_aggregation": {"require_authorship_notes": True}}}}
    task.logger = MagicMock()
    task.execute()

    assert stats_db.find_daily_aggregation_affected_dates.call_args.kwargs["require_authorship_notes"] is True
```

Add failure test:

```python
@patch("core.scheduler.tasks.daily_aggregation_task.StatsDatabase")
def test_execute_fails_when_repository_id_update_fails(mock_stats_db_cls):
    stats_db = MagicMock()
    stats_db.list_repositories_for_daily_aggregation.return_value = [
        {"id": "r1", "repo_path": "repo/a", "last_daily_aggregation_id": None}
    ]
    stats_db.find_daily_aggregation_affected_dates.return_value = {
        "commit_dates": [20260605],
        "last_id": "c003",
    }
    stats_db.aggregate_committed_daily_stats.return_value = []
    stats_db.update_repository_last_daily_aggregation_id.return_value = False
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask.__new__(DailyAggregationTask)
    task.config = {}
    task.logger = MagicMock()

    with pytest.raises(RuntimeError, match="daily aggregation id"):
        task.execute()
```

- [ ] **Step 2: Run tests to verify fail**

Run:

```bash
pytest tests/unit/test_scheduler/test_stats_task.py -v
```

Expected: FAIL because task still uses old query and in-memory aggregation.

- [ ] **Step 3: Implement new task orchestration**

In `core/scheduler/tasks/daily_aggregation_task.py`, remove `_event_stat_date` and `_aggregate_by_repo_contributor`. Keep `_require_authorship_notes`.

Implement `execute` as:

```python
def execute(self, context=None):
    self.logger.info("开始执行每日统计聚合任务")
    context = context or {}
    stats_db = StatsDatabase()
    stats_db.consolidate_unknown_repositories()

    repo_url = context.get("repo_url")
    require_authorship_notes = self._require_authorship_notes(context)
    repositories = stats_db.list_repositories_for_daily_aggregation(repo_url=repo_url)

    total_records = 0
    for repo in repositories:
        repo_id = repo["id"]
        repo_path = repo.get("repo_path")
        last_id = repo.get("last_daily_aggregation_id")
        affected = stats_db.find_daily_aggregation_affected_dates(
            repo_url=repo_path,
            last_aggregation_id=last_id,
            require_authorship_notes=require_authorship_notes,
        )
        commit_dates = affected.get("commit_dates") or []
        latest_id = affected.get("last_id")
        if not commit_dates:
            continue

        rows = stats_db.aggregate_committed_daily_stats(
            repo_url=repo_path,
            commit_dates=commit_dates,
            require_authorship_notes=require_authorship_notes,
        )
        for row in rows:
            stats_db.upsert_daily_stat(
                row["stat_date"],
                repo_id,
                row["contributor_name"],
                row["contributor_email"],
                row,
            )
        if latest_id:
            updated = stats_db.update_repository_last_daily_aggregation_id(repo_id, latest_id)
            if updated is False:
                raise RuntimeError(
                    "Failed to update repository daily aggregation id marker "
                    f"for repo_id={repo_id} committed_id={latest_id}"
                )
        total_records += len(rows)

    self.logger.info(f"聚合完成，共处理 {total_records} 条记录")
    return {"success": True, "records": total_records}
```

If `start_date`, `end_date`, or `contributor` context support must remain, keep them out of the first implementation because the approved design makes repository ID cursor the main path. Do not pass date filters into the final SUM query unless a later requirement redefines cursor semantics.

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/unit/test_scheduler/test_stats_task.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/scheduler/tasks/daily_aggregation_task.py tests/unit/test_scheduler/test_stats_task.py
git commit -m "feat: aggregate daily stats by repository id cursor"
```

## Task 6: Query and API Field Migration

**Files:**
- Modify: `core/database/stats_db.py`
- Modify: `api/routes/stats.py`
- Test: `tests/integration/test_dimensions_api.py`
- Test: `tests/integration/test_dimensions_db.py`

- [ ] **Step 1: Write failing aggregate stats DB test**

In `tests/integration/test_dimensions_db.py`, add:

```python
def test_get_aggregated_stats_uses_new_daily_fields(setup_dbs):
    _, stats_db = setup_dbs
    repo_id = stats_db.get_or_create_repository("example.com/org/repo")
    stats_db.upsert_daily_stat(
        20260605,
        repo_id,
        "alice",
        "alice@example.com",
        {
            "repo_name": "org/repo",
            "contributor_name": "alice",
            "contributor_email": "alice@example.com",
            "human_additions": 10,
            "unknown_additions": 1,
            "git_diff_deleted_lines": 2,
            "git_diff_added_lines": 30,
            "mixed_additions": 3,
            "ai_additions": 4,
            "ai_accepted": 5,
            "total_ai_additions": 6,
            "total_ai_deletions": 7,
        },
    )

    rows = stats_db.get_aggregated_stats(20260601, 20260630, repo_id=repo_id)

    assert rows == [
        {
            "stat_date": 20260605,
            "human_additions": 10,
            "unknown_additions": 1,
            "git_diff_deleted_lines": 2,
            "git_diff_added_lines": 30,
            "mixed_additions": 3,
            "ai_additions": 4,
            "ai_accepted": 5,
            "total_ai_additions": 6,
            "total_ai_deletions": 7,
        }
    ]
```

- [ ] **Step 2: Update API tests to expect new summary names**

In `tests/integration/test_dimensions_api.py`, update mock items:

```python
db.get_aggregated_stats.return_value = [
    {
        "stat_date": 20260605,
        "ai_additions": 30,
        "ai_accepted": 25,
        "human_additions": 75,
        "git_diff_added_lines": 100,
    },
    {
        "stat_date": 20260606,
        "ai_additions": 80,
        "ai_accepted": 75,
        "human_additions": 25,
        "git_diff_added_lines": 100,
    },
]
```

Expected summary assertions:

```python
assert data["total_lines"] == 200
assert data["ai_lines"] == 100
assert data["ai_lines_pct"] == 50.0
```

Keep compatibility endpoint response keys `total_lines`, `ai_lines`, and `ai_lines_pct` for callers, but compute from new internal fields.

- [ ] **Step 3: Run tests to verify fail**

Run:

```bash
pytest tests/integration/test_dimensions_db.py::test_get_aggregated_stats_uses_new_daily_fields tests/integration/test_dimensions_api.py -v
```

Expected: FAIL because DB/API still use old field names.

- [ ] **Step 4: Implement new aggregate stats output**

In `core/database/stats_db.py`, update `get_aggregated_stats` query to sum:

```python
func.sum(StatsDailyStat.human_additions).label("human_additions")
func.sum(StatsDailyStat.unknown_additions).label("unknown_additions")
func.sum(StatsDailyStat.git_diff_deleted_lines).label("git_diff_deleted_lines")
func.sum(StatsDailyStat.git_diff_added_lines).label("git_diff_added_lines")
func.sum(StatsDailyStat.mixed_additions).label("mixed_additions")
func.sum(StatsDailyStat.ai_additions).label("ai_additions")
func.sum(StatsDailyStat.ai_accepted).label("ai_accepted")
func.sum(StatsDailyStat.total_ai_additions).label("total_ai_additions")
func.sum(StatsDailyStat.total_ai_deletions).label("total_ai_deletions")
```

Return dicts with those same new keys.

Update `_group_by_granularity` to initialize and sum those same keys. Convert `stat_date` with `datetime.strptime(str(item["stat_date"]), "%Y%m%d")`, not `datetime.fromtimestamp(item["stat_date"] / 1000)`, because `stat_date` is `yyyyMMdd`.

- [ ] **Step 5: Update API summary helper**

In `api/routes/stats.py`, update `_build_summary`:

```python
total_generated = sum(_to_int(i.get("ai_additions")) for i in items)
total_accepted = sum(_to_int(i.get("ai_accepted")) for i in items)
total_human = sum(_to_int(i.get("human_additions")) for i in items)
total_lines = sum(_to_int(i.get("git_diff_added_lines")) for i in items)
```

Keep the returned summary keys unchanged:

```python
return {
    "total_ai_generated": total_generated,
    "total_ai_accepted": total_accepted,
    "total_human": total_human,
    "total_lines": total_lines,
    "avg_ai_percentage": avg_pct,
}
```

In `get_stats_aggregate_compat`, update AI commit detection:

```python
ai_commits = sum(1 for row in committed_rows if int(row.get("ai_accepted") or 0) > 0)
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/integration/test_dimensions_db.py::test_get_aggregated_stats_uses_new_daily_fields tests/integration/test_dimensions_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/database/stats_db.py api/routes/stats.py tests/integration/test_dimensions_db.py tests/integration/test_dimensions_api.py
git commit -m "feat: expose new daily aggregation metrics"
```

## Task 7: Committed Event Query Compatibility

**Files:**
- Modify: `core/database/stats_db.py`
- Test: `tests/integration/test_dimensions_db.py`

- [ ] **Step 1: Update committed query tests**

In `tests/integration/test_dimensions_db.py`, update assertions from:

```python
assert committed[0]["ai_accepted_lines"] == 3
```

to:

```python
assert committed[0]["ai_accepted"] == 3
assert committed[0]["ai_additions"] == 3
assert committed[0]["total_ai_additions"] == 3
```

Add a seconds range assertion:

```python
assert committed[0]["timestamp"] == 1710000000
assert committed[0]["commit_date"] == 20240309
```

- [ ] **Step 2: Run tests to verify fail**

Run:

```bash
pytest tests/integration/test_dimensions_db.py::test_query_committed_and_checkpoint_events -v
```

Expected: FAIL while `query_committed_events` still returns old names or parses JSON totals.

- [ ] **Step 3: Update `query_committed_events`**

In `core/database/stats_db.py`, update committed event dicts:

```python
"timestamp": int(row.timestamp or 0),
"commit_date": int(row.commit_date or 0),
"mixed_additions": int(row.mixed_additions_total or 0),
"human_additions": int(row.human_additions or 0),
"git_diff_deleted_lines": int(row.git_diff_deleted_lines or 0),
"git_diff_added_lines": int(row.git_diff_added_lines or 0),
"ai_additions": int(row.ai_additions_total or 0),
"ai_accepted": int(row.ai_accepted_total or 0),
"total_ai_additions": int(row.total_ai_additions_total or 0),
"total_ai_deletions": int(row.total_ai_deletions_total or 0),
```

Keep `tool_model_pairs_total` if existing API/tests still need it.

Update `get_committed_events_paginated` to display numeric snapshot fields instead of reparsing JSON for:

```python
"mixed_additions": int(row.mixed_additions_total or 0),
"ai_additions": int(row.ai_additions_total or 0),
"ai_accepted": int(row.ai_accepted_total or 0),
"total_ai_additions": int(row.total_ai_additions_total or 0),
"total_ai_deletions": int(row.total_ai_deletions_total or 0),
```

- [ ] **Step 4: Run committed query tests**

Run:

```bash
pytest tests/integration/test_dimensions_db.py::test_query_committed_and_checkpoint_events tests/unit/test_database/test_sqlite.py::test_query_committed_events_normalizes_repo_url_filter -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/database/stats_db.py tests/integration/test_dimensions_db.py tests/unit/test_database/test_sqlite.py
git commit -m "feat: query committed metrics from snapshot columns"
```

## Task 8: SQL Schema and Migration

**Files:**
- Modify: `sql/metrics_schema_mysql.sql`
- Create: `sql/daily_aggregation_id_date_migration_mysql.sql`

- [ ] **Step 1: Update base schema**

In `sql/metrics_schema_mysql.sql`:

For `metrics_events_committed`, add:

```sql
commit_date BIGINT COMMENT '提交日期 yyyyMMdd',
mixed_additions_total INT DEFAULT 0 COMMENT '混合生成代码行数首值',
ai_additions_total INT DEFAULT 0 COMMENT 'AI 生成代码行数首值',
ai_accepted_total INT DEFAULT 0 COMMENT '被接受 AI 代码行数首值',
total_ai_additions_total INT DEFAULT 0 COMMENT '总 AI 新增代码行数首值',
total_ai_deletions_total INT DEFAULT 0 COMMENT '总 AI 删除代码行数首值',
time_waiting_for_ai_total BIGINT DEFAULT 0 COMMENT '等待 AI 响应时长首值',
INDEX idx_committed_repo_id (repo_url, id),
INDEX idx_committed_repo_commit_date (repo_url, commit_date),
```

For `stats_repositories`, replace:

```sql
last_daily_aggregation_commit_sha VARCHAR(40) COMMENT '最近一次每日聚合成功统计到的提交 SHA',
```

with:

```sql
last_daily_aggregation_id VARCHAR(20) COMMENT '最近一次每日聚合成功统计到的 committed 事件 ID',
```

For `stats_commit_daily`, replace old metric columns with the new fields from the spec.

For `authorship_notes`, add:

```sql
commit_date BIGINT COMMENT '提交日期 yyyyMMdd',
INDEX idx_authorship_notes_repo_commit_date (repo_url, commit_date),
```

- [ ] **Step 2: Create migration SQL**

Create `sql/daily_aggregation_id_date_migration_mysql.sql` with:

```sql
-- 2026-06-07 每日聚合 ID 游标与 commit_date 迁移

ALTER TABLE metrics_events_committed
    ADD COLUMN commit_date BIGINT NULL COMMENT '提交日期 yyyyMMdd' AFTER timestamp,
    ADD COLUMN mixed_additions_total INT NOT NULL DEFAULT 0 COMMENT '混合生成代码行数首值' AFTER time_waiting_for_ai,
    ADD COLUMN ai_additions_total INT NOT NULL DEFAULT 0 COMMENT 'AI 生成代码行数首值' AFTER mixed_additions_total,
    ADD COLUMN ai_accepted_total INT NOT NULL DEFAULT 0 COMMENT '被接受 AI 代码行数首值' AFTER ai_additions_total,
    ADD COLUMN total_ai_additions_total INT NOT NULL DEFAULT 0 COMMENT '总 AI 新增代码行数首值' AFTER ai_accepted_total,
    ADD COLUMN total_ai_deletions_total INT NOT NULL DEFAULT 0 COMMENT '总 AI 删除代码行数首值' AFTER total_ai_additions_total,
    ADD COLUMN time_waiting_for_ai_total BIGINT NOT NULL DEFAULT 0 COMMENT '等待 AI 响应时长首值' AFTER total_ai_deletions_total;

UPDATE metrics_events_committed
SET timestamp = CASE WHEN timestamp > 9999999999 THEN FLOOR(timestamp / 1000) ELSE timestamp END
WHERE timestamp IS NOT NULL;

UPDATE metrics_events_committed
SET commit_date = CAST(DATE_FORMAT(FROM_UNIXTIME(timestamp), '%Y%m%d') AS UNSIGNED)
WHERE timestamp IS NOT NULL AND timestamp > 0;

UPDATE metrics_events_committed
SET
    mixed_additions_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(mixed_additions, '$[0]')) AS UNSIGNED), 0),
    ai_additions_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(ai_additions, '$[0]')) AS UNSIGNED), 0),
    ai_accepted_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(ai_accepted, '$[0]')) AS UNSIGNED), 0),
    total_ai_additions_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(total_ai_additions, '$[0]')) AS UNSIGNED), 0),
    total_ai_deletions_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(total_ai_deletions, '$[0]')) AS UNSIGNED), 0),
    time_waiting_for_ai_total = COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(time_waiting_for_ai, '$[0]')) AS UNSIGNED), 0);

ALTER TABLE metrics_events_committed
    ADD INDEX idx_committed_repo_id (repo_url, id),
    ADD INDEX idx_committed_repo_commit_date (repo_url, commit_date);

ALTER TABLE authorship_notes
    ADD COLUMN commit_date BIGINT NULL COMMENT '提交日期 yyyyMMdd' AFTER commit_time;

UPDATE authorship_notes
SET commit_date = CAST(
    DATE_FORMAT(
        FROM_UNIXTIME(CASE WHEN commit_time > 9999999999 THEN FLOOR(commit_time / 1000) ELSE commit_time END),
        '%Y%m%d'
    ) AS UNSIGNED
)
WHERE commit_time IS NOT NULL AND commit_time > 0;

ALTER TABLE authorship_notes
    ADD INDEX idx_authorship_notes_repo_commit_date (repo_url, commit_date);

ALTER TABLE stats_repositories
    ADD COLUMN last_daily_aggregation_id VARCHAR(20) NULL COMMENT '最近一次每日聚合成功统计到的 committed 事件 ID' AFTER last_blame_commit_sha;

ALTER TABLE stats_commit_daily
    ADD COLUMN human_additions INT DEFAULT 0 COMMENT '人类手动添加代码行数' AFTER contributor_email,
    ADD COLUMN unknown_additions INT DEFAULT 0 COMMENT '未知来源新增代码行数' AFTER human_additions,
    ADD COLUMN git_diff_deleted_lines INT DEFAULT 0 COMMENT 'Git diff 删除行数' AFTER unknown_additions,
    ADD COLUMN git_diff_added_lines INT DEFAULT 0 COMMENT 'Git diff 新增行数' AFTER git_diff_deleted_lines,
    ADD COLUMN mixed_additions INT DEFAULT 0 COMMENT '混合生成代码行数' AFTER git_diff_added_lines,
    ADD COLUMN ai_additions INT DEFAULT 0 COMMENT 'AI 生成代码行数' AFTER mixed_additions,
    ADD COLUMN ai_accepted INT DEFAULT 0 COMMENT '被接受 AI 代码行数' AFTER ai_additions,
    ADD COLUMN total_ai_additions INT DEFAULT 0 COMMENT '总 AI 新增代码行数' AFTER ai_accepted,
    ADD COLUMN total_ai_deletions INT DEFAULT 0 COMMENT '总 AI 删除代码行数' AFTER total_ai_additions;

UPDATE stats_commit_daily
SET
    human_additions = COALESCE(human_lines, 0),
    git_diff_added_lines = COALESCE(total_lines, 0),
    ai_additions = COALESCE(ai_lines, 0),
    ai_accepted = COALESCE(ai_accepted_lines, 0),
    total_ai_additions = COALESCE(ai_total_lines, 0);

ALTER TABLE stats_commit_daily
    DROP COLUMN ai_lines,
    DROP COLUMN ai_total_lines,
    DROP COLUMN ai_accepted_lines,
    DROP COLUMN human_lines,
    DROP COLUMN total_lines;
```

Do not drop `stats_repositories.last_daily_aggregation_commit_sha` in this first migration unless the deployment process confirms no older app version will run after migration. The ORM will stop using it.

- [ ] **Step 3: Smoke-check SQL text**

Run:

```bash
rg -n "commit_date|last_daily_aggregation_id|mixed_additions_total|ai_accepted|DROP COLUMN ai_lines" sql/metrics_schema_mysql.sql sql/daily_aggregation_id_date_migration_mysql.sql
```

Expected: all new fields appear; old daily stat drops appear only in migration.

- [ ] **Step 4: Commit**

```bash
git add sql/metrics_schema_mysql.sql sql/daily_aggregation_id_date_migration_mysql.sql
git commit -m "feat: add daily aggregation id date migration"
```

## Task 9: Full Test Cleanup and Verification

**Files:**
- Modify: any remaining tests under `tests/` that reference removed `stats_commit_daily` fields.
- Modify: any remaining core/API references to removed daily stat fields.

- [ ] **Step 1: Search for stale field references**

Run:

```bash
rg -n "StatsDailyStat\\.(ai_lines|ai_total_lines|ai_accepted_lines|human_lines|total_lines)|last_daily_aggregation_commit_sha|update_repository_last_daily_aggregation_commit_sha|ai_accepted_lines|human_lines|total_lines" core api tests
```

Expected: Remaining `ai_lines`, `non_ai_lines`, and `total_lines` references under blame stats files are allowed because they belong to `stats_blame_*`, not `stats_commit_daily`. No remaining `StatsDailyStat.*` old fields, old daily aggregation commit SHA cursor method, or daily API tests should reference removed daily stat fields.

- [ ] **Step 2: Update any stale tests**

For stale daily aggregation assertions, use this mapping:

```text
human_lines -> human_additions
total_lines -> git_diff_added_lines
ai_lines -> ai_additions
ai_total_lines -> total_ai_additions
ai_accepted_lines -> ai_accepted
```

For stale cursor assertions:

```text
last_daily_aggregation_commit_sha -> last_daily_aggregation_id
update_repository_last_daily_aggregation_commit_sha -> update_repository_last_daily_aggregation_id
```

- [ ] **Step 3: Run focused test suites**

Run:

```bash
pytest tests/unit/test_models/test_metrics.py tests/unit/test_models/test_stats.py tests/unit/test_database/test_sqlite.py tests/integration/test_dimensions_db.py tests/unit/test_scheduler/test_stats_task.py tests/test_metrics_event_processor_task.py tests/integration/test_dimensions_api.py -v
```

Expected: PASS.

- [ ] **Step 4: Run broader backend tests if time allows**

Run:

```bash
pytest tests/unit tests/integration/test_dimensions_db.py tests/integration/test_dimensions_api.py tests/test_metrics_event_processor_task.py -v
```

Expected: PASS. If unrelated existing failures appear, record exact failing tests and error messages.

- [ ] **Step 5: Final search verification**

Run:

```bash
rg -n "StatsDailyStat\\.(ai_lines|ai_total_lines|ai_accepted_lines|human_lines|total_lines)|last_daily_aggregation_commit_sha|update_repository_last_daily_aggregation_commit_sha" core api tests
```

Expected: no matches.

- [ ] **Step 6: Commit cleanup**

```bash
git add core api tests
git commit -m "test: update daily aggregation expectations"
```

## Task 10: Manual Runtime Check

**Files:**
- No planned source edits.

- [ ] **Step 1: Run app import smoke test**

Run:

```bash
python -c "from core.scheduler.tasks.daily_aggregation_task import DailyAggregationTask; from core.services.metrics_service import MetricsService; from core.database.stats_db import StatsDatabase; print('imports ok')"
```

Expected:

```text
imports ok
```

- [ ] **Step 2: Run scheduler task with mocked DB only if unit tests passed**

No live database command is required for this plan. Do not run against production database during implementation.

- [ ] **Step 3: Commit any smoke-test fixes**

If Step 1 required import-only fixes:

```bash
git add core
git commit -m "fix: resolve daily aggregation import issues"
```

If no fixes were needed, do not create a commit.
