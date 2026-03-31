import pytest
from unittest.mock import MagicMock, patch
from core.scheduler.scheduled import scheduled
from core.scheduler.registry import TaskRegistry
from core.scheduler.tasks.base import BaseTask
from core.scheduler.scheduler import AICodeScheduler
from typing import Dict, Optional


@pytest.fixture
def mock_config():
    return {
        "scheduler": {
            "enabled": True,
            "timezone": "Asia/Shanghai",
            "jobs": {"sched_test_task": {"cron": "0 10 * * *", "enabled": True}},
        },
        "database": {},
    }


def test_scheduler_registers_tasks_from_registry(mock_config):
    TaskRegistry._tasks.clear()

    @scheduled(
        cron="0 2 * * *", job_id="sched_test_task", name="测试任务", enabled=True
    )
    class SampleTask(BaseTask):
        def execute(self, context: Optional[Dict] = None) -> Dict:
            return {"success": True, "processed": 10}

    TaskRegistry.register(SampleTask)

    with patch("core.config.logging.Logger.get_logger"):
        scheduler = AICodeScheduler(mock_config)
        scheduler.start()

        assert "sched_test_task" in scheduler.task_instances
        assert isinstance(scheduler.task_instances["sched_test_task"], SampleTask)

        job_status = scheduler.get_job_status("sched_test_task")
        assert job_status is not None
        assert "hour='10'" in job_status["trigger"]
        assert "minute='0'" in job_status["trigger"]


def test_scheduler_respects_disabled_tasks(mock_config):
    TaskRegistry._tasks.clear()

    @scheduled(
        cron="0 2 * * *", job_id="disabled_test_task", name="禁用任务", enabled=True
    )
    class DisabledTask(BaseTask):
        def execute(self, context: Optional[Dict] = None) -> Dict:
            return {"success": True}

    TaskRegistry.register(DisabledTask)

    mock_config["scheduler"]["jobs"] = {"disabled_test_task": {"enabled": False}}

    with patch("core.config.logging.Logger.get_logger"):
        scheduler = AICodeScheduler(mock_config)
        scheduler.start()

        assert "disabled_test_task" not in scheduler.task_instances
