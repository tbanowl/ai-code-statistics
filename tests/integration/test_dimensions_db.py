import os
import tempfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as db_base
from core.database.authorship_notes_db import compute_note_content_hash
from core.database.metrics_db import MetricsDatabase
from core.database.stats_db import StatsDatabase
from core.scheduler.tasks.daily_aggregation_task import DailyAggregationTask
from core.services.metrics_service import MetricsService
from core.database.base import session_scope
from core.database.models import (
    AuthorshipNotes,
    MetricsEventsAgentUsage,
    MetricsEventsCheckpoint,
    MetricsEventsCommitted,
    MetricsEventsInstallHooks,
    StatsContributor,
    StatsDailyStat,
    StatsRepoContributor,
    StatsRepository,
)
from core.utils.data_uid import gen_checkpoint_uid, gen_commited_uid


@pytest.fixture
def db_url():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield f"sqlite:///{path}"
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def setup_dbs(db_url):
    loader.config_data = {
        "features": {"enabled": True},
        "git": {"type": "github"},
        "database": {"url": db_url, "echo": False},
    }
    db_base.global_engine = create_engine(db_url)
    metrics_db = MetricsDatabase()
    stats_db = StatsDatabase()
    db_base.Base.metadata.create_all(metrics_db.engine)
    return metrics_db, stats_db


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


def test_metrics_processor_non_committed_events_store_seconds(setup_dbs):
    metrics_db, _stats_db = setup_dbs
    service = MetricsService()
    raw_id = metrics_db.save_metrics_raw(
        version=1,
        event_count=3,
        payload_json="{}",
        received_at=1710000000000,
    )

    service._process_single_event(
        {
            "e": 2,
            "t": 1710000000,
            "v": {},
            "a": {
                "1": "https://example.com/org/repo.git",
                "2": "Alice <alice@example.com>",
                "3": "abc123",
            },
        },
        raw_id,
    )
    service._process_single_event(
        {
            "e": 3,
            "t": 1710000000,
            "v": {
                "0": "codex",
                "1": "installed",
                "2": "ok",
            },
            "a": {},
        },
        raw_id,
    )
    service._process_single_event(
        {
            "e": 4,
            "t": 1710000000,
            "v": {
                "0": 1710000000,
                "1": "ai_agent",
                "2": "core/file.py",
            },
            "a": {
                "1": "https://example.com/org/repo.git",
                "2": "Alice <alice@example.com>",
                "3": "abc123",
            },
        },
        raw_id,
    )

    with session_scope(metrics_db.engine) as session:
        agent_usage = session.query(MetricsEventsAgentUsage).one()
        install_hooks = session.query(MetricsEventsInstallHooks).one()
        checkpoint = session.query(MetricsEventsCheckpoint).one()

        assert agent_usage.timestamp == 1710000000
        assert install_hooks.timestamp == 1710000000
        assert checkpoint.timestamp == 1710000000
        assert checkpoint.checkpoint_ts == 1710000000 * 1000


def test_metrics_processor_checkpoint_missing_checkpoint_ts_preserves_none(setup_dbs):
    metrics_db, _stats_db = setup_dbs
    service = MetricsService()
    raw_id = metrics_db.save_metrics_raw(
        version=1,
        event_count=1,
        payload_json="{}",
        received_at=1710000000000,
    )

    service._process_single_event(
        {
            "e": 4,
            "t": 1710000000,
            "v": {
                "1": "ai_agent",
                "2": "core/file.py",
            },
            "a": {
                "1": "https://example.com/org/repo.git",
                "2": "Alice <alice@example.com>",
                "3": "abc123",
            },
        },
        raw_id,
    )

    with session_scope(metrics_db.engine) as session:
        checkpoint = session.query(MetricsEventsCheckpoint).one()
        assert checkpoint.timestamp == 1710000000
        assert checkpoint.checkpoint_ts is None


