from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
from core.models.stats import StatRecord
from core.models.metrics import (
    MetricsCommittedRecord,
    MetricsCheckpointRecord, MetricsAgentUsageRecord,
    MetricsInstallHooksRecord, MetricsDailyStat,
    MetricsWeeklyStat, MetricsMonthlyStat,
    MetricsRepoStat, MetricsContributorStat,
    MetricsRepo, MetricsContributor, MetricsRepoContributor
)


class Database(ABC):
    """数据库抽象基类"""

    def __init__(self, config: Dict):
        self.config = config

        # 初始化日志记录器
        from core.config.logging import Logger
        self.logger = Logger.get_logger(f'database.{self.__class__.__name__}')

    # ========== 原有方法（stats 相关） ==========

    @abstractmethod
    def init_db(self) -> None:
        """初始化数据库表结构"""
        pass

    @abstractmethod
    def save_stats(self, stats: StatRecord) -> int:
        """保存统计数据"""
        pass

    @abstractmethod
    def get_latest_stat(self) -> Optional[Dict]:
        """获取最新的统计数据"""
        pass

    @abstractmethod
    def get_stats_history(self, days: int) -> List[Dict]:
        """获取指定天数的历史统计数据"""
        pass

    @abstractmethod
    def get_repo_stats(self) -> List[Dict]:
        """获取仓库统计数据"""
        pass

    @abstractmethod
    def get_contributor_stats(self) -> List[Dict]:
        """获取贡献者统计数据"""
        pass

    # ========== Metrics 原始数据方法 ==========

    @abstractmethod
    def save_metrics_raw(self, batch_id: str, version: int,
                        event_count: int, payload_json: str,
                        received_at: int) -> int:
        """保存原始 metrics batch，返回 raw_id"""
        pass

    @abstractmethod
    def get_committed_events_in_range(self, start: datetime, end: datetime) -> List[Dict]:
        """获取时间范围内的 Committed 事件"""
        pass

    @abstractmethod
    def save_committed_event(self, event: MetricsCommittedRecord) -> int:
        """保存 Committed 事件"""
        pass

    @abstractmethod
    def save_checkpoint_event(self, event: MetricsCheckpointRecord) -> int:
        """保存 Checkpoint 事件"""
        pass

    @abstractmethod
    def save_agent_usage_event(self, event: MetricsAgentUsageRecord) -> int:
        """保存 AgentUsage 事件"""
        pass

    @abstractmethod
    def save_install_hooks_event(self, event: MetricsInstallHooksRecord) -> int:
        """保存 InstallHooks 事件"""
        pass

    # ========== CAS 方法 ==========

    @abstractmethod
    def save_cas_object(self, hash: str, content_json: str,
                        metadata_json: str = '') -> None:
        """保存 CAS 对象"""
        pass

    @abstractmethod
    def get_cas_object(self, hash: str) -> Optional[Dict]:
        """获取 CAS 对象"""
        pass

    # ========== Metrics 汇总表方法 ==========

    @abstractmethod
    def save_metrics_daily_stat(self, stat: MetricsDailyStat) -> int:
        """保存按天统计"""
        pass

    @abstractmethod
    def save_metrics_weekly_stat(self, stat: MetricsWeeklyStat) -> int:
        """保存按周统计"""
        pass

    @abstractmethod
    def save_metrics_monthly_stat(self, stat: MetricsMonthlyStat) -> int:
        """保存按月统计"""
        pass

    @abstractmethod
    def save_metrics_repo_stat(self, stat: MetricsRepoStat) -> int:
        """保存按仓库统计"""
        pass

    @abstractmethod
    def save_metrics_contributor_stat(self, stat: MetricsContributorStat) -> int:
        """保存按贡献者统计"""
        pass

    @abstractmethod
    def get_latest_metrics_stat(self, granularity: str) -> Optional[Dict]:
        """获取最新的统计记录（day/week/month）"""
        pass

    # ========== 维度表方法 ==========

    @abstractmethod
    def save_metrics_repo(self, repo: MetricsRepo) -> int:
        """保存仓库维度记录，返回记录 id"""
        pass

    @abstractmethod
    def get_metrics_repo(self, repo_id: str) -> Optional[Dict]:
        """获取仓库维度记录"""
        pass

    @abstractmethod
    def get_metrics_repos(self, page: int = 1, page_size: int = 20,
                          sort: str = '') -> Dict:
        """获取仓库维度列表，支持分页和排序"""
        pass

    @abstractmethod
    def save_metrics_contributor(self, contributor: MetricsContributor) -> int:
        """保存作者维度记录，返回记录 id"""
        pass

    @abstractmethod
    def get_metrics_contributor(self, author: str) -> Optional[Dict]:
        """获取作者维度记录"""
        pass

    @abstractmethod
    def get_metrics_contributors(self, page: int = 1, page_size: int = 20,
                                  sort: str = '') -> Dict:
        """获取作者维度列表，支持分页和排序"""
        pass

    @abstractmethod
    def save_metrics_repo_contributor(
        self, repo_contributor: MetricsRepoContributor
    ) -> int:
        """保存仓库作者关联记录，返回记录 id"""
        pass

    @abstractmethod
    def get_metrics_repo_contributors(
        self, repo_id: str = '', author: str = '',
        page: int = 1, page_size: int = 20
    ) -> Dict:
        """获取仓库作者关联列表，支持按仓库或作者筛选"""
        pass

    # ========== 聚合任务辅助方法 ==========

    @abstractmethod
    def get_latest_daily_stat(self) -> Optional[MetricsDailyStat]:
        """获取最新的日统计记录"""
        pass

    @abstractmethod
    def get_latest_weekly_stat(self) -> Optional[MetricsWeeklyStat]:
        """获取最新的周统计记录"""
        pass

    @abstractmethod
    def get_latest_monthly_stat(self) -> Optional[MetricsMonthlyStat]:
        """获取最新的月统计记录"""
        pass

    @abstractmethod
    def get_all_repo_urls(self) -> List[str]:
        """获取所有仓库 URL 列表"""
        pass

    @abstractmethod
    def get_all_authors(self) -> List[str]:
        """获取所有作者列表"""
        pass

    @abstractmethod
    def get_committed_events_by_date_range(self, start_ts: int, end_ts: int) -> List[Dict]:
        """按时间范围查询 committed 事件"""
        pass

    @abstractmethod
    def get_committed_events_by_repo(self, repo_url: str) -> List[Dict]:
        """按仓库查询 committed 事件"""
        pass

    @abstractmethod
    def get_committed_events_by_author(self, author: str) -> List[Dict]:
        """按作者查询 committed 事件"""
        pass
