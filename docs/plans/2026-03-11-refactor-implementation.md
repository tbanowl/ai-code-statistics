# Git AI Code Metrics Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将现有 Git AI 代码统计工具改造为工程化架构，支持多 Git 平台、多数据库、定时任务和 YAML 配置管理。

**Architecture:** 采用分层架构，Web 层 → 服务层 → 抽象层（GitProvider/Database）→ 具体实现。

**Tech Stack:** Flask, requests, PyYAML, APScheduler, PostgreSQL/MySQL/SQLite, pytest

---

## Task 1: 项目结构初始化

**Files:**
- Create: `core/__init__.py`
- Create: `core/config/__init__.py`
- Create: `core/git_providers/__init__.py`
- Create: `core/database/__init__.py`
- Create: `core/models/__init__.py`
- Create: `core/services/__init__.py`
- Create: `core/scheduler/__init__.py`
- Create: `api/__init__.py`
- Create: `api/routes/__init__.py`
- Create: `api/schemas/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `data/.gitkeep`
- Create: `logs/.gitkeep`

**Step 1: 创建 core 模块初始化文件**

```bash
# 批量创建空的 __init__.py 文件
cd Q:/w/prj/git-ai-code-metrics
touch core/__init__.py core/config/__init__.py core/git_providers/__init__.py
touch core/database/__init__.py core/models/__init__.py core/services/__init__.py
touch core/scheduler/__init__.py
touch api/__init__.py api/routes/__init__.py api/schemas/__init__.py
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
touch data/.gitkeep logs/.gitkeep
```

**Step 2: 验证目录结构**

```bash
tree -L 3 core api tests data logs
```
预期: 显示完整的目录树结构

**Step 3: 提交**

```bash
git add core api tests data logs
git commit -m "refactor: 初始化项目目录结构"
```

---

## Task 2: 数据模型定义

**Files:**
- Create: `core/models/stats.py`
- Test: `tests/unit/test_models/test_stats.py`

**Step 1: 编写数据模型**

```python
# core/models/stats.py
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
```

**Step 2: 更新 requirements.txt**

```
# dataclasses_json for serialization
dataclasses-json>=0.6.0
```

**Step 3: 安装依赖**

```bash
pip install dataclasses-json
```

**Step 4: 编写测试**

```python
# tests/unit/test_models/test_stats.py
from datetime import datetime
from core.models.stats import StatRecord, RepoStatRecord, ContributorStatRecord, RepoContributorStatRecord


def test_stat_record_creation():
    now = datetime.now()
    record = StatRecord(
        id="test-id",
        timestamp=now,
        total_lines=1000,
        total_ai_lines=500
    )
    assert record.id == "test-id"
    assert record.total_lines == 1000
    assert record.overall_percentage == 0.0  # 计算前默认值


def test_repo_stat_record_creation():
    now = datetime.now()
    record = RepoStatRecord(
        id="repo-id",
        stat_id="stat-id",
        repo_name="test-repo",
        repo_id="123",
        provider_type="gitlab",
        branch="main"
    )
    assert record.repo_name == "test-repo"
    assert record.provider_type == "gitlab"


def test_stat_record_serialization():
    now = datetime.now()
    record = StatRecord(
        id="test-id",
        timestamp=now,
        total_lines=1000,
        total_ai_lines=500
    )
    json_data = record.to_dict()
    assert json_data['id'] == "test-id"
    assert json_data['total_lines'] == 1000
```

**Step 5: 运行测试**

```bash
pytest tests/unit/test_models/test_stats.py -v
```
预期: PASS 所有测试

**Step 6: 提交**

```bash
git add core/models/stats.py tests/unit/test_models/test_stats.py requirements.txt
git commit -m "feat: 添加数据模型定义"
```

---

## Task 3: Git Provider 抽象基类

**Files:**
- Create: `core/git_providers/base.py`
- Test: `tests/unit/test_git_providers/test_base.py`

**Step 1: 编写抽象基类**

```python
# core/git_providers/base.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional


class GitProvider(ABC):
    """Git 平台抽象基类"""

    def __init__(self, config: Dict):
        self.config = config
        self.base_url = config.get('base_url', '')
        self.token = config.get('token') or config.get('private_token', '')

    @abstractmethod
    def get_project_info(self, project_id: str) -> Dict:
        """获取单个项目的详细信息（名称、描述、URL等）"""
        pass

    @abstractmethod
    def get_projects(self, project_ids: Optional[List[str]] = None,
                    search: Optional[str] = None,
                    page: int = 1, per_page: int = 20) -> Dict:
        """根据参数查询多个项目的简要信息"""
        pass

    @abstractmethod
    def get_commits(self, project_id: str, branch: str, since: datetime, until: datetime) -> List[Dict]:
        """获取提交列表"""
        pass

    @abstractmethod
    def get_ai_notes(self, project_id: str, commit_sha: str) -> Optional[Dict]:
        """获取 AI Notes 数据"""
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """验证连接是否正常"""
        pass
```

**Step 2: 编写测试**

```python
# tests/unit/test_git_providers/test_base.py
import pytest
from core.git_providers.base import GitProvider


def test_git_provider_is_abstract():
    """GitProvider 应该是抽象类，不能直接实例化"""
    with pytest.raises(TypeError):
        GitProvider({})
```

**Step 3: 运行测试**

```bash
pytest tests/unit/test_git_providers/test_base.py -v
```
预期: PASS - 测试确认抽象类不能直接实例化

**Step 4: 提交**

```bash
git add core/git_providers/base.py tests/unit/test_git_providers/test_base.py
git commit -m "feat: 新增 GitProvider 抽象基类"
```

---

## Task 4: GitLab Provider 实现

**Files:**
- Create: `core/git_providers/gitlab.py`
- Create: `core/git_providers/factory.py`
- Test: `tests/unit/test_git_providers/test_gitlab.py`

**Step 1: 编写 GitLab Provider**

```python
# core/git_providers/gitlab.py
import base64
import json
import requests
from datetime import datetime
from typing import List, Dict, Optional
from .base import GitProvider


