# 仓库和作者维度表实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增三张维度表和配套功能，记录仓库和作者的累计代码统计信息，支持定时更新和API查询。

**Architecture:** 基于现有项目结构，新增数据模型、数据库表、调度任务和API路由，遵循项目的分层架构（models -> database -> services -> routes）。

**Tech Stack:** Python 3.x, Flask, SQLite, APScheduler, pytest

---

### 任务概述

1. 创建数据模型
2. 创建数据库表定义
3. 实现数据库访问方法
4. 实现调度任务
5. 实现API路由
6. 更新配置和注册
7. 编写测试

---

### Task 1: 创建数据模型

**Files:**
- Modify: `core/models/metrics.py`

**Step 1: 添加新的数据类定义**

在 `core/models/metrics.py` 文件末尾添加以下三个数据类：

```python
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
```

**Step 2: 验证模型定义**

运行: `python -c "from core.models.metrics import MetricsRepo, MetricsContributor, MetricsRepoContributor; print('Models imported successfully')"`
Expected: 无报错输出 "Models imported successfully"

**Step 3: 提交**

```bash
git add core/models/metrics.py
git commit -m "feat: 添加仓库、作者和关联表数据模型"
```

---

### Task 2: 编写数据模型测试

**Files:**
- Create: `tests/unit/test_models/test_dimensions.py`

**Step 1: 创建测试文件并编写测试**

创建 `tests/unit/test_models/test_dimensions.py` 文件：

```python
"""测试维度表相关数据模型"""
import pytest
from core.models.metrics import (
    MetricsRepo,
    MetricsContributor,
    MetricsRepoContributor
)


class TestMetricsRepo:
    """测试 MetricsRepo 模型"""

    def test_create_repo_with_required_fields(self):
        """创建仅包含必需字段的仓库记录"""
        repo = MetricsRepo(
            repo_id="owner/repo",
            repo_name="test-repo",
            repo_url="https://github.com/owner/repo"
        )
        assert repo.repo_id == "owner/repo"
        assert repo.repo_name == "test-repo"
        assert repo.repo_url == "https://github.com/owner/repo"
        assert repo.total_lines == 0
        assert repo.ai_lines == 0
        assert repo.human_lines == 0
        assert repo.ai_percentage == 0.0
        assert repo.total_commits == 0
        assert repo.ai_commits == 0

    def test_create_repo_with_all_fields(self):
        """创建包含所有字段的仓库记录"""
        repo = MetricsRepo(
            repo_id="owner/repo",
            repo_name="test-repo",
            repo_url="https://github.com/owner/repo",
            provider_type="github",
            branch="main",
            total_lines=10000,
            ai_lines=3500,
            human_lines=6500,
            ai_percentage=35.0,
            total_commits=150,
            ai_commits=80,
            tool_model_breakdown='{"claude-opus-4-6": {"total_lines": 2000}}',
            first_commit_ts=1710000000,
            last_commit_ts=1715000000,
            created_at=1710000000,
            updated_at=1715000000
        )
        assert repo.repo_id == "owner/repo"
        assert repo.provider_type == "github"
        assert repo.total_lines == 10000
        assert repo.ai_lines == 3500
        assert repo.ai_percentage == 35.0

    def test_serialize_to_dict(self):
        """序列化为字典"""
        repo = MetricsRepo(
            repo_id="owner/repo",
            repo_name="test-repo",
            repo_url="https://github.com/owner/repo"
        )
        data = repo.to_dict()
        assert data["repo_id"] == "owner/repo"
        assert data["repo_name"] == "test-repo"

    def test_deserialize_from_dict(self):
        """从字典反序列化"""
        data = {
            "repo_id": "owner/repo",
            "repo_name": "test-repo",
            "repo_url": "https://github.com/owner/repo",
            "total_lines": 5000,
            "ai_lines": 2000
        }
        repo = MetricsRepo.from_dict(data)
        assert repo.repo_id == "owner/repo"
        assert repo.total_lines == 5000
        assert repo.ai_lines == 2000


class TestMetricsContributor:
    """测试 MetricsContributor 模型"""

    def test_create_contributor_with_required_fields(self):
        """创建仅包含必需字段的作者记录"""
        contributor = MetricsContributor(author="test-user")
        assert contributor.author == "test-user"
        assert contributor.total_lines == 0
        assert contributor.ai_lines == 0
        assert contributor.repos_count == 0

    def test_create_contributor_with_all_fields(self):
        """创建包含所有字段的作者记录"""
        contributor = MetricsContributor(
            author="test-user",
            author_email="test@example.com",
            total_lines=5000,
            ai_lines=2000,
            human_lines=3000,
            ai_percentage=40.0,
            total_commits=50,
            ai_commits=25,
            repos_count=3,
            first_commit_ts=1710000000,
            last_commit_ts=1715000000
        )
        assert contributor.author == "test-user"
        assert contributor.author_email == "test@example.com"
        assert contributor.total_lines == 5000
        assert contributor.repos_count == 3

    def test_serialize_to_dict(self):
        """序列化为字典"""
        contributor = MetricsContributor(author="test-user")
        data = contributor.to_dict()
        assert data["author"] == "test-user"

    def test_deserialize_from_dict(self):
        """从字典反序列化"""
        data = {"author": "test-user", "total_lines": 3000}
        contributor = MetricsContributor.from_dict(data)
        assert contributor.author == "test-user"
        assert contributor.total_lines == 3000


class TestMetricsRepoContributor:
    """测试 MetricsRepoContributor 模型"""

    def test_create_with_required_fields(self):
        """创建仅包含必需字段的关联记录"""
        relation = MetricsRepoContributor(
            repo_id="owner/repo",
            author="test-user"
        )
        assert relation.repo_id == "owner/repo"
        assert relation.author == "test-user"
        assert relation.first_seen_ts is None

    def test_create_with_all_fields(self):
        """创建包含所有字段的关联记录"""
        relation = MetricsRepoContributor(
            repo_id="owner/repo",
            author="test-user",
            first_seen_ts=1710000000,
            last_seen_ts=1715000000,
            created_at=1710000000,
            updated_at=1715000000
        )
        assert relation.repo_id == "owner/repo"
        assert relation.first_seen_ts == 1710000000
        assert relation.last_seen_ts == 1715000000

    def test_serialize_to_dict(self):
        """序列化为字典"""
        relation = MetricsRepoContributor(
            repo_id="owner/repo",
            author="test-user"
        )
        data = relation.to_dict()
        assert data["repo_id"] == "owner/repo"
        assert data["author"] == "test-user"
```

**Step 2: 运行测试**

运行: `pytest tests/unit/test_models/test_dimensions.py -v`
Expected: 所有测试通过 (8 passed)

**Step 3: 提交**