def test_get_committed_events_in_range_uses_second_bounds(setup_dbs):
    metrics_db, _stats_db = setup_dbs
    service = MetricsService()
    raw_id = metrics_db.save_metrics_raw(
        version=1,
        event_count=1,
        payload_json="{}",
        received_at=1710000000000,
    )
    service._process_single_event(
        {
            "e": 1,
            "t": 1710000000,
            "v": {
                "0": 11,
                "1": 2,
                "2": 13,
            },
            "a": {
                "1": "https://example.com/org/repo.git",
                "2": "Alice <alice@example.com>",
                "3": "abc123",
            },
        },
        raw_id,
    )

    rows = metrics_db.get_committed_events_in_range(
        datetime.fromtimestamp(1710000000, timezone.utc),
        datetime.fromtimestamp(1710000010, timezone.utc),
    )

    assert len(rows) == 1
    assert rows[0]["timestamp"] == 1710000000


def test_query_committed_and_checkpoint_events(setup_dbs):
    metrics_db, stats_db = setup_dbs

    raw_id = metrics_db.save_metrics_raw(
        version=1,
        event_count=2,
        payload_json="{}",
        received_at=1710000000000,
    )
    committed = MetricsEventsCommitted(
        raw_id=raw_id,
        timestamp=1710000000,
        commit_date=20240309,
        repo_url="repo/a",
        author="alice <alice@example.com>",
        human_additions=6,
        git_diff_added_lines=10,
        git_diff_deleted_lines=2,
        ai_additions=[3, 1],
        ai_accepted=[3, 1],
        total_ai_additions=[3, 1],
        ai_additions_total=3,
        ai_accepted_total=3,
        total_ai_additions_total=3,
    )
    committed.uid = gen_commited_uid(committed)
    metrics_db.upsert_committed_event(committed)

    checkpoint = MetricsEventsCheckpoint(
        raw_id=raw_id,
        timestamp=1710000000002,
        repo_url="repo/a",
        author="alice <alice@example.com>",
        kind="ai_agent",
        lines_added=5,
        lines_added_sloc=3,
    )
    checkpoint.uid = gen_checkpoint_uid(checkpoint)
    metrics_db.save_checkpoint_event(checkpoint)

    committed = stats_db.query_committed_events(1710000000, 1710000010)
    checkpoints = stats_db.query_checkpoint_events(1710000000000, 1710000000010)

    assert len(committed) == 1
    assert committed[0]["repo_url"] == "repo/a"
    assert committed[0]["author"] == "alice"
    assert committed[0]["author_email"] == "alice@example.com"
    assert committed[0]["ai_accepted_lines"] == 3
    assert committed[0]["human_additions"] == 6
    assert len(checkpoints) == 1
    assert checkpoints[0]["author"] == "alice"
    assert checkpoints[0]["lines_added"] == 5
    assert checkpoints[0]["lines_added_sloc"] == 3


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
        timestamp=1710000001,
        commit_date=20240309,
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
        timestamp=1710000002,
        commit_date=20240309,
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
        1710000000, 1710000010, require_authorship_notes=False
    )
    filtered = stats_db.query_committed_events(
        1710000000, 1710000010, require_authorship_notes=True
    )

    assert {row["commit_sha"] for row in unfiltered} == {"abc123", "def456"}
    assert [row["commit_sha"] for row in filtered] == ["abc123"]
    assert filtered[0]["repo_url"] == "example.com/org/repo"
    assert filtered[0]["timestamp"] == 1710000001


def test_query_committed_events_authorship_notes_match_normalized_repo_url(setup_dbs):
    metrics_db, stats_db = setup_dbs

    raw_id = metrics_db.save_metrics_raw(
        version=1,
        event_count=1,
        payload_json="{}",
        received_at=1710000000000,
    )

    committed = MetricsEventsCommitted(
        raw_id=raw_id,
        timestamp=1710000001,
        commit_date=20240309,
        repo_url="https://example.com/org/repo.git",
        author="alice <alice@example.com>",
        commit_sha="abc123",
        human_additions=6,
        git_diff_added_lines=10,
        ai_additions=[3, 1],
        ai_accepted=[3, 1],
        total_ai_additions=[3, 1],
    )
    committed.uid = gen_commited_uid(committed)
    metrics_db.upsert_committed_event(committed)

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

    filtered = stats_db.query_committed_events(
        1710000000, 1710000010, require_authorship_notes=True
    )

    assert [row["commit_sha"] for row in filtered] == ["abc123"]
    assert filtered[0]["repo_url"] == "example.com/org/repo"


