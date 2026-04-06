"""
SQLAlchemy ORM 模型定义

本文件包含所有数据库表的 ORM 模型类。
使用 SQLAlchemy 2.0 新特性（MappedColumn、类型注解）。
"""

import time
from xid import XID
from typing import Any, Dict
from sqlalchemy import (
    String,
    BigInteger,
    Integer,
    Text,
    ForeignKey,
    JSON,
    Numeric,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


def now_ts() -> int:
    """返回当前时间戳（毫秒）"""
    return int(time.time() * 1000)

def gen_xid() -> str:
    """生成 XID 字符串"""
    return XID().string()


class ModelBase(Base):
    """模型基类，提供通用字段和方法"""

    __abstract__ = True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


# ============================================================================
# Metrics 事件表
# ============================================================================


class MetricsEventsRaw(ModelBase):
    """原始事件表"""

    __tablename__ = "metrics_events_raw"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    version: Mapped[int] = mapped_column(Integer, default=1)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    # 提取标识：0-未提取、1-提取成功、2-提取中、3-提取失败
    extract: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 提取失败原因
    extract_fail: Mapped[str] = mapped_column(Text, nullable=True)
    received_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class MetricsEventsCommitted(ModelBase):
    """Committed 事件表"""

    __tablename__ = "metrics_events_committed"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    uid: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("metrics_events_raw.id", ondelete="CASCADE")
    )
    event_id: Mapped[int] = mapped_column(Integer, default=1)
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # 标量值
    human_additions: Mapped[int] = mapped_column(Integer, nullable=True)
    git_diff_deleted_lines: Mapped[int] = mapped_column(Integer, nullable=True)
    git_diff_added_lines: Mapped[int] = mapped_column(Integer, nullable=True)
    first_checkpoint_ts: Mapped[int] = mapped_column(BigInteger, nullable=True)
    commit_subject: Mapped[str] = mapped_column(String, nullable=True)
    commit_body: Mapped[str] = mapped_column(Text, nullable=True)

    # JSON 存储
    tool_model_pairs: Mapped[dict] = mapped_column(JSON, nullable=True)
    mixed_additions: Mapped[dict] = mapped_column(JSON, nullable=True)
    ai_additions: Mapped[dict] = mapped_column(JSON, nullable=True)
    ai_accepted: Mapped[dict] = mapped_column(JSON, nullable=True)
    total_ai_additions: Mapped[dict] = mapped_column(JSON, nullable=True)
    total_ai_deletions: Mapped[dict] = mapped_column(JSON, nullable=True)
    time_waiting_for_ai: Mapped[dict] = mapped_column(JSON, nullable=True)

    # 事件属性
    git_ai_version: Mapped[str] = mapped_column(String(20), nullable=True)
    repo_url: Mapped[str] = mapped_column(String(200), nullable=True, index=True)
    author: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=True, index=True)
    base_commit_sha: Mapped[str] = mapped_column(String(40), nullable=True)
    branch: Mapped[str] = mapped_column(String(100), nullable=True)
    tool: Mapped[str] = mapped_column(String(100), nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=True)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=True)
    external_prompt_id: Mapped[str] = mapped_column(String(100), nullable=True)
    custom_attributes: Mapped[dict] = mapped_column(JSON, nullable=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class MetricsEventsCheckpoint(ModelBase):
    """Checkpoint 事件表"""

    __tablename__ = "metrics_events_checkpoint"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    uid: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("metrics_events_raw.id", ondelete="CASCADE")
    )
    event_id: Mapped[int] = mapped_column(Integer, default=4)
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    checkpoint_ts: Mapped[int] = mapped_column(BigInteger, nullable=True)
    kind: Mapped[str] = mapped_column(String, nullable=True)
    file_path: Mapped[str] = mapped_column(String, nullable=True, index=True)
    lines_added: Mapped[int] = mapped_column(Integer, nullable=True)
    lines_deleted: Mapped[int] = mapped_column(Integer, nullable=True)
    lines_added_sloc: Mapped[int] = mapped_column(Integer, nullable=True)
    lines_deleted_sloc: Mapped[int] = mapped_column(Integer, nullable=True)

    git_ai_version: Mapped[str] = mapped_column(String, nullable=True)
    repo_url: Mapped[str] = mapped_column(String, nullable=True)
    author: Mapped[str] = mapped_column(String, nullable=True)
    commit_sha: Mapped[str] = mapped_column(String, nullable=True)
    base_commit_sha: Mapped[str] = mapped_column(String, nullable=True)
    branch: Mapped[str] = mapped_column(String, nullable=True)
    tool: Mapped[str] = mapped_column(String, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=True)
    prompt_id: Mapped[str] = mapped_column(String, nullable=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class MetricsEventsAgentUsage(ModelBase):
    """AgentUsage 事件表"""

    __tablename__ = "metrics_events_agent_usage"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    uid: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("metrics_events_raw.id", ondelete="CASCADE")
    )
    event_id: Mapped[int] = mapped_column(Integer, default=2)
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    git_ai_version: Mapped[str] = mapped_column(String, nullable=True)
    repo_url: Mapped[str] = mapped_column(String, nullable=True)
    author: Mapped[str] = mapped_column(String, nullable=True)
    commit_sha: Mapped[str] = mapped_column(String, nullable=True)
    base_commit_sha: Mapped[str] = mapped_column(String, nullable=True)
    branch: Mapped[str] = mapped_column(String, nullable=True)
    tool: Mapped[str] = mapped_column(String, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=True)
    prompt_id: Mapped[str] = mapped_column(String, nullable=True)
    external_prompt_id: Mapped[str] = mapped_column(String, nullable=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class MetricsEventsInstallHooks(ModelBase):
    """InstallHooks 事件表"""

    __tablename__ = "metrics_events_install_hooks"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    uid: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("metrics_events_raw.id", ondelete="CASCADE")
    )
    event_id: Mapped[int] = mapped_column(Integer, default=3)
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)

    tool_id: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(String, nullable=True)
    git_ai_version: Mapped[str] = mapped_column(String, nullable=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class MetricsEventErrors(ModelBase):
    """事件解析错误记录表"""

    __tablename__ = "metrics_event_errors"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    raw_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("metrics_events_raw.id", ondelete="CASCADE")
    )
    event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    event_data_raw: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_snippet: Mapped[str] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_retry_at: Mapped[int] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)

    # 添加索引
    __table_args__ = (Index("idx_raw_event_index", "raw_id", "event_index"),)


