from abc import ABC, abstractmethod
from typing import Dict, Optional
from core.config.logging import Logger
from core.database.factory import create_database


class BaseTask(ABC):
    def __init__(self, config: Dict):
        self.config = config
        self.database = create_database(config.get("database", {}))
        job_id = self._schedule_meta.get("job_id", "unknown")
        self.logger = Logger.get_logger(f"task.{job_id}")

    def before_execute(self) -> Dict:
        return {}

    @abstractmethod
    def execute(self, context: Optional[Dict] = None) -> Dict:
        pass

    def after_execute(self, result: Dict, context: Dict) -> None:
        pass

    def run(self) -> Dict:
        try:
            context = self.before_execute()
            result = self.execute(context)
            self.after_execute(result, context)
            return result
        except Exception as e:
            self.logger.error(f"任务执行失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