def test_update_repository_last_daily_aggregation_id(setup_dbs):
    _, stats_db = setup_dbs
    repo_id = stats_db.get_or_create_repository("https://example.com/org/repo.git")

    assert stats_db.update_repository_last_daily_aggregation_id(repo_id, "") is False
    assert stats_db.update_repository_last_daily_aggregation_id(repo_id, "   ") is False
    assert (
        stats_db.update_repository_last_daily_aggregation_id(
            "missingrepo0000001", "czmissing"
        )
        is False
    )

    with session_scope(stats_db.engine) as session:
        repo = session.query(StatsRepository).filter(StatsRepository.id == repo_id).one()
        repo.updated_at = 1
        session.flush()
        original_updated_at = repo.updated_at
        assert repo.last_daily_aggregation_id is None

    assert (
        stats_db.update_repository_last_daily_aggregation_id(repo_id, "  czabc123  ")
        is True
    )

    with session_scope(stats_db.engine) as session:
        repo = session.query(StatsRepository).filter(StatsRepository.id == repo_id).one()
        assert repo.last_daily_aggregation_id == "czabc123"
        assert repo.updated_at is not None
        assert repo.updated_at > original_updated_at


def test_find_daily_aggregation_affected_dates_uses_id_cursor(setup_dbs):
    metrics_db, stats_db = setup_dbs
    raw_id = metrics_db.save_metrics_raw(1, 3, "{}", 1710000000)
    stats_db.get_or_create_repository("example.com/org/repo")

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


def test_find_daily_aggregation_affected_dates_rejects_missing_commit_date(setup_dbs):
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
                    commit_date=20240308,
                    repo_url="example.com/org/repo",
                    author="alice <alice@example.com>",
                ),
                MetricsEventsCommitted(
                    id="c002",
                    uid="uid-c002",
                    raw_id=raw_id,
                    timestamp=1710003600,
                    commit_date=20240309,
                    repo_url="example.com/org/repo",
                    author="alice <alice@example.com>",
                ),
                MetricsEventsCommitted(
                    id="c003",
                    uid="uid-c003",
                    raw_id=raw_id,
                    timestamp=1710090000,
                    commit_date=None,
                    repo_url="example.com/org/repo",
                    author="bob <bob@example.com>",
                ),
            ]
        )

    with pytest.raises(ValueError, match="c003"):
        stats_db.find_daily_aggregation_affected_dates(
            repo_url="example.com/org/repo",
            last_aggregation_id="c001",
            require_authorship_notes=False,
        )


def test_find_daily_aggregation_affected_dates_validates_before_authorship_filter(setup_dbs):
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
                    commit_date=20240308,
                    repo_url="example.com/org/repo",
                    author="alice <alice@example.com>",
                    commit_sha="before-cursor",
                ),
                MetricsEventsCommitted(
                    id="c002",
                    uid="uid-c002",
                    raw_id=raw_id,
                    timestamp=1710003600,
                    commit_date=None,
                    repo_url="example.com/org/repo",
                    author="alice <alice@example.com>",
                    commit_sha="invalid-without-note",
                ),
                MetricsEventsCommitted(
                    id="c003",
                    uid="uid-c003",
                    raw_id=raw_id,
                    timestamp=1710090000,
                    commit_date=20240310,
                    repo_url="example.com/org/repo",
                    author="bob <bob@example.com>",
                    commit_sha="valid-with-note",
                ),
                AuthorshipNotes(
                    repo_url="example.com/org/repo",
                    branch="main",
                    commit_sha="valid-with-note",
                    commit_date=20240310,
                    note_blob_oid=None,
                    author_name="bob",
                    author_email="bob@example.com",
                    note_content="note",
                    content_hash=compute_note_content_hash("note"),
                    change_seq=1,
                ),
            ]
        )

    with pytest.raises(ValueError, match="c002"):
        stats_db.find_daily_aggregation_affected_dates(
            repo_url="example.com/org/repo",
            last_aggregation_id="c001",
            require_authorship_notes=True,
        )


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


def test_aggregate_committed_daily_stats_merges_parsed_contributor_keys(setup_dbs):
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
                    author="Alice <alice@example.com>",
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
                    author=" Alice <alice@example.com> ",
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
    assert row["contributor_name"] == "Alice"
    assert row["contributor_email"] == "alice@example.com"
    assert row["human_additions"] == 12
    assert row["git_diff_deleted_lines"] == 3
    assert row["git_diff_added_lines"] == 21
    assert row["mixed_additions"] == 5
    assert row["ai_additions"] == 7
    assert row["ai_accepted"] == 9
    assert row["total_ai_additions"] == 14
    assert row["total_ai_deletions"] == 3


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


