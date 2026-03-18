# Git AI 代码统计工具 - 架构设计文档

**日期：** 2026-03-11
**版本：** 2.0.0
**作者：** Claude Code

---

## 1. 概述

本文档描述 Git AI 代码统计工具的架构设计。目标是将原有项目工程化改造，实现：

1. **Git API 抽象化**：支持 GitLab、GitHub，易于扩展其他平台
2. **数据层抽象化**：支持 PostgreSQL、MySQL、SQLite
3. **定时任务功能**：按配置自动统计，增量拉取 Git Notes
4. **YAML 配置管理**：统一配置文件，控制功能开关

---

## 2. 系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                           Web 层                                   │
│                    (Flask Blueprint)                             │
│   ┌────────────┐  ┌──────────────┐  ┌──────────────────┐        │
│   │  统计分析   │  │  历史查询     │  │   配置管理        │        │
│   │   API      │  │     API       │  │     API          │        │
│   └────────────┘  └──────────────┘  └──────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                           服务层                                   │
│                        (Business Logic)                          │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐        │
│   │  AI 代码统计 │  │  定时任务管理  │  │   配置解析器      │        │
│   │   Service    │  │   Scheduler   │  │   ConfigLoader   │        │
│   └──────────────┘  └──────────────┘  └──────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
┌─────────────────────────────┐      ┌─────────────────────────────┐
│       API 抽象层              │      │      数据访问层              │
│    GitProvider (Base)        │      │    Database (Base)          │
│   ┌──────────────┐           │      │   ┌──────────────┐          │
│   │ GitLabProvider│ ---------┼──────┼───│ PostgreSQLDB │          │
│   └──────────────┘           │      │   └──────────────┘          │
│   ┌──────────────┐           │      │   ┌──────────────┐          │
│   │ GitHubProvider│          │      │   │   MySQLDB    │          │
│   └──────────────┘           │      │   └──────────────┘          │
└─────────────────────────────┘      │   ┌──────────────┐          │
                                    │   │  SQLiteDatabase│          │
                                    │   └──────────────┘          │
                                    └─────────────────────────────┘
```

---

## 3. API 抽象层设计

### 3.1 接口定义

```python
# core/git_providers/base.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional

class GitProvider(ABC):
    """Git 平台抽象基类"""

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

### 3.2 实现

- **GitLabProvider**：使用 GitLab API v4
- **GitHubProvider**：使用 GitHub REST API

### 3.3 工厂模式

```python
# core/git_providers/factory.py
def create_provider(config: dict) -> GitProvider:
    provider_type = config.get('type', 'gitlab')
    if provider_type == 'gitlab':
        return GitLabProvider(config)
    elif provider_type == 'github':
        return GitHubProvider(config)
    else:
        raise ValueError(f"Unsupported provider: {provider_type}")
```

---

## 4. 数据访问层设计

### 4.1 数据模型

```python
# core/models/stats.py
from typing import List, Dict, Optional
from datetime import datetime

class StatRecord:
    """统计数据记录 - 以统计任务为粒度"""
    id: str  # UUID
    timestamp: datetime
    total_lines: int
    total_ai_lines: int
    overall_percentage: float
    total_commits: int
    commits_with_ai: int
    start_date: datetime
    end_date: datetime
    repos_count: int

class RepoStatRecord:
    """仓库统计数据 - 以项目仓库为粒度"""
    id: str
    stat_id: str
    repo_name: str
    repo_id: str
    provider_type: str
    branch: str
    total_lines: int
    ai_lines: int
    ai_percentage: float
    total_commits: int
    commits_with_ai: int
    start_date: datetime
    end_date: datetime
    commit_details: List[Dict]

class ContributorStatRecord:
    """贡献者统计数据 - 以代码提交人为粒度"""
    id: str
    stat_id: str
    author_name: str
    author_email: str
    total_commits: int
    total_lines: int
    ai_lines: int
    ai_percentage: float
    repos_breakdown: List[Dict]
    start_date: datetime
    end_date: datetime

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
    total_commits: int
    total_lines: int
    ai_lines: int
    ai_percentage: float
    start_date: datetime
    end_date: datetime
    commit_details: List[Dict]
```

### 4.2 数据库支持

| 类型 | 适用场景 |
|------|----------|
| PostgreSQL | 生产环境、多用户 |
| MySQL | 生产环境、已有 MySQL |
| SQLite | 开发、单用户 |

### 4.3 接口定义

```python
# core/database/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

class Database(ABC):
    """数据库抽象基类"""

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

---

## 5. 定时任务设计

### 5.1 调度器

基于 `APScheduler` 实现，支持：

- **Cron 表达式**：如 `0 2 * * *` 每天凌晨 2 点执行
- **间隔执行**：如每 6 小时执行一次

### 5.2 增量统计逻辑

```python
def execute(self):
    # 1. 从数据库获取上次统计时间
    latest = self.database.get_latest_stat()

    # 2. 确定统计时间范围
    if latest:
        start_date = latest.get('timestamp')
    else:
        start_date = datetime.now() - timedelta(days=30)

    end_date = datetime.now()

    # 3. 执行统计
    results = self._calculate_stats(start_date, end_date)

    # 4. 保存结果
    stat_id = self.database.save_stats(results)
```

---

## 6. 配置文件设计

### 6.1 YAML 配置格式

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
  github:
    base_url: https://api.github.com
    token: ${GITHUB_TOKEN}
    api_timeout: 30

# 数据库配置
database:
  type: postgresql
  postgresql:
    host: localhost
    port: 5432
    database: ai_stats
    user: postgres
    password: ${DB_PASSWORD}
    pool_size: 5
  sqlite:
    path: data/ai_stats.db

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

---

## 7. API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/stats/analyze` | 执行统计分析 |
| GET | `/api/v1/stats/latest` | 获取最新统计结果 |
| GET | `/api/v1/stats/history` | 获取统计历史记录 |
| GET | `/api/v1/stats/{stat_id}` | 获取指定统计详情 |
| GET | `/api/v1/projects` | 获取项目列表 |
| GET | `/api/v1/departments` | 获取部门列表 |
| GET | `/api/v1/scheduler/jobs` | 获取所有任务 |
| GET | `/api/v1/scheduler/jobs/{job_id}` | 获取任务状态 |

---

## 8. 项目结构

```
git-ai-code-metrics/
├── app.py
├── config.yaml
├── requirements.txt
│
├── core/
│   ├── config/
│   ├── git_providers/
│   ├── database/
│   ├── models/
│   ├── services/
│   └── scheduler/
│
├── api/
│   ├── routes/
│   └── schemas/
│
├── data/
├── logs/
├── tests/
│   ├── unit/
│   └── integration/
│
└── docs/
    └── plans/
```

---

## 9. 部署

### 9.1 Docker Compose

```yaml
services:
  app:
    build: .
    ports:
      - "8888:8888"
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

---

## 10. 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | Flask |
| 配置管理 | PyYAML, python-dotenv |
| Git API | requests |
| 数据库 | PostgreSQL, MySQL, SQLite |
| 定时任务 | APScheduler |
| 测试 | pytest |