# core/models/metrics.py
"""Metrics 相关数据模型"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class MetricsRawRecord:
    """Metrics 原始批次记录"""
    batch_id: str
    version: int = 1
    event_count: int = 0
    payload_json: str = ""
    received_at: int = 0
    created_at: int = 0


@dataclass_json
@dataclass
class MetricsCommittedRecord:
    """Committed 事件记录"""
    raw_id: int
    event_id: int = 1
    timestamp: int = 0
    human_additions: Optional[int] = None
    git_diff_deleted_lines: Optional[int] = None
    git_diff_added_lines: Optional[int] = None
    first_checkpoint_ts: Optional[int] = None
    commit_subject: Optional[str] = None
    commit_body: Optional[str] = None
    tool_model_pairs: Optional[str] = None
    mixed_additions: Optional[str] = None
    ai_additions: Optional[str] = None
    ai_accepted: Optional[str] = None
    total_ai_additions: Optional[str] = None
    total_ai_deletions: Optional[str] = None
    time_waiting_for_ai: Optional[str] = None
    git_ai_version: Optional[str] = None
    repo_url: Optional[str] = None
    author: Optional[str] = None
    commit_sha: Optional[str] = None
    base_commit_sha: Optional[str] = None
    branch: Optional[str] = None
    tool: Optional[str] = None
    model: Optional[str] = None
    prompt_id: Optional[str] = None
    external_prompt_id: Optional[str] = None
    custom_attributes: Optional[str] = None
    created_at: int = 0


@dataclass_json
@dataclass
class MetricsCheckpointRecord:
    """Checkpoint 事件记录"""
    raw_id: int
    event_id: int = 4
    timestamp: int = 0
    checkpoint_ts: Optional[int] = None
    kind: Optional[str] = None
    file_path: Optional[str] = None
    lines_added: Optional[int] = None
    lines_deleted: Optional[int] = None
    lines_added_sloc: Optional[int] = None
    lines_deleted_sloc: Optional[int] = None
    git_ai_version: Optional[str] = None
    repo_url: Optional[str] = None
    author: Optional[str] = None
    commit_sha: Optional[str] = None
    base_commit_sha: Optional[str] = None
    branch: Optional[str] = None
    tool: Optional[str] = None
    model: Optional[str] = None
    prompt_id: Optional[str] = None
    created_at: int = 0


@dataclass_json
@dataclass
class MetricsAgentUsageRecord:
    """AgentUsage 事件记录"""
    raw_id: int
    event_id: int = 2
    timestamp: int = 0
    git_ai_version: Optional[str] = None
    repo_url: Optional[str] = None
    author: Optional[str] = None
    commit_sha: Optional[str] = None
    base_commit_sha: Optional[str] = None
    branch: Optional[str] = None
    tool: Optional[str] = None
    model: Optional[str] = None
    prompt_id: Optional[str] = None
    external_prompt_id: Optional[str] = None
    created_at: int = 0


@dataclass_json
@dataclass
class MetricsInstallHooksRecord:
    """InstallHooks 事件记录"""
    raw_id: int
    event_id: int = 3
    timestamp: int = 0
    tool_id: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    git_ai_version: Optional[str] = None
    created_at: int = 0


@dataclass_json
@dataclass
class MetricsDailyStat:
    """按天统计"""
    date: str
    date_ts: int
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    total_commits: int = 0
    commits_with_ai: int = 0
    tool_model_breakdown: Optional[str] = None
    start_date: Optional[int] = None
    end_date: Optional[int] = None
    created_at: int = 0
    updated_at: int = 0


@dataclass_json
@dataclass
class MetricsWeeklyStat:
    """按周统计"""
    year: int
    week: int
    week_start: str
    week_start_ts: int
    week_end: str
    week_end_ts: int
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    total_commits: int = 0
    commits_with_ai: int = 0
    tool_model_breakdown: Optional[str] = None
    created_at: int = 0
    updated_at: int = 0


@dataclass_json
@dataclass
class MetricsMonthlyStat:
    """按月统计"""
    year: int
    month: int
    month_start: str
    month_start_ts: int
    month_end: str
    month_end_ts: int
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    total_commits: int = 0
    commits_with_ai: int = 0
    tool_model_breakdown: Optional[str] = None
    created_at: int = 0
    updated_at: int = 0


@dataclass_json
@dataclass
class MetricsRepoStat:
    """按仓库统计"""
    repo_id: str
    repo_name: str
    repo_url: str
    provider_type: Optional[str] = None
    branch: Optional[str] = None
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    total_commits: int = 0
    commits_with_ai: int = 0
    tool_model_breakdown: Optional[str] = None
    start_date: Optional[int] = None
    end_date: Optional[int] = None
    created_at: int = 0
    updated_at: int = 0


@dataclass_json
@dataclass
class MetricsContributorStat:
    """按贡献者统计（多粒度）"""
    author: str
    author_email: Optional[str] = None
    granularity: str = "daily"
    date: Optional[str] = None
    year_week: Optional[str] = None
    year_month: Optional[str] = None
    date_ts: int = 0
    total_commits: int = 0
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    repos_breakdown: Optional[str] = None
    start_date: Optional[int] = None
    end_date: Optional[int] = None
    created_at: int = 0
    updated_at: int = 0


@dataclass_json
@dataclass
class MetricsRepo:
    """仓库维度主表 - 记录仓库的累计代码统计信息"""
    # === 仓库识别信息 ===
    repo_id: str  # 仓库唯一标识，如 owner/repo 或项目的唯一ID
    repo_name: str  # 仓库名称，用于展示
    repo_url: str  # 仓库的完整URL地址
    provider_type: Optional[str] = None  # 代码托管商类型，如 github/gitea/gitlab
    branch: Optional[str] = None  # 主要统计分支名称

    # === 代码量统计 ===
    total_lines: int = 0  # 累计总代码行数（人类+AI）
    ai_lines: int = 0  # 累计AI生成的代码行数
    human_lines: int = 0  # 累计人类手动编写的代码行数
    ai_percentage: float = 0.0  # AI代码占比百分比 (ai_lines / total_lines * 100)

    # === 提交统计 ===
    total_commits: int = 0  # 累计总提交次数
    ai_commits: int = 0  # 累计包含AI生成的提交次数

    # === 工具模型分布 ===
    tool_model_breakdown: Optional[str] = None  # JSON字符串，记录不同工具和模型的代码贡献分布

    # === 时间范围 ===
    first_commit_ts: Optional[int] = None  # 首次提交的Unix时间戳
    last_commit_ts: Optional[int] = None  # 最新提交的Unix时间戳

    # === 元数据 ===
    created_at: int = 0  # 记录创建时间
    updated_at: int = 0  # 记录更新时间


@dataclass_json
@dataclass
class MetricsContributor:
    """作者维度主表 - 记录作者的累计代码统计信息"""
    # === 作者识别信息 ===
    author: str  # 作者唯一标识
    author_email: Optional[str] = None  # 作者邮箱

    # === 代码量统计 ===
    total_lines: int = 0  # 累计总代码行数
    ai_lines: int = 0  # 累计AI生成的代码行数
    human_lines: int = 0  # 累计人类代码行数
    ai_percentage: float = 0.0  # AI代码占比

    # === 提交统计 ===
    total_commits: int = 0  # 累计总提交次数
    ai_commits: int = 0  # 累计包含AI的提交次数

    # === 工具模型分布 ===
    tool_model_breakdown: Optional[str] = None  # 工具模型分布

    # === 时间范围 ===
    first_commit_ts: Optional[int] = None  # 首次提交时间戳
    last_commit_ts: Optional[int] = None  # 最新提交时间戳

    # === 活动范围 ===
    repos_count: int = 0  # 参与仓库数量

    # === 元数据 ===
    created_at: int = 0  # 记录创建时间
    updated_at: int = 0  # 记录更新时间


@dataclass_json
@dataclass
class MetricsRepoContributor:
    """仓库作者关联表 - 仅记录仓库与作者的关联关系"""
    # === 关联信息 ===
    repo_id: str  # 仓库唯一标识
    author: str  # 作者唯一标识

    # === 时间信息 ===
    first_seen_ts: Optional[int] = None  # 首次发现时间
    last_seen_ts: Optional[int] = None  # 最后发现时间

    # === 元数据 ===
    created_at: int = 0  # 记录创建时间
    updated_at: int = 0  # 记录更新时间
