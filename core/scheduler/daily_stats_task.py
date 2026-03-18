"""日统计任务"""
from typing import Dict, Optional
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta
from core.services.metrics_aggregation_service import MetricsAggregationService


@scheduled(cron="0 2 * * *", job_id="daily_stats", name="日统计任务")
class DailyStatsTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context: Optional[Dict] = None) -> Dict:
        self.logger.info("开始执行日统计任务")
        service = MetricsAggregationService(self.database)
        return service.aggregate_daily_stats()
