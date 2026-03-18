import pytest
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta
from core.scheduler.registry import TaskRegistry


def test_meta_auto_registers_scheduled_class():
    initial_count = len(TaskRegistry.get_all())

    @scheduled(cron="0 2 * * *", job_id="auto_task")
    class AutoTask(metaclass=TaskMeta):
        pass

    assert TaskRegistry.get("auto_task") is AutoTask
    assert len(TaskRegistry.get_all()) == initial_count + 1


def test_meta_does_not_register_non_scheduled_class():
    initial_count = len(TaskRegistry.get_all())

    class NoMetaTask(metaclass=TaskMeta):
        pass

    assert TaskRegistry.get("no_meta_task") is None
    assert len(TaskRegistry.get_all()) == initial_count


def test_meta_raises_on_duplicate_id():
    @scheduled(cron="0 2 * * *", job_id="dup_id")
    class Task1(metaclass=TaskMeta):
        pass

    with pytest.raises(ValueError, match="任务 ID 冲突"):

        @scheduled(cron="0 3 * * *", job_id="dup_id")
        class Task2(metaclass=TaskMeta):
            pass
