from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class StatRecord:
    """统计数据记录 - 以统计任务为粒度"""
    id: str
    timestamp: datetime
    total_lines: int = 0
    total_ai_lines: int = 0
    overall_percentage: float = 0.0
    total_commits: int = 0
    commits_with_ai: int = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    repos_count: int = 0


@dataclass_json
@dataclass
class RepoStatRecord:
    """仓库统计数据 - 以项目仓库为粒度"""
    id: str
    stat_id: str
    repo_name: str
    repo_id: str
    provider_type: str
    branch: str
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    total_commits: int = 0
    commits_with_ai: int = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    commit_details: List[Dict] = field(default_factory=list)


@dataclass_json
@dataclass
class ContributorStatRecord:
    """贡献者统计数据 - 以代码提交人为粒度"""
    id: str
    stat_id: str
    author_name: str
    author_email: str
    total_commits: int = 0
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    repos_breakdown: List[Dict] = field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass_json
@dataclass
class RepoContributorStatRecord:
    """仓库贡献者统计数据 - 以仓库+提交人为组合粒度"""
    id: str
    stat_id: str
    repo_stat_id: str
    contributor_stat_id: str
    repo_name: str
    repo_id: str
    provider_type: str
    branch: str
    author_name: str
    author_email: str
    total_commits: int = 0
    total_lines: int = 0
    ai_lines: int = 0
    ai_percentage: float = 0.0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    commit_details: List[Dict] = field(default_factory=list)
