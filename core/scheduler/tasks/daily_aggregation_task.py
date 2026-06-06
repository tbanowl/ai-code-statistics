"""每日统计聚合任务"""

from datetime import datetime, timedelta
from typing import Dict, List
from core.scheduler.tasks.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.database import StatsDatabase
from core.utils.repo_url import normalize_repo_url


@scheduled(cron="0 0 * * *", job_id="daily_aggregation", name="每日统计聚合")
class DailyAggregationTask(BaseTask):
    """每日统计聚合任务 - 从 Metrics 事件表聚合生成每日统计数据"""

    def execute(self, context=None):
        self.logger.info("开始执行每日统计聚合任务")
        context = context or {}

        stats_db = StatsDatabase()
        stats_db.consolidate_unknown_repositories()

        start_ts = context.get("start_date")
        end_ts = context.get("end_date")
        repo_url = context.get("repo_url")
        contributor = context.get("contributor")

        if start_ts is None or end_ts is None:
            today = datetime.now()
            today_start = today.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            # YYYYMMDD
            latest = stats_db.get_latest_stat_date()
            if not isinstance(latest, (int, float)) or latest <= 0:
                range_start = today_start
            else:
                latest = datetime.strptime(str(latest), "%Y%m%d")
                range_start = latest + timedelta(days=1)
                range_start = range_start.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            range_end = today_start
        else:
            range_start = datetime.fromtimestamp(start_ts / 1000).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            range_end = datetime.fromtimestamp(end_ts / 1000).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        if range_start > range_end:
            self.logger.info("统计数据已是最新，无需聚合")
            return {"success": True, "records": 0, "message": "already up to date"}

        total_records = 0
        cursor = range_start
        while cursor <= range_end:
            day_start_ts = int(cursor.timestamp() * 1000)
            day_end_ts = int(
                cursor.replace(
                    hour=23, minute=59, second=59, microsecond=999999
                ).timestamp()
                * 1000
            )
            stat_date = int(cursor.strftime("%Y%m%d"))

            self.logger.info(f"聚合时间范围: {day_start_ts} - {day_end_ts}")

            committed_events = stats_db.query_committed_events(
                day_start_ts,
                day_end_ts,
                repo_url=repo_url,
                author=contributor,
            )
            self.logger.info(
                f"查询到 {len(committed_events)} 个 Committed 事件"
            )

            aggregated = self._aggregate_by_repo_contributor(committed_events)

            for key, stats in aggregated.items():
                repo_path, author_name, author_email = key

                repo_id = stats_db.get_or_create_repository(repo_path)
                stats_db.upsert_daily_stat(
                    stat_date, repo_id, author_name, author_email, stats
                )

            total_records += len(aggregated)
            cursor = cursor + timedelta(days=1)

        self.logger.info(f"聚合完成，共处理 {total_records} 条记录")
        return {"success": True, "records": total_records}

    def _aggregate_by_repo_contributor(self, committed_events: List[Dict]) -> Dict:
        aggregated = {}

        for event in committed_events:
            repo_path = normalize_repo_url(event.get("repo_url"))
            author_name = event.get("author", "")
            author_email = event.get("author_email")
            key = (repo_path, author_name, author_email)

            if key not in aggregated:
                aggregated[key] = {
                    "repo_name": StatsDatabase._extract_repo_name(repo_path),
                    "contributor_name": author_name or "unknown",
                    "contributor_email": author_email,
                    "ai_lines": 0,
                    "ai_total_lines": 0,
                    "ai_accepted_lines": 0,
                    "human_lines": 0,
                    "total_lines": 0,
                }

            stats = aggregated[key]
            stats["ai_total_lines"] += int(event.get("total_ai_additions_total", 0))
            stats["ai_lines"] += int(event.get("ai_additions", 0))
            stats["ai_accepted_lines"] += int(event.get("ai_accepted_lines", 0))
            stats["human_lines"] += int(event.get("human_additions", 0))
            stats["total_lines"] += int(event.get("git_diff_added_lines", 0))

        return aggregated