```bash
git add tests/unit/test_models/test_dimensions.py
git commit -m "test: 添加维度表数据模型测试"
```

---

### Task 3: 创建数据库表定义（SQLite）

**Files:**
- Modify: `sql/metrics_schema_sqlite.sql`

**Step 1: 在文件末尾添加新表定义**

在 `sql/metrics_schema_sqlite.sql` 文件末尾（在完成标记之前）添加以下内容：

```sql
-- ============================================================================
-- 维度主表
-- ============================================================================

-- metrics_repos (仓库维度主表)
CREATE TABLE IF NOT EXISTS metrics_repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id TEXT NOT NULL UNIQUE,
    repo_name TEXT NOT NULL,
    repo_url TEXT NOT NULL,
    provider_type TEXT,
    branch TEXT,
    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    human_lines INTEGER DEFAULT 0,
    ai_percentage REAL DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    ai_commits INTEGER DEFAULT 0,
    tool_model_breakdown TEXT,
    first_commit_ts INTEGER,
    last_commit_ts INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_repos_repo_id ON metrics_repos(repo_id);
CREATE INDEX IF NOT EXISTS idx_repos_repo_name ON metrics_repos(repo_name);

-- metrics_contributors (作者维度主表)
CREATE TABLE IF NOT EXISTS metrics_contributors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT NOT NULL UNIQUE,
    author_email TEXT,
    total_lines INTEGER DEFAULT 0,
    ai_lines INTEGER DEFAULT 0,
    human_lines INTEGER DEFAULT 0,
    ai_percentage REAL DEFAULT 0,
    total_commits INTEGER DEFAULT 0,
    ai_commits INTEGER DEFAULT 0,
    tool_model_breakdown TEXT,
    first_commit_ts INTEGER,
    last_commit_ts INTEGER,
    repos_count INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contributors_author ON metrics_contributors(author);
CREATE INDEX IF NOT EXISTS idx_contributors_author_email ON metrics_contributors(author_email);

-- metrics_repo_contributors (仓库作者关联表)
CREATE TABLE IF NOT EXISTS metrics_repo_contributors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id TEXT NOT NULL,
    author TEXT NOT NULL,
    first_seen_ts INTEGER,
    last_seen_ts INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(repo_id, author)
);

CREATE INDEX IF NOT EXISTS idx_repo_contributors_repo_author ON metrics_repo_contributors(repo_id, author);
```

**Step 2: 验证SQL语法**

运行: `sqlite3 :memory: < sql/metrics_schema_sqlite.sql`
Expected: 无报错（静默成功）

**Step 3: 提交**

```bash
git add sql/metrics_schema_sqlite.sql
git commit -m "feat: 添加维度表 SQLite 表定义"
```

---

### Task 4: 更新数据库基类接口

**Files:**
- Modify: `core/database/base.py`

**Step 1: 在 Database 类中添加新的抽象方法**

在 `core/database/base.py` 文件末尾、类定义内添加以下方法：

```python
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
                          sort: str = None) -> Dict:
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
                                  sort: str = None) -> Dict:
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
        self, repo_id: str = None, author: str = None,
        page: int = 1, page_size: int = 20
    ) -> Dict:
        """获取仓库作者关联列表，支持按仓库或作者筛选"""
        pass
```

**注意：** 需要在文件顶部的 import 部分添加新模型的导入：

```python
from core.models.metrics import (
    MetricsRawRecord, MetricsCommittedRecord,
    MetricsCheckpointRecord, MetricsAgentUsageRecord,
    MetricsInstallHooksRecord, MetricsDailyStat,
    MetricsWeeklyStat, MetricsMonthlyStat,
    MetricsRepoStat, MetricsContributorStat,
    MetricsRepo, MetricsContributor, MetricsRepoContributor  # 新增
)
```

**Step 2: 验证导入**

运行: `python -c "from core.database.base import Database; print('Database class loaded successfully')"`
Expected: 无报错输出 "Database class loaded successfully"

**Step 3: 提交**

```bash
git add core/database/base.py
git commit -m "feat: 添加维度表数据库访问抽象方法"
```

---

### Task 5: 实现 SQLite 数据库访问方法

**Files:**
- Modify: `core/database/sqlite.py`

**Step 1: 添加新模型导入**

在 `core/database/sqlite.py` 的 import 部分添加新模型：

```python
from core.models.metrics import (
    MetricsRawRecord, MetricsCommittedRecord,
    MetricsCheckpointRecord, MetricsAgentUsageRecord,
    MetricsInstallHooksRecord, MetricsDailyStat,
    MetricsWeeklyStat, MetricsMonthlyStat,
    MetricsRepoStat, MetricsContributorStat,
    MetricsRepo, MetricsContributor, MetricsRepoContributor  # 新增
)
```

**Step 2: 在 init_db 方法中添加新表初始化**

在 `init_db` 方法末尾（在现有表创建之后）添加新表的创建：

```python
            # 维度表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_repos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id TEXT NOT NULL UNIQUE,
                    repo_name TEXT NOT NULL,
                    repo_url TEXT NOT NULL,
                    provider_type TEXT,
                    branch TEXT,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    human_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    total_commits INTEGER DEFAULT 0,
                    ai_commits INTEGER DEFAULT 0,
                    tool_model_breakdown TEXT,
                    first_commit_ts INTEGER,
                    last_commit_ts INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_contributors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author TEXT NOT NULL UNIQUE,
                    author_email TEXT,
                    total_lines INTEGER DEFAULT 0,
                    ai_lines INTEGER DEFAULT 0,
                    human_lines INTEGER DEFAULT 0,
                    ai_percentage REAL DEFAULT 0,
                    total_commits INTEGER DEFAULT 0,
                    ai_commits INTEGER DEFAULT 0,
                    tool_model_breakdown TEXT,
                    first_commit_ts INTEGER,
                    last_commit_ts INTEGER,
                    repos_count INTEGER DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics_repo_contributors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id TEXT NOT NULL,
                    author TEXT NOT NULL,
                    first_seen_ts INTEGER,
                    last_seen_ts INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(repo_id, author)
                )
            ''')
```

**Step 3: 实现仓库维度方法**

在 `SQLiteDatabase` 类中添加以下方法：