def test_get_aggregated_stats_groups_yyyy_mm_dd_monthly_and_weekly(setup_dbs):
    _, stats_db = setup_dbs
    repo_id = stats_db.get_or_create_repository("example.com/org/repo")
    rows = [
        (20260605, 10, 1, 2, 30, 3, 4, 5, 6, 7),
        (20260606, 20, 2, 4, 40, 6, 8, 10, 12, 14),
    ]
    for (
        stat_date,
        human,
        unknown,
        deleted,
        added,
        mixed,
        ai,
        accepted,
        total_ai,
        total_ai_deleted,
    ) in rows:
        stats_db.upsert_daily_stat(
            stat_date,
            repo_id,
            "alice",
            "alice@example.com",
            {
                "repo_name": "org/repo",
                "contributor_name": "alice",
                "contributor_email": "alice@example.com",
                "human_additions": human,
                "unknown_additions": unknown,
                "git_diff_deleted_lines": deleted,
                "git_diff_added_lines": added,
                "mixed_additions": mixed,
                "ai_additions": ai,
                "ai_accepted": accepted,
                "total_ai_additions": total_ai,
                "total_ai_deletions": total_ai_deleted,
            },
        )

    monthly = stats_db.get_aggregated_stats(
        20260601, 20260630, repo_id=repo_id, granularity="monthly"
    )
    weekly = stats_db.get_aggregated_stats(
        20260601, 20260630, repo_id=repo_id, granularity="weekly"
    )

    expected_metrics = {
        "human_additions": 30,
        "unknown_additions": 3,
        "git_diff_deleted_lines": 6,
        "git_diff_added_lines": 70,
        "mixed_additions": 9,
        "ai_additions": 12,
        "ai_accepted": 15,
        "total_ai_additions": 18,
        "total_ai_deletions": 21,
    }
    assert monthly == [
        {"period": "2026-06", "stat_date": 20260601, **expected_metrics}
    ]
    assert weekly == [
        {"period": "2026-W23", "stat_date": 20260601, **expected_metrics}
    ]


def test_repository_contributor_and_daily_stats_flow(setup_dbs):
    _, stats_db = setup_dbs

    repo_id = stats_db.get_or_create_repository("https://github.com/org/repo-a.git")
    contributor_id = stats_db.get_or_create_contributor("alice", "alice@example.com")
    stats_db.ensure_repo_contributor_link(repo_id, contributor_id)
    stats_db.upsert_daily_stat(
        1710000000000,
        repo_id,
        "alice",
        "alice@example.com",
        {
            "repo_name": "org/repo-a",
            "contributor_name": "alice",
            "contributor_email": "alice@example.com",
            "human_additions": 40,
            "unknown_additions": 1,
            "git_diff_deleted_lines": 3,
            "git_diff_added_lines": 100,
            "mixed_additions": 2,
            "ai_additions": 20,
            "ai_accepted": 18,
            "total_ai_additions": 24,
            "total_ai_deletions": 5,
        },
    )

    repos, repo_total = stats_db.list_repositories(limit=10, offset=0)
    contributors, contributor_total = stats_db.list_contributors(limit=10, offset=0)
    daily = stats_db.query_daily_stats(
        start_date=1709999999000,
        end_date=1710000001000,
        repo_id=repo_id,
        contributor_email="alice@example.com",
        limit=10,
        offset=0,
    )

    assert repo_total == 1
    assert contributor_total == 1
    assert repos[0]["repo_path"] == "github.com/org/repo-a"
    assert repos[0]["repo_name"] == "org/repo-a"
    assert contributors[0]["name"] == "alice"
    assert len(daily) == 1
    assert daily[0]["human_additions"] == 40
    assert daily[0]["unknown_additions"] == 1
    assert daily[0]["git_diff_deleted_lines"] == 3
    assert daily[0]["git_diff_added_lines"] == 100
    assert daily[0]["mixed_additions"] == 2
    assert daily[0]["ai_additions"] == 20
    assert daily[0]["ai_accepted"] == 18
    assert daily[0]["total_ai_additions"] == 24
    assert daily[0]["total_ai_deletions"] == 5
    assert daily[0]["repo_name"] == "org/repo-a"
    assert daily[0]["contributor_name"] == "alice"
    assert daily[0]["contributor_email"] == "alice@example.com"


