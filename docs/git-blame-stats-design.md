# Git 代码归因统计功能设计文档

## 一、需求概述

### 1.1 功能目标

创建一个每天凌晨 2 点执行的定时任务，用于统计 Git 代码仓库的 AI 代码指标：

**文件级指标：**
- AI 代码总行数
- 不同贡献者的 AI 代码行数
- 不同贡献者的非 AI 代码行数
- 贡献者代码总行数
- 文件中代码总行数

**仓库级指标：**
- 仓库中 AI 代码总行数
- 仓库中总代码行数
- 仓库中 AI 代码占比
- 不同贡献者的 AI 代码总行数
- 不同贡献者的非 AI 代码总行数

### 1.2 技术约束

1. 服务端不能直接访问 Git 仓库，需要通过 SSH Key 方式 clone
2. Git blame 实现参考 git-ai 项目，数据来源于 `authorship_notes` 表
3. SSH Key 不自动生成，通过 API 上传或配置文件中设置
4. 优先准确统计，性能次要
5. 统计维度为天，存在当天数据则先删除再插入

---

## 二、架构设计

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          每日凌晨2点触发                                 │
│                     AICodeScheduler (调度器)                            │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   GitBlameStatsTask (统计任务)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  1. 获取待统计仓库列表 (stats_repositories, repo_stats_flag=1)           │
│  2. 对每个仓库:                                                            │
│     ├─ 获取 SSH Key (仓库配置 → 配置文件默认 → 跳过)                        │
│     ├─ 使用指定的 SSH Key 克隆仓库到临时目录                              │
│     ├─ 执行 git blame 分析                                                │
│     ├─ 查询 authorship_notes 判断 AI 归属                                  │
│     ├─ 聚合统计结果                                                      │
│     └─ 清理临时目录                                                      │
│  3. 保存统计结果到 stats_blame_* 表                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
stats_repositories (仓库列表，repo_stats_flag=1)
    ↓
获取 SSH Key (优先级: 仓库配置 > 配置文件默认)
    ↓ ├─ 无可用 Key → 跳过
    ↓
GitCloneService.clone_with_ssh_key()
    ↓
临时目录 → git blame --line-porcelain
    ↓
BlameStatsService 分析
    ↓
查询 authorship_notes (AI 归属)
    ↓
聚合统计 → 保存到 stats_blame_* 表
```

---

## 三、数据库设计

### 3.1 扩展 stats_repositories 表

```sql
-- SQLite 版本
ALTER TABLE stats_repositories ADD COLUMN repo_stats_flag INTEGER DEFAULT 0;
ALTER TABLE stats_repositories ADD COLUMN ssh_key_id VARCHAR(20);
ALTER TABLE stats_repositories ADD COLUMN repo_name TEXT;

-- PostgreSQL 版本
ALTER TABLE stats_repositories ADD COLUMN repo_stats_flag BOOLEAN DEFAULT FALSE;
ALTER TABLE stats_repositories ADD COLUMN ssh_key_id VARCHAR(20);
ALTER TABLE stats_repositories ADD COLUMN repo_name TEXT;
```

**字段说明：**
- `repo_stats_flag`: 是否启用 AI 代码量统计
- `ssh_key_id`: 关联的 SSH Key ID（为空时使用配置文件默认 Key）
- `repo_name`: 仓库名称

### 3.2 SSH Key 管理表

```sql
CREATE TABLE IF NOT EXISTS ssh_keys (
    id VARCHAR(20) PRIMARY KEY,
    key_name TEXT NOT NULL UNIQUE,
    public_key TEXT NOT NULL,
    private_key_encrypted TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);
```

**设计说明：**
- SSH Key 通过 API 上传或来自配置文件
- 不自动生成，不与 Codeup 集成上传
- 私钥使用加密存储

### 3.3 归因统计表

#### 3.3.1 仓库级归因表

```sql
CREATE TABLE IF NOT EXISTS stats_blame_repo (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    commit_sha VARCHAR(40) NOT NULL,
    branch TEXT NOT NULL,
    total_lines INTEGER NOT NULL,
    ai_lines INTEGER NOT NULL,
    non_ai_lines INTEGER NOT NULL,
    ai_ratio DECIMAL(5,2) NOT NULL,
    total_files INTEGER NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(repo_id, stat_date)
);

