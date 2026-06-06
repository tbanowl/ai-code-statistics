from datetime import datetime
from unittest.mock import MagicMock, patch

from core.scheduler.tasks.daily_aggregation_task import DailyAggregationTask
from core.utils.repo_url import UNKNOWN_REPO


def _millis(year, month, day, hour=0, minute=0, second=0):
    return int(datetime(year, month, day, hour, minute, second).timestamp() * 1000)


def test_aggregate_by_repo_contributor():
    task = DailyAggregationTask.__new__(DailyAggregationTask)

    committed = [
        {
            "repo_url": "repo/a",
            "author": "alice",
            "author_uid": "alice <a@example.com>",
            "author_email": "a@example.com",
            "human_additions": 5,
            "git_diff_added_lines": 20,
            "ai_additions": 4,
            "total_ai_additions_total": 6,
            "ai_accepted_lines": 10,
            "timestamp": _millis(2026, 6, 5, 10, 30),
        },
        {
            "repo_url": "repo/a",
            "author": "alice",
            "author_uid": "alice <a@example.com>",
            "author_email": "a@example.com",
            "human_additions": 7,
            "git_diff_added_lines": 11,
            "ai_additions": 3,
            "total_ai_additions_total": 5,
            "ai_accepted_lines": 2,
            "timestamp": _millis(2026, 6, 5, 11, 30),
        },
    ]

    data, latest_commits = task._aggregate_by_repo_contributor(committed)
    key = (20260605, "repo/a", "alice", "a@example.com")
    assert key in data
    assert data[key]["ai_accepted_lines"] == 12
    assert data[key]["human_lines"] == 12
    assert data[key]["ai_lines"] == 7
    assert data[key]["ai_total_lines"] == 11
    assert data[key]["total_lines"] == 31
    assert data[key]["contributor_email"] == "a@example.com"
    assert "ai_percentage" not in data[key]
    assert "git_ai_version" not in data[key]
    assert latest_commits == {}


@patch("core.scheduler.tasks.daily_aggregation_task.StatsDatabase")
def test_execute_calls_stats_db_methods(mock_stats_db_cls):
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
            "timestamp": _millis(2026, 6, 5, 10, 30),
        }
    ]
    stats_db.get_latest_stat_date.return_value = 0
    stats_db.get_or_create_repository.return_value = "r1"
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask.__new__(DailyAggregationTask)
    task.logger = MagicMock()
    result = task.execute()

    assert result["success"] is True
    assert result["records"] == 1
    stats_db.get_or_create_repository.assert_called_once_with("repo/a")
    stats_db.get_or_create_contributor.assert_not_called()
    stats_db.ensure_repo_contributor_link.assert_not_called()
    assert stats_db.upsert_daily_stat.call_count == 1
    args = stats_db.upsert_daily_stat.call_args.args
    assert args[0] == 20260605
    assert args[1] == "r1"
    assert args[2] == "alice"
    assert args[3] == "a@example.com"
    stats_db.update_repository_last_daily_aggregation_commit_sha.assert_called_once_with(
        "r1", "abc123"
    )


def test_aggregate_normalizes_none_and_missing_repo_url_to_unknown():
    task = DailyAggregationTask.__new__(DailyAggregationTask)

    committed = [
        {
            "author": "bob",
            "author_uid": "bob",
            "author_email": "b@b.com",
            "human_additions": 3,
            "timestamp": _millis(2026, 6, 5),
        },
        {
            "repo_url": None,
            "author": "bob",
            "author_uid": "bob",
            "author_email": "b@b.com",
            "human_additions": 5,
            "timestamp": _millis(2026, 6, 5),
        },
        {
            "repo_url": "",
            "author": "bob",
            "author_uid": "bob",
            "author_email": "b@b.com",
            "human_additions": 2,
            "timestamp": _millis(2026, 6, 5),
        },
    ]
    data, _latest_commits = task._aggregate_by_repo_contributor(committed)

    # All three events should merge into a single key with repo_path == UNKNOWN_REPO
    key = (20260605, UNKNOWN_REPO, "bob", "b@b.com")
    assert key in data
    assert data[key]["human_lines"] == 10
    assert len(data) == 1


def test_aggregate_normalizes_different_url_formats_to_same_key():
    task = DailyAggregationTask.__new__(DailyAggregationTask)

    committed = [
        {
            "repo_url": "https://git.example.com/org/repo.git",
            "author": "carol",
            "author_uid": "carol",
            "author_email": "c@c.com",
            "human_additions": 4,
            "timestamp": _millis(2026, 6, 5),
        },
        {
            "repo_url": "git@git.example.com:org/repo.git",
            "author": "carol",
            "author_uid": "carol",
            "author_email": "c@c.com",
            "human_additions": 6,
            "timestamp": _millis(2026, 6, 5),
        },
    ]
    data, _latest_commits = task._aggregate_by_repo_contributor(committed)

    # Both normalize to "git.example.com/org/repo"
    expected_repo_path = "git.example.com/org/repo"
    key = (20260605, expected_repo_path, "carol", "c@c.com")
    assert key in data
    assert data[key]["human_lines"] == 10
    assert data[key]["repo_name"] == "org/repo"
    assert len(data) == 1


@patch("core.scheduler.tasks.daily_aggregation_task.StatsDatabase")
def test_execute_passes_authorship_notes_gate_from_config(mock_stats_db_cls):
    stats_db = MagicMock()
    stats_db.query_committed_events.return_value = []
    stats_db.get_latest_stat_date.return_value = 0
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask.__new__(DailyAggregationTask)
    task.config = {
        "scheduler": {
            "jobs": {
                "daily_aggregation": {
                    "require_authorship_notes": True,
                }
            }
        }
    }
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

    task = DailyAggregationTask.__new__(DailyAggregationTask)
    task.config = {
        "scheduler": {
            "jobs": {
                "daily_aggregation": {
                    "require_authorship_notes": False,
                }
            }
        }
    }
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

    task = DailyAggregationTask.__new__(DailyAggregationTask)
    task.config = {}
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