class GitLabProvider(GitProvider):
    """GitLab API 实现"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_base = f"{self.base_url.rstrip('/')}/api/v4"
        self.timeout = config.get('api_timeout', 30)

    def get_project_info(self, project_id: str) -> Dict:
        """获取项目信息"""
        url = f"{self.api_base}/projects/{project_id}"
        headers = {"PRIVATE-TOKEN": self.token}
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"获取项目信息失败: {e}")

    def get_projects(self, project_ids: Optional[List[str]] = None,
                    search: Optional[str] = None,
                    page: int = 1, per_page: int = 20) -> Dict:
        """查询项目列表"""
        url = f"{self.api_base}/projects"
        headers = {"PRIVATE-TOKEN": self.token}
        params = {"page": page, "per_page": per_page}

        if project_ids:
            # GitLab API 支持按 ID 搜索
            url = f"{self.api_base}/projects"
            result_projects = []
            for pid in project_ids:
                try:
                    project = self.get_project_info(pid)
                    result_projects.append(project)
                except Exception:
                    continue
            return {"projects": result_projects, "total": len(result_projects), "page": 1, "per_page": per_page}

        if search:
            params["search"] = search

        response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        projects = response.json()
        return {
            "projects": projects,
            "total": response.headers.get('X-Total', len(projects)),
            "page": page,
            "per_page": per_page
        }

    def get_commits(self, project_id: str, branch: str, since: datetime, until: datetime) -> List[Dict]:
        """获取提交列表"""
        url = f"{self.api_base}/projects/{project_id}/repository/commits"
        headers = {"PRIVATE-TOKEN": self.token}
        params = {
            "ref_name": branch,
            "since": since.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "until": until.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "with_stats": True,
            "per_page": 100
        }

        all_commits = []
        page = 1

        while True:
            params["page"] = page
            try:
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
                response.raise_for_status()
                commits = response.json()
                if not commits:
                    break
                all_commits.extend(commits)
                if len(commits) < params["per_page"]:
                    break
                page += 1
            except requests.RequestException as e:
                raise Exception(f"获取 commits 失败: {e}")

        return all_commits

    def get_ai_notes(self, project_id: str, commit_sha: str) -> Optional[Dict]:
        """获取 AI Notes 数据 (refs/notes/ai)"""
        url = f"{self.api_base}/projects/{project_id}/repository/files/{commit_sha}"
        headers = {"PRIVATE-TOKEN": self.token}
        params = {"ref": "refs/notes/ai"}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()

            if "content" in data:
                content = base64.b64decode(data["content"]).decode('utf-8')
                if "---" in content:
                    json_part = content.split("---", 1)[1].strip()
                else:
                    json_part = content.strip()
                try:
                    return json.loads(json_part)
                except json.JSONDecodeError:
                    return None
            return None
        except Exception:
            return None

    def validate_connection(self) -> bool:
        """验证连接"""
        try:
            url = f"{self.api_base}/user"
            headers = {"PRIVATE-TOKEN": self.token}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return True
        except Exception:
            return False
```

**Step 2: 编写工厂类**

```python
# core/git_providers/factory.py
from typing import Dict
from .base import GitProvider
from .gitlab import GitLabProvider


def create_provider(config: Dict) -> GitProvider:
    """创建 Git Provider 实例"""
    git_config = config.get('git', config)
    provider_type = git_config.get('type', 'gitlab')

    # 根据类型获取对应的配置子节点
    provider_config = git_config.get(provider_type, git_config)
    provider_config['type'] = provider_type

    if provider_type == 'gitlab':
        return GitLabProvider(provider_config)
    elif provider_type == 'github':
        # 待实现
        raise NotImplementedError("GitHub provider not yet implemented")
    else:
        raise ValueError(f"Unsupported provider: {provider_type}")


# 重新导出
__all__ = ['create_provider', 'GitProvider', 'GitLabProvider']
```

**Step 3: 更新 core/git_providers/__init__.py**

```python
# core/git_providers/__init__.py
from .base import GitProvider
from .factory import create_provider
from .gitlab import GitLabProvider

__all__ = ['GitProvider', 'create_provider', 'GitLabProvider']
```

**Step 4: 编写测试（使用 mock）**

```python
# tests/unit/test_git_providers/test_gitlab.py
from unittest.mock import Mock, patch
import pytest
from datetime import datetime
from core.git_providers.gitlab import GitLabProvider


@pytest.fixture
def mock_gitlab_provider():
    config = {
        'base_url': 'https://gitlab.example.com',
        'private_token': 'test_token',
        'api_timeout': 30
    }
    return GitLabProvider(config)


@patch('requests.get')
def test_get_commits(mock_get, mock_gitlab_provider):
    # Arrange
    mock_response = Mock()
    mock_response.json.return_value = [
        {
            'id': 'abc123',
            'author_name': 'John',
            'created_at': '2026-03-11T10:00:00Z',
            'stats': {'additions': 100, 'deletions': 20}
        }
    ]
    mock_response.raise_for_status = Mock()
    mock_response.headers = {}
    mock_get.return_value = mock_response

    # Act
    commits = mock_gitlab_provider.get_commits(
        '123', 'main',
        datetime(2026, 3, 1), datetime(2026, 3, 11)
    )

    # Assert
    assert len(commits) == 1
    assert commits[0]['id'] == 'abc123'
    assert commits[0]['stats']['additions'] == 100


@patch('requests.get')
def test_get_ai_notes(mock_get, mock_gitlab_provider):
    # Arrange
    import base64
    notes_data = {"prompts": {"prompt1": {"accepted_lines": 50}}}
    notes_json = json.dumps(notes_data)
    notes_b64 = base64.b64encode(notes_json.encode()).decode()

    mock_response = Mock()
    mock_response.json.return_value = {
        "file_name": "abc123",
        "content": notes_b64
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Act
    notes = mock_gitlab_provider.get_ai_notes('123', 'abc123')

    # Assert
    assert notes is not None
    assert 'prompts' in notes
    assert notes['prompts']['prompt1']['accepted_lines'] == 50
```

**Step 5: 运行测试**

```bash
pytest tests/unit/test_git_providers/test_gitlab.py -v
```
预期: PASS 所有测试

**Step 6: 提交**

```bash
git add core/git_providers/{gitlab.py,factory.py} core/git_providers/__init__.py tests/unit/test_git_providers/test_gitlab.py
git commit -m "feat: 实现 GitLab Provider 和工厂模式"
```

---

## Task 5: Database 抽象基类

**Files:**
- Create: `core/database/base.py`
- Test: `tests/unit/test_database/test_base.py`

**Step 1: 编写抽象基类**

```python
# core/database/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
from core.models.stats import StatRecord, RepoStatRecord, ContributorStatRecord


class Database(ABC):
    """数据库抽象基类"""

    def __init__(self, config: Dict):
        self.config = config

    @abstractmethod
    def init_db(self) -> None:
        """初始化数据库表结构"""
        pass

    @abstractmethod
    def save_stats(self, stats: StatRecord) -> str:
        """保存统计数据，返回统计记录 ID"""
        pass

    @abstractmethod
    def get_latest_stat(self) -> Optional[Dict]:
        """获取最新的统计记录"""
        pass

    @abstractmethod
    def get_stats_history(self, start: Optional[datetime] = None,
                         end: Optional[datetime] = None,
                         limit: int = 100) -> List[Dict]:
        """获取统计数据历史记录"""
        pass

    @abstractmethod
    def get_stat_by_id(self, stat_id: str) -> Optional[Dict]:
        """根据 ID 获取单条统计记录"""
        pass

    @abstractmethod
    def get_repo_stats(self, stat_id: Optional[str] = None,
                      repo_name: Optional[str] = None) -> List[RepoStatRecord]:
        """获取仓库级统计数据"""
        pass

    @abstractmethod
    def get_contributor_stats(self, stat_id: Optional[str] = None,
                              author_email: Optional[str] = None) -> List[ContributorStatRecord]:
        """获取贡献者级统计数据"""
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """验证数据库连接"""
        pass
```

**Step 2: 编写测试**

```python
# tests/unit/test_database/test_base.py
import pytest
from core.database.base import Database


def test_database_is_abstract():
    """Database 应该是抽象类，不能直接实例化"""
    with pytest.raises(TypeError):
        Database({})
```

**Step 3: 运行测试**

```bash
pytest tests/unit/test_database/test_base.py -v
```
预期: PASS - 测试确认抽象类不能直接实例化

**Step 4: 提交**

```bash
git add core/database/base.py tests/unit/test_database/test_base.py
git commit -m "feat: 新增 Database 抽象基类"
```

---

## Task 6: SQLite Database 实现

**Files:**
- Create: `core/database/sqlite.py`
- Create: `core/database/factory.py`
- Test: `tests/unit/test_database/test_sqlite.py`

**Step 1: 编写 SQLite 实现**

```python
# core/database/sqlite.py
import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from .base import Database
from core.models.stats import StatRecord, RepoStatRecord, ContributorStatRecord


class SQLiteDatabase(Database):
    """SQLite 数据库实现"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.db_path = config.get('path', 'data/ai_stats.db')
        _ensure_db_directory(self.db_path)

    def _get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)

    def init_db(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS stat_records (
                    id TEXT PRIMARY KEY,
                    timestamp INTEGER NOT NULL,
                    total_lines INTEGER DEFAULT 0,
                    total_ai_lines INTEGER DEFAULT 0,
                    overall_percentage REAL DEFAULT 0,
                    total_commits INTEGER DEFAULT 0,
                    commits_with_ai INTEGER DEFAULT 0,
                    start_date INTEGER,
                    end_date INTEGER,
                    repos_count INTEGER DEFAULT 0
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS repo_stat_records (
                    id TEXT PRIMARY KEY,
                    stat_id TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    repo_id TEXT NOT NULL,
                    provider_type TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    total_commits INTEGER DEFAULT 0,
                    commits_with_ai INTEGER DEFAULT 0,
                    start_date INTEGER,
                    end_date INTEGER,
                    commit_details TEXT,
                    FOREIGN KEY (stat_id) REFERENCES stat_records(id)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS contributor_stat_records (
                    id TEXT PRIMARY KEY,
                    stat_id TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    author_email TEXT NOT NULL,
                    total_commits INTEGER DEFAULT 0,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    repos_breakdown TEXT,
                    start_date INTEGER,
                    end_date INTEGER,
                    FOREIGN KEY (stat_id) REFERENCES stat_records(id)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS repo_contributor_stat_records (
                    id TEXT PRIMARY KEY,
                    stat_id TEXT NOT NULL,
                    repo_stat_id TEXT NOT NULL,
                    contributor_stat_id TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    repo_id TEXT NOT NULL,
                    provider_type TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    author_email TEXT NOT NULL,
                    total_commits INTEGER DEFAULT 0,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    start_date INTEGER,
                    end_date INTEGER,
                    commit_details TEXT,
                    FOREIGN KEY (stat_id) REFERENCES stat_records(id)
                )
            ''')

            # 创建索引
            conn.execute('CREATE INDEX IF NOT EXISTS idx_stat_timestamp ON stat_records(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_repo_stat_id ON repo_stat_records(stat_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_contributor_stat_id ON contributor_stat_records(stat_id)')

    def save_stats(self, stats: StatRecord) -> str:
        """保存统计数据"""
        stat_id = stats.id or str(uuid.uuid4())

        with self._get_connection() as conn:
            # 保存主记录
            conn.execute('''
                INSERT OR REPLACE INTO stat_records
                (id, timestamp, total_lines, total_ai_lines, overall_percentage,
                 total_commits, commits_with_ai, start_date, end_date, repos_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stat_id,
                int(stats.timestamp.timestamp()),
                stats.total_lines,
                stats.total_ai_lines,
                stats.overall_percentage,
                stats.total_commits,
                stats.commits_with_ai,
                int(stats.start_date.timestamp()) if stats.start_date else None,
                int(stats.end_date.timestamp()) if stats.end_date else None,
                stats.repos_count
            ))
            conn.commit()

        return stat_id

    def get_latest_stat(self) -> Optional[Dict]:
        """获取最新的统计记录"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM stat_records ORDER BY timestamp DESC LIMIT 1'
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def get_stats_history(self, start: Optional[datetime] = None,
                         end: Optional[datetime] = None,
                         limit: int = 100) -> List[Dict]:
        """获取统计历史记录"""
        query = 'SELECT * FROM stat_records'
        params = []

        conditions = []
        if start:
            conditions.append('timestamp >= ?')
            params.append(int(start.timestamp()))
        if end:
            conditions.append('timestamp <= ?')
            params.append(int(end.timestamp()))

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_stat_by_id(self, stat_id: str) -> Optional[Dict]:
        """根据 ID 获取单条统计记录"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM stat_records WHERE id = ?', (stat_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def get_repo_stats(self, stat_id: Optional[str] = None,
                      repo_name: Optional[str] = None) -> List[RepoStatRecord]:
        """获取仓库级统计数据"""
        query = 'SELECT * FROM repo_stat_records'
        params = []
        conditions = []

        if stat_id:
            conditions.append('stat_id = ?')
            params.append(stat_id)
        if repo_name:
            conditions.append('repo_name = ?')
            params.append(repo_name)

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            records = []
            for row in cursor.fetchall():
                record = self._row_to_dict(row)
                # 解析 JSON 字段
                if record.get('commit_details'):
                    record['commit_details'] = json.loads(record['commit_details'])
                records.append(RepoStatRecord(**record))
            return records

    def get_contributor_stats(self, stat_id: Optional[str] = None,
                              author_email: Optional[str] = None) -> List[ContributorStatRecord]:
        """获取贡献者级统计数据"""
        query = 'SELECT * FROM contributor_stat_records'
        params = []
        conditions = []

        if stat_id:
            conditions.append('stat_id = ?')
            params.append(stat_id)
        if author_email:
            conditions.append('author_email = ?')
            params.append(author_email)

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            records = []
            for row in cursor.fetchall():
                record = self._row_to_dict(row)
                if record.get('repos_breakdown'):
                    record['repos_breakdown'] = json.loads(record['repos_breakdown'])
                records.append(ContributorStatRecord(**record))
            return records

    def validate_connection(self) -> bool:
        """验证数据库连接"""
        try:
            with self._get_connection() as conn:
                conn.execute('SELECT 1')
                return True
        except Exception:
            return False

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """将 SQLite Row 转换为 Dict"""
        return dict(row)


def _ensure_db_directory(db_path: str):
    """确保数据库目录存在"""
    import os
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
```

**Step 2: 编写工厂类**

```python
# core/database/factory.py
from typing import Dict
from .base import Database
from .sqlite import SQLiteDatabase


def create_database(config: Dict) -> Database:
    """创建数据库实例"""
    db_config = config.get('database', config)
    db_type = db_config.get('type', 'sqlite')

    # 根据类型获取对应的配置子节点
    database_config = db_config.get(db_type, db_config)
    database_config['type'] = db_type

    if db_type == 'sqlite':
        return SQLiteDatabase(database_config)
    elif db_type == 'postgresql':
        # 待实现
        raise NotImplementedError("PostgreSQL database not yet implemented")
    elif db_type == 'mysql':
        # 待实现
        raise NotImplementedError("MySQL database not yet implemented")
    else:
        raise ValueError(f"Unsupported database: {db_type}")


# 重新导出
__all__ = ['create_database', 'Database', 'SQLiteDatabase']
```

**Step 3: 更新 core/database/__init__.py**

```python
# core/database/__init__.py
from .base import Database
from .factory import create_database
from .sqlite import SQLiteDatabase

__all__ = ['Database', 'create_database', 'SQLiteDatabase']
```

**Step 4: 编写测试**

```python
# tests/unit/test_database/test_sqlite.py
import pytest
import os
import tempfile
from datetime import datetime
from core.database.sqlite import SQLiteDatabase
from core.models.stats import StatRecord


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    config = {'path': path}
    db = SQLiteDatabase(config)
    db.init_db()
    yield db
    # 清理
    os.unlink(path)


def test_init_db(temp_db):
    """测试数据库初始化"""
    # 检查表是否存在
    assert temp_db.validate_connection()


def test_save_and_get_stats(temp_db):
    """测试保存和获取统计数据"""
    # Arrange
    stat = StatRecord(
        id="test-id",
        timestamp=datetime.now(),
        total_lines=1000,
        total_ai_lines=500,
        overall_percentage=50.0,
        total_commits=10,
        commits_with_ai=5,
        repos_count=2
    )

    # Act
    stat_id = temp_db.save_stats(stat)

    # Assert
    assert stat_id == "test-id"
    latest = temp_db.get_latest_stat()
    assert latest is not None
    assert latest['id'] == "test-id"
    assert latest['total_lines'] == 1000
    assert latest['total_ai_lines'] == 500


def test_get_stats_history(temp_db):
    """测试获取历史记录"""
    # 创建多条记录
    for i in range(3):
        stat = StatRecord(
            id=f"stat-{i}",
            timestamp=datetime(2026, 3, 10 + i),
            total_lines=100,
            total_ai_lines=50
        )
        temp_db.save_stats(stat)

    # 获取历史记录
    history = temp_db.get_stats_history(limit=2)

    # 验证
    assert len(history) == 2
    assert history[0]['id'] == "stat-2"  # 最新的在前
    assert history[1]['id'] == "stat-1"
```

**Step 5: 运行测试**

```bash
pytest tests/unit/test_database/test_sqlite.py -v
```
预期: PASS 所有测试

**Step 6: 提交**

```bash
git add core/database/{sqlite.py,factory.py} core/database/__init__.py tests/unit/test_database/test_sqlite.py
git commit -m "feat: 实现 SQLite 数据库"
```

---

## Task 7: 配置加载器

**Files:**
- Create: `core/config/loader.py`
- Create: `config.yaml`
- Test: `tests/unit/test_config/test_loader.py`

**Step 1: 创建示例配置文件**

```yaml
# config.yaml
# 功能开关
features:
  enabled: true
  auto_stats: true

# Git 平台配置
git:
  type: gitlab
  gitlab:
    base_url: https://gitlab.com
    private_token: ${GITLAB_PRIVATE_TOKEN}
    api_timeout: 30
  github:
    base_url: https://api.github.com
    token: ${GITHUB_TOKEN}
    api_timeout: 30

# 数据库配置
database:
  type: sqlite
  sqlite:
    path: data/ai_stats.db
  postgresql:
    host: localhost
    port: 5432
    database: ai_stats
    user: postgres
    password: ${DB_PASSWORD}
    pool_size: 5

# 仓库配置
repos:
  enabled_repos:
    - id: "123456"
      name: "my-project"
      branch: "main"
      provider: gitlab
  departments:
    前端:
      - id: "111"
        name: "web-app"
        branch: "main"
    后端:
      - id: "222"
        name: "api-server"
        branch: "master"

# 定时任务配置
scheduler:
  enabled: true
  timezone: Asia/Shanghai
  jobs:
    - id: daily_stats
      name: 每日统计
      type: cron
      cron: "0 2 * * *"
      params:
        lookback_days: 1

# Web 服务配置
web:
  host: 0.0.0.0
  port: 8888
  debug: false

# 日志配置
logging:
  level: INFO
  file: logs/app.log
  max_bytes: 10485760
  backup_count: 5
```

**Step 2: 编写配置加载器**

```python
# core/config/loader.py
import yaml
import os
from typing import Dict, Any


class ConfigLoader:
    """配置文件加载器"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """加载配置文件并处理环境变量"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 递归处理环境变量替换
        self._replace_env_vars(self.config)

        # 验证配置
        self._validate_config()

        return self.config

    def _replace_env_vars(self, obj: Any) -> Any:
        """递归替换配置中的环境变量占位符"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                obj[key] = self._replace_env_vars(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = self._replace_env_vars(item)
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_var = obj[2:-1]
            default_value = None
            if ":" in env_var:
                env_var, default_value = env_var.split(":", 1)
            return os.getenv(env_var, default_value)
        return obj

    def _validate_config(self) -> None:
        """验证配置完整性"""
        if not self.config.get('features', {}).get('enabled'):
            raise ValueError("Features not enabled")

        git_type = self.config.get('git', {}).get('type')
        if git_type not in ['gitlab', 'github']:
            raise ValueError(f"Unsupported git provider: {git_type}")

        db_type = self.config.get('database', {}).get('type')
        if db_type not in ['postgresql', 'mysql', 'sqlite']:
            raise ValueError(f"Unsupported database: {db_type}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的路径"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
```

**Step 3: 更新 core/config/__init__.py**

```python
# core/config/__init__.py
from .loader import ConfigLoader

__all__ = ['ConfigLoader']
```

**Step 4: 编写测试**

```python
# tests/unit/test_config/test_loader.py
import pytest
import os
import tempfile
import yaml
import json
from core.config.loader import ConfigLoader


@pytest.fixture
def temp_config_file():
    """创建临时配置文件"""
    fd, path = tempfile.mkstemp(suffix='.yaml')
    config_data = {
        'features': {'enabled': True, 'auto_stats': True},
        'git': {'type': 'gitlab', 'gitlab': {'base_url': 'https://gitlab.com', 'private_token': '${TEST_TOKEN}'}},
        'database': {'type': 'sqlite', 'sqlite': {'path': 'data/test.db'}}
    }
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f)
    os.close(fd)
    yield path
    os.unlink(path)


def test_load_config(temp_config_file):
    """测试配置加载"""
    loader = ConfigLoader(temp_config_file)
    config = loader.load()

    assert config['features']['enabled'] is True
    assert config['git']['type'] == 'gitlab'
    assert config['database']['type'] == 'sqlite'


def test_get_config_value(temp_config_file):
    """测试获取配置值"""
    os.environ['TEST_TOKEN'] = 'test-token-123'
    loader = ConfigLoader(temp_config_file)
    config = loader.load()

    assert loader.get('features.enabled') is True
    assert loader.get('git.type') == 'gitlab'
    assert loader.get('git.gitlab.private_token') == 'test-token-123'
    assert loader.get('non.existent.key', 'default') == 'default'


def test_invalid_config():
    """测试无效配置"""
    fd, path = tempfile.mkstemp(suffix='.yaml')
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump({'features': {'enabled': False}, 'git': {'type': 'unknown'}}, f)
    os.close(fd)

    loader = ConfigLoader(path)
    with pytest.raises(ValueError):
        loader.load()

    os.unlink(path)
```

**Step 5: 运行测试**

```bash
pytest tests/unit/test_config/test_loader.py -v
```
预期: PASS 所有测试

**Step 6: 提交**

```bash
git add core/config/loader.py core/config/__init__.py config.yaml tests/unit/test_config/test_loader.py
git commit -m "feat: 添加配置加载器和示例配置文件"
```

---

## Task 8: 调度器实现

**Files:**
- Create: `core/scheduler/scheduler.py`
- Create: `core/scheduler/stats_task.py`
- Test: `tests/unit/test_scheduler/test_scheduler.py`

**Step 1: 编写调度器**

```python
# core/scheduler/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from typing import Callable, Dict, Optional


class AICodeScheduler:
    """AI 代码统计定时任务调度器"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.jobs: Dict[str, Dict] = {}  # job_id -> {func, config}
        self.is_running = False

    def start(self) -> None:
        """启动调度器"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True

    def stop(self) -> None:
        """停止调度器"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False

    def add_cron_job(self, job_id: str, func: Callable,
                    cron_expr: str, **kwargs) -> None:
        """添加 Cron 表达式任务"""
        minute, hour, day, month, day_of_week = cron_expr.split()

        self.scheduler.add_job(
            func=func,
            trigger=CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week
            ),
            id=job_id,
            **kwargs
        )
        self.jobs[job_id] = {'func': func, 'type': 'cron', 'expr': cron_expr}

    def add_interval_job(self, job_id: str, func: Callable,
                        minutes: Optional[int] = None,
                        hours: Optional[int] = None,
                        days: Optional[int] = None) -> None:
        """添加间隔执行任务"""
        self.scheduler.add_job(
            func=func,
            trigger=IntervalTrigger(
                minutes=minutes,
                hours=hours,
                days=days
            ),
            id=job_id
        )
        self.jobs[job_id] = {
            'func': func,
            'type': 'interval',
            'interval': {'minutes': minutes, 'hours': hours, 'days': days}
        }

    def remove_job(self, job_id: str) -> bool:
        """移除任务"""
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.jobs:
                del self.jobs[job_id]
            return True
        except Exception:
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """获取任务状态"""
        job = self.scheduler.get_job(job_id)
        if job:
            return {
                'id': job.id,
                'next_run_time': job.next_run_time,
                'trigger': str(job.trigger)
            }
        return None

    def get_all_jobs(self) -> List[Dict]:
        """获取所有任务列表"""
        return [
            {
                'id': job.id,
                'next_run_time': job.next_run_time,
                'trigger': str(job.trigger)
            }
            for job in self.scheduler.get_jobs()
        ]
```

**Step 2: 编写统计任务执行器**

```python
# core/scheduler/stats_task.py
from typing import Dict
from datetime import datetime, timedelta
from core.git_providers.factory import create_provider
from core.database.factory import create_database
from core.models.stats import StatRecord, RepoStatRecord


class AICodeStatsTask:
    """AI 代码统计任务执行器"""

    def __init__(self, config: Dict):
        self.config = config
        self.git_provider = create_provider(config)
        self.database = create_database(config)
        self.repos_config = config.get('repos', [])

    def execute(self) -> Dict:
        """执行统计任务"""
        # 1. 从数据库获取上次统计时间
        latest = self.database.get_latest_stat()

        # 2. 确定统计时间范围
        if latest:
            start_date = latest.get('timestamp')
            if isinstance(start_date, (int, float)):
                start_date = datetime.fromtimestamp(start_date)
        else:
            start_date = datetime.now() - timedelta(days=30)

        end_date = datetime.now()

        # 3. 获取仓库列表
        repos = self._get_repos_to_analyze()

        if not repos:
            return {'success': False, 'error': 'No repos to analyze'}

        # 4. 执行统计
        results = self._calculate_stats(repos, start_date, end_date)

        # 5. 保存结果
        stat_record = StatRecord(
            id=None,
            timestamp=datetime.now(),
            total_lines=results['total_lines'],
            total_ai_lines=results['total_ai_lines'],
            overall_percentage=results['overall_percentage'],
            total_commits=results['total_commits'],
            commits_with_ai=results['commits_with_ai'],
            start_date=start_date,
            end_date=end_date,
            repos_count=len(repos)
        )

        stat_id = self.database.save_stats(stat_record)

        # 6. 保存仓库级统计
        for repo_stat in results['repo_details']:
            repo_record = RepoStatRecord(
                id=None,
                stat_id=stat_id,
                repo_name=repo_stat['name'],
                repo_id=str(repo_stat.get('repo_id', '')),
                provider_type=self.config['git']['type'],
                branch=repo_stat.get('branch', 'main'),
                total_lines=repo_stat['total_lines'],
                ai_lines=repo_stat['ai_lines'],
                ai_percentage=repo_stat['percentage'],
                total_commits=repo_stat['total_commits'],
                commits_with_ai=repo_stat.get('commits_with_ai', 0),
                start_date=start_date,
                end_date=end_date,
                commit_details=repo_stat.get('commit_details', [])
            )
            self.database.save_repo_stat(repo_record)

        return {
            'success': True,
            'stat_id': stat_id,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'results': results
        }

    def _get_repos_to_analyze(self) -> list:
        """获取需要分析的仓库列表"""
        all_repos = []

        # 从 enabled_repos 获取
        if 'enabled_repos' in self.repos_config:
            all_repos.extend(self.repos_config['enabled_repos'])

        # 从 departments 获取
        if 'departments' in self.repos_config:
            for dept_repos in self.repos_config['departments'].values():
                all_repos.extend(dept_repos)

        return all_repos

    def _calculate_stats(self, repos: list, start_date: datetime, end_date: datetime) -> Dict:
        """计算统计数据"""
        total_lines = 0
        total_ai_lines = 0
        commits_with_ai = 0
        total_commits = 0
        repo_details = []

        for repo in repos:
            repo_name = repo.get('name', 'unknown')
            branch = repo.get('branch', 'main')

            # 获取 commits
            try:
                commits = self.git_provider.get_commits(
                    repo['id'], branch, start_date, end_date
                )
            except Exception as e:
                print(f"获取仓库 {repo_name} 的 commits 失败: {e}")
                continue

            repo_total_lines = 0
            repo_ai_lines = 0
            repo_commits_with_ai = 0
            commit_details = []

            for commit in commits:
                total_commits += 1
                commit_sha = commit['id']
                stats = commit.get('stats', {})
                additions = stats.get('additions', 0)
                repo_total_lines += additions

                notes = self.git_provider.get_ai_notes(repo['id'], commit_sha)
                commit_ai_lines = 0
                if notes and 'prompts' in notes:
                    for prompt_data in notes['prompts'].values():
                        accepted_lines = prompt_data.get('accepted_lines', 0)
                        commit_ai_lines += accepted_lines
                        repo_ai_lines += accepted_lines
                    if commit_ai_lines > 0:
                        repo_commits_with_ai += 1

                commit_details.append({
                    'sha': commit_sha[:8],
                    'short_sha': commit_sha[:8],
                    'full_sha': commit_sha,
                    'message': commit.get('message', '').split('\n')[0][:100],
                    'author': commit.get('author_name', 'Unknown'),
                    'date': commit.get('created_at', ''),
                    'additions': additions,
                    'ai_lines': commit_ai_lines
                })

            total_lines += repo_total_lines
            total_ai_lines += repo_ai_lines
            commits_with_ai += repo_commits_with_ai

            repo_percentage = (repo_ai_lines / repo_total_lines * 100) if repo_total_lines > 0 else 0
            repo_details.append({
                'name': repo_name,
                'repo_id': repo['id'],
                'branch': branch,
                'total_lines': repo_total_lines,
                'ai_lines': repo_ai_lines,
                'percentage': round(repo_percentage, 2),
                'total_commits': len(commits),
                'commits_with_ai': repo_commits_with_ai,
                'commit_details': commit_details
            })

        overall_percentage = (total_ai_lines / total_lines * 100) if total_lines > 0 else 0

        return {
            'total_lines': total_lines,
            'total_ai_lines': total_ai_lines,
            'overall_percentage': round(overall_percentage, 2),
            'total_commits': total_commits,
            'commits_with_ai': commits_with_ai,
            'repo_details': repo_details
        }
```

**Step 3: 更新 core/scheduler/__init__.py**

```python
# core/scheduler/__init__.py
from .scheduler import AICodeScheduler
from .stats_task import AICodeStatsTask

__all__ = ['AICodeScheduler', 'AICodeStatsTask']
```

**Step 4: 在 Database 接口添加 save_repo_stat 方法**

```python
# 编辑 core/database/base.py，添加新方法

    @abstractmethod
    def save_repo_stat(self, repo_stat: RepoStatRecord) -> str:
        """保存仓库统计数据，返回记录 ID"""
        pass
```

**Step 5: 更新 SQLite 实现**

```python
# 编辑 core/database/sqlite.py，添加 save_repo_stat 方法

    def save_repo_stat(self, repo_stat: RepoStatRecord) -> str:
        """保存仓库统计数据"""
        stat_id = repo_stat.id or str(uuid.uuid4())

        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO repo_stat_records
                (id, stat_id, repo_name, repo_id, provider_type, branch,
                 total_lines, ai_lines, ai_percentage, total_commits, commits_with_ai,
                 start_date, end_date, commit_details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stat_id,
                repo_stat.stat_id,
                repo_stat.repo_name,
                repo_stat.repo_id,
                repo_stat.provider_type,
                repo_stat.branch,
                repo_stat.total_lines,
                repo_stat.ai_lines,
                repo_stat.ai_percentage,
                repo_stat.total_commits,
                repo_stat.commits_with_ai,
                int(repo_stat.start_date.timestamp()) if repo_stat.start_date else None,
                int(repo_stat.end_date.timestamp()) if repo_stat.end_date else None,
                json.dumps(repo_stat.commit_details) if repo_stat.commit_details else None
            ))
            conn.commit()

        return stat_id