# ============================================================================
# CAS 对象表
# ============================================================================


class CasObjects(ModelBase):
    """CAS (Content Addressable Storage) 对象表"""

    __tablename__ = "cas_objects"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    hash: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


# ============================================================================
# 新统计表 (stats_ 前缀)
# ============================================================================


class StatsRepository(ModelBase):
    """仓库表"""

    __tablename__ = "stats_repositories"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_path: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    repo_name: Mapped[str] = mapped_column(String, nullable=True)
    # 是否启用 AI 代码归因统计
    repo_stats_flag: Mapped[int] = mapped_column(Integer, default=1)
    # 关联的 SSH Key ID（为空时使用配置文件默认 Key）
    ssh_key_id: Mapped[str] = mapped_column(String(20), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )

    # 关系
    branch_configs = relationship(
        "StatsRepoBranchConfig", back_populates="repository", cascade="all, delete-orphan"
    )


class StatsRepoBranchConfig(ModelBase):
    """仓库分支配置表"""

    __tablename__ = "stats_repo_branch_config"

    __table_args__ = (UniqueConstraint("repo_id", "branch_pattern"),)

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stats_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    # pattern_type 有效值: 'exact' (精确匹配), 'wildcard' (通配符), 'special' (特殊规则)
    pattern_type: Mapped[str] = mapped_column(String(20), nullable=False, default="exact")
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )

    # 关系
    repository = relationship("StatsRepository", back_populates="branch_configs")


