from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional
from core.config.logging import Logger
from core.database.scheduler_db import SchedulerDatabase


class BaseTask(ABC):
    _schedule_meta = {}

    def __init__(self, config: Dict):
        self.config = config
        self.database = None
        self.scheduler_db = SchedulerDatabase()
        self.current_execution_id: Optional[str] = None
        self.logger = Logger.get_logger("baseTask")

    def before_execute(self) -> Dict:
        return {}

    @abstractmethod
    def execute(self, context: Optional[Dict] = None) -> Dict:
        pass

    def after_execute(self, result: Dict, context: Dict) -> None:
        pass

    def run(self, execution_id: Optional[str] = None) -> Dict:
        self.current_execution_id = execution_id
        start_time = datetime.now()

        try:
            context = self.before_execute()
            result = self.execute(context)
            self.after_execute(result, context)

            # 更新执行记录
            if execution_id:
                finished_at = datetime.now()
                execution_time_ms = int(
                    (finished_at - start_time).total_seconds() * 1000
                )
                self.scheduler_db.complete_task_execution(
                    execution_id, start_time, finished_at, execution_time_ms
                )

            return result
        except Exception as e:
            self.logger.error(f"任务执行失败: {e}", exc_info=True)

            # 更新执行记录为失败状态
            if execution_id:
                finished_at = datetime.now()
                execution_time_ms = int(
                    (finished_at - start_time).total_seconds() * 1000
                )
                self.scheduler_db.complete_task_execution(
                    execution_id, start_time, finished_at, execution_time_ms, str(e)
                )

            return {"success": False, "error": str(e)}