```

**Step 6: 编写测试**

```python
# tests/unit/test_scheduler/test_stats_task.py
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from core.scheduler.stats_task import AICodeStatsTask


@pytest.fixture
def mock_config():
    return {
        'git': {
            'type': 'gitlab',
            'gitlab': {
                'base_url': 'https://gitlab.example.com',
                'private_token': 'test_token'
            }
        },
        'database': {
            'type': 'sqlite',
            'sqlite': {'path': ':memory:'}
        },
        'repos': {
            'enabled_repos': [
                {'id': '123', 'name': 'test-repo', 'branch': 'main'}
            ]
        }
    }


def test_get_repos_to_analyze(mock_config):
    """测试获取仓库列表"""
    task = AICodeStatsTask(mock_config)
    repos = task._get_repos_to_analyze()

    assert len(repos) == 1
    assert repos[0]['name'] == 'test-repo'
    assert repos[0]['id'] == '123'


@patch('core.git_providers.factory.create_provider')
def test_calculate_stats(mock_create_provider, mock_config):
    """测试统计数据计算"""
    # Mock provider
    mock_provider = Mock()
    mock_provider.get_commits.return_value = [
        {
            'id': 'abc123',
            'author_name': 'John',
            'created_at': '2026-03-11T10:00:00Z',
            'stats': {'additions': 100, 'deletions': 20}
        }
    ]
    mock_provider.get_ai_notes.return_value = {
        'prompts': {'p1': {'accepted_lines': 50}}
    }
    mock_create_provider.return_value = mock_provider

    task = AICodeStatsTask(mock_config)
    start_date = datetime(2026, 3, 1)
    end_date = datetime(2026, 3, 11)

    results = task._calculate_stats(
        [{'id': '123', 'name': 'test-repo', 'branch': 'main'}],
        start_date,
        end_date
    )

    assert results['total_lines'] == 100
    assert results['total_ai_lines'] == 50
    assert results['overall_percentage'] == 50.0
    assert len(results['repo_details']) == 1
