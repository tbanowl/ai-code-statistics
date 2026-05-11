"""OTLP Logs 调用计数数据库操作。"""

from typing import Iterable

from .base import BaseDatabase, session_scope
from .models import OtelInvocationCount


class OtelLogsDatabase(BaseDatabase):
    """Claude Code OTLP Logs 调用计数数据库访问类。"""

    def save_invocation_counts(self, records: Iterable[OtelInvocationCount]) -> int:
        """批量保存调用计数记录，返回保存条数。"""
        records_list = list(records)
        if not records_list:
            return 0

        with session_scope(self.engine) as session:
            session.add_all(records_list)
            return len(records_list)
