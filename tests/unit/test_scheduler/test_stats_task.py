from unittest.mock import MagicMock, patch

from core.scheduler.tasks.daily_aggregation_task import DailyAggregationTask
from core.utils.repo_url import UNKNOWN_REPO


def test_aggregate_by_repo_contributor():
    task = DailyAggregationTask.__new__(DailyAggregationTask)

    committed = [
        {
            "repo_url": "repo/a",
            "author": "alice",
            "author_uid": "alice <a@example.com>",
            "author_email": "a@example.com",
            "human_additions": 5,
            "ai_accepted_lines": 10,
        },
        {
            "repo_url": "repo/a",
            "author": "alice",
            "author_uid": "alice <a@example.com>",
            "author_email": "a@example.com",
            "human_additions": 7,
            "ai_accepted_lines": 2,
        },
    ]
    checkpoints = [
        {
            "repo_url": "repo/a",
            "author": "alice",
            "author_uid": "alice <a@example.com>",
            "lines_added": 8,
            "lines_added_sloc": 3,
        }
    ]

    data = task._aggregate_by_repo_contributor(committed, checkpoints)
    key = ("repo/a", "alice", "a@example.com", "alice <a@example.com>")
    assert key in data
    assert data[key]["ai_accepted_lines"] == 12
    assert data[key]["human_lines"] == 12
    assert data[key]["ai_generated_lines"] == 3
    assert data[key]["ai_generated_lines_total"] == 8


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
            "ai_accepted_lines": 10,
        }
    ]
    stats_db.query_checkpoint_events.return_value = []
    stats_db.get_latest_stat_date.return_value = 0
    stats_db.get_or_create_repository.return_value = "r1"
    stats_db.get_or_create_contributor.return_value = "c1"
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask.__new__(DailyAggregationTask)
    task.logger = MagicMock()
    result = task.execute()

    assert result["success"] is True
    assert result["records"] == 1
    stats_db.get_or_create_repository.assert_called_once_with("repo/a")
    stats_db.get_or_create_contributor.assert_called_once_with(
        "alice", "a@example.com"
    )
    stats_db.ensure_repo_contributor_link.assert_called_once_with("r1", "c1")
    assert stats_db.upsert_daily_stat.call_count == 1


def test_aggregate_normalizes_none_and_missing_repo_url_to_unknown():
    task = DailyAggregationTask.__new__(DailyAggregationTask)

    committed = [
        {
            "author": "bob",
            "author_uid": "bob",
            "author_email": "b@b.com",
            "human_additions": 3,
        },
        {
            "repo_url": None,
            "author": "bob",
            "author_uid": "bob",
            "author_email": "b@b.com",
            "human_additions": 5,
        },
        {
            "repo_url": "",
            "author": "bob",
            "author_uid": "bob",
            "author_email": "b@b.com",
            "human_additions": 2,
        },
    ]
    data = task._aggregate_by_repo_contributor(committed, [])

    # All three events should merge into a single key with repo_path == UNKNOWN_REPO
    key = (UNKNOWN_REPO, "bob", "b@b.com", "bob")
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
        },
        {
            "repo_url": "git@git.example.com:org/repo.git",
            "author": "carol",
            "author_uid": "carol",
            "author_email": "c@c.com",
            "human_additions": 6,
        },
    ]
    data = task._aggregate_by_repo_contributor(committed, [])

    # Both normalize to "git.example.com/org/repo"
    expected_repo_path = "git.example.com/org/repo"
    key = (expected_repo_path, "carol", "c@c.com", "carol")
    assert key in data
    assert data[key]["human_lines"] == 10
    assert data[key]["repo_name"] == "org/repo"
    assert len(data) == 1