```

**Step 7: 运行测试**

```bash
pytest tests/unit/test_scheduler/test_stats_task.py -v
```
预期: PASS 所有测试

**Step 8: 提交**

```bash
git add core/scheduler/{scheduler.py,stats_task.py} core/scheduler/__init__.py
git add core/database/base.py core/database/sqlite.py tests/unit/test_scheduler/
git commit -m "feat: 实现调度器和统计任务执行器"
```

---

## Task 9: Web API 路由

**Files:**
- Create: `api/routes/stats.py`
- Create: `api/routes/projects.py`
- Create: `api/routes/scheduler.py`
- Create: `api/schemas/stats.py`

**Step 1: 编写统计 API**

```python
# api/routes/stats.py
from flask import Blueprint, request, jsonify
from datetime import datetime
from core.scheduler.stats_task import AICodeStatsTask
from core.config.loader import ConfigLoader

stats_bp = Blueprint('stats', __name__, url_prefix='/api/v1/stats')

# 全局配置
config_loader = ConfigLoader()
config = config_loader.load()


@stats_bp.route('/analyze', methods=['POST'])
def analyze():
    """执行统计分析"""
    try:
        data = request.get_json()
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        if not start_date_str or not end_date_str:
            return jsonify({'success': False, 'error': '请提供开始和结束日期'}), 400

        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

        # 获取仓库列表
        selected_departments = data.get('departments', [])
        repos = _get_filtered_repos(config, selected_departments)

        if not repos:
            return jsonify({'success': False, 'error': '未配置任何仓库或选中的部门没有仓库'}), 400

        # 执行统计
        task = AICodeStatsTask(config)
        results = task._calculate_stats(repos, start_date, end_date)

        return jsonify({'success': True, 'data': results})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@stats_bp.route('/latest', methods=['GET'])
