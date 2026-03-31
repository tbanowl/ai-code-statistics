"""每日统计聚合任务"""

from datetime import datetime, timedelta
from typing import Dict, List
from core.scheduler.tasks.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.database import StatsDatabase


@scheduled(cron="0 2 * * *", job_id="daily_aggregation", name="每日统计聚合")
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
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_start = yesterday.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            latest = stats_db.get_latest_stat_date()
            if not isinstance(latest, (int, float)) or latest <= 0:
                range_start = yesterday_start
            else:
                range_start = datetime.fromtimestamp(latest / 1000) + timedelta(days=1)
                range_start = range_start.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            range_end = yesterday_start
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

            self.logger.info(f"聚合时间范围: {day_start_ts} - {day_end_ts}")

            committed_events = stats_db.query_committed_events(
                day_start_ts,
                day_end_ts,
                repo_url=repo_url,
                author=contributor,
            )
            # checkpoint_events = stats_db.query_checkpoint_events(
            #     day_start_ts,
            #     day_end_ts,
            #     repo_url=repo_url,
            #     author=contributor,
            # )
            checkpoint_events = []

            self.logger.info(
                f"查询到 {len(committed_events)} 个 Committed 事件, {len(checkpoint_events)} 个 Checkpoint 事件"
            )

            aggregated = self._aggregate_by_repo_contributor(
                committed_events, checkpoint_events
            )

            for key, stats in aggregated.items():
                repo_path, author_name, author_email, author_uid = key

                repo_id = stats_db.get_or_create_repository(repo_path)
                contributor_id = stats_db.get_or_create_contributor(
                    author_name, author_email, contributor_uid=author_uid
                )
                stats_db.ensure_repo_contributor_link(repo_id, contributor_id)

                stats_db.upsert_daily_stat(day_start_ts, repo_id, contributor_id, stats)

            total_records += len(aggregated)
            cursor = cursor + timedelta(days=1)

        self.logger.info(f"聚合完成，共处理 {total_records} 条记录")
        return {"success": True, "records": total_records}

    def _aggregate_by_repo_contributor(
        self, committed_events: List[Dict], checkpoint_events: List[Dict]
    ) -> Dict:
        aggregated = {}

        for event in committed_events:
            repo_path = event.get("repo_url", "")
            author_name = event.get("author", "")
            author_email = event.get("author_email")
            author_uid = event.get("author_uid") or author_name
            key = (repo_path, author_name, author_email, author_uid)

            if key not in aggregated:
                aggregated[key] = {
                    "repo_name": StatsDatabase._extract_repo_name(repo_path),
                    "contributor_name": author_name or "unknown",
                    "ai_generated_lines": 0,
                    "ai_generated_lines_total": 0,
                    "ai_accepted_lines": 0,
                    "human_lines": 0,
                    "git_ai_version": None,
                }

            stats = aggregated[key]
            stats["ai_generated_lines_total"] += int(event.get("total_ai_additions_total", 0))
            stats["ai_generated_lines"] = stats["ai_generated_lines_total"]
            stats["ai_accepted_lines"] += int(event.get("ai_accepted_lines", 0))
            stats["human_lines"] += int(event.get("human_additions", 0))
            if event.get("git_ai_version"):
                stats["git_ai_version"] = event.get("git_ai_version")

        for event in checkpoint_events:
            repo_path = event.get("repo_url", "")
            author_name = event.get("author", "")
            author_uid = event.get("author_uid") or author_name
            matched = False
            for key in aggregated.keys():
                if (
                    key[0] == repo_path
                    and key[1] == author_name
                    and key[3] == author_uid
                ):
                    aggregated[key]["ai_generated_lines_total"] += int(
                        event.get("lines_added", 0)
                    )
                    aggregated[key]["ai_generated_lines"] += int(
                        event.get("lines_added_sloc", 0)
                    )
                    if event.get("git_ai_version") and not aggregated[key].get(
                        "git_ai_version"
                    ):
                        aggregated[key]["git_ai_version"] = event.get("git_ai_version")
                    matched = True

            if not matched:
                key = (repo_path, author_name, None, author_uid)
                aggregated[key] = {
                    "repo_name": StatsDatabase._extract_repo_name(repo_path),
                    "contributor_name": author_name or "unknown",
                    "ai_generated_lines": int(event.get("lines_added_sloc", 0)),
                    "ai_generated_lines_total": int(event.get("lines_added", 0)),
                    "ai_accepted_lines": 0,
                    "human_lines": 0,
                    "git_ai_version": event.get("git_ai_version"),
                }

        for stats in aggregated.values():
            total = int(stats.get("human_lines", 0)) + int(
                stats.get("ai_accepted_lines", 0)
            )
            stats["ai_percentage"] = (
                round((int(stats.get("ai_accepted_lines", 0)) / total) * 100, 2)
                if total > 0
                else 0
            )

        return aggregated
