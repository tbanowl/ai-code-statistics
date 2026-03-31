from core.scheduler.tasks.base import BaseTask
from core.scheduler.scheduled import scheduled


@scheduled(cron="0 3 * * *", job_id="task_cleanup", name="任务执行记录清理")
class TaskCleanupTask(BaseTask):
    def execute(self, context=None):
        """清理旧的任务执行记录"""
        self.logger.info('开始清理任务执行记录')

        # 保留最近 100 条记录
        deleted_count = self.scheduler_db.cleanup_old_task_executions(keep_count=100)

        self.logger.info(f'清理完成，删除了 {deleted_count} 条记录')

        return {
            'success': True,
            'deleted_count': deleted_count
        }
