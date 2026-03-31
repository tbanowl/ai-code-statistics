from typing import Dict, Optional, Type
from core.scheduler.tasks.base import BaseTask
from core.config.logging import Logger

logging = Logger.get_logger("taskRegistry")


class TaskRegistry:
    """任务注册表，存储所有已注册的任务类"""

    _tasks: Dict[str, Type] = {}

    @classmethod
    def register(cls, task_class: Type) -> None:
        """注册一个任务类"""
        meta = task_class._schedule_meta
        job_id = meta["job_id"]

        if job_id in cls._tasks:
            raise ValueError(
                f"任务 ID 冲突: {job_id} (已存在 {cls._tasks[job_id].__name__})"
            )

        cls._tasks[job_id] = task_class

    @classmethod
    def get_all(cls) -> Dict[str, Type]:
        """获取所有已注册的任务"""
        return cls._tasks.copy()

    @classmethod
    def get(cls, job_id: str) -> Optional[Type]:
        """根据 job_id 获取任务类"""
        return cls._tasks.get(job_id)


def register_all() -> Dict[str, Type[BaseTask]]:
    """
    动态发现并注册所有带 @scheduled 装饰器的任务类

    Returns:
        已注册的任务字典 {job_id: TaskClass}
    """
    import importlib
    import pkgutil
    import core.scheduler.tasks as tasks_package

    # 遍历 tasks 目录下所有 Python 模块
    for _, module_name, _ in pkgutil.iter_modules(tasks_package.__path__):
        # 排除 __init__.py 和测试文件
        if (
            module_name
            and not module_name.startswith("_")
            and not module_name.startswith("test_")
        ):
            full_module_name = f"{tasks_package.__name__}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                # 查找模块中带 _schedule_meta 的任务类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and hasattr(attr, "_schedule_meta")
                        and attr is not BaseTask
                    ):
                        job_id = attr._schedule_meta.get("job_id")
                        existed = TaskRegistry.get(job_id) if job_id else None
                        if existed is None:
                            TaskRegistry.register(attr)
                        elif existed is not attr:
                            raise ValueError(
                                f"任务 ID 冲突: {job_id} (已存在 {existed.__name__})"
                            )
            except ImportError as e:
                logging.error(f"导入模块失败: {full_module_name} - {e}", exc_info=True)
                continue

    return TaskRegistry.get_all()
