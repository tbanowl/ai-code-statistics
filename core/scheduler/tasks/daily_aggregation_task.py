"""每日统计聚合任务"""

from typing import Dict

from core.database import StatsDatabase
from core.scheduler.scheduled import scheduled
from core.scheduler.tasks.base import BaseTask


@scheduled(cron="0/1 * * * *", job_id="daily_aggregation", name="每日统计聚合")
class DailyAggregationTask(BaseTask):
    """每日统计聚合任务 - 从 Metrics 事件表聚合生成每日统计数据"""

    def execute(self, context=None):
        self.logger.info("开始执行每日统计聚合任务")
        context = context or {}
        stats_db = StatsDatabase()
        stats_db.consolidate_unknown_repositories()

        repo_url = context.get("repo_url")
        require_authorship_notes = self._require_authorship_notes(context)
        repositories = stats_db.list_repositories_for_daily_aggregation(
            repo_url=repo_url
        )

        total_records = 0
        for repo in repositories:
            repo_id = repo["id"]
            repo_path = repo.get("repo_path", "")
            last_id = repo.get("last_daily_aggregation_id")
            affected = stats_db.find_daily_aggregation_affected_dates(
                repo_url=repo_path,
                last_aggregation_id=last_id,
                require_authorship_notes=require_authorship_notes,
            )
            commit_dates = affected.get("commit_dates") or []
            latest_id = affected.get("last_id")
            if not commit_dates:
                continue

            rows = stats_db.aggregate_committed_daily_stats(
                repo_url=repo_path,
                commit_dates=commit_dates,
                require_authorship_notes=require_authorship_notes,
            )
            for row in rows:
                stats_db.upsert_daily_stat(
                    row["stat_date"],
                    repo_id,
                    row["contributor_name"],
                    row["contributor_email"],
                    row,
                )
            if latest_id:
                updated = stats_db.update_repository_last_daily_aggregation_id(
                    repo_id, latest_id
                )
                if updated is False:
                    raise RuntimeError(
                        "Failed to update repository daily aggregation id marker "
                        f"for repo_id={repo_id} committed_id={latest_id}"
                    )
            total_records += len(rows)

        self.logger.info(f"聚合完成，共处理 {total_records} 条记录")
        return {"success": True, "records": total_records}

    def _require_authorship_notes(self, context: Dict) -> bool:
        if "require_authorship_notes" in context:
            return bool(context.get("require_authorship_notes"))

        config = getattr(self, "config", None) or {}
        job_config = (
            config.get("scheduler", {})
            .get("jobs", {})
            .get("daily_aggregation", {})
        )
        return bool(job_config.get("require_authorship_notes", False))
