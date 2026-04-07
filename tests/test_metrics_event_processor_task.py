"""测试 MetricsEventProcessorTask"""
import pytest
from unittest.mock import patch, MagicMock
from core.scheduler.tasks.metrics_event_processor_task import MetricsEventProcessorTask
from core.config import load_config


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

    # Mock 数据库
    with patch('core.database.SchedulerDatabase') as mock_scheduler_db, \
         patch('core.database.MetricsDatabase') as mock_metrics_db:
        mock_scheduler_instance = mock_scheduler_db.return_value
        mock_scheduler_instance.has_running_task.return_value = None
        mock_scheduler_instance.get_running_task_execution.return_value = None
        mock_scheduler_instance.update_task_execution_status.return_value = None

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
        mock_scheduler_instance.has_running_task.assert_called_once_with("metrics_event_processor", 10)


def test_task_skipped_when_running():
    """测试有运行中任务时跳过执行"""
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

    with patch('core.database.SchedulerDatabase') as mock_scheduler_db:
        mock_scheduler_instance = mock_scheduler_db.return_value
        mock_scheduler_instance.has_running_task.return_value = {
            'id': 'exec1',
            'status': 'running'
        }

        task = MetricsEventProcessorTask(config)
        result = task.execute()

        assert result['success'] is True
        assert result['skipped'] is True
        assert result['skip_reason'] == 'running_task'