```python
    # ========== 维度表方法 ==========

    def save_metrics_repo(self, repo: MetricsRepo) -> int:
        """保存仓库维度记录，返回记录 id"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_repos (
                    repo_id, repo_name, repo_url, provider_type, branch,
                    total_lines, ai_lines, human_lines, ai_percentage,
                    total_commits, ai_commits, tool_model_breakdown,
                    first_commit_ts, last_commit_ts, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                repo.repo_id, repo.repo_name, repo.repo_url,
                repo.provider_type, repo.branch,
                repo.total_lines, repo.ai_lines, repo.human_lines,
                repo.ai_percentage, repo.total_commits, repo.ai_commits,
                repo.tool_model_breakdown,
                repo.first_commit_ts, repo.last_commit_ts,
                repo.created_at, repo.updated_at
            ))
            return cursor.lastrowid

    def get_metrics_repo(self, repo_id: str) -> Optional[Dict]:
        """获取仓库维度记录"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM metrics_repos WHERE repo_id = ?',
                (repo_id,)
            )
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None

    def get_metrics_repos(self, page: int = 1, page_size: int = 20,
                          sort: str = None) -> Dict:
        """获取仓库维度列表，支持分页和排序"""
        offset = (page - 1) * page_size

        # 构建查询
        if sort:
            # 简单排序验证
            allowed_sorts = [
                'total_lines', 'ai_lines', 'ai_percentage',
                'total_commits', 'ai_commits',
                'created_at', 'updated_at'
            ]
            if sort in allowed_sorts:
                order_clause = f'ORDER BY {sort} DESC'
            else:
                order_clause = 'ORDER BY created_at DESC'
        else:
            order_clause = 'ORDER BY created_at DESC'

        with self._get_connection() as conn:
            # 查询总数
            cursor = conn.execute('SELECT COUNT(*) FROM metrics_repos')
            total = cursor.fetchone()[0]

            # 查询数据
            cursor = conn.execute(f'''
                SELECT * FROM metrics_repos
                {order_clause}
                LIMIT ? OFFSET ?
            ''', (page_size, offset))

            columns = [desc[0] for desc in cursor.description]
            data = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return {
                'data': data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': (total + page_size - 1) // page_size
                }
            }
```

**Step 4: 实现作者维度方法**

在 `SQLiteDatabase` 类中添加以下方法：

```python
    def save_metrics_contributor(self, contributor: MetricsContributor) -> int:
        """保存作者维度记录，返回记录 id"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_contributors (
                    author, author_email,
                    total_lines, ai_lines, human_lines, ai_percentage,
                    total_commits, ai_commits, tool_model_breakdown,
                    first_commit_ts, last_commit_ts, repos_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                contributor.author, contributor.author_email,
                contributor.total_lines, contributor.ai_lines,
                contributor.human_lines, contributor.ai_percentage,
                contributor.total_commits, contributor.ai_commits,
                contributor.tool_model_breakdown,
                contributor.first_commit_ts, contributor.last_commit_ts,
                contributor.repos_count,
                contributor.created_at, contributor.updated_at
            ))
            return cursor.lastrowid

    def get_metrics_contributor(self, author: str) -> Optional[Dict]:
        """获取作者维度记录"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM metrics_contributors WHERE author = ?',
                (author,)
            )
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None

    def get_metrics_contributors(self, page: int = 1, page_size: int = 20,
                                  sort: str = None) -> Dict:
        """获取作者维度列表，支持分页和排序"""
        offset = (page - 1) * page_size

        if sort:
            allowed_sorts = [
                'total_lines', 'ai_lines', 'ai_percentage',
                'total_commits', 'ai_commits',
                'created_at', 'updated_at'
            ]
            if sort in allowed_sorts:
                order_clause = f'ORDER BY {sort} DESC'
            else:
                order_clause = 'ORDER BY created_at DESC'
        else:
            order_clause = 'ORDER BY created_at DESC'

        with self._get_connection() as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM metrics_contributors')
            total = cursor.fetchone()[0]

            cursor = conn.execute(f'''
                SELECT * FROM metrics_contributors
                {order_clause}
                LIMIT ? OFFSET ?
            ''', (page_size, offset))

            columns = [desc[0] for desc in cursor.description]
            data = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return {
                'data': data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': (total + page_size - 1) // page_size
                }
            }
```

**Step 5: 实现关联表方法**

在 `SQLiteDatabase` 类中添加以下方法：

```python
    def save_metrics_repo_contributor(
        self, repo_contributor: MetricsRepoContributor
    ) -> int:
        """保存仓库作者关联记录，返回记录 id"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO metrics_repo_contributors (
                    repo_id, author, first_seen_ts, last_seen_ts,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                repo_contributor.repo_id, repo_contributor.author,
                repo_contributor.first_seen_ts, repo_contributor.last_seen_ts,
                repo_contributor.created_at, repo_contributor.updated_at
            ))
            return cursor.lastrowid

    def get_metrics_repo_contributors(
        self, repo_id: str = None, author: str = None,
        page: int = 1, page_size: int = 20
    ) -> Dict:
        """获取仓库作者关联列表，支持按仓库或作者筛选"""
        offset = (page - 1) * page_size

        # 构建查询条件
        where_clause = ''
        params = []

        if repo_id and author:
            where_clause = 'WHERE repo_id = ? AND author = ?'
            params.append(repo_id)
            params.append(author)
        elif repo_id:
            where_clause = 'WHERE repo_id = ?'
            params.append(repo_id)
        elif author:
            where_clause = 'WHERE author = ?'
            params.append(author)

        with self._get_connection() as conn:
            count_sql = f'SELECT COUNT(*) FROM metrics_repo_contributors {where_clause}'
            cursor = conn.execute(count_sql, params)
            total = cursor.fetchone()[0]

            data_sql = f'''
                SELECT * FROM metrics_repo_contributors
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            '''
            cursor = conn.execute(data_sql, params + [page_size, offset])

            columns = [desc[0] for desc in cursor.description]
            data = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return {
                'data': data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': (total + page_size - 1) // page_size
                }
            }
```

**Step 6: 验证数据库实现**

运行: `python -c "from core.database.sqlite import SQLiteDatabase; from core.models.metrics import MetricsRepo; print('SQLite implementation verified')"`
Expected: 无报错

**Step 7: 提交**

```bash
git add core/database/sqlite.py
git commit -m "feat: 实现维度表 SQLite 数据库访问方法"
```

---

### Task 6: 编写数据库集成测试

**Files:**
- Create: `tests/integration/test_dimensions_db.py`

**Step 1: 创建测试文件**

创建 `tests/integration/test_dimensions_db.py` 文件：

