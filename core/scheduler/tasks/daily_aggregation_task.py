"""每日统计聚合任务"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from core.scheduler.tasks.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.database import StatsDatabase
from core.utils.repo_url import normalize_repo_url


@scheduled(cron="0/1 * * * *", job_id="daily_aggregation", name="每日统计聚合")
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
        require_authorship_notes = self._require_authorship_notes(context)

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
                require_authorship_notes=require_authorship_notes,
            )
            self.logger.info(
                f"查询到 {len(committed_events)} 个 Committed 事件"
            )

            aggregated, latest_commits = self._aggregate_by_repo_contributor(
                committed_events
            )
            repo_ids: Dict[str, str] = {}

            for key, stats in aggregated.items():
                stat_date, repo_path, author_name, author_email = key

                repo_id = repo_ids.get(repo_path)
                if repo_id is None:
                    repo_id = stats_db.get_or_create_repository(repo_path)
                    repo_ids[repo_path] = repo_id
                stats_db.upsert_daily_stat(
                    stat_date, repo_id, author_name, author_email, stats
                )

            for repo_path, latest_commit in latest_commits.items():
                commit_sha = (latest_commit.get("commit_sha") or "").strip()
                if not commit_sha:
                    continue

                repo_id = repo_ids.get(repo_path)
                if repo_id is None:
                    repo_id = stats_db.get_or_create_repository(repo_path)
                    repo_ids[repo_path] = repo_id
                updated = stats_db.update_repository_last_daily_aggregation_commit_sha(
                    repo_id, commit_sha
                )
                if updated is False:
                    raise RuntimeError(
                        "Failed to update repository daily aggregation commit marker "
                        f"for repo_id={repo_id} commit_sha={commit_sha}"
                    )

            total_records += len(aggregated)
            cursor = cursor + timedelta(days=1)

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

    @staticmethod
    def _event_stat_date(event: Dict) -> int:
        raw_timestamp = event.get("timestamp")
        if raw_timestamp is None:
            return 0
        try:
            timestamp = int(raw_timestamp)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid committed event timestamp: {raw_timestamp!r}"
            ) from exc
        if timestamp <= 0:
            raise ValueError(
                f"Invalid committed event timestamp: {raw_timestamp!r}"
            )
        return int(datetime.fromtimestamp(timestamp / 1000).strftime("%Y%m%d"))

    def _aggregate_by_repo_contributor(
        self, committed_events: List[Dict]
    ) -> Tuple[Dict, Dict]:
        aggregated = {}
        latest_commits = {}

        for event in committed_events:
            stat_date = self._event_stat_date(event)
            repo_path = normalize_repo_url(event.get("repo_url"))
            author_name = event.get("author", "")
            author_email = event.get("author_email")
            key = (stat_date, repo_path, author_name, author_email)

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

            commit_sha = (event.get("commit_sha") or "").strip()
            timestamp = int(event.get("timestamp") or 0)
            if commit_sha:
                current = latest_commits.get(repo_path)
                if current is None or timestamp >= int(current.get("timestamp") or 0):
                    latest_commits[repo_path] = {
                        "commit_sha": commit_sha,
                        "timestamp": timestamp,
                    }

        return aggregated, latest_commits
