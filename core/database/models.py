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
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column
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
    commit_date: Mapped[int] = mapped_column(BigInteger, nullable=True, index=True)

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

    mixed_additions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_additions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_accepted_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_ai_additions_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_ai_deletions_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    time_waiting_for_ai_total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )

    # 事件属性
    git_ai_version: Mapped[str] = mapped_column(String, nullable=True)
    repo_url: Mapped[str] = mapped_column(String, nullable=True, index=True)
    author: Mapped[str] = mapped_column(String, nullable=True, index=True)
    commit_sha: Mapped[str] = mapped_column(String, nullable=True, index=True)
    base_commit_sha: Mapped[str] = mapped_column(String, nullable=True)
    branch: Mapped[str] = mapped_column(String, nullable=True)
    tool: Mapped[str] = mapped_column(String, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=True)
    prompt_id: Mapped[str] = mapped_column(String, nullable=True)
    external_prompt_id: Mapped[str] = mapped_column(String, nullable=True)
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


class OtelInvocationCount(ModelBase):
    """Claude Code OTLP Logs Skill 调用计数表。"""

    __tablename__ = "otel_invocation_counts"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="claude_code"
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="skill"
    )
    plugin_name: Mapped[str] = mapped_column(String(200), nullable=False)
    skill_name: Mapped[str] = mapped_column(String(200), nullable=False)
    invocation_trigger: Mapped[str] = mapped_column(String(50), nullable=True)
    org_user: Mapped[str] = mapped_column(String(200), nullable=False)
    service_name: Mapped[str] = mapped_column(String(200), nullable=True)
    service_version: Mapped[str] = mapped_column(String(100), nullable=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    time_unix_nano: Mapped[str] = mapped_column(String(30), nullable=True)
    received_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    otel_log_date: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)

    __table_args__ = (
        Index("idx_otel_invocation_received_at", "received_at"),
        Index(
            "idx_otel_invocation_org_plugin_skill",
            "org_user",
            "plugin_name",
            "skill_name",
        ),
    )


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
    name_level1: Mapped[str] = mapped_column(String(50), nullable=True)
    name_level2: Mapped[str] = mapped_column(String(50), nullable=True)
    name_level3: Mapped[str] = mapped_column(String(50), nullable=True)
    name_level4: Mapped[str] = mapped_column(String(50), nullable=True)
    name_level5: Mapped[str] = mapped_column(String(50), nullable=True)
    repo_short_name: Mapped[str] = mapped_column(String(50), nullable=True)
    # 是否启用 AI 代码归因统计
    repo_stats_flag: Mapped[int] = mapped_column(Integer, default=1)
    # 关联的 SSH Key ID（为空时使用配置文件默认 Key）
    ssh_key_id: Mapped[str] = mapped_column(String(20), nullable=True)
    # 最近一次 Git Blame 统计成功的提交 SHA
    last_blame_commit_sha: Mapped[str] = mapped_column(String(40), nullable=True)
    # 最近一次每日聚合成功统计到的事件 ID
    last_daily_aggregation_id: Mapped[str] = mapped_column(String(20), nullable=True)
    last_stat_date: Mapped[int] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsRepoBranchConfig(ModelBase):
    """仓库分支配置表"""

    __tablename__ = "stats_repo_branch_config"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    branch_pattern: Mapped[str] = mapped_column(String(400), nullable=False)
    # pattern_type 有效值: 'exact' (精确匹配), 'wildcard' (通配符), 'special' (特殊规则)
    pattern_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="exact"
    )
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsRepositoryBranch(ModelBase):
    """仓库实际分支表"""

    __tablename__ = "stats_repositories_branch"
    __table_args__ = (
        UniqueConstraint("repo_id", "branch_name"),
        Index("idx_repositories_branch_repo", "repo_id"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    branch_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[int] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsContributor(ModelBase):
    """贡献者表"""

    __tablename__ = "stats_contributors"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
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

    __tablename__ = "stats_commit_daily"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    # 统计日期，格式：YYYYMMDD
    stat_date: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    repo_id: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    repo_name: Mapped[str] = mapped_column(String, nullable=True)
    contributor_name: Mapped[str] = mapped_column(String, nullable=True)
    contributor_email: Mapped[str] = mapped_column(String, nullable=True, index=True)

    human_additions: Mapped[int] = mapped_column(Integer, default=0)
    unknown_additions: Mapped[int] = mapped_column(Integer, default=0)
    git_diff_deleted_lines: Mapped[int] = mapped_column(Integer, default=0)
    git_diff_added_lines: Mapped[int] = mapped_column(Integer, default=0)
    mixed_additions: Mapped[int] = mapped_column(Integer, default=0)
    ai_additions: Mapped[int] = mapped_column(Integer, default=0)
    ai_accepted: Mapped[int] = mapped_column(Integer, default=0)
    total_ai_additions: Mapped[int] = mapped_column(Integer, default=0)
    total_ai_deletions: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


# ============================================================================
# 任务执行表
# ============================================================================


class TaskRunning(ModelBase):
    """任务执行记录表"""

    __tablename__ = "task_running"

    job_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    started_at: Mapped[int] = mapped_column(BigInteger, default=now_ts)


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
        Index("idx_authorship_notes_repo_change_seq", "repo_url", "change_seq"),
        Index("idx_authorship_notes_repo_status", "repo_url", "status"),
        Index(
            "idx_authorship_notes_superseded_rewrite",
            "repo_url",
            "superseded_rewrite_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_url: Mapped[str] = mapped_column(String, nullable=False)
    branch: Mapped[str] = mapped_column(String(40), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    note_blob_oid: Mapped[str] = mapped_column(String(40), nullable=True)
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    author_email: Mapped[str] = mapped_column(Text, nullable=False)
    note_content: Mapped[str] = mapped_column(Text, nullable=False)
    commit_time: Mapped[int] = mapped_column(BigInteger, nullable=True, index=True)
    commit_date: Mapped[int] = mapped_column(BigInteger, nullable=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    change_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    superseded_by: Mapped[str] = mapped_column(String(40), nullable=True)
    superseded_at: Mapped[int] = mapped_column(BigInteger, nullable=True)
    superseded_rewrite_id: Mapped[str] = mapped_column(String(200), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class AuthorshipNotesSeq(ModelBase):
    """单调递增序列表，用于 authorship_notes.change_seq。"""

    __tablename__ = "authorship_notes_seq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class AuthorshipNoteRewrite(ModelBase):
    """作者注释重写操作记录表"""

    __tablename__ = "authorship_note_rewrites"

    __table_args__ = (
        UniqueConstraint("rewrite_id"),
        Index("idx_authorship_note_rewrites_repo", "repo_url"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    rewrite_id: Mapped[str] = mapped_column(String(200), nullable=False)
    repo_url: Mapped[str] = mapped_column(String, nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    original_head: Mapped[str] = mapped_column(String(40), nullable=True)
    new_head: Mapped[str] = mapped_column(String(40), nullable=True)
    request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class AuthorshipNoteRewriteMapping(ModelBase):
    """作者注释重写提交映射表"""

    __tablename__ = "authorship_note_rewrite_mappings"

    __table_args__ = (
        UniqueConstraint("repo_url", "source_commit", "target_commit", "rewrite_id"),
        Index("idx_authorship_note_rewrite_source", "repo_url", "source_commit"),
        Index("idx_authorship_note_rewrite_target", "repo_url", "target_commit"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    rewrite_id: Mapped[str] = mapped_column(String(200), nullable=False)
    repo_url: Mapped[str] = mapped_column(String, nullable=False)
    source_commit: Mapped[str] = mapped_column(String(40), nullable=False)
    target_commit: Mapped[str] = mapped_column(String(40), nullable=False)
    source_note_blob_oid: Mapped[str] = mapped_column(String(40), nullable=True)
    target_note_blob_oid: Mapped[str] = mapped_column(String(40), nullable=True)
    target_content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    disposition: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class CodeupMergeAuthorshipTask(ModelBase):
    """Codeup 合并后 authorship 重算任务表"""

    __tablename__ = "codeup_merge_authorship_tasks"

    __table_args__ = (
        UniqueConstraint("repo_url", "merge_request_id", "merge_commit_sha"),
        Index("idx_codeup_merge_authorship_status_attempts", "status", "attempts"),
        Index("idx_codeup_merge_authorship_repo_url", "repo_url"),
        Index("idx_codeup_merge_authorship_commit", "merge_commit_sha"),
        Index("idx_codeup_merge_authorship_event_kind", "event_kind"),
        Index("idx_codeup_merge_authorship_merge_type", "merge_type"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_url: Mapped[str] = mapped_column(String, nullable=False)
    project_id: Mapped[Any] = mapped_column(String(100), nullable=True)
    merge_request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    target_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    merge_commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    source_commit_shas: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    event_kind: Mapped[Any] = mapped_column(String(64), nullable=True)
    payload_version_hint: Mapped[Any] = mapped_column(String(32), nullable=True)
    normalized_payload: Mapped[Any] = mapped_column(
        LONGTEXT().with_variant(Text(), "sqlite"), nullable=True
    )
    merge_type: Mapped[Any] = mapped_column(String(64), nullable=True)
    skipped_reason: Mapped[Any] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Any] = mapped_column(Text, nullable=True)
    result_summary: Mapped[Any] = mapped_column(Text, nullable=True)
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
    public_key: Mapped[str] = mapped_column(Text, nullable=True)
    private_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsBlameRepo(ModelBase):
    """仓库级归因统计表"""

    __tablename__ = "stats_blame_repo"

    __table_args__ = (
        UniqueConstraint("repo_id", "stat_date", "branch"),
        Index("idx_blame_repo_date", "repo_id", "stat_date"),
        Index("idx_blame_stat_date", "stat_date"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stat_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    branch: Mapped[str] = mapped_column(String(40), nullable=False)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    non_ai_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    total_files: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


class StatsBlameRepoContributor(ModelBase):
    """仓库贡献者归因统计表"""

    __tablename__ = "stats_blame_repo_contributor"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    branch: Mapped[str] = mapped_column(String(40), nullable=False)
    stat_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contributor_name: Mapped[str] = mapped_column(Text, nullable=False)
    contributor_email: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    ai_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    non_ai_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )


# ============================================================================
# 系统管理表
# ============================================================================


class SysDept(ModelBase):
    __tablename__ = "sys_dept"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    parent_id: Mapped[str] = mapped_column(String(20), nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class SysMenu(ModelBase):
    __tablename__ = "sys_menu"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    parent_id: Mapped[str] = mapped_column(String(20), nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    router_name: Mapped[str] = mapped_column(String(100), nullable=False)
    path: Mapped[str] = mapped_column(String(200), nullable=True)
    component: Mapped[str] = mapped_column(String(200), nullable=True)
    icon: Mapped[str] = mapped_column(String(100), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    menu_type: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    show_link: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    keep_alive: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class SysRole(ModelBase):
    __tablename__ = "sys_role"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    remark: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class SysUser(ModelBase):
    __tablename__ = "sys_user"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    nickname: Mapped[str] = mapped_column(String(100), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    email: Mapped[str] = mapped_column(String(200), nullable=True)
    dept_id: Mapped[str] = mapped_column(String(20), nullable=True)
    avatar: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class SysUserRole(ModelBase):
    __tablename__ = "sys_user_role"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    user_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    role_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)


class SysRoleMenu(ModelBase):
    __tablename__ = "sys_role_menu"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    role_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    menu_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