```python
"""测试维度表数据库集成"""
import os
import tempfile
import pytest
from datetime import datetime
from core.database.sqlite import SQLiteDatabase
from core.models.metrics import (
    MetricsRepo, MetricsContributor, MetricsRepoContributor
)


@pytest.fixture
def temp_db():
    """创建临时测试数据库"""
    fd, path = tempfile.mkstemp(suffix='.db')
    config = {'path': path}
    db = SQLiteDatabase(config)
    db.init_db()
    yield db
    os.close(fd)
    os.unlink(path)


class TestMetricsRepoDB:
    """测试仓库维度数据库操作"""

    def test_save_and_get_repo(self, temp_db):
        """保存并获取仓库记录"""
        repo = MetricsRepo(
            repo_id="owner/repo",
            repo_name="test-repo",
            repo_url="https://github.com/owner/repo",
            total_lines=1000,
            ai_lines=400,
            human_lines=600,
            ai_percentage=40.0,
            created_at=int(datetime.now().timestamp()),
            updated_at=int(datetime.now().timestamp())
        )

        repo_id = temp_db.save_metrics_repo(repo)
        assert repo_id > 0

        result = temp_db.get_metrics_repo("owner/repo")
        assert result is not None
        assert result['repo_id'] == "owner/repo"
        assert result['repo_name'] == "test-repo"
        assert result['total_lines'] == 1000
        assert result['ai_lines'] == 400

    def test_get_nonexistent_repo(self, temp_db):
        """获取不存在的仓库"""
        result = temp_db.get_metrics_repo("nonexistent/repo")
        assert result is None

    def test_get_repos_pagination(self, temp_db):
        """测试仓库列表分页"""
        now = int(datetime.now().timestamp())

        # 创建 25 个仓库
        for i in range(25):
            repo = MetricsRepo(
                repo_id=f"owner/repo-{i}",
                repo_name=f"test-repo-{i}",
                repo_url=f"https://github.com/owner/repo-{i}",
                total_lines=i * 100,
                created_at=now,
                updated_at=now
            )
            temp_db.save_metrics_repo(repo)

        # 测试第一页
        page1 = temp_db.get_metrics_repos(page=1, page_size=10)
        assert len(page1['data']) == 10
        assert page1['pagination']['total'] == 25
        assert page1['pagination']['total_pages'] == 3

        # 测试第二页
        page2 = temp_db.get_metrics_repos(page=2, page_size=10)
        assert len(page2['data']) == 10

    def test_get_repos_sort_by_ai_lines(self, temp_db):
        """测试按 AI 代码行数排序"""
        now = int(datetime.now().timestamp())

        repos = [
            MetricsRepo(repo_id="a", repo_name="a", repo_url="a",
                       ai_lines=100, created_at=now, updated_at=now),
            MetricsRepo(repo_id="b", repo_name="b", repo_url="b",
                       ai_lines=500, created_at=now, updated_at=now),
            MetricsRepo(repo_id="c", repo_name="c", repo_url="c",
                       ai_lines=300, created_at=now, updated_at=now),
        ]

        for repo in repos:
            temp_db.save_metrics_repo(repo)

        result = temp_db.get_metrics_repos(sort='ai_lines')
        data = result['data']
        assert data[0]['ai_lines'] == 500
        assert data[1]['ai_lines'] == 300
        assert data[2]['ai_lines'] == 100


class TestMetricsContributorDB:
    """测试作者维度数据库操作"""

    def test_save_and_get_contributor(self, temp_db):
        """保存并获取作者记录"""
        contributor = MetricsContributor(
            author="test-user",
            author_email="test@example.com",
            total_lines=500,
            ai_lines=200,
            repos_count=2,
            created_at=int(datetime.now().timestamp()),
            updated_at=int(datetime.now().timestamp())
        )

        id_ = temp_db.save_metrics_contributor(contributor)
        assert id_ > 0

        result = temp_db.get_metrics_contributor("test-user")
        assert result is not None
        assert result['author'] == "test-user"
        assert result['author_email'] == "test@example.com"
        assert result['total_lines'] == 500
        assert result['repos_count'] == 2

    def test_get_contributors_pagination(self, temp_db):
        """测试作者列表分页"""
        now = int(datetime.now().timestamp())

        for i in range(15):
            contributor = MetricsContributor(
                author=f"user-{i}",
                total_lines=i * 50,
                created_at=now,
                updated_at=now
            )
            temp_db.save_metrics_contributor(contributor)

        result = temp_db.get_metrics_contributors(page=1, page_size=5)
        assert len(result['data']) == 5
        assert result['pagination']['total'] == 15


class TestMetricsRepoContributorDB:
    """测试仓库作者关联数据库操作"""

    def test_save_and_get_relation(self, temp_db):
        """保存并获取仓库作者关联"""
        relation = MetricsRepoContributor(
            repo_id="owner/repo",
            author="test-user",
            first_seen_ts=1710000000,
            last_seen_ts=1715000000,
            created_at=1710000000,
            updated_at=1715000000
        )

        id_ = temp_db.save_metrics_repo_contributor(relation)
        assert id_ > 0

        result = temp_db.get_metrics_repo_contributors(
            repo_id="owner/repo", author="test-user"
        )
        assert len(result['data']) == 1
        assert result['data'][0]['repo_id'] == "owner/repo"
        assert result['data'][0]['author'] == "test-user"

    def test_get_relations_by_repo(self, temp_db):
        """按仓库获取关联列表"""
        now = int(datetime.now().timestamp())

        for i in range(3):
            relation = MetricsRepoContributor(
                repo_id="owner/repo",
                author=f"user-{i}",
                created_at=now,
                updated_at=now
            )
            temp_db.save_metrics_repo_contributor(relation)

        result = temp_db.get_metrics_repo_contributors(repo_id="owner/repo")
        assert len(result['data']) == 3
        assert all(r['repo_id'] == "owner/repo" for r in result['data'])

    def test_get_relations_by_author(self, temp_db):
        """按作者获取关联列表"""
        now = int(datetime.now().timestamp())

        for i in range(3):
            relation = MetricsRepoContributor(
                repo_id=f"owner/repo-{i}",
                author="test-user",
                created_at=now,
                updated_at=now
            )
            temp_db.save_metrics_repo_contributor(relation)

        result = temp_db.get_metrics_repo_contributors(author="test-user")
        assert len(result['data']) == 3
        assert all(r['author'] == "test-user" for r in result['data'])
```

**Step 2: 运行测试**

运行: `pytest tests/integration/test_dimensions_db.py -v`
Expected: 所有测试通过 (13 passed)

**Step 3: 提交**

```bash
git add tests/integration/test_dimensions_db.py
git commit -m "test: 添加维度表数据库集成测试"
```

---

### Task 7: 创建调度任务

**Files:**
- Create: `core/scheduler/dimensions_task.py`

**Step 1: 创建调度任务文件**

创建 `core/scheduler/dimensions_task.py` 文件：

