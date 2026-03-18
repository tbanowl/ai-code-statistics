from typing import Dict, Optional, Type


class TaskRegistry:
    _tasks: Dict[str, Type] = {}

    @classmethod
    def register(cls, task_class: Type) -> None:
        meta = task_class._schedule_meta
        job_id = meta["job_id"]

        if job_id in cls._tasks:
            raise ValueError(
                f"任务 ID 冲突: {job_id} (已存在 {cls._tasks[job_id].__name__})"
            )

        cls._tasks[job_id] = task_class

    @classmethod
    def get_all(cls) -> Dict[str, Type]:
        return cls._tasks.copy()

    @classmethod
    def get(cls, job_id: str) -> Optional[Type]:
        return cls._tasks.get(job_id)