class StatsContributor(ModelBase):
    """贡献者表"""

    __tablename__ = "stats_contributors"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    contributor_uid: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsRepoContributor(ModelBase):
    """仓库贡献者关联表"""

    __tablename__ = "stats_repo_contributors"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stats_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contributor_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stats_contributors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsDailyStat(ModelBase):
    """每日统计表"""

    __tablename__ = "stats_daily_stats"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    stat_date: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    repo_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stats_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repo_name: Mapped[str] = mapped_column(String, nullable=True)
    contributor_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stats_contributors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contributor_name: Mapped[str] = mapped_column(String, nullable=True)

    ai_generated_lines: Mapped[int] = mapped_column(Integer, default=0)
    ai_generated_lines_total: Mapped[int] = mapped_column(Integer, default=0)
    ai_accepted_lines: Mapped[int] = mapped_column(Integer, default=0)
    human_lines: Mapped[int] = mapped_column(Integer, default=0)
    ai_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    git_ai_version: Mapped[str] = mapped_column(String(50), nullable=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


# ============================================================================
# 任务执行表
# ============================================================================


class TaskExecution(ModelBase):
    """任务执行记录表"""

    __tablename__ = "task_executions"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    job_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    started_at: Mapped[int] = mapped_column(BigInteger, nullable=True)
    finished_at: Mapped[int] = mapped_column(BigInteger, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


# ============================================================================
# GIT AI 数据收集
# ============================================================================


class TelemetryEnvelope(ModelBase):
    """GIT AI 数据收集表"""

    __tablename__ = "telemetry_envelope"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    envelope_data: Mapped[str] = mapped_column(JSON, nullable=False)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


# ============================================================================
# REST Notes Store 表
# ============================================================================


class AuthorshipNotes(ModelBase):
    """作者注释表 - 用于 REST Notes Store API"""

    __tablename__ = "authorship_notes"

    __table_args__ = (
        UniqueConstraint("repo_url", "commit_sha"),
        Index("idx_authorship_notes_repo_url", "repo_url"),
        Index("idx_authorship_notes_repo_commit", "repo_url", "commit_sha"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(Text, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    note_blob_oid: Mapped[str] = mapped_column(String(40), nullable=True)
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    author_email: Mapped[str] = mapped_column(Text, nullable=False)
    note_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


# ============================================================================
# Git Blame 统计表 (stats_blame_ 前缀)
# ============================================================================


class StatsSshKey(ModelBase):
    """SSH Key 表"""

    __tablename__ = "stats_ssh_keys"

    __table_args__ = (Index("idx_ssh_key_name", "key_name"),)

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    key_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    private_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsBlameRepo(ModelBase):
    """仓库级归因统计表"""

    __tablename__ = "stats_blame_repo"

    __table_args__ = (
        UniqueConstraint("repo_id", "stat_date"),
        Index("idx_blame_repo_date", "repo_id", "stat_date"),
        Index("idx_blame_stat_date", "stat_date"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stat_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    branch: Mapped[str] = mapped_column(Text, nullable=False)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    non_ai_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_ratio: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    total_files: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsBlameFile(ModelBase):
    """文件级归因统计表"""

    __tablename__ = "stats_blame_file"

    __table_args__ = (
        UniqueConstraint("repo_id", "stat_date", "file_path"),
        Index("idx_blame_file_repo", "repo_id", "stat_date"),
        Index("idx_blame_file_date", "stat_date"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stat_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    non_ai_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_ratio: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsBlameRepoContributor(ModelBase):
    """仓库贡献者归因统计表"""

    __tablename__ = "stats_blame_repo_contributor"

    __table_args__ = (
        UniqueConstraint("repo_id", "stat_date", "contributor_id"),
        Index("idx_blame_rc_repo", "repo_id", "stat_date"),
        Index("idx_blame_rc_date", "stat_date"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stat_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contributor_id: Mapped[str] = mapped_column(String(20), nullable=False)
    contributor_name: Mapped[str] = mapped_column(Text, nullable=False)
    contributor_email: Mapped[str] = mapped_column(Text, nullable=True)
    ai_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    non_ai_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsBlameFileContributor(ModelBase):
    """文件贡献者归因统计表"""

    __tablename__ = "stats_blame_file_contributor"

    __table_args__ = (
        UniqueConstraint("file_id", "stat_date", "contributor_id"),
        Index("idx_blame_fc_file", "repo_id", "stat_date", "file_path"),
        Index("idx_blame_fc_date", "stat_date"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    file_id: Mapped[str] = mapped_column(String(20), nullable=False)
    stat_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    repo_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    contributor_id: Mapped[str] = mapped_column(String(20), nullable=False)
    contributor_name: Mapped[str] = mapped_column(Text, nullable=False)
    contributor_email: Mapped[str] = mapped_column(Text, nullable=True)
    ai_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    non_ai_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )
