"""仓库统计任务"""
from typing import Dict, Optional
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta
from core.services.metrics_aggregation_service import MetricsAggregationService


@scheduled(cron="0 5 * * *", job_id="repo_stats", name="仓库统计任务")
class RepoStatsTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context: Optional[Dict] = None) -> Dict:
        self.logger.info("开始执行仓库统计任务")
        service = MetricsAggregationService(self.database)
        return service.aggregate_repo_stats()
