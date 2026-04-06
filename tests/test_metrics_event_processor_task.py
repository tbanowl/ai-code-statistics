"""测试 MetricsEventProcessorTask"""

import json
from unittest.mock import call, patch

from core.scheduler.tasks.metrics_event_processor_task import MetricsEventProcessorTask


def test_task_no_pending_records():
    """测试没有待处理记录时的执行"""
    config = {
        "scheduler": {
            "jobs": {
                "metrics_event_processor": {
                    "batch_size": 100,
                }
            }
        }
    }

    with (
        patch(
            "core.scheduler.tasks.metrics_event_processor_task.MetricsDatabase"
        ) as mock_metrics_db,
        patch("core.scheduler.tasks.metrics_event_processor_task.StatsDatabase"),
        patch("core.scheduler.tasks.metrics_event_processor_task.MetricsService"),
    ):
        mock_metrics_instance = mock_metrics_db.return_value
        mock_metrics_instance.get_pending_raw_records.return_value = []

        task = MetricsEventProcessorTask(config)
        result = task.execute()

        assert result["success"] is True
        assert result["processed"] == 0
        assert result["batches"] == 0
        mock_metrics_instance.get_pending_raw_records.assert_called_once_with(
            limit=100, last_id=None
        )


def test_task_skips_locked_raw_record():
    """测试原始记录被其他进程锁定时跳过"""
    config = {
        "scheduler": {
            "jobs": {
                "metrics_event_processor": {
                    "batch_size": 100,
                }
            }
        }
    }
    raw_record = {"id": "raw-1", "payload_json": json.dumps({"events": []})}

    with (
        patch(
            "core.scheduler.tasks.metrics_event_processor_task.MetricsDatabase"
        ) as mock_metrics_db,
        patch("core.scheduler.tasks.metrics_event_processor_task.StatsDatabase"),
        patch(
            "core.scheduler.tasks.metrics_event_processor_task.MetricsService"
        ) as mock_service,
    ):
        mock_metrics_instance = mock_metrics_db.return_value
        mock_metrics_instance.get_pending_raw_records.side_effect = [[raw_record], []]
        mock_metrics_instance.mark_raw_extracting.return_value = False

        task = MetricsEventProcessorTask(config)
        result = task.execute()

        assert result["success"] is True
        assert result["processed"] == 0
        assert result["batches"] == 1
        mock_service.return_value.process_raw_event.assert_not_called()
        mock_metrics_instance.mark_raw_extracted.assert_not_called()


def test_task_syncs_repo_contributor_dimensions_after_processing():
    """测试处理成功后同步仓库、贡献者和仓库贡献者关系"""
    config = {
        "scheduler": {
            "jobs": {
                "metrics_event_processor": {
                    "batch_size": 100,
                }
            }
        }
    }
    payload_json = json.dumps(
        {
            "events": [
                {
                    "e": 1,
                    "a": {
                        "1": "https://github.com/acme/repo-a.git",
                        "2": "Alice <alice@example.com>",
                    },
                },
                {
                    "e": 4,
                    "a": {
                        "1": "https://github.com/acme/repo-a.git",
                        "2": "Alice <alice@example.com>",
                    },
                },
                {
                    "e": 2,
                    "a": {
                        "1": "https://github.com/acme/repo-b.git",
                        "2": "Bob <bob@example.com>",
                    },
                },
                {
                    "e": 3,
                    "a": {
                        "0": "1.0.0",
                    },
                },
            ]
        }
    )
    raw_record = {"id": "raw-1", "payload_json": payload_json}

    with (
        patch(
            "core.scheduler.tasks.metrics_event_processor_task.MetricsDatabase"
        ) as mock_metrics_db,
        patch(
            "core.scheduler.tasks.metrics_event_processor_task.StatsDatabase"
        ) as mock_stats_db,
        patch(
            "core.scheduler.tasks.metrics_event_processor_task.MetricsService"
        ) as mock_service,
    ):
        mock_metrics_instance = mock_metrics_db.return_value
        mock_metrics_instance.get_pending_raw_records.side_effect = [[raw_record], []]
        mock_metrics_instance.mark_raw_extracting.return_value = True

        mock_service.return_value.process_raw_event.return_value = {
            "success": True,
            "events_processed": 3,
            "error_count": 0,
        }

        mock_stats_instance = mock_stats_db.return_value
        mock_stats_instance.get_or_create_repository.side_effect = ["repo-1", "repo-2"]
        mock_stats_instance.get_or_create_contributor.side_effect = [
            "contrib-1",
            "contrib-2",
        ]

        task = MetricsEventProcessorTask(config)
        result = task.execute()

        assert result == {
            "success": True,
            "processed": 1,
            "successful": 1,
            "failed": 0,
            "total_events": 3,
            "error_events": 0,
            "batches": 1,
        }
        mock_service.return_value.process_raw_event.assert_called_once_with(
            "raw-1", payload_json
        )
        assert mock_stats_instance.get_or_create_repository.call_args_list == [
            call("https://github.com/acme/repo-a.git"),
            call("https://github.com/acme/repo-b.git"),
        ]
        assert mock_stats_instance.get_or_create_contributor.call_args_list == [
            call(
                "Alice",
                "alice@example.com",
                contributor_uid="Alice <alice@example.com>",
            ),
            call(
                "Bob",
                "bob@example.com",
                contributor_uid="Bob <bob@example.com>",
            ),
        ]
        assert mock_stats_instance.ensure_repo_contributor_link.call_args_list == [
            call("repo-1", "contrib-1"),
            call("repo-2", "contrib-2"),
        ]
        mock_metrics_instance.mark_raw_extracted.assert_called_once_with(
            "raw-1", success=True
        )
