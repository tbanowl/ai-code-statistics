from unittest.mock import MagicMock, patch

from core.scheduler.tasks.daily_aggregation_task import DailyAggregationTask


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