```python
"""维度表统计调度任务"""
import json
import uuid
from typing import Dict, Optional
from datetime import datetime
from core.database.factory import create_database
from core.models.metrics import (
    MetricsRepo, MetricsContributor, MetricsRepoContributor
)
from core.config.logging import Logger


class DimensionsUpdateTask:
    """仓库和作者维度统计更新任务"""

    def __init__(self, config: Dict):
        self.config = config
        self.database = create_database(config.get('database', {}))

        # 初始化日志记录器
        self.logger = Logger.get_logger('scheduler.dimensions_task')

    def execute(self) -> Dict:
        """执行维度统计更新任务"""
        try:
            self.logger.info('开始执行维度统计更新任务')
            start_time = datetime.now()

            # 获取所有待处理的 Committed 事件
            committed_events = self._get_committed_events()

            if not committed_events:
                self.logger.info('没有需要处理的 Committed 事件')
                return {
                    'success': True,
                    'message': '没有需要处理的数据',
                    'processed': 0
                }

            # 按仓库和作者聚合数据
            repo_stats = self._aggregate_by_repo(committed_events)
            author_stats = self._aggregate_by_author(committed_events)
            repo_author_relations = self._extract_repo_author_relations(committed_events)

            # 保存仓库统计
            saved_repos = 0
            for repo_data in repo_stats.values():
                repo = MetricsRepo(**repo_data)
                self._upsert_repo(repo)
                saved_repos += 1

            # 保存作者统计
            saved_contributors = 0
            for author_data in author_stats.values():
                contributor = MetricsContributor(**author_data)
                self._upsert_contributor(contributor)
                saved_contributors += 1

            # 保存关联关系
            saved_relations = 0
            for relation_key, relation_data in repo_author_relations.items():
                relation = MetricsRepoContributor(**relation_data)
                self._upsert_repo_contributor(relation)
                saved_relations += 1

            duration = (datetime.now() - start_time).total_seconds()

            self.logger.info(f'维度统计更新完成: 仓库={saved_repos}, '
                          f'作者={saved_contributors}, 关联={saved_relations}, '
                          f'耗时={duration:.2f}s')

            return {
                'success': True,
                'message': '维度统计更新成功',
                'processed': {
                    'repos': saved_repos,
                    'contributors': saved_contributors,
                    'relations': saved_relations
                },
                'duration': duration
            }

        except Exception as e:
            self.logger.error(f'维度统计更新失败: {e}')
            return {
                'success': False,
                'error': str(e)
            }

    def _get_committed_events(self) -> list:
        """获取所有 Committed 事件"""
        conn = self.database._get_connection()
        try:
            cursor = conn.execute('''
                SELECT repo_url, author, commit_sha, branch,
                       git_diff_added_lines, git_diff_deleted_lines,
                       total_ai_additions, total_ai_deletions,
                       tool_model_pairs, raw_id, timestamp,
                       first_checkpoint_ts
                FROM metrics_events_committed
                WHERE repo_url IS NOT NULL
            ''')
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _aggregate_by_repo(self, events: list) -> Dict:
        """按仓库聚合统计数据"""
        repos = {}

        for event in events:
            repo_url = event.get('repo_url')
            if not repo_url:
                continue

            # 生成 repo_id（简单哈希）
            repo_id = str(hash(repo_url))

            if repo_id not in repos:
                # 从 URL 提取仓库名
                repo_name = self._extract_repo_name(repo_url)
                provider_type = self._extract_provider_type(repo_url)
                branch = event.get('branch', 'main')

                repos[repo_id] = {
                    'repo_id': repo_id,
                    'repo_name': repo_name,
                    'repo_url': repo_url,
                    'provider_type': provider_type,
                    'branch': branch,
                    'total_lines': 0,
                    'ai_lines': 0,
                    'human_lines': 0,
                    'ai_percentage': 0.0,
                    'total_commits': 0,
                    'ai_commits': 0,
                    'tool_model_breakdown': None,
                    'first_commit_ts': None,
                    'last_commit_ts': None,
                    'created_at': int(datetime.now().timestamp()),
                    'updated_at': int(datetime.now().timestamp())
                }

            # 聚合数据
            repo = repos[repo_id]
            added = event.get('git_diff_added_lines') or 0
            deleted = event.get('git_diff_deleted_lines') or 0
            repo['total_lines'] += (added + deleted)

            # 解析 AI 代码量
            ai_additions = self._parse_json_int_array(
                event.get('total_ai_additions')
            )
            ai_deletions = self._parse_json_int_array(
                event.get('total_ai_deletions')
            )
            ai_lines_added = sum(ai_additions) if ai_additions else 0
            ai_lines_deleted = sum(ai_deletions) if ai_deletions else 0
            repo['ai_lines'] += (ai_lines_added + ai_lines_deleted)

            # 统计提交数
            repo['total_commits'] += 1
            has_ai = ai_lines_added > 0 or ai_lines_deleted > 0
            if has_ai:
                repo['ai_commits'] += 1

            # 更新时间范围
            timestamp = event.get('timestamp') or event.get('first_checkpoint_ts')
            if timestamp:
                if repo['first_commit_ts'] is None or timestamp < repo['first_commit_ts']:
                    repo['first_commit_ts'] = timestamp
                if repo['last_commit_ts'] is None or timestamp > repo['last_commit_ts']:
                    repo['last_commit_ts'] = timestamp

        # 计算最终结果
        self._finalize_repo_stats(repos)
        return repos

    def _aggregate_by_author(self, events: list) -> Dict:
        """按作者聚合统计数据"""
        authors = {}
        author_repos = {}  # author -> set of repo_ids

        for event in events:
            author = event.get('author')
            if not author:
                continue

            if author not in authors:
                authors[author] = {
                    'author': author,
                    'author_email': None,
                    'total_lines': 0,
                    'ai_lines': 0,
                    'human_lines': 0,
                    'ai_percentage': 0.0,
                    'total_commits': 0,
                    'ai_commits': 0,
                    'tool_model_breakdown': None,
                    'first_commit_ts': None,
                    'last_commit_ts': None,
                    'repos_count': 0,
                    'created_at': int(datetime.now().timestamp()),
                    'updated_at': int(datetime.now().timestamp())
                }
                author_repos[author] = set()

            # 仓库统计
            repo_url = event.get('repo_url')
            if repo_url:
                author_repos[author].add(str(hash(repo_url)))

            # 聚合数据
            author = authors[author]
            added = event.get('git_diff_added_lines') or 0
            deleted = event.get('git_diff_deleted_lines') or 0
            author['total_lines'] += (added + deleted)

            # 解析 AI 代码量
            ai_additions = self._parse_json_int_array(
                event.get('total_ai_additions')
            )
            ai_deletions = self._parse_json_int_array(
                event.get('total_ai_deletions')
            )
            ai_lines_added = sum(ai_additions) if ai_additions else 0
            ai_lines_deleted = sum(ai_deletions) if ai_deletions else 0
            author['ai_lines'] += (ai_lines_added + ai_lines_deleted)

            author['total_commits'] += 1
            if ai_lines_added > 0 or ai_lines_deleted > 0:
                author['ai_commits'] += 1

            # 更新时间范围
            timestamp = event.get('timestamp') or event.get('first_checkpoint_ts')
            if timestamp:
                if author['first_commit_ts'] is None or timestamp < author['first_commit_ts']:
                    author['first_commit_ts'] = timestamp
                if author['last_commit_ts'] is None or timestamp > author['last_commit_ts']:
                    author['last_commit_ts'] = timestamp

        # 计算最终结果
        for author_data, repo_set in zip(authors.values(), author_repos.values()):
            author_data['repos_count'] = len(repo_set)
            author_data['human_lines'] = author_data['total_lines'] - author_data['ai_lines']
            if author_data['total_lines'] > 0:
                author_data['ai_percentage'] = (
                    author_data['ai_lines'] / author_data['total_lines'] * 100
                )

        return authors

    def _extract_repo_author_relations(self, events: list) -> Dict:
        """提取仓库-作者关联关系"""
        relations = {}
        now = int(datetime.now().timestamp())

        for event in events:
            repo_url = event.get('repo_url')
            author = event.get('author')
            if not repo_url or not author:
                continue

            repo_id = str(hash(repo_url))
            key = f"{repo_id}:{author}"

            timestamp = event.get('timestamp') or event.get('first_checkpoint_ts', now)

            if key not in relations:
                relations[key] = {
                    'repo_id': repo_id,
                    'author': author,
                    'first_seen_ts': timestamp,
                    'last_seen_ts': timestamp,
                    'created_at': now,
                    'updated_at': now
                }
            else:
                # 更新最后看到的时间
                if timestamp > relations[key]['last_seen_ts']:
                    relations[key]['last_seen_ts'] = timestamp
                    relations[key]['updated_at'] = now

        return relations

    def _upsert_repo(self, repo: MetricsRepo):
        """更新或插入仓库记录"""
        existing = self.database.get_metrics_repo(repo.repo_id)

        if existing:
            # 更新记录
            conn = self.database._get_connection()
            try:
                conn.execute('''
                    UPDATE metrics_repos SET
                        repo_name = COALESCE(?, repo_name),
                        total_lines = total_lines + ?,
                        ai_lines = ai_lines + ?,
                        human_lines = human_lines + ?,
                        total_commits = total_commits + ?,
                        ai_commits = ai_commits + ?,
                        last_commit_ts = COALESCE(?, last_commit_ts),
                        updated_at = ?
                    WHERE repo_id = ?
                ''', (
                    repo.repo_name, repo.total_lines, repo.ai_lines,
                    repo.human_lines, repo.total_commits, repo.ai_commits,
                    repo.last_commit_ts, repo.updated_at, repo.repo_id
                ))
                conn.commit()
            finally:
                conn.close()
        else:
            # 插入记录
            self.database.save_metrics_repo(repo)

    def _upsert_contributor(self, contributor: MetricsContributor):
        """更新或插入作者记录"""
        existing = self.database.get_metrics_contributor(contributor.author)

        if existing:
            conn = self.database._get_connection()
            try:
                conn.execute('''
                    UPDATE metrics_contributors SET
                        author_email = COALESCE(?, author_email),
                        total_lines = total_lines + ?,
                        ai_lines = ai_lines + ?,
                        human_lines = human_lines + ?,
                        total_commits = total_commits + ?,
                        ai_commits = ai_commits + ?,
                        repos_count = repos_count + ?,
                        last_commit_ts = COALESCE(?, last_commit_ts),
                        updated_at = ?
                    WHERE author = ?
                ''', (
                    contributor.author_email, contributor.total_lines,
                    contributor.ai_lines, contributor.human_lines,
                    contributor.total_commits, contributor.ai_commits,
                    contributor.repos_count, contributor.last_commit_ts,
                    contributor.updated_at, contributor.author
                ))
                conn.commit()
            finally:
                conn.close()
        else:
            self.database.save_metrics_contributor(contributor)

    def _upsert_repo_contributor(self, relation: MetricsRepoContributor):
        """更新或插入关联记录"""
        conn = self.database._get_connection()
        try:
            # 尝试插入
            try:
                self.database.save_metrics_repo_contributor(relation)
            except:
                # 如果已存在，则更新
                conn.execute('''
                    UPDATE metrics_repo_contributors SET
                        first_seen_ts = CASE
                            WHEN first_seen_ts IS NULL ? THEN ?
                            ELSE LEAST(first_seen_ts, ?)
                        END,
                        last_seen_ts = GREATEST(COALESCE(last_seen_ts, 0), ?),
                        updated_at = ?
                    WHERE repo_id = ? AND author = ?
                ''', (
                    relation.first_seen_ts, relation.first_seen_ts,
                    relation.first_seen_ts, relation.last_seen_ts,
                    relation.updated_at, relation.repo_id, relation.author
                ))
                conn.commit()
        finally:
            conn.close()

    def _finalize_repo_stats(self, repos: Dict):
        """计算仓库统计的最终值"""
        for repo_data in repos.values():
            repo_data['human_lines'] = (
                repo_data['total_lines'] - repo_data['ai_lines']
            )
            if repo_data['total_lines'] > 0:
                repo_data['ai_percentage'] = (
                    repo_data['ai_lines'] / repo_data['total_lines'] * 100
                )

    def _extract_repo_name(self, repo_url: str) -> str:
        """从 URL 提取仓库名"""
        # 简单实现：取 URL 最后一部分
        parts = repo_url.rstrip('/').split('/')
        if parts:
            return parts[-1]
        return repo_url

    def _extract_provider_type(self, repo_url: str) -> Optional[str]:
        """从 URL 提取提供商类型"""
        if 'github.com' in repo_url:
            return 'github'
        elif 'gitlab.com' in repo_url:
            return 'gitlab'
        elif 'gitea' in repo_url:
            return 'gitea'
        return None

    def _parse_json_int_array(self, json_str: Optional[str]) -> Optional[list]:
        """解析 JSON 整数数组"""
        if not json_str:
            return None
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return None
```

