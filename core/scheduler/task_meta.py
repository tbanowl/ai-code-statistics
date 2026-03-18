from abc import ABCMeta
from core.scheduler.registry import TaskRegistry


class TaskMeta(ABCMeta):
    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)

        if hasattr(new_class, "_schedule_meta"):
            TaskRegistry.register(new_class)

        return new_class
