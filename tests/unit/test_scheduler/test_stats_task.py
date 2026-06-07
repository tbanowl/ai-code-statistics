from unittest.mock import MagicMock, patch

import pytest

from core.scheduler.tasks.daily_aggregation_task import DailyAggregationTask


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
    stats_db.list_repositories_for_daily_aggregation.assert_called_once_with(
        repo_url=None
    )
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
    stats_db.update_repository_last_daily_aggregation_id.assert_called_once_with(
        "r1", "c003"
    )


@patch("core.scheduler.tasks.daily_aggregation_task.StatsDatabase")
def test_execute_passes_authorship_notes_gate_to_discovery_and_aggregation(
    mock_stats_db_cls,
):
    stats_db = MagicMock()
    stats_db.list_repositories_for_daily_aggregation.return_value = [
        {"id": "r1", "repo_path": "repo/a", "last_daily_aggregation_id": None}
    ]
    stats_db.find_daily_aggregation_affected_dates.return_value = {
        "commit_dates": [20260605],
        "last_id": None,
    }
    stats_db.aggregate_committed_daily_stats.return_value = []
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask.__new__(DailyAggregationTask)
    task.config = {
        "scheduler": {
            "jobs": {
                "daily_aggregation": {"require_authorship_notes": True}
            }
        }
    }
    task.logger = MagicMock()
    task.execute()

    assert stats_db.find_daily_aggregation_affected_dates.call_args.kwargs[
        "require_authorship_notes"
    ] is True
    assert stats_db.aggregate_committed_daily_stats.call_args.kwargs[
        "require_authorship_notes"
    ] is True


@patch("core.scheduler.tasks.daily_aggregation_task.StatsDatabase")
def test_execute_context_overrides_authorship_notes_gate(mock_stats_db_cls):
    stats_db = MagicMock()
    stats_db.list_repositories_for_daily_aggregation.return_value = [
        {"id": "r1", "repo_path": "repo/a", "last_daily_aggregation_id": None}
    ]
    stats_db.find_daily_aggregation_affected_dates.return_value = {
        "commit_dates": [20260605],
        "last_id": None,
    }
    stats_db.aggregate_committed_daily_stats.return_value = []
    mock_stats_db_cls.return_value = stats_db

    task = DailyAggregationTask.__new__(DailyAggregationTask)
    task.config = {
        "scheduler": {
            "jobs": {
                "daily_aggregation": {"require_authorship_notes": False}
            }
        }
    }
    task.logger = MagicMock()
    task.execute({"require_authorship_notes": True})

    assert stats_db.find_daily_aggregation_affected_dates.call_args.kwargs[
        "require_authorship_notes"
    ] is True
    assert stats_db.aggregate_committed_daily_stats.call_args.kwargs[
        "require_authorship_notes"
    ] is True


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
