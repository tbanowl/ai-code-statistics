import pytest
from core.scheduler.scheduled import scheduled
from core.scheduler.registry import TaskRegistry


def test_registry_register():
    @scheduled(cron="0 2 * * *", job_id="test_task")
    class TestTask:
        pass

    TaskRegistry.register(TestTask)

    assert TaskRegistry.get("test_task") is TestTask
    assert TestTask in TaskRegistry.get_all().values()


def test_registry_duplicate_id_raises_error():
    @scheduled(cron="0 2 * * *", job_id="duplicate_task")
    class Task1:
        pass

    @scheduled(cron="0 2 * * *", job_id="duplicate_task")
    class Task2:
        pass

    TaskRegistry.register(Task1)

    with pytest.raises(ValueError, match="任务 ID 冲突"):
        TaskRegistry.register(Task2)


def test_registry_get_nonexistent_returns_none():
    assert TaskRegistry.get("nonexistent") is None


def test_registry_get_all_returns_copy():
    @scheduled(cron="0 2 * * *", job_id="copy_test_task")
    class TestTask:
        pass

    TaskRegistry.register(TestTask)
    tasks = TaskRegistry.get_all()

    tasks.clear()

    assert TaskRegistry.get("copy_test_task") is TestTask