CREATE INDEX IF NOT EXISTS idx_blame_repo_date ON stats_blame_repo(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_stat_date ON stats_blame_repo(stat_date);
```

#### 3.3.2 文件级归因表

```sql
CREATE TABLE IF NOT EXISTS stats_blame_file (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    file_path TEXT NOT NULL,
    commit_sha VARCHAR(40) NOT NULL,
    total_lines INTEGER NOT NULL,
    ai_lines INTEGER NOT NULL,
    non_ai_lines INTEGER NOT NULL,
    ai_ratio DECIMAL(5,2) NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(repo_id, stat_date, file_path)
);

CREATE INDEX IF NOT EXISTS idx_blame_file_repo ON stats_blame_file(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_file_date ON stats_blame_file(stat_date);
```

#### 3.3.3 仓库贡献者归因表

```sql
CREATE TABLE IF NOT EXISTS stats_blame_repo_contributor (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    contributor_id VARCHAR(20) NOT NULL,
    contributor_name TEXT NOT NULL,
    contributor_email TEXT,
    ai_lines INTEGER NOT NULL DEFAULT 0,
    non_ai_lines INTEGER NOT NULL DEFAULT 0,
    total_lines INTEGER NOT NULL DEFAULT 0,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(repo_id, stat_date, contributor_id)
);

CREATE INDEX IF NOT EXISTS idx_blame_rc_repo ON stats_blame_repo_contributor(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_rc_date ON stats_blame_repo_contributor(stat_date);
```

#### 3.3.4 文件贡献者归因表

```sql
CREATE TABLE IF NOT EXISTS stats_blame_file_contributor (
    id VARCHAR(20) PRIMARY KEY,
    file_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    repo_id VARCHAR(20) NOT NULL,
    file_path TEXT NOT NULL,
    contributor_id VARCHAR(20) NOT NULL,
    contributor_name TEXT NOT NULL,
    contributor_email TEXT,
    ai_lines INTEGER NOT NULL DEFAULT 0,
    non_ai_lines INTEGER NOT NULL DEFAULT 0,
    total_lines INTEGER NOT NULL DEFAULT 0,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(file_id, stat_date, contributor_id)
);

CREATE INDEX IF NOT EXISTS idx_blame_fc_file ON stats_blame_file_contributor(repo_id, stat_date, file_path);
CREATE INDEX IF NOT EXISTS idx_blame_fc_date ON stats_blame_file_contributor(stat_date);
```

---

## 四、核心服务设计

### 4.1 SSH Key 管理服务

```python
# core/services/ssh_key_service.py

class SshKeyService:
    """SSH Key 管理服务"""

    def add_ssh_key(
        self, key_name: str, public_key: str, private_key: str
    ) -> Dict:
        """添加 SSH Key（通过 API 上传）

        Args:
            key_name: Key 名称
            public_key: 公钥内容
            private_key: 私钥内容

        Returns:
            SSH Key 信息
        """

    def delete_ssh_key(self, key_id: str) -> bool:
        """删除 SSH Key"""

    def load_default_ssh_key_from_config(self) -> Dict:
        """从配置文件加载默认 SSH Key（运行时使用，不持久化）

        读取 config.yaml 中的 default_ssh_key_* 配置项
        """

    def get_ssh_key_for_repo(self, repo_id: str, config_ssh_key: Optional[Dict] = None) -> Optional[Dict]:
        """获取仓库的 SSH Key

        优先级：
        1. 仓库单独配置的 SSH Key (ssh_key_id 不为空)
        2. 配置文件中的默认 SSH Key (config_ssh_key)
        3. None（无可用 Key）
        """
```

### 4.2 Git Clone 服务

```python
# core/services/git_clone_service.py

class GitCloneService:
    """Git Clone 服务（使用指定 SSH Key）"""

    def clone_with_ssh_key(
        self,
        repo_url: str,
        ssh_key: Dict,
        target_dir: Optional[str] = None
    ) -> str:
        """使用指定的 SSH Key 克隆仓库

        流程：
        1. 解密私钥到临时文件
        2. 创建 SSH 配置（指定 IdentityFile）
        3. 设置 GIT_SSH_COMMAND 环境变量
        4. 执行 git clone --depth 1
        5. 清理临时文件

        Args:
            repo_url: 仓库 URL
            ssh_key: SSH Key 信息 {id, key_name, public_key, private_key_encrypted}
            target_dir: 目标目录，None 则使用临时目录

        Returns:
            克隆后的目录路径
        """
```

### 4.3 Blame 统计服务

```python
# core/services/blame_stats_service.py

class BlameStatsService:
    """Blame 统计服务"""

    def _parse_authorship_log(self, content: str) -> Dict:
        """解析 AuthorshipLog 内容

        返回格式: {
            "file_path": {
                "session_id": [(line_start, line_end), ...],
                ...
            },
            ...
        }
        """

    def analyze_file_blame(
        self,
        repo_url: str,
        file_path: str,
        blame_output: str
    ) -> FileBlameData:
        """分析单个文件的 blame 输出

        解析 git blame --line-porcelain 输出，
        查询 authorship_notes 判断 AI 归属
        """
```

### 4.4 数据库操作服务

```python
# core/database/blame_stats_db.py

class BlameStatsDatabase(BaseDatabase):
    """归因统计数据库操作类"""

    def update_repository_stats_flag(
        self, repo_id: str, repo_stats_flag: bool
    ) -> None:
        """更新仓库的统计标识"""

    def update_repository_ssh_key(
        self, repo_id: str, ssh_key_id: Optional[str]
    ) -> None:
        """更新仓库关联的 SSH Key"""

    def get_repositories_to_stat(self) -> List[Dict]:
        """获取需要统计的仓库列表 (repo_stats_flag=1)"""

    def delete_daily_repo_stats(self, repo_id: str, stat_date: int) -> int:
        """删除指定仓库指定日期的统计记录（删除再插入策略）"""

    def save_repo_blame_stats(...) -> str:
        """保存仓库级归因统计"""

    def save_file_blame_stats(...) -> str:
        """保存文件级归因统计"""

    def save_repo_contributor_stats(...) -> str:
        """保存仓库贡献者归因统计"""

    def save_file_contributor_stats(...) -> str:
        """保存文件贡献者归因统计"""

    def get_or_create_contributor(self, name: str, email: Optional[str] = None) -> str:
        """获取或创建贡献者"""
```

---

## 五、定时任务设计

```python
# core/scheduler/tasks/git_blame_stats_task.py

@scheduled(cron="0 2 * * *", job_id="git_blame_stats", name="Git代码归因统计")
class GitBlameStatsTask(BaseTask):
    """Git 代码归因统计任务"""

    def execute(self, context: Optional[Dict] = None) -> Dict:
        """执行任务主逻辑

        1. 获取统计日期（默认昨天）
        2. 加载配置文件中的默认 SSH Key（如果有）
        3. 获取待统计仓库列表 (repo_stats_flag=1)
        4. 对每个仓库获取可用 SSH Key
        5. 对每个有可用 SSH Key 的仓库执行统计
        6. 汇总结果
        """

    def _stat_repository(
        self, repo_id: str, repo_path: str, stat_date: int, ssh_key: Dict
    ) -> Dict:
        """统计单个仓库

        流程：
        1. 使用 GitCloneService 克隆仓库
        2. 获取文件列表
        3. 过滤文件类型（可配置）
        4. 删除当天已有的统计记录
        5. 获取当前 commit SHA 和分支
        6. 对每个文件执行 git blame
        7. 查询 authorship_notes 判断 AI 归属
        8. 聚合统计结果
        9. 保存到数据库
        """
```

---

## 六、SSH Key 管理流程

### 6.1 管理员操作流程

```
1. 配置默认 SSH Key（可选，在 config.yaml 中）
   ├─ 设置 default_ssh_key_public
   ├─ 设置 default_ssh_key_private
   └─ 启动服务时运行时加载

2. 添加仓库并启用统计
   └─ UPDATE stats_repositories SET repo_stats_flag = 1 WHERE id = '<repo_id>';

3. 为仓库配置 SSH Key（三种方式）

   方式 A: 使用默认 SSH Key（如果已配置）
   └─ 不设置 ssh_key_id，自动使用配置文件中的默认 Key

   方式 B: 关联已有的 SSH Key
   └─ PUT /api/stats/repo/<repo_id>/ssh-key
      body: { "ssh_key_id": "xxx" }

   方式 C: 上传新的 SSH Key（通过 API）
   └─ POST /api/stats/repo/ssh-key
      body: { "key_name": "...", "public_key": "...", "private_key": "..." }
      └─ 再关联到仓库

4. 定时任务自动统计
   └─ 检查仓库是否有可用 SSH Key（仓库配置或默认配置）
      ├─ 有 → 执行统计
      └─ 无 → 跳过，记录警告日志
```

### 6.2 API 端点

```python
# api/routes/stats_repo.py

# 上传/添加 SSH Key
POST /api/stats/repo/ssh-key
  body: {
    "key_name": "my-git-key",
    "public_key": "ssh-rsa AAAA...",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----..."
  }

# 列出所有 SSH Keys
GET /api/stats/repo/ssh-keys

# 获取仓库的 SSH Key 状态
GET /api/stats/repo/<repo_id>/ssh-status

# 关联仓库的 SSH Key
PUT /api/stats/repo/<repo_id>/ssh-key
  body: { "ssh_key_id": "xxx" }  或  null 表示使用默认 Key

# 删除 SSH Key
DELETE /api/stats/repo/ssh-key/<key_id>
```

---

## 七、配置文件

```yaml
# config.yaml

blame_stats:
  # 默认 SSH Key 配置（可选）
  default_ssh_key_name: "default-git-blame"
  default_ssh_key_public: "${DEFAULT_SSH_PUBLIC_KEY}"
  default_ssh_key_private: "${DEFAULT_SSH_PRIVATE_KEY}"

  file_filter:
    enabled: false
    mode: code_only  # code_only | all | custom
    extensions:
      - .py
      - .js
      - .ts

scheduler:
  enabled: true
  timezone: Asia/Shanghai
  jobs:
    git_blame_stats:
      cron: "0 2 * * *"
      enabled: true
```

**环境变量：**
- `DEFAULT_SSH_PUBLIC_KEY`: 默认公钥
- `DEFAULT_SSH_PRIVATE_KEY`: 默认私钥

---

## 八、数据库迁移脚本

### 8.1 SQLite 版本

```sql
-- sql/blame_stats_schema_sqlite.sql

-- 扩展 stats_repositories 表
ALTER TABLE stats_repositories ADD COLUMN repo_stats_flag INTEGER DEFAULT 0;
ALTER TABLE stats_repositories ADD COLUMN ssh_key_id VARCHAR(20);
ALTER TABLE stats_repositories ADD COLUMN repo_name TEXT;

-- SSH Keys 表
CREATE TABLE IF NOT EXISTS ssh_keys (
    id VARCHAR(20) PRIMARY KEY,
    key_name TEXT NOT NULL UNIQUE,
    public_key TEXT NOT NULL,
    private_key_encrypted TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

-- 归因统计表（表名去掉 _stats 后缀）
CREATE TABLE IF NOT EXISTS stats_blame_repo (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    commit_sha VARCHAR(40) NOT NULL,
    branch TEXT NOT NULL,
    total_lines INTEGER NOT NULL,
    ai_lines INTEGER NOT NULL,
    non_ai_lines INTEGER NOT NULL,
    ai_ratio DECIMAL(5,2) NOT NULL,
    total_files INTEGER NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(repo_id, stat_date)
);

CREATE INDEX IF NOT EXISTS idx_blame_repo_date ON stats_blame_repo(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_stat_date ON stats_blame_repo(stat_date);

CREATE TABLE IF NOT EXISTS stats_blame_file (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    file_path TEXT NOT NULL,
    commit_sha VARCHAR(40) NOT NULL,
    total_lines INTEGER NOT NULL,
    ai_lines INTEGER NOT NULL,
    non_ai_lines INTEGER NOT NULL,
    ai_ratio DECIMAL(5,2) NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(repo_id, stat_date, file_path)
);

CREATE INDEX IF NOT EXISTS idx_blame_file_repo ON stats_blame_file(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_file_date ON stats_blame_file(stat_date);

CREATE TABLE IF NOT EXISTS stats_blame_repo_contributor (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    contributor_id VARCHAR(20) NOT NULL,
    contributor_name TEXT NOT NULL,
    contributor_email TEXT,
    ai_lines INTEGER NOT NULL DEFAULT 0,
    non_ai_lines INTEGER NOT NULL DEFAULT 0,
    total_lines INTEGER NOT NULL DEFAULT 0,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(repo_id, stat_date, contributor_id)
);

CREATE INDEX IF NOT EXISTS idx_blame_rc_repo ON stats_blame_repo_contributor(repo_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_blame_rc_date ON stats_blame_repo_contributor(stat_date);

CREATE TABLE IF NOT EXISTS stats_blame_file_contributor (
    id VARCHAR(20) PRIMARY KEY,
    file_id VARCHAR(20) NOT NULL,
    stat_date BIGINT NOT NULL,
    repo_id VARCHAR(20) NOT NULL,
    file_path TEXT NOT NULL,
    contributor_id VARCHAR(20) NOT NULL,
    contributor_name TEXT NOT NULL,
    contributor_email TEXT,
    ai_lines INTEGER NOT NULL DEFAULT 0,
    non_ai_lines INTEGER NOT NULL DEFAULT 0,
    total_lines INTEGER NOT NULL DEFAULT 0,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(file_id, stat_date, contributor_id)
);

CREATE INDEX IF NOT EXISTS idx_blame_fc_file ON stats_blame_file_contributor(repo_id, stat_date, file_path);
CREATE INDEX IF NOT EXISTS idx_blame_fc_date ON stats_blame_file_contributor(stat_date);
```

---

## 九、文件清单

### 9.1 新增文件

```
core/services/
├── ssh_key_service.py          # SSH Key 管理服务（简化）
├── git_clone_service.py        # Git Clone 服务
└── blame_stats_service.py      # Blame 统计服务

core/database/
└── blame_stats_db.py           # 归因统计数据库操作

core/scheduler/tasks/
└── git_blame_stats_task.py     # 归因统计定时任务

api/routes/
└── stats_repo.py               # 仓库 & SSH Key 管理 API

sql/
└── blame_stats_schema_sqlite.sql   # 数据库迁移脚本

docs/
└── git-blame-stats-design.md        # 本设计文档
```

### 9.2 修改文件

```
core/database/
├── models.py                    # 添加 ssh_keys 及归因统计表模型
└── stats_db.py                  # 可能需要扩展

core/database/base_db.py         # 扩展 StatsRepository 模型属性

config.yaml                     # 添加 blame_stats 配置

api/routes/__init__.py          # 注册 stats_repo 路由
```

---

## 十、实现要点

### 10.1 SSH Key 管理

1. **不自动生成**：SSH Key 通过 API 上传或配置文件提供
2. **私钥加密**：使用 PBKDF2 + Fernet 加密存储
3. **双源支持**：仓库单独配置 或 配置文件默认
4. **临时文件**：clone 时将私钥写入临时文件（权限 600），使用后立即删除
5. **SSH 配置**：创建临时 SSH 配置文件，指定 IdentityFile

### 10.2 Git Blame 实现

1. 命令：`git blame --line-porcelain <file>`
2. 解析输出：获取每行的 commit SHA、作者信息
3. 查询 authorship_notes：根据 commit SHA + 文件路径 + 行号判断 AI 归属
4. 缓存优化：批量查询 notes，避免逐个查询

### 10.3 统计策略

1. **删除再插入**：同一仓库同一天日期的数据先删除再插入
2. **文件过滤**：支持 code_only / all / custom 三种模式
3. **临时目录**：使用临时目录克隆，任务结束后清理
4. **错误处理**：单个文件失败跳过，继续处理其他文件

---

## 十一、后续扩展

1. **增量统计**：记录上次统计的 commit SHA，只统计有变化的文件
2. **并行处理**：使用线程池并行处理多个文件或多个仓库
3. **压缩存储**：定期归档历史统计数据
4. **查询 API**：提供前端查询统计数据的接口
5. **统计分析**：基于统计数据的趋势分析、环比同比等
