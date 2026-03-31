import pytest
from typing import Dict, Optional
from core.scheduler.scheduled import scheduled


def test_scheduled_decorator_stores_meta():
    """验证装饰器正确存储调度元数据"""

    @scheduled(cron="0 2 * * *", job_id="test_task", name="测试任务", enabled=True)
    class TestTask:
        pass

    assert hasattr(TestTask, "_schedule_meta")
    assert TestTask._schedule_meta["cron"] == "0 2 * * *"
    assert TestTask._schedule_meta["job_id"] == "test_task"
    assert TestTask._schedule_meta["name"] == "测试任务"
    assert TestTask._schedule_meta["enabled"] is True


def test_scheduled_decorator_default_name():
    """验证默认 name 使用类名"""

    @scheduled(cron="0 2 * * *", job_id="test_task")
    class MyTaskClass:
        pass

    assert MyTaskClass._schedule_meta["name"] == "MyTaskClass"


def test_scheduled_decorator_default_enabled():
    """验证默认 enabled 为 True"""

    @scheduled(cron="0 2 * * *", job_id="test_task")
    class MyTaskClass:
        pass

    assert MyTaskClass._schedule_meta["enabled"] is True


def test_scheduled_decorator_false_enabled():
    """验证可以设置 enabled 为 False"""

    @scheduled(cron="0 2 * * *", job_id="test_task", enabled=False)
    class MyTaskClass:
        pass

    assert MyTaskClass._schedule_meta["enabled"] is False