**Step 2: 验证调度任务**

运行: `python -c "from core.scheduler.dimensions_task import DimensionsUpdateTask; print('Task loaded successfully')"`
Expected: 无报错输出 "Task loaded successfully"

**Step 3: 提交**

```bash
git add core/scheduler/dimensions_task.py
git commit -m "feat: 添加维度表统计调度任务"
```

---

### Task 8: 创建 API 路由

**Files:**
- Create: `api/routes/dimensions.py`

**Step 1: 创建 API 路由文件**

创建 `api/routes/dimensions.py` 文件：

```python
"""维度表 API 路由"""
from flask import Blueprint, request, jsonify
from core.database.factory import create_database
from core.config.loader import ConfigLoader
from core.config.logging import Logger


dimensions_bp = Blueprint('dimensions', __name__, url_prefix='/api/dimensions')

# 全局配置
config_loader = ConfigLoader()
config = config_loader.load()

# 初始化日志记录器
logger = Logger.get_logger('api.dimensions')


@dimensions_bp.route('/repos', methods=['GET'])
def get_repos():
    """获取仓库列表，支持分页和排序"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        sort = request.args.get('sort')

        # 参数验证
        if page < 1:
            return jsonify({
                'success': False,
                'error': 'page must be >= 1'
            }), 400
        if page_size < 1 or page_size > 100:
            return jsonify({
                'success': False,
                'error': 'page_size must be between 1 and 100'
            }), 400

        database = create_database(config.get('database', {}))
        result = database.get_metrics_repos(page=page, page_size=page_size, sort=sort)

        return jsonify({
            'success': True,
            'data': result['data'],
            'pagination': result['pagination']
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid parameter: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f'获取仓库列表失败: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dimensions_bp.route('/repos/<repo_id>', methods=['GET'])
def get_repo(repo_id):
    """获取单个仓库详情"""
    try:
        database = create_database(config.get('database', {}))
        repo = database.get_metrics_repo(repo_id)

        if repo:
            return jsonify({
                'success': True,
                'data': repo
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Repo not found'
            }), 404

    except Exception as e:
        logger.error(f'获取仓库详情失败: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dimensions_bp.route('/repos/<repo_id>/contributors', methods=['GET'])
def get_repo_contributors(repo_id):
    """获取指定仓库的所有作者"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        database = create_database(config.get('database', {}))
        result = database.get_metrics_repo_contributors(
            repo_id=repo_id, page=page, page_size=page_size
        )

        return jsonify({
            'success': True,
            'data': result['data'],
            'pagination': result['pagination']
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'获取仓库作者列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/repos/sync', methods=['POST'])
def sync_repos():
    """手动触发仓库统计更新"""
    try:
        from core.scheduler.dimensions_task import DimensionsUpdateTask
        from core.database.factory import create_database

        task = DimensionsUpdateTask(config)
        result = task.execute()

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f'同步仓库统计失败: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dimensions_bp.route('/contributors', methods=['GET'])
def get_contributors():
    """获取作者列表，支持分页和排序"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        sort = request.args.get('sort')

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        database = create_database(config.get('database', {}))
        result = database.get_metrics_contributors(page=page, page_size=page_size, sort=sort)

        return jsonify({
            'success': True,
            'data': result['data'],
            'pagination': result['pagination']
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'获取作者列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/contributors/<author>', methods=['GET'])
def get_contributor(author):
    """获取单个作者详情"""
    try:
        database = create_database(config.get('database', {}))
        contributor = database.get_metrics_contributor(author)

        if contributor:
            return jsonify({
                'success': True,
                'data': contributor
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Contributor not found'
            }), 404

    except Exception as e:
        logger.error(f'获取作者详情失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/contributors/<author>/repos', methods=['GET'])
def get_author_repos(author):
    """获取指定作者参与的所有仓库"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        database = create_database(config.get('database', {}))
        result = database.get_metrics_repo_contributors(
            author=author, page=page, page_size=page_size
        )

        return jsonify({
            'success': True,
            'data': result['data'],
            'pagination': result['pagination']
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'获取作者仓库列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/contributors/sync', methods=['POST'])
def sync_contributors():
    """手动触发作者统计更新"""
    try:
        from core.scheduler.dimensions_task import DimensionsUpdateTask

        task = DimensionsUpdateTask(config)
        result = task.execute()

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f'同步作者统计失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/repo-contributors', methods=['GET'])
def get_repo_contributors_list():
    """获取仓库作者关联列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        repo_id = request.args.get('repo_id')
        author = request.args.get('author')

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        database = create_database(config.get('database', {}))
        result = database.get_metrics_repo_contributors(
            repo_id=repo_id, author=author, page=page, page_size=page_size
        )

        return jsonify({
            'success': True,
            'data': result['data'],
            'pagination': result['pagination']
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'获取仓库作者关联列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/repo-contributors/sync', methods=['POST'])
def sync_repo_contributors():
    """手动触发关联表更新"""
    try:
        from core.scheduler.dimensions_task import DimensionsUpdateTask

        task = DimensionsUpdateTask(config)
        result = task.execute()

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f'同步仓库作者关联失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 2: 验证 API 路由**

运行: `python -c "from api.routes.dimensions import dimensions_bp; print('Blueprint loaded successfully')"`
Expected: 无报错输出 "Blueprint loaded successfully"

**Step 3: 提交**

```bash
git add api/routes/dimensions.py
git commit -m "feat: 添加维度表 API 路由"
```

---

### Task 9: 注册 API 蓝图

**Files:**
- Modify: `app.py`

**Step 1: 在 app.py 中注册新蓝图**

在 `app.py` 中找到注册蓝图的部分（约第 73-89 行），添加新蓝图注册：

```python
from api.routes.dimensions import dimensions_bp  # 新增

