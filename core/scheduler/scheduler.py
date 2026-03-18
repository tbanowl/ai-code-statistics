from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Dict, Optional
from core.config.logging import Logger
from core.scheduler.registry import TaskRegistry
from core.scheduler.base import BaseTask


class AICodeScheduler:
    def __init__(self, config: Dict):
        self.scheduler = BackgroundScheduler()
        self.config = config
        self.task_instances: Dict[str, BaseTask] = {}
        self.is_running = False
        self.logger = Logger.get_logger("scheduler")

    def start(self) -> None:
        if not self.is_running:
            self.scheduler.start()
            self._register_tasks()
            self.is_running = True
            self.logger.info("调度器已启动")
        else:
            self.logger.warning("调度器已在运行中")

    def _register_tasks(self) -> None:
        jobs_config = self.config.get("scheduler", {}).get("jobs", {})
        task_classes = TaskRegistry.get_all()

        for job_id, task_class in task_classes.items():
            if not issubclass(task_class, BaseTask):
                continue

            annotation_meta = task_class._schedule_meta.copy()

            job_config = jobs_config.get(job_id, {})
            cron = job_config.get("cron", annotation_meta["cron"])
            name = job_config.get("name", annotation_meta["name"])
            enabled = job_config.get("enabled", annotation_meta["enabled"])

            if not enabled:
                self.logger.info(f"任务已禁用: {name} ({job_id})")
                continue

            try:
                minute, hour, day, month, day_of_week = cron.split()
            except ValueError:
                self.logger.error(f"任务 {name} ({job_id}) 的 cron 表达式无效: {cron}")
                continue

            try:
                task_instance = task_class(self.config)
            except TypeError as e:
                if "abstract" in str(e).lower():
                    self.logger.debug(f"跳过抽象任务: {name} ({job_id})")
                    continue
                raise

            self.task_instances[job_id] = task_instance

            self.scheduler.add_job(
                func=task_instance.run,
                trigger=CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                ),
                id=job_id,
                name=name,
            )

            self.logger.info(f"已注册任务: {name} ({job_id}) at {cron}")

    def stop(self) -> None:
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            self.logger.info("调度器已停止")

    def remove_job(self, job_id: str) -> bool:
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.task_instances:
                del self.task_instances[job_id]
            return True
        except Exception:
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        job = self.scheduler.get_job(job_id)
        if job:
            return {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time,
                "trigger": str(job.trigger),
            }
        return None

    def get_all_jobs(self) -> list:
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time,
                "trigger": str(job.trigger),
            }
            for job in self.scheduler.get_jobs()
        ]
