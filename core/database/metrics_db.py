"""
Metrics 原始数据操作类

负责 Metrics 事件表和 CAS 对象表的所有操作。
"""

from typing import Dict, List, Optional
from datetime import datetime

from polars import first

from .base import BaseDatabase, session_scope
from .models import (
    MetricsEventsRaw,
    MetricsEventsCommitted,
    MetricsEventsCheckpoint,
    MetricsEventsAgentUsage,
    MetricsEventsInstallHooks,
    MetricsEventErrors,
    CasObjects,
)
from core.utils.repo_url import normalize_repo_url


class MetricsDatabase(BaseDatabase):
    """Metrics 原始数据操作类"""

    # ========== 原始批次 ==========

    def save_metrics_raw(self,  version: int, event_count: int,
                        payload_json: str, received_at: int) -> str:
        """保存原始 metrics batch，返回 raw_id"""
        with session_scope(self.engine) as session:
            record = MetricsEventsRaw(
                version=version,
                event_count=event_count,
                payload_json=payload_json,
                received_at=received_at
            )
            session.add(record)
            session.flush()
            return record.id

    def get_pending_raw_records(self, limit: int = 100, last_id: Optional[str] = None) -> List[Dict]:
        """
        获取待处理的原始记录
        使用 id 游标分页，确保处理顺序一致

        Args:
            limit: 每批获取的记录数
            last_id: 游标，用于分页（获取 id > last_id 的记录）

        Returns:
            记录列表
        """
        with session_scope(self.engine) as session:
            query = session.query(MetricsEventsRaw)\
                .filter(MetricsEventsRaw.extract == 0)

            if last_id:
                query = query.filter(MetricsEventsRaw.id > last_id)

            query = query.order_by(MetricsEventsRaw.id.asc())\
                .limit(limit)

            results = query.all()
            return [{'id': r.id, 'payload_json': r.payload_json, 'event_count': r.event_count} for r in results]

    def mark_raw_extracting(self, raw_id: str) -> bool:
        """标记原始记录为提取中"""
        with session_scope(self.engine) as session:
            record = session.query(MetricsEventsRaw).filter(MetricsEventsRaw.id == raw_id).first()
            if record and record.extract == 0:
                record.extract = 2  # 提取中
                return True
            return False

    def mark_raw_extracted(self, raw_id: str, success: bool = True) -> bool:
        """标记原始记录提取状态"""
        with session_scope(self.engine) as session:
            record = session.query(MetricsEventsRaw).filter(MetricsEventsRaw.id == raw_id).first()
            if record:
                record.extract = 1 if success else 3  # 1=成功, 3=失败
                return True
            return False

    def reset_stuck_extracting_records(self) -> int:
        """
        将所有 extract=2（处理中）的记录重置为 extract=0（未处理）
        用于任务超时后的恢复

        Returns:
            重置的记录数
        """
        with session_scope(self.engine) as session:
            records = (
                session.query(MetricsEventsRaw)
                .filter(MetricsEventsRaw.extract == 2)
                .all()
            )
            count = len(records)
            for record in records:
                record.extract = 0
            return count

    # ========== Committed 事件 ==========

    def upsert_committed_event(self, record: MetricsEventsCommitted) -> str:
        """保存 Committed 事件"""
        record.repo_url = normalize_repo_url(record.repo_url)
        with session_scope(self.engine) as session:
            exsisted = session.query(MetricsEventsCommitted)\
                .filter(MetricsEventsCommitted.uid == record.uid)\
                .first()
            if exsisted:
                record.id = exsisted.id
                del record.created_at
                del record.uid
                session.merge(record)
            else:
                session.add(record)
            session.flush()
            return record.id

    def get_committed_events_in_range(self, start: datetime, end: datetime) -> List[Dict]:
        """获取时间范围内的 Committed 事件"""
        start_ts = int(start.timestamp() * 1000)
        end_ts = int(end.timestamp() * 1000)
        with session_scope(self.engine) as session:
            results = session.query(MetricsEventsCommitted)\
                .filter(MetricsEventsCommitted.timestamp >= start_ts)\
                .filter(MetricsEventsCommitted.timestamp <= end_ts)\
                .all()
            return [r.to_dict() for r in results]

    def get_committed_events_by_date_range(self, start_ts: int, end_ts: int) -> List[Dict]:
        """按时间戳范围查询 Committed 事件"""
        with session_scope(self.engine) as session:
            results = session.query(MetricsEventsCommitted)\
                .filter(MetricsEventsCommitted.timestamp >= start_ts)\
                .filter(MetricsEventsCommitted.timestamp <= end_ts)\
                .all()
            return [r.to_dict() for r in results]

    def get_committed_events_by_repo(self, repo_url: str) -> List[Dict]:
        """按仓库查询 Committed 事件"""
        normalized_repo_url = normalize_repo_url(repo_url)
        with session_scope(self.engine) as session:
            results = session.query(MetricsEventsCommitted)\
                .filter(MetricsEventsCommitted.repo_url == normalized_repo_url)\
                .all()
            return [r.to_dict() for r in results]

    def get_committed_events_by_author(self, author: str) -> List[Dict]:
        """按作者查询 Committed 事件"""
        with session_scope(self.engine) as session:
            results = session.query(MetricsEventsCommitted)\
                .filter(MetricsEventsCommitted.author == author)\
                .all()
            return [r.to_dict() for r in results]

    # ========== Checkpoint 事件 ==========

    def save_checkpoint_event(self, event: MetricsEventsCheckpoint) -> str:
        """保存 Checkpoint 事件"""
        event.repo_url = normalize_repo_url(event.repo_url)
        with session_scope(self.engine) as session:
            record = event
            exsisted = session.query(MetricsEventsCheckpoint)\
                .filter(MetricsEventsCheckpoint.uid == record.uid)\
                .first()
            if exsisted:
                record.id = exsisted.id
                del record.created_at
                del record.uid
                session.merge(record)
            else:
                session.add(record)
            session.flush()
            return record.id

    def get_checkpoint_events_in_range(self, start_ts: int, end_ts: int) -> List[Dict]:
        """获取时间范围内的 Checkpoint 事件"""
        with session_scope(self.engine) as session:
            results = session.query(MetricsEventsCheckpoint)\
                .filter(MetricsEventsCheckpoint.timestamp >= start_ts)\
                .filter(MetricsEventsCheckpoint.timestamp <= end_ts)\
                .all()
            return [r.to_dict() for r in results]

    # ========== AgentUsage 事件 ==========

    def save_agent_usage_event(self, event: MetricsEventsAgentUsage) -> str:
        """保存 AgentUsage 事件"""
        event.repo_url = normalize_repo_url(event.repo_url)
        with session_scope(self.engine) as session:
            record = event
            exsisted = session.query(MetricsEventsAgentUsage)\
                .filter(MetricsEventsAgentUsage.uid == record.uid)\
                .first()
            if exsisted:
                record.id = exsisted.id
                del record.created_at
                del record.uid
                session.merge(record)
            else:
                session.add(record)
            session.flush()
            return record.id

    # ========== InstallHooks 事件 ==========

    def save_install_hooks_event(self, event: MetricsEventsInstallHooks) -> str:
        """保存 InstallHooks 事件"""
        with session_scope(self.engine) as session:
            record = event
            exsisted = session.query(MetricsEventsInstallHooks)\
                .filter(MetricsEventsInstallHooks.uid == record.uid)\
                .first()
            if exsisted:
                record.id = exsisted.id
                del record.created_at
                del record.uid
                session.merge(record)
            else:
                session.add(record)
            session.flush()
            return record.id

    # ========== CAS ==========

    def save_cas_object(self, hash: str, content_json: Optional[Dict] = None,
                       metadata_json: Optional[Dict] = None) -> None:
        """保存 CAS 对象"""
        with session_scope(self.engine) as session:
            obj = CasObjects(hash=hash, content_json=content_json, metadata_json=metadata_json)
            session.merge(obj)

    def get_cas_object(self, hash: str) -> Optional[Dict]:
        """获取 CAS 对象"""
        with session_scope(self.engine) as session:
            obj = session.query(CasObjects).filter(CasObjects.hash == hash).first()
            return obj.to_dict() if obj else None

    # ========== 辅助查询方法 ==========

    def get_all_repo_urls(self) -> List[str]:
        """获取所有仓库 URL 列表"""
        with session_scope(self.engine) as session:
            from sqlalchemy import distinct
            results = session.query(distinct(MetricsEventsCommitted.repo_url))\
                .filter(MetricsEventsCommitted.repo_url.isnot(None)).all()
            return sorted({normalize_repo_url(r[0]) for r in results if r[0]})

    def get_all_authors(self) -> List[str]:
        """获取所有作者列表"""
        with session_scope(self.engine) as session:
            from sqlalchemy import distinct
            results = session.query(distinct(MetricsEventsCommitted.author))\
                .filter(MetricsEventsCommitted.author.isnot(None)).all()
            return [r[0] for r in results if r[0]]

    # ========== 时间范围查询 ==========

    def get_committed_events_timestamp_range(self) -> Optional[Dict[str, int]]:
        """获取 Committed 事件的最早和最晚时间戳"""
        with session_scope(self.engine) as session:
            from sqlalchemy import func
            result = session.query(
                func.min(MetricsEventsCommitted.timestamp),
                func.max(MetricsEventsCommitted.timestamp)
            ).first()

            if result and result[0] is not None:
                return {'min_ts': result[0], 'max_ts': result[1]}
            return None

    # ========== 错误处理 ==========

    def save_event_error(self, raw_id: str, event_index: int, event_data_raw: str,
                        error_message: str, payload_snippet: str | None) -> str:
        """保存事件错误记录"""
        with session_scope(self.engine) as session:
            record = MetricsEventErrors(
                raw_id=raw_id,
                event_index=event_index,
                event_data_raw=event_data_raw,
                error_message=error_message,
                payload_snippet=payload_snippet[:1024] if payload_snippet else None
            )
            session.add(record)
            session.flush()
            return record.id

    def get_error_events_by_raw_id(self, raw_id: str) -> List[Dict]:
        """获取某个 raw 记录的所有错误事件"""
        with session_scope(self.engine) as session:
            results = session.query(MetricsEventErrors)\
                .filter(MetricsEventErrors.raw_id == raw_id)\
                .order_by(MetricsEventErrors.event_index)\
                .all()
            return [r.to_dict() for r in results]