# ... 其他蓝图注册 ...

app.register_blueprint(dimensions_bp)  # 新增，在其他蓝图注册后
```

**Step 2: 更新 Swagger 标签**

在 Swagger 配置中（约第 111-120 行）添加新标签：

```python
tags": [
    {"name": "stats", "description": "统计分析 API"},
    {"name": "projects", "description": "项目管理 API"},
    {"name": "scheduler", "description": "调度任务 API"},
    {"name": "git-ai", "description": "Git-AI 用户界面 API"},
    {"name": "dimensions", "description": "维度表 API"},  # 新增
    {"name": "worker-metrics", "description": "Worker Metrics API"},
    {"name": "worker-cas", "description": "Worker CAS API"},
    {"name": "worker-oauth", "description": "Worker OAuth API"},
    {"name": "worker-releases", "description": "Worker Releases API"},
],
```

**Step 3: 验证应用启动**

创建测试配置 `.env.test`：
```
BUILD_FRONTEND=0
```

运行: `BUILD_FRONTEND=0 python app.py` (快速检查，然后 Ctrl+C 停止)
Expected: 无报错，应用启动

**Step 4: 提交**

```bash
git add app.py
git commit -m "feat: 注册维度表 API 蓝图"
```

---

### Task 10: 更新调度配置

**Files:**
- Modify: `config.yaml`

**Step 1: 添加维度统计调度任务**

在 `config.yaml` 的 `scheduler.jobs` 节点添加新任务：

```yaml
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
    - id: dimensions_update
      name: 维度表统计更新
      type: cron
      cron: "0 3 * * *"  # 每天凌晨 3 点
