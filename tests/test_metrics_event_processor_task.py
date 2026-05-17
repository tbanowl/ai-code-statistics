"""测试 MetricsEventProcessorTask"""
from unittest.mock import Mock, patch

from core.scheduler.tasks.metrics_event_processor_task import MetricsEventProcessorTask


def test_task_no_pending_records():
    """测试没有待处理记录时的执行"""
    # Mock 配置
    config = {
        'scheduler': {
            'jobs': {
                'metrics_event_processor': {
                    'batch_size': 100,
                    'timeout_minutes': 10
                }
            }
        }
    }

    # Patch the symbols imported directly by metrics_event_processor_task.py.
    with patch('core.scheduler.tasks.base.SchedulerDatabase'), \
         patch('core.scheduler.tasks.metrics_event_processor_task.MetricsDatabase') as mock_metrics_db, \
         patch('core.scheduler.tasks.metrics_event_processor_task.MetricsService'), \
         patch('core.scheduler.tasks.metrics_event_processor_task.StatsDatabase'):
        mock_metrics_instance = mock_metrics_db.return_value
        mock_metrics_instance.get_pending_raw_records.return_value = []
        mock_metrics_instance.reset_stuck_extracting_records.return_value = 0

        # 执行任务
        task = MetricsEventProcessorTask(config)
        result = task.execute()

        # 验证结果
        assert result['success'] is True
        assert result['processed'] == 0
        assert result['batches'] == 0
        mock_metrics_instance.get_pending_raw_records.assert_called_once_with(
            limit=100,
            last_id=None,
        )


def test_task_processes_pending_record_successfully():
    """测试有待处理 raw 记录时执行解析并标记成功"""
    config = {
        'scheduler': {
            'jobs': {
                'metrics_event_processor': {
                    'batch_size': 100,
                    'timeout_minutes': 10
                }
            }
        }
    }

    raw_payload = {
        "events": [
            {
                "e": 2,
                "a": {
                    "1": "https://example.com/repo.git",
                    "2": "Alice <alice@example.com>",
                },
            }
        ]
    }
    pending_record = {
        "id": "raw-1",
        "payload_json": __import__("json").dumps(raw_payload),
        "event_count": 1,
    }

    with patch('core.scheduler.tasks.base.SchedulerDatabase'), \
         patch('core.scheduler.tasks.metrics_event_processor_task.MetricsDatabase') as mock_metrics_db, \
         patch('core.scheduler.tasks.metrics_event_processor_task.MetricsService') as mock_service_cls, \
         patch('core.scheduler.tasks.metrics_event_processor_task.StatsDatabase') as mock_stats_db:
        mock_metrics_instance = mock_metrics_db.return_value
        mock_metrics_instance.get_pending_raw_records.side_effect = [
            [pending_record],
            [],
        ]
        mock_metrics_instance.mark_raw_extracting.return_value = True

        mock_service = mock_service_cls.return_value
        mock_service.process_raw_event.return_value = {
            "success": True,
            "events_processed": 1,
            "error_count": 0,
        }

        stats_db = mock_stats_db.return_value
        stats_db.get_or_create_repository.return_value = "repo-1"
        stats_db.get_or_create_contributor.return_value = "contributor-1"

        task = MetricsEventProcessorTask(config)
        result = task.execute()

        assert result['success'] is True
        assert result['processed'] == 1
        assert result['successful'] == 1
        assert result['failed'] == 0
        assert result['total_events'] == 1
        assert result['error_events'] == 0
        assert result['batches'] == 1

        mock_metrics_instance.mark_raw_extracting.assert_called_once_with("raw-1")
        mock_service.process_raw_event.assert_called_once_with(
            "raw-1",
            pending_record["payload_json"],
        )
        mock_metrics_instance.mark_raw_extracted.assert_called_once_with(
            "raw-1",
            success=True,
        )
        stats_db.ensure_repo_contributor_link.assert_called_once_with(
            "repo-1",
            "contributor-1",
        )


def test_task_syncs_repository_branch_from_metrics_events():
    """测试解析 metrics 成功后将仓库分支写入分支维度表"""
    config = {
        'scheduler': {
            'jobs': {
                'metrics_event_processor': {
                    'batch_size': 100,
                    'timeout_minutes': 10
                }
            }
        }
    }

    raw_payload = {
        "events": [
            {
                "e": 1,
                "a": {
                    "1": "https://example.com/repo.git",
                    "2": "Alice <alice@example.com>",
                    "5": "main",
                },
            },
            {
                "e": 4,
                "a": {
                    "1": "https://example.com/repo.git",
                    "2": "Alice <alice@example.com>",
                    "5": "main",
                },
            },
        ]
    }
    pending_record = {
        "id": "raw-branch-1",
        "payload_json": __import__("json").dumps(raw_payload),
        "event_count": 2,
    }

    with patch('core.scheduler.tasks.base.SchedulerDatabase'), \
         patch('core.scheduler.tasks.metrics_event_processor_task.MetricsDatabase') as mock_metrics_db, \
         patch('core.scheduler.tasks.metrics_event_processor_task.MetricsService') as mock_service_cls, \
         patch('core.scheduler.tasks.metrics_event_processor_task.StatsDatabase') as mock_stats_db:
        mock_metrics_instance = mock_metrics_db.return_value
        mock_metrics_instance.get_pending_raw_records.side_effect = [
            [pending_record],
            [],
        ]
        mock_metrics_instance.mark_raw_extracting.return_value = True

        mock_service = mock_service_cls.return_value
        mock_service.process_raw_event.return_value = {
            "success": True,
            "events_processed": 2,
            "error_count": 0,
        }

        stats_db = mock_stats_db.return_value
        stats_db.get_or_create_repository.return_value = "repo-1"
        stats_db.get_or_create_contributor.return_value = "contributor-1"

        task = MetricsEventProcessorTask(config)
        result = task.execute()

        assert result['success'] is True
        stats_db.ensure_repository_branch.assert_called_once_with("repo-1", "main")


def test_task_syncs_multiple_branches_for_same_repo_author():
    """测试相同仓库/作者的多个分支都写入分支维度表"""
    payload = {
        "events": [
            {
                "e": 1,
                "a": {
                    "1": "https://example.com/repo.git",
                    "2": "Alice <alice@example.com>",
                    "5": "main",
                },
            },
            {
                "e": 1,
                "a": {
                    "1": "https://example.com/repo.git",
                    "2": "Alice <alice@example.com>",
                    "5": "release",
                },
            },
        ]
    }
    stats_db = Mock()
    stats_db.get_or_create_repository.return_value = "repo-1"
    stats_db.get_or_create_contributor.return_value = "contributor-1"

    MetricsEventProcessorTask._sync_stats_dimensions(
        stats_db,
        __import__("json").dumps(payload),
    )

    assert stats_db.ensure_repository_branch.call_args_list == [
        __import__("unittest").mock.call("repo-1", "main"),
        __import__("unittest").mock.call("repo-1", "release"),
    ]