def test_repository_fallback_unknown(setup_dbs):
    _, stats_db = setup_dbs

    repo_id = stats_db.get_or_create_repository("")
    repo = stats_db.get_repository_by_id(repo_id)

    assert repo is not None
    assert repo["repo_path"] == "未知仓库"
    assert repo["repo_name"] == "未知仓库"


def test_consolidate_empty_repository_rows(setup_dbs):
    _, stats_db = setup_dbs

    with session_scope(stats_db.engine) as session:
        unknown = StatsRepository(repo_path="未知仓库", repo_name="未知仓库")
        bad_repo = StatsRepository(repo_path="", repo_name="")
        contributor = StatsContributor(name="alice", email="alice@example.com")
        session.add_all([unknown, bad_repo, contributor])
        session.flush()

        session.add(
            StatsDailyStat(
                stat_date=1710000000000,
                repo_id=unknown.id,
                contributor_name=contributor.name,
                contributor_email=contributor.email,
                human_additions=10,
                unknown_additions=1,
                git_diff_deleted_lines=2,
                git_diff_added_lines=30,
                mixed_additions=3,
                ai_additions=4,
                ai_accepted=5,
                total_ai_additions=6,
                total_ai_deletions=7,
            )
        )
        session.add(
            StatsDailyStat(
                stat_date=1710000000000,
                repo_id=bad_repo.id,
                contributor_name=contributor.name,
                contributor_email=contributor.email,
                human_additions=20,
                unknown_additions=2,
                git_diff_deleted_lines=4,
                git_diff_added_lines=40,
                mixed_additions=6,
                ai_additions=8,
                ai_accepted=10,
                total_ai_additions=12,
                total_ai_deletions=14,
            )
        )
        session.add(
            StatsRepoContributor(repo_id=bad_repo.id, contributor_id=contributor.id)
        )

    unknown_id = stats_db.consolidate_unknown_repositories()

    with session_scope(stats_db.engine) as session:
        bad = (
            session.query(StatsRepository)
            .filter(StatsRepository.repo_path == "")
            .first()
        )
        assert bad is None

        daily = session.query(StatsDailyStat).all()
        assert len(daily) == 1
        assert daily[0].repo_id == unknown_id
        assert daily[0].human_additions == 30
        assert daily[0].unknown_additions == 3
        assert daily[0].git_diff_deleted_lines == 6
        assert daily[0].git_diff_added_lines == 70
        assert daily[0].mixed_additions == 9
        assert daily[0].ai_additions == 12
        assert daily[0].ai_accepted == 15
        assert daily[0].total_ai_additions == 18
        assert daily[0].total_ai_deletions == 21

        links = session.query(StatsRepoContributor).all()
        assert len(links) == 1
        assert links[0].repo_id == unknown_id


def test_aggregation_range_does_not_create_empty_repository(setup_dbs):
    metrics_db, stats_db = setup_dbs

    with session_scope(stats_db.engine) as session:
        session.add(StatsRepository(repo_path="", repo_name=""))

    raw_id = metrics_db.save_metrics_raw(
        version=1,
        event_count=1,
        payload_json="{}",
        received_at=1772323200000,
    )
    committed = MetricsEventsCommitted(
        raw_id=raw_id,
        timestamp=1772323200000,
        repo_url="",
        author="alice <alice@example.com>",
        human_additions=2,
        git_diff_added_lines=8,
        git_diff_deleted_lines=1,
        ai_additions=[3, 1],
        ai_accepted=[3, 1],
        total_ai_additions=[3, 1],
    )
    committed.uid = gen_commited_uid(committed)
    metrics_db.upsert_committed_event(committed)

    task = DailyAggregationTask(loader.config_data)
    task.execute(
        {
            "start_date": 1772294400000,
            "end_date": 1774195199999,
        }
    )

    with session_scope(stats_db.engine) as session:
        bad_count = (
            session.query(StatsRepository)
            .filter(
                (StatsRepository.repo_path == "") | (StatsRepository.repo_name == "")
            )
            .count()
        )
        assert bad_count == 0

        unknown = (
            session.query(StatsRepository)
            .filter(StatsRepository.repo_path == "未知仓库")
            .first()
        )
        assert unknown is not None