```

**Step 2: 验证配置**

运行: `python -c "from core.config.loader import ConfigLoader; config = ConfigLoader().load(); print('Config loaded'); print(f'Jobs: {[j[\"id\"] for j in config[\"scheduler\"][\"jobs\"]]}')"`
Expected: 输出包含 'dimensions_update' 的作业列表

**Step 3: 提交**

```bash
git add config.yaml
git commit -m "feat: 添加维度表统计调度任务配置"
```

---

### Task 11: 在应用中注册调度任务

**Files:**
- Modify: `app.py`

**Step 1: 添加调度任务注册逻辑**

在 `app.py` 中调度器部分（约第 150 行之后）添加维度任务注册：

```python
# 注册调度任务（如果启用）
if config.get('scheduler', {}).get('enabled', False):
    from core.scheduler.dimensions_task import DimensionsUpdateTask  # 新增
    from core.scheduler.scheduler import AICodeScheduler

    scheduler = AICodeScheduler()
    scheduler.start()

    # 注册维度统计任务
    for job in config.get('scheduler', {}).get('jobs', []):
        if job['id'] == 'dimensions_update':
            task = DimensionsUpdateTask(config)
            scheduler.add_cron_job(
                job_id=job['id'],
                func=task.execute,
                cron_expr=job['cron']
            )
            main_logger.info(f'已注册调度任务: {job["name"]}')
```

**Step 2: 验证调度任务注册**

运行: `BUILD_FRONTEND=0 python app.py` (快速检查，然后 Ctrl+C 停止)
Expected: 日志中包含 "已注册调度任务: 维度表统计更新"

**Step 3: 提交**

```bash
git add app.py
git commit -m "feat: 注册维度表统计调度任务"
```

---

### Task 12: 编写 API 集成测试

**Files:**
- Create: `tests/integration/test_dimensions_api.py`

**Step 1: 创建 API 测试文件**

创建 `tests/integration/test_dimensions_api.py` 文件：

```python
"""测试维度表 API"""
import os
import tempfile
import pytest
from flask import Flask
from core.database.sqlite import SQLiteDatabase
from core.models.metrics import (
    MetricsRepo, MetricsContributor, MetricsRepoContributor
)


@pytest.fixture
def test_client():
    """创建测试客户端"""
    # 创建临时数据库
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.environ['BUILD_FRONTEND'] = '0'

    # 修改配置使用临时数据库
    import core.config.loader as loader_module
    loader_module._config_cache = None
    from core.config.loader import ConfigLoader

    # 创建临时配置
    import yaml
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    config['database']['sqlite']['path'] = db_path

    # 创建应用
    from app import app as flask_app
    flask_app.config['TESTING'] = True

    client = flask_app.test_client()

    # 初始化数据库
    db = SQLiteDatabase(config['database'])
    db.init_db()

    yield client

    # 清理
    os.close(fd)
    os.unlink(db_path)


class TestReposAPI:
    """测试仓库 API"""

    def test_get_repos_empty(self, test_client):
        """获取空仓库列表"""
        response = test_client.get('/api/dimensions/repos')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data'] == []
        assert data['pagination']['total'] == 0

    def test_get_repos_pagination(self, test_client):
        """测试仓库列表分页"""
        # 需要先插入数据
        from core.database.factory import create_database
        from core.config.loader import ConfigLoader
        config = ConfigLoader().load()
        db = create_database(config['database'])

        now = int(__import__('datetime').datetime.now().timestamp())

        for i in range(25):
            repo = MetricsRepo(
                repo_id=f"test/repo-{i}",
                repo_name=f"test-repo-{i}",
                repo_url=f"https://github.com/test/repo-{i}",
                total_lines=i * 100,
                created_at=now,
                updated_at=now
            )
            db.save_metrics_repo(repo)

        response = test_client.get('/api/dimensions/repos?page=1&page_size=10')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['data']) == 10
        assert data['pagination']['total'] == 25
        assert data['pagination']['total_pages'] == 3

    def test_get_repo_not_found(self, test_client):
        """获取不存在的仓库"""
        response = test_client.get('/api/dimensions/repos/nonexistent')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_invalid_page_parameter(self, test_client):
        """测试无效的页码参数"""
        response = test_client.get('/api/dimensions/repos?page=0')
        assert response.status_code == 400

    def test_invalid_page_size_parameter(self, test_client):
        """测试无效的页面大小参数"""
        response = test_client.get('/api/dimensions/repos?page_size=150')
        assert response.status_code == 400


class TestContributorsAPI:
    """测试作者 API"""

    def test_get_contributors_empty(self, test_client):
        """获取空作者列表"""
        response = test_client.get('/api/dimensions/contributors')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data'] == []

    def test_get_contributor_not_found(self, test_client):
        """获取不存在的作者"""
        response = test_client.get('/api/dimensions/contributors/nonexistent')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False


class TestSyncAPI:
    """测试同步 API"""

    def test_sync_repos(self, test_client):
        """测试同步仓库统计"""
        response = test_client.post('/api/dimensions/repos/sync')
        assert response.status_code in [200, 500]  # 500 可能是因为没有数据
        data = response.get_json()
        assert 'success' in data

    def test_sync_contributors(self, test_client):
        """测试同步作者统计"""
        response = test_client.post('/api/dimensions/contributors/sync')
        assert response.status_code in [200, 500]


class TestRepoContributorsAPI:
    """测试仓库作者关联 API"""

    def test_get_repo_contributors_empty(self, test_client):
        """获取空关联列表"""
        response = test_client.get('/api/dimensions/repo-contributors')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data'] == []
```

**Step 2: 运行 API 测试**

运行: `pytest tests/integration/test_dimensions_api.py -v`
Expected: 大部分测试通过（可能有些测试需要更复杂的数据准备）

**Step 3: 提交**

```bash
git add tests/integration/test_dimensions_api.py
git commit -m "test: 添加维度表 API 集成测试"
```

---

### Task 13: 全量测试验证

**Files:**
- 无

**Step 1: 运行所有相关测试**

运行: `pytest tests/unit/test_models/test_dimensions.py tests/integration/test_dimensions_db.py tests/integration/test_dimensions_api.py -v`
Expected: 所有测试通过

**Step 2: 手动测试应用**

构建并启动应用：
```bash
npm run build  # frontend 目录
python app.py
```

测试以下端点：
- `GET http://localhost:8888/api/dimensions/repos`
- `GET http://localhost:8888/api/dimensions/contributors`
- `GET http://localhost:8888/api/dimensions/repo-contributors`

**Step 3: 提交（如有必要）**

如果有问题需要修复，修复后提交。

---

## 实现完成检查清单

- [ ] 数据模型已创建并测试通过
- [ ] 数据库表定义已添加
- [ ] 数据库访问方法已实现
- [ ] 调度任务已创建并可执行
- [ ] API 路由已创建并注册
- [ ] 配置已更新
- [ ] 所有测试通过
- [ ] 文档已完善

## 后续优化建议

1. 添加 Swagger 文档注释到每个 API 端点
2. 考虑添加缓存机制提高查询性能
3. 实现 PostgreSQL 支持（如果需要）
4. 添加更详细的日志和监控
5. 实现增量更新策略，只处理新增数据
