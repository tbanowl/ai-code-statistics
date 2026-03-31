import pytest
from abc import ABC, abstractmethod
from typing import Dict, Optional
from unittest.mock import MagicMock, patch
from core.scheduler.tasks.base import BaseTask
from core.scheduler.scheduled import scheduled


def test_base_task_is_abstract():
    @scheduled(cron="0 2 * * *", job_id="abstract_task")
    class AbstractTask(BaseTask):
        pass

    config = {}
    instantiate = AbstractTask.__call__
    with pytest.raises(TypeError, match="abstract"):
        instantiate(config)


def test_base_task_initialization():
    @scheduled(cron="0 2 * * *", job_id="init_task")
    class ConcreteTask(BaseTask):
        def execute(self, context: Optional[Dict] = None) -> Dict:
            return {"success": True}

    config = {"database": {}}

    task = ConcreteTask(config)
    assert task.config is config
    assert task.database is None
    assert task.logger is not None


def test_base_task_hooks_execution_order():
    call_log = []

    @scheduled(cron="0 2 * * *", job_id="hook_task")
    class HookTask(BaseTask):
        def before_execute(self) -> Dict:
            call_log.append("before")
            return {"context_data": True}

        def execute(self, context: Optional[Dict] = None) -> Dict:
            call_log.append("execute")
            assert context is not None
            return {"success": True, "result": "done"}

        def after_execute(self, result: Dict, context: Dict) -> None:
            call_log.append("after")

    config = {}

    with patch("core.config.logging.Logger.get_logger", return_value=MagicMock()):
        task = HookTask(config)
        result = task.run()

    assert call_log == ["before", "execute", "after"]
    assert result["success"] is True


def test_base_task_run_catches_exception():
    @scheduled(cron="0 2 * * *", job_id="error_task")
    class ErrorTask(BaseTask):
        def execute(self, context: Optional[Dict] = None) -> Dict:
            raise ValueError("Something went wrong")

    config = {}
    mock_logger = MagicMock()

    with patch("core.config.logging.Logger.get_logger", return_value=mock_logger):
        task = ErrorTask(config)
        result = task.run()

    assert result["success"] is False
    assert "Something went wrong" in result["error"]
    mock_logger.error.assert_called_once()