def get_latest():
    """获取最新统计结果"""
    try:
        from core.database.factory import create_database
        db = create_database(config)
        latest = db.get_latest_stat()

        if latest is None:
            return jsonify({'success': False, 'error': '暂无统计数据'}), 404

        return jsonify({'success': True, 'data': latest})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@stats_bp.route('/history', methods=['GET'])
def get_history():
    """获取统计历史记录"""
    try:
        from core.database.factory import create_database
        from datetime import datetime

        db = create_database(config)
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        limit = int(request.args.get('limit', 100))

        start = datetime.fromisoformat(start_str) if start_str else None
        end = datetime.fromisoformat(end_str) if end_str else None

        history = db.get_stats_history(start, end, limit)

        return jsonify({'success': True, 'data': history})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@stats_bp.route('/<stat_id>', methods=['GET'])
def get_stat_by_id(stat_id: str):
    """获取指定统计详情"""
    try:
        from core.database.factory import create_database
        db = create_database(config)
        stat = db.get_stat_by_id(stat_id)

        if stat is None:
            return jsonify({'success': False, 'error': '统计记录不存在'}), 404

        return jsonify({'success': True, 'data': stat})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _get_filtered_repos(config, selected_departments):
    """根据部门过滤仓库"""
    repos_config = config.get('repos', {})
    all_repos = []

    if 'enabled_repos' in repos_config:
        all_repos.extend(repos_config['enabled_repos'])

    if 'departments' in repos_config:
        if selected_departments:
            for dept in selected_departments:
                if dept in repos_config['departments']:
                    all_repos.extend(repos_config['departments'][dept])
        else:
            for dept_repos in repos_config['departments'].values():
                all_repos.extend(dept_repos)

    return all_repos
