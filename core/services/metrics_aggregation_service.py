"""Metrics 聚合服务"""
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from core.config.logging import Logger
from core.database.base import Database
from core.models.metrics import (
    MetricsDailyStat, MetricsWeeklyStat, MetricsMonthlyStat,
    MetricsRepoStat, MetricsContributorStat
)


class MetricsAggregationService:
    """Metrics 聚合服务"""

    def __init__(self, database: Database):
        self.database = database
        self.logger = Logger.get_logger('services.metrics_aggregation')

    def aggregate_daily_stats(self, force_full: bool = False) -> Dict:
        """聚合日统计"""
        try:
            self.logger.info("开始日统计聚合")
            start_time = datetime.now()

            # 智能检测
            is_first_run = self._is_first_run('daily') or force_full

            if is_first_run:
                self.logger.info("首次运行,执行全量聚合")
                result = self._aggregate_daily_full()
            else:
                self.logger.info("增量聚合")
                result = self._aggregate_daily_incremental()

            duration = (datetime.now() - start_time).total_seconds()
            result['duration'] = duration
            self.logger.info(f"日统计聚合完成,耗时 {duration:.2f}s")
            return result

        except Exception as e:
            self.logger.error(f"日统计聚合失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def aggregate_weekly_stats(self, force_full: bool = False) -> Dict:
        """聚合周统计"""
        try:
            self.logger.info("开始周统计聚合")
            start_time = datetime.now()

            is_first_run = self._is_first_run('weekly') or force_full

            if is_first_run:
                result = self._aggregate_weekly_full()
            else:
                result = self._aggregate_weekly_incremental()

            duration = (datetime.now() - start_time).total_seconds()
            result['duration'] = duration
            return result

        except Exception as e:
            self.logger.error(f"周统计聚合失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def aggregate_monthly_stats(self, force_full: bool = False) -> Dict:
        """聚合月统计"""
        try:
            self.logger.info("开始月统计聚合")
            start_time = datetime.now()

            is_first_run = self._is_first_run('monthly') or force_full

            if is_first_run:
                result = self._aggregate_monthly_full()
            else:
                result = self._aggregate_monthly_incremental()

            duration = (datetime.now() - start_time).total_seconds()
            result['duration'] = duration
            return result

        except Exception as e:
            self.logger.error(f"月统计聚合失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def aggregate_repo_stats(self) -> Dict:
        """聚合仓库统计"""
        try:
            self.logger.info("开始仓库统计聚合")
            start_time = datetime.now()

            repo_urls = self.database.get_all_repo_urls()
            success_count = 0
            failed_items = []

            for repo_url in repo_urls:
                try:
                    self._aggregate_single_repo(repo_url)
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"仓库 {repo_url} 聚合失败: {e}")
                    failed_items.append(repo_url)

            duration = (datetime.now() - start_time).total_seconds()
            return {
                "success": len(failed_items) == 0,
                "processed": success_count,
                "failed": len(failed_items),
                "duration": duration,
                "details": {"failed_items": failed_items}
            }

        except Exception as e:
            self.logger.error(f"仓库统计聚合失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def aggregate_contributor_stats(self) -> Dict:
        """聚合贡献者统计"""
        try:
            self.logger.info("开始贡献者统计聚合")
            start_time = datetime.now()

            authors = self.database.get_all_authors()
            success_count = 0
            failed_items = []

            for author in authors:
                try:
                    self._aggregate_single_contributor(author)
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"贡献者 {author} 聚合失败: {e}")
                    failed_items.append(author)

            duration = (datetime.now() - start_time).total_seconds()
            return {
                "success": len(failed_items) == 0,
                "processed": success_count,
                "failed": len(failed_items),
                "duration": duration,
                "details": {"failed_items": failed_items}
            }

        except Exception as e:
            self.logger.error(f"贡献者统计聚合失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ========== 内部方法 ==========

    def _is_first_run(self, stat_type: str) -> bool:
        """检查是否首次运行"""
        if stat_type == 'daily':
            return self.database.get_latest_daily_stat() is None
        elif stat_type == 'weekly':
            return self.database.get_latest_weekly_stat() is None
        elif stat_type == 'monthly':
            return self.database.get_latest_monthly_stat() is None
        return False

    def _calculate_metrics(self, events: List[Dict]) -> Dict:
        """计算统计指标"""
        total_lines = 0
        ai_lines = 0
        total_commits = set()
        commits_with_ai = set()
        tool_model_breakdown = {}

        for event in events:
            human_additions = event.get('human_additions') or 0
            ai_additions_json = event.get('ai_additions') or '[]'

            try:
                ai_additions_array = json.loads(ai_additions_json)
                ai_additions = sum(ai_additions_array) if isinstance(ai_additions_array, list) else 0
            except:
                ai_additions = 0

            total_lines += human_additions + ai_additions
            ai_lines += ai_additions

            commit_sha = event.get('commit_sha')
            if commit_sha:
                total_commits.add(commit_sha)
                if ai_additions > 0:
                    commits_with_ai.add(commit_sha)

            # 工具模型分布
            if ai_additions > 0:
                tool = event.get('tool')
                model = event.get('model')
                if tool and model:
                    key = f"{tool}/{model}"
                    tool_model_breakdown[key] = tool_model_breakdown.get(key, 0) + ai_additions

        return {
            'total_lines': total_lines,
            'ai_lines': ai_lines,
            'ai_percentage': round(ai_lines / total_lines * 100, 2) if total_lines > 0 else 0,
            'total_commits': len(total_commits),
            'commits_with_ai': len(commits_with_ai),
            'tool_model_breakdown': json.dumps(tool_model_breakdown)
        }

    def _extract_repo_id(self, repo_url: str) -> str:
        """从 URL 提取仓库 ID"""
        if not repo_url:
            return ""
        parts = repo_url.replace("https://", "").replace("http://", "").split("/")
        if len(parts) >= 3:
            return f"{parts[-2]}/{parts[-1]}"
        return repo_url

    def _aggregate_daily_full(self) -> Dict:
        """日统计全量聚合"""
        with self.database._get_connection() as conn:
            conn.row_factory = None
            cursor = conn.execute(
                'SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM metrics_events_committed'
            )
            row = cursor.fetchone()
            if not row or not row[0]:
                return {"success": True, "processed": 0, "failed": 0, "message": "无数据"}

            min_ts, max_ts = row[0], row[1]
            start_date = datetime.fromtimestamp(min_ts / 1000)
            end_date = datetime.fromtimestamp(max_ts / 1000)

        return self._aggregate_daily_range(start_date, end_date)

    def _aggregate_daily_incremental(self) -> Dict:
        """日统计增量聚合"""
        latest = self.database.get_latest_daily_stat()
        if not latest:
            return self._aggregate_daily_full()

        start_date = datetime.fromtimestamp(latest.date_ts / 1000) + timedelta(days=1)
        end_date = datetime.now()

        return self._aggregate_daily_range(start_date, end_date)

    def _aggregate_daily_range(self, start_date: datetime, end_date: datetime) -> Dict:
        """聚合指定日期范围的日统计"""
        success_count = 0
        failed_items = []

        current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

        while current_date <= end_date:
            try:
                date_str = current_date.strftime('%Y-%m-%d')
                date_ts = int(current_date.timestamp() * 1000)
                next_date_ts = int((current_date + timedelta(days=1)).timestamp() * 1000)

                events = self.database.get_committed_events_by_date_range(date_ts, next_date_ts)

                if events:
                    metrics = self._calculate_metrics(events)
                    stat = MetricsDailyStat(
                        date=date_str,
                        date_ts=date_ts,
                        total_lines=metrics['total_lines'],
                        ai_lines=metrics['ai_lines'],
                        ai_percentage=metrics['ai_percentage'],
                        total_commits=metrics['total_commits'],
                        commits_with_ai=metrics['commits_with_ai'],
                        tool_model_breakdown=metrics['tool_model_breakdown'],
                        start_date=date_ts,
                        end_date=next_date_ts - 1,
                        created_at=int(datetime.now().timestamp() * 1000),
                        updated_at=int(datetime.now().timestamp() * 1000)
                    )
                    self.database.save_metrics_daily_stat(stat)
                    success_count += 1

                current_date += timedelta(days=1)

            except Exception as e:
                self.logger.error(f"日期 {date_str} 聚合失败: {e}")
                failed_items.append(date_str)
                current_date += timedelta(days=1)

        return {
            "success": len(failed_items) == 0,
            "processed": success_count,
            "failed": len(failed_items),
            "details": {"failed_items": failed_items}
        }

    def _aggregate_weekly_full(self) -> Dict:
        """周统计全量聚合"""
        with self.database._get_connection() as conn:
            conn.row_factory = None
            cursor = conn.execute(
                'SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM metrics_events_committed'
            )
            row = cursor.fetchone()
            if not row or not row[0]:
                return {"success": True, "processed": 0, "failed": 0, "message": "无数据"}

            min_ts, max_ts = row[0], row[1]
            start_date = datetime.fromtimestamp(min_ts / 1000)
            end_date = datetime.fromtimestamp(max_ts / 1000)

        return self._aggregate_weekly_range(start_date, end_date)

    def _aggregate_weekly_incremental(self) -> Dict:
        """周统计增量聚合"""
        latest = self.database.get_latest_weekly_stat()
        if not latest:
            return self._aggregate_weekly_full()

        start_date = datetime.fromtimestamp(latest.week_start_ts / 1000) + timedelta(weeks=1)
        end_date = datetime.now()

        return self._aggregate_weekly_range(start_date, end_date)

    def _aggregate_weekly_range(self, start_date: datetime, end_date: datetime) -> Dict:
        """聚合指定日期范围的周统计"""
        success_count = 0
        failed_items = []

        # 找到起始周的周一
        current_date = start_date - timedelta(days=start_date.weekday())
        current_date = current_date.replace(hour=0, minute=0, second=0, microsecond=0)

        while current_date <= end_date:
            try:
                week_start = current_date
                week_end = current_date + timedelta(days=6, hours=23, minutes=59, seconds=59)

                year, week, _ = week_start.isocalendar()
                week_start_ts = int(week_start.timestamp() * 1000)
                week_end_ts = int(week_end.timestamp() * 1000)

                events = self.database.get_committed_events_by_date_range(week_start_ts, week_end_ts + 1)

                if events:
                    metrics = self._calculate_metrics(events)
                    stat = MetricsWeeklyStat(
                        year=year,
                        week=week,
                        week_start=week_start.strftime('%Y-%m-%d'),
                        week_start_ts=week_start_ts,
                        week_end=week_end.strftime('%Y-%m-%d'),
                        week_end_ts=week_end_ts,
                        total_lines=metrics['total_lines'],
                        ai_lines=metrics['ai_lines'],
                        ai_percentage=metrics['ai_percentage'],
                        total_commits=metrics['total_commits'],
                        commits_with_ai=metrics['commits_with_ai'],
                        tool_model_breakdown=metrics['tool_model_breakdown'],
                        created_at=int(datetime.now().timestamp() * 1000),
                        updated_at=int(datetime.now().timestamp() * 1000)
                    )
                    self.database.save_metrics_weekly_stat(stat)
                    success_count += 1

                current_date += timedelta(weeks=1)

            except Exception as e:
                self.logger.error(f"周 {year}-W{week} 聚合失败: {e}")
                failed_items.append(f"{year}-W{week}")
                current_date += timedelta(weeks=1)

        return {
            "success": len(failed_items) == 0,
            "processed": success_count,
            "failed": len(failed_items),
            "details": {"failed_items": failed_items}
        }

    def _aggregate_monthly_full(self) -> Dict:
        """月统计全量聚合"""
        with self.database._get_connection() as conn:
            conn.row_factory = None
            cursor = conn.execute(
                'SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM metrics_events_committed'
            )
            row = cursor.fetchone()
            if not row or not row[0]:
                return {"success": True, "processed": 0, "failed": 0, "message": "无数据"}

            min_ts, max_ts = row[0], row[1]
            start_date = datetime.fromtimestamp(min_ts / 1000)
            end_date = datetime.fromtimestamp(max_ts / 1000)

        return self._aggregate_monthly_range(start_date, end_date)

    def _aggregate_monthly_incremental(self) -> Dict:
        """月统计增量聚合"""
        latest = self.database.get_latest_monthly_stat()
        if not latest:
            return self._aggregate_monthly_full()

        start_date = datetime.fromtimestamp(latest.month_start_ts / 1000)
        # 下个月
        if start_date.month == 12:
            start_date = start_date.replace(year=start_date.year + 1, month=1, day=1)
        else:
            start_date = start_date.replace(month=start_date.month + 1, day=1)

        end_date = datetime.now()

        return self._aggregate_monthly_range(start_date, end_date)

    def _aggregate_monthly_range(self, start_date: datetime, end_date: datetime) -> Dict:
        """聚合指定日期范围的月统计"""
        success_count = 0
        failed_items = []

        current_date = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        while current_date <= end_date:
            try:
                year = current_date.year
                month = current_date.month

                # 计算月末
                if month == 12:
                    next_month = current_date.replace(year=year + 1, month=1, day=1)
                else:
                    next_month = current_date.replace(month=month + 1, day=1)

                month_end = next_month - timedelta(seconds=1)

                month_start_ts = int(current_date.timestamp() * 1000)
                month_end_ts = int(month_end.timestamp() * 1000)

                events = self.database.get_committed_events_by_date_range(month_start_ts, month_end_ts + 1)

                if events:
                    metrics = self._calculate_metrics(events)
                    stat = MetricsMonthlyStat(
                        year=year,
                        month=month,
                        month_start=current_date.strftime('%Y-%m-%d'),
                        month_start_ts=month_start_ts,
                        month_end=month_end.strftime('%Y-%m-%d'),
                        month_end_ts=month_end_ts,
                        total_lines=metrics['total_lines'],
                        ai_lines=metrics['ai_lines'],
                        ai_percentage=metrics['ai_percentage'],
                        total_commits=metrics['total_commits'],
                        commits_with_ai=metrics['commits_with_ai'],
                        tool_model_breakdown=metrics['tool_model_breakdown'],
                        created_at=int(datetime.now().timestamp() * 1000),
                        updated_at=int(datetime.now().timestamp() * 1000)
                    )
                    self.database.save_metrics_monthly_stat(stat)
                    success_count += 1

                current_date = next_month

            except Exception as e:
                self.logger.error(f"月份 {year}-{month:02d} 聚合失败: {e}")
                failed_items.append(f"{year}-{month:02d}")
                if month == 12:
                    current_date = current_date.replace(year=year + 1, month=1, day=1)
                else:
                    current_date = current_date.replace(month=month + 1, day=1)

        return {
            "success": len(failed_items) == 0,
            "processed": success_count,
            "failed": len(failed_items),
            "details": {"failed_items": failed_items}
        }

    def _aggregate_single_repo(self, repo_url: str) -> None:
        """聚合单个仓库"""
        events = self.database.get_committed_events_by_repo(repo_url)
        if not events:
            return

        metrics = self._calculate_metrics(events)
        repo_id = self._extract_repo_id(repo_url)
        repo_name = repo_url.split('/')[-1] if '/' in repo_url else repo_url

        # 提取时间范围
        timestamps = [e['timestamp'] for e in events if e.get('timestamp')]
        start_date = min(timestamps) if timestamps else None
        end_date = max(timestamps) if timestamps else None

        stat = MetricsRepoStat(
            repo_id=repo_id,
            repo_name=repo_name,
            repo_url=repo_url,
            provider_type='github',
            branch=events[0].get('branch') if events else None,
            total_lines=metrics['total_lines'],
            ai_lines=metrics['ai_lines'],
            ai_percentage=metrics['ai_percentage'],
            total_commits=metrics['total_commits'],
            commits_with_ai=metrics['commits_with_ai'],
            tool_model_breakdown=metrics['tool_model_breakdown'],
            start_date=start_date,
            end_date=end_date,
            created_at=int(datetime.now().timestamp() * 1000),
            updated_at=int(datetime.now().timestamp() * 1000)
        )
        self.database.save_metrics_repo_stat(stat)

    def _aggregate_single_contributor(self, author: str) -> None:
        """聚合单个贡献者"""
        events = self.database.get_committed_events_by_author(author)
        if not events:
            return

        # 按不同粒度聚合
        self._aggregate_contributor_by_granularity(author, events, 'daily')
        self._aggregate_contributor_by_granularity(author, events, 'weekly')
        self._aggregate_contributor_by_granularity(author, events, 'monthly')

    def _aggregate_contributor_by_granularity(self, author: str, events: List[Dict], granularity: str) -> None:
        """按粒度聚合贡献者统计"""
        grouped = {}

        for event in events:
            timestamp = event.get('timestamp')
            if not timestamp:
                continue

            dt = datetime.fromtimestamp(timestamp / 1000)

            if granularity == 'daily':
                key = dt.strftime('%Y-%m-%d')
                date_ts = int(dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
            elif granularity == 'weekly':
                year, week, _ = dt.isocalendar()
                key = f"{year}-W{week:02d}"
                week_start = dt - timedelta(days=dt.weekday())
                date_ts = int(week_start.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
            else:  # monthly
                key = dt.strftime('%Y-%m')
                date_ts = int(dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)

            if key not in grouped:
                grouped[key] = {'events': [], 'date_ts': date_ts}
            grouped[key]['events'].append(event)

        # 保存每个时间段的统计
        for key, data in grouped.items():
            metrics = self._calculate_metrics(data['events'])

            # 计算仓库分布
            repos_breakdown = {}
            for event in data['events']:
                repo_url = event.get('repo_url')
                if repo_url:
                    ai_additions_json = event.get('ai_additions') or '[]'
                    try:
                        ai_additions = sum(json.loads(ai_additions_json))
                    except:
                        ai_additions = 0
                    repos_breakdown[repo_url] = repos_breakdown.get(repo_url, 0) + ai_additions

            stat = MetricsContributorStat(
                author=author,
                author_email=None,
                granularity=granularity,
                date=key if granularity == 'daily' else None,
                year_week=key if granularity == 'weekly' else None,
                year_month=key if granularity == 'monthly' else None,
                date_ts=data['date_ts'],
                total_commits=metrics['total_commits'],
                total_lines=metrics['total_lines'],
                ai_lines=metrics['ai_lines'],
                ai_percentage=metrics['ai_percentage'],
                repos_breakdown=json.dumps(repos_breakdown),
                start_date=data['date_ts'],
                end_date=data['date_ts'],
                created_at=int(datetime.now().timestamp() * 1000),
                updated_at=int(datetime.now().timestamp() * 1000)
            )
            self.database.save_metrics_contributor_stat(stat)
