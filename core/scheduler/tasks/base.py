from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional
from core.config.logging import Logger
from core.database.scheduler_db import SchedulerDatabase
import threading


class BaseTask(ABC):
    _schedule_meta = {}

    def __init__(self, config: Dict):
        self.config = config
        self.database = None
        self.scheduler_db = SchedulerDatabase()
        self.current_execution_id: Optional[str] = None
        self.logger = Logger.get_logger("baseTask")
        self.running = False

    def before_execute(self, context: Optional[Dict] = None) -> Dict:
        return {}

    @abstractmethod
    def execute(self, context: Optional[Dict] = None) -> Dict:
        pass

    def after_execute(self, result: Dict, context: Dict) -> None:
        pass

    def run(self, job_id: str, context: Optional[Dict] = None, async_mode: bool = False) -> Dict:
        started_at = int(datetime.now().timestamp() * 1000)
        self._check_running(job_id)
        try:
            self.scheduler_db.create_task_running(job_id, started_at)
        except Exception:
            return { "success": True, "error": "任务执行中"}
        
        execution_id = self.scheduler_db.create_task_execution(job_id, started_at)
        self.current_execution_id = execution_id
    
        try:
            if async_mode:
                def async_run():
                    self._run(job_id, started_at, execution_id, context)
                thread = threading.Thread(target=async_run, daemon=True)
                thread.start()
                return { "success": True }
            
            return self._run(job_id, started_at, execution_id, context)
        except Exception as e:
            self.logger.error(f"任务执行失败: {e}", exc_info=True)
            # 更新执行记录为失败状态
            return self._complete_task_execution(job_id, started_at, execution_id, str(e))

    
    def _run(self, job_id: str, started_at: int, execution_id: Optional[str] = None, context: Optional[Dict] = None)-> Dict:
        try:
            context = self.before_execute(context)
            result = self.execute(context)
            self.after_execute(result, context)

            # 更新执行记录
            self._complete_task_execution(job_id, started_at, execution_id, None)
            return result
        except Exception as e:
            self.logger.error(f"任务执行失败: {e}", exc_info=True)
            # 更新执行记录为失败状态
            return self._complete_task_execution(job_id, started_at, execution_id, str(e))
        finally:
            self.current_execution_id = None
        
    def _complete_task_execution(
        self,
        job_id: str,
        started_at: int,
        execution_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        finished_at = int(datetime.now().timestamp() * 1000)
        execution_time_ms = finished_at - started_at
        self.scheduler_db.complete_task_execution(
            job_id, finished_at, execution_time_ms, execution_id, error_message
        )

        return {"success": False if error_message else True, "error": error_message}


    def _check_running(self, job_id: str) -> bool:
        """
        检查任务是否正在运行 True-运行中 Flase-未运行
        """
        running = self.scheduler_db.get_running_task_execution(job_id)
        if not running:
            return False
        # 超时时间默认 1 小时
        timeout_minutes = self.config.get("scheduler", {})\
            .get("jobs", {})\
            .get(job_id, {})\
            .get("timeout_minutes", 60) * 60 * 1000
        started_at = running.get("started_at") or 0
        now_ms = int(datetime.now().timestamp() * 1000)
        if started_at and now_ms - started_at > timeout_minutes:
            error_msg = "存在过期执行记录，自动标记失败"
            self.logger.warning(
                f"任务 {job_id} {error_msg}: {running.get('id')}"
            )
            self.scheduler_db.update_task_execution_status(
                str(running.get("id")), "failed"
            )
            self._complete_task_execution(job_id, started_at, None, error_msg)
        else:
            self.logger.warning(f"任务 {job_id} 正在执行中，跳过触发")
        return True