```

**Step 2: 编写项目 API**

```python
# api/routes/projects.py
from flask import Blueprint, jsonify
from core.config.loader import ConfigLoader

projects_bp = Blueprint('projects', __name__, url_prefix='/api/v1/projects')

config_loader = ConfigLoader()
config = config_loader.load()


@projects_bp.route('/', methods=['GET'])
def get_projects():
    """获取项目列表（按部门分组）"""
    try:
        repos_config = config.get('repos', {})

        departments = []
        repos_by_department = {}
        all_repos = []

        if 'departments' in repos_config:
            departments = list(repos_config['departments'].keys())
            repos_by_department = repos_config['departments']
            for dept_repos in repos_by_department.values():
                all_repos.extend(dept_repos)

        if 'enabled_repos' in repos_config:
            all_repos.extend(repos_config['enabled_repos'])

        return jsonify({
            'success': True,
            'data': {
                'departments': departments,
                'repos_by_department': repos_by_department,
                'all_repos': all_repos
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/departments', methods=['GET'])
def get_departments():
    """获取部门列表"""
    try:
        repos_config = config.get('repos', {})
        departments = list(repos_config.get('departments', {}).keys())

        return jsonify({
            'success': True,
            'data': {'departments': departments}
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 3: 编写调度管理 API**

```python
# api/routes/scheduler.py
from flask import Blueprint, jsonify
from core.scheduler.scheduler import AICodeScheduler

scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/api/v1/scheduler')

# 全局调度器实例
_global_scheduler = None


def get_scheduler():
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = AICodeScheduler()
    return _global_scheduler


@scheduler_bp.route('/jobs', methods=['GET'])
def get_jobs():
    """获取所有任务"""
    try:
        scheduler = get_scheduler()
        jobs = scheduler.get_all_jobs()

        return jsonify({
            'success': True,
            'data': {'jobs': jobs}
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scheduler_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id: str):
    """获取任务状态"""
    try:
        scheduler = get_scheduler()
        job = scheduler.get_job_status(job_id)

        if job is None:
            return jsonify({'success': False, 'error': '任务不存在'}), 404

        return jsonify({
            'success': True,
            'data': job
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 4: 更新 api/routes/__init__.py**

```python
# api/routes/__init__.py
from .stats import stats_bp
from .projects import projects_bp
from .scheduler import scheduler_bp

__all__ = ['stats_bp', 'projects_bp', 'scheduler_bp']
```

**Step 5: 提交**

```bash
git add api/routes/ api/schemas/
git commit -m "feat: 添加 Web API 路由"
```

---

## Task 10: 更新主应用

**Files:**
- Modify: `app.py`
- Update: `requirements.txt`

**Step 1: 更新 app.py**

```python
# app.py
"""
Git AI 代码统计 - 独立 Web 应用 v2.0
统计 GitLab/GitHub 仓库中 AI 生成代码的占比。
"""
from flask import Flask, send_from_directory
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 添加项目根目录到 path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 加载配置
from core.config.loader import ConfigLoader
config_loader = ConfigLoader()
config = config_loader.load()

# 创建 Flask 应用
app = Flask(__name__, static_folder='static', template_folder='templates')

# 注册 API 蓝图
from api.routes.stats import stats_bp
from api.routes.projects import projects_bp
from api.routes.scheduler import scheduler_bp

app.register_blueprint(stats_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(scheduler_bp)

# 启动调度器（如果配置启用）
if config.get('scheduler.enabled', False):
    from core.scheduler import AICodeScheduler, AICodeStatsTask

    scheduler = AICodeScheduler()
    scheduler.start()

    # 添加定时任务
    for job_config in config.get('scheduler.jobs', []):
        task = AICodeStatsTask(config)

        if job_config.get('type') == 'cron':
            scheduler.add_cron_job(
                job_config['id'],
                task.execute,
                job_config['cron']
            )
        elif job_config.get('type') == 'interval':
            scheduler.add_interval_job(
                job_config['id'],
                task.execute,
                **job_config.get('interval', {})
            )


@app.route('/')
def index():
    """首页"""
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/health')
def health():
    """健康检查"""
    return {'status': 'ok', 'version': '2.0.0'}


if __name__ == '__main__':
    web_config = config.get('web', {})
    port = web_config.get('port', 8888)
    host = web_config.get('host', '0.0.0.0')
    debug = web_config.get('debug', False)

    print(f'Git AI 代码统计工具 v2.0: http://{host}:{port}')
    print(f'健康检查: http://{host}:{port}/health')

    app.run(debug=debug, port=port, host=host)
```

**Step 2: 更新 requirements.txt**

```
flask>=3.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
requests>=2.28.0
apscheduler>=3.10.0
dataclasses-json>=0.6.0
```

**Step 3: 创建 .env.example**

```bash
# .env.example

# GitLab 配置
GITLAB_PRIVATE_TOKEN=your_gitlab_token_here

# GitHub 配置（可选）
GITHUB_TOKEN=your_github_token_here

# 数据库配置（如果使用 PostgreSQL/MySQL）
DB_PASSWORD=your_db_password_here
```

**Step 4: 更新 .gitignore**

```
# 数据文件
data/*.db
data/*.sqlite

# 日志文件
logs/*.log

# 环境变量
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
dist/
build/

# 测试
.pytest_cache/
.coverage
htmlcov/

# IDE
.vscode/
.idea/
*.swp
*.swo
```

**Step 5: 提交**

```bash
git add app.py requirements.txt .env.example .gitignore
git commit -m "refactor: 更新主应用和配置文件"
```

---

## Task 11: 集成测试

**Files:**
- Create: `tests/integration/test_api.py`

**Step 1: 编写集成测试**

```python
# tests/integration/test_api.py
import pytest
from app import app


@pytest.fixture
def client():
    """测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    """测试健康检查"""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'


def test_get_projects(client):
    """测试获取项目列表"""
    response = client.get('/api/v1/projects/')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data


def test_get_departments(client):
    """测试获取部门列表"""
    response = client.get('/api/v1/projects/departments')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data


def test_get_scheduler_jobs(client):
    """测试获取调度任务"""
    response = client.get('/api/v1/scheduler/jobs')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_analyze_missing_dates(client):
    """测试缺少日期参数"""
    response = client.post('/api/v1/stats/analyze', json={})
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
```

**Step 2: 运行集成测试**

```bash
pytest tests/integration/test_api.py -v
```
预期: PASS 所有测试（注意：需要有有效的 config.yaml）

**Step 3: 提交**

```bash
git add tests/integration/test_api.py
git commit -m "test: 添加 API 集成测试"
```

---

## Task 12: 文档更新

**Files:**
- Create: `docs/README.md`
- Update: `README.md`

**Step 1: 创建 docs/README.md**

```markdown
# 文档

## 设计文档

- [架构设计文档](plans/2026-03-11-architecture-design.md)
- [实现计划](plans/2026-03-11-refactor-implementation.md)

## API 文档

### 统计分析 API

- `POST /api/v1/stats/analyze` - 执行统计分析
- `GET /api/v1/stats/latest` - 获取最新统计结果
- `GET /api/v1/stats/history` - 获取统计历史记录
- `GET /api/v1/stats/{stat_id}` - 获取指定统计详情

### 项目管理 API

- `GET /api/v1/projects/` - 获取项目列表
- `GET /api/v1/projects/departments` - 获取部门列表

### 调度管理 API

- `GET /api/v1/scheduler/jobs` - 获取所有任务
- `GET /api/v1/scheduler/jobs/{job_id}` - 获取任务状态
```

**Step 2: 创建新的 README.md**

```markdown
# Git AI 代码统计工具 v2.0

团队使用了 Cursor、Copilot 等 AI 工具写代码，本工具基于 Git Notes (`refs/notes/ai`) 统计 AI 生成代码的占比。

## 新版本特性

- 支持多 Git 平台（GitLab、GitHub）
- 支持多数据库
- 定时任务自动统计
- YAML 配置文件管理
- 历史数据查询和趋势分析

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，配置必要的密钥
```

### 3. 配置应用

编辑 `config.yaml` 文件，配置 Git 平台、数据库、仓库信息等。

### 4. 启动服务

```bash
python app.py
```

访问 http://127.0.0.1:8888

## 配置说明

详见 [config.yaml](../config.yaml) 文件。

## API 文档

详见 [API 文档](README.md)。

## 项目结构

```
git-ai-code-metrics/
├── app.py              # 应用入口
├── config.yaml         # 配置文件
├── core/               # 核心模块
├── api/                # API 路由
├── data/               # 数据目录
├── logs/               # 日志目录
└── tests/              # 测试
```

## License

MIT
```

**Step 3: 提交**

```bash
git add docs/ README.md
git commit -m "docs: 更新项目文档"
```

---

## 实现完成

所有任务已完成！项目已成功改造为工程化架构。

### 参考文档

- 架构设计: `docs/plans/2026-03-11-architecture-design.md`
- 实现计划: `docs/plans/2026-03-11-refactor-implementation.md`

### 下一步

1. 运行测试确保所有功能正常
2. 手动测试 Web 界面和 API
3. 根据需要添加更多测试用例
4. 考虑添加 Docker 部署支持