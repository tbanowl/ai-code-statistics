"""
SQLAlchemy 数据库模块

本模块使用 SQLAlchemy 2.0 ORM 提供统一的数据访问接口。
支持多数据库（SQLite、PostgreSQL、MySQL），由 SQLAlchemy 方言自动处理。
"""

from .base import Base, session_scope, BaseDatabase
from .metrics_db import MetricsDatabase
from .stats_db import StatsDatabase
from .scheduler_db import SchedulerDatabase
from .blame_stats_db import BlameStatsDatabase
from .authorship_notes_db import AuthorshipNotesDatabase
from .otel_logs_db import OtelLogsDatabase
from .release_db import ReleaseDatabase

__all__ = [
    "Base",
    "session_scope",
    "BaseDatabase",
    "MetricsDatabase",
    "StatsDatabase",
    "SchedulerDatabase",
    "BlameStatsDatabase",
    "AuthorshipNotesDatabase",
    "OtelLogsDatabase",
    "ReleaseDatabase",
]

# 模型在需要时按需导入，避免循环依赖
