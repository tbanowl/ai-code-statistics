from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime
from typing import Dict, Optional, Any
from core.config.logging import Logger
from core.scheduler.registry import register_all
from core.scheduler.tasks.base import BaseTask
from core.database import SchedulerDatabase


# 模块级变量，用于存储调度器实例（供任务执行函数使用）
_scheduler_instance: Optional['AICodeScheduler'] = None


def _run_task_with_execution(job_id: str):
    """
    模块级任务执行函数，可被 JobStore 序列化

    Args:
        job_id: 任务 ID
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        return

    task_instance = _scheduler_instance.task_instances.get(job_id)
    if task_instance is None:
        _scheduler_instance.logger.warning(f"任务实例不存在: {job_id}")
        return

    execution_id = _scheduler_instance.scheduler_db.create_task_execution(job_id)
    task_instance.run(execution_id=execution_id)


class AICodeScheduler:
    def __init__(self, config: Dict):
        global _scheduler_instance
        _scheduler_instance = self

        self.config = config
        self.task_instances: Dict[str, BaseTask] = {}
        self.scheduler_db = SchedulerDatabase()
        self.is_running = False
        self.logger = Logger.get_logger("scheduler")

        # 配置 JobStore
        jobstores = self._setup_jobstore()
        # 配置默认任务行为
        job_defaults = self._setup_job_defaults()
        # 获取时区配置
        timezone = config.get('scheduler', {}).get('timezone', 'Asia/Shanghai')

        self.scheduler: BackgroundScheduler = BackgroundScheduler(
            jobstores=jobstores,
            job_defaults=job_defaults,
            timezone=timezone
        )

    def _setup_jobstore(self) -> Dict[str, Any]:
        """
        配置并初始化 SQLAlchemy JobStore

        Returns:
            包含 default JobStore 的字典，如果初始化失败则返回空字典
        """
        # 检查是否启用 JobStore 持久化
        jobstore_config = self.config.get('scheduler', {}).get('jobstore')
        if not jobstore_config:
            self.logger.info("未配置 JobStore，使用内存模式")
            return {}

        jobstore_type = jobstore_config.get('type', 'sqlalchemy')
        if jobstore_type != 'sqlalchemy':
            self.logger.warning(f"不支持的 JobStore 类型: {jobstore_type}，使用内存模式")
            return {}

        try:
            engine = self._get_engine_from_db()
            jobstores = {
                'default': SQLAlchemyJobStore(engine=engine)
            }
            self.logger.info("JobStore 持久化已启用（SQLAlchemy）")
            return jobstores
        except Exception as e:
            self.logger.error(f"JobStore 初始化失败，使用内存模式: {e}", exc_info=True)
            return {}

    def _get_engine_from_db(self):
        """
        从现有 Database 实例获取 SQLAlchemy engine

        Returns:
            SQLAlchemy Engine 实例
        """
        # 首先尝试从 SchedulerDatabase 获取
        if hasattr(self, 'scheduler_db') and self.scheduler_db:
            return self.scheduler_db.engine
        # 备用：创建新的 BaseDatabase 实例获取 engine
        from core.database.base import BaseDatabase
        db = BaseDatabase()
        return db.engine

    def _setup_job_defaults(self) -> Dict[str, Any]:
        """
        配置任务的默认行为

        Returns:
            包含任务默认配置的字典
        """
        defaults = self.config.get('scheduler', {}).get('job_defaults', {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300
        })
        return defaults

    def start(self) -> None:
        if not self.is_running:
            self.scheduler.start()
            self._register_tasks()
            self.is_running = True
            self.logger.info("调度器已启动")
        else:
            self.logger.warning("调度器已在运行中")

    def _register_tasks(self) -> None:

        task_classes = register_all()

        for job_id, task_class in task_classes.items():
            if not issubclass(task_class, BaseTask):
                continue

            annotation_meta = task_class._schedule_meta.copy()

            job_overrides = (
                self.config.get("scheduler", {}).get("jobs", {}).get(job_id, {})
            )

            cron = job_overrides.get("cron", annotation_meta["cron"])
            name = annotation_meta["name"]
            enabled = job_overrides.get("enabled", annotation_meta["enabled"])

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
                func=_run_task_with_execution,
                args=[job_id],
                trigger=CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                ),
                id=job_id,
                name=name,
                replace_existing=True,  # 覆盖已存在的任务
            )

            self.logger.info(f"注册任务: {name} ({job_id}) at {cron}")

    # 删除原有的实例方法，已移动到模块级函数

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

    def trigger_job_with_execution(
        self, job_id: str, context: Optional[Dict] = None
    ) -> Optional[str]:
        """手动触发任务并创建执行记录，返回 execution_id"""
        # 检查任务是否存在
        job = self.scheduler.get_job(job_id)
        if not job:
            self.logger.warning(f"进程中任务不存在: {job_id}")
            return None

        # 检查是否有正在运行的任务
        running = self.scheduler_db.get_running_task_execution(job_id)
        if running:
            timeout_minutes = self.config.get("scheduler", {})\
                .get("jobs", {})\
                .get("metrics_event_processor", {})\
                .get("timeout_minutes", 10) * 60 * 1000
            created_at = running.get("created_at") or 0
            now_ms = int(datetime.now().timestamp() * 1000)
            if created_at and now_ms - created_at > timeout_minutes:
                self.logger.warning(
                    f"任务 {job_id} 存在过期执行记录，自动标记失败: {running.get('id')}"
                )
                self.scheduler_db.update_task_execution_status(
                    str(running.get("id")), "failed"
                )
            else:
                self.logger.warning(f"任务 {job_id} 正在执行中，跳过触发")
                return None

        # 获取任务实例
        task_instance = self.task_instances.get(job_id)
        if task_instance is None:
            self.logger.warning(f"任务不存在: {job_id}")
            return

        execution_id = self.scheduler_db.create_task_execution(job_id)
        self.logger.info(f"创建任务执行记录: {job_id} -> execution_id={execution_id}")
        original_before_execute = task_instance.before_execute
        task_instance.before_execute = lambda: context or {}
        try:
            task_instance.run(execution_id=execution_id)
            self.logger.info(f"已触发任务: {job_id}")
        except Exception as e:
            self.logger.info("任务执行失败: {job_id}", e)
        finally:
            task_instance.before_execute = original_before_execute

        return execution_id
