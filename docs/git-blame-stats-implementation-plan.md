# Git Blame Stats 功能实施计划

## 概述

根据 `docs/git-blame-stats-design.md` 设计文档，本计划将实现 Git 代码归因统计功能。

**核心功能**：通过定时任务每天凌晨 2 点执行，使用 git blame 统计仓库中的 AI 代码行数占比。

**数据来源**：从 `authorship_notes` 表中获取 AI 归属信息。

**技术约束**：
- 服务端通过 SSH Key 方式克隆 Git 仓库
- SSH Key 通过 API 上传或配置文件设置，不自动生成
- 优先准确统计，性能次要

---

## 实施步骤

### 阶段 1：数据库层

#### 1.1 添加数据模型

**文件**: `core/database/models.py`

添加以下模型类：
- `SshKey` - SSH 存储模型
- `StatsBlameRepo` - 仓库级归因统计模型
- `StatsBlameFile` - 文件级归因统计模型
- `StatsBlameRepoContributor` - 仓库贡献者归因统计模型
- `StatsBlameFileContributor` - 文件贡献者归因统计模型

扩展 `StatsRepository` 模型，添加字段：
- `repo_stats_flag` (BOOLEAN/INTEGER) - 是否启用 AI 代码量统计
- `ssh_key_id` (VARCHAR) - 关联的 SSH Key ID

#### 1.2 创建数据库迁移脚本

**文件**: `sql/blame_stats_schema_sqlite.sql`

**内容**：
```sql
-- 扩展 stats_repositories 表
ALTER TABLE stats_repositories ADD COLUMN repo_stats_flag INTEGER DEFAULT 0;
ALTER TABLE stats_repositories ADD COLUMN ssh_key_id VARCHAR(20);

-- SSH Keys 表
CREATE TABLE IF NOT EXISTS ssh_keys (...);

-- 归因统计表（4个）
CREATE TABLE IF NOT EXISTS stats_blame_repo (...);
CREATE TABLE IF NOT EXISTS stats_blame_file (...);
CREATE TABLE IF NOT EXISTS stats_blame_repo_contributor (...);
CREATE TABLE IF NOT EXISTS stats_blame_file_contributor (...);

-- 相应索引
```

#### 1.3 创建数据库操作类

**文件**: `core/database/blame_stats_db.py`

**类**: `BlameStatsDatabase`

**方法**：
- 扩展仓库管理：`update_repository_stats_flag()`, `update_repository_ssh_key()`, `get_repositories_to_stat()`
- 删除当天数据：`delete_daily_repo_stats()`, `delete_daily_file_stats()`
- 保存统计结果：`save_repo_blame_stats()`, `save_file_blame_stats()`, `save_repo_contributor_stats()`, `save_file_contributor_stats()`
- SSH Key 管理：`add_ssh_key()`, `get_ssh_key()`, `list_ssh_keys()`, `delete_ssh_key()`
- 贡献者管理：`get_or_create_contributor()`
- 查询方法：`get_repo_blame_stats()`, `get_file_blame_stats()` 等

---

### 阶段 2：核心服务层

#### 2.1 SSH Key 管理服务

**文件**: `core/services/ssh_key_service.py`

**类**: `SshKeyService`

**方法**：
- `add_ssh_key(key_name, public_key, private_key)` - 添加 SSH Key（API 上传）
- `load_default_ssh_key_from_config()` - 从配置文件加载默认 Key
- `get_ssh_key_for_repo(repo_id, config_ssh_key)` - 获取仓库 SSH Key（优先级：仓库配置 > 默认配置）
- `_encrypt_private_key(private_key)` - 加密私钥
- `_decrypt_private_key(private_key_encrypted)` - 解密私钥

#### 2.2 Git Clone 服务

**文件**: `core/services/git_clone_service.py`

**类**: `GitCloneService`

**方法**：
- `clone_with_ssh_key(repo_url, ssh_key, target_dir)` - 使用指定 SSH Key 克隆仓库
- `_create_ssh_config(ssh_key_path)` - 创建临时 SSH 配置
- `_cleanup_temp_dir(temp_dir)` - 清理临时目录

**流程**：
1. 解密私钥到临时文件（权限 600）
2. 创建 SSH 配置指定 IdentityFile
3. 设置 GIT_SSH_COMMAND 环境变量
4. 执行 `git clone --depth 1`
5. 清理临时文件

#### 2.3 Blame 统计服务

**文件**: `core/services/blame_stats_service.py`

**类**: `BlameStatsService`

**方法**：
- `analyze_repository(repo_url, repo_dir, stat_date)` - 分析整个仓库
- `_parse_authorship_log(content)` - 解析 AuthorshipLog 内容
- `analyze_file_blame(repo_url, file_path, blame_output)` - 分析单个文件
- `_query_ai_lines_from_notes(sha, file_path, line_num, notes)` - 从 notes 查询 AI 归属
- `_filter_files(file_list)` - 根据配置过滤文件类型

**流程**：
1. 获取文件列表
2. 对每个文件执行 `git blame --line-porcelain`
3. 解析 blame 输出，获取每行的 commit SHA 和作者
4. 批量查询 `authorship_notes` 判断 AI 归属
5. 聚合统计结果

---

### 阶段 3：定时任务

#### 3.1 创建 Git Blame 统计任务

**文件**: `core/scheduler/tasks/git_blame_stats_task.py`

**类**: `GitBlameStatsTask`

**装饰器**: `@scheduled(cron="0 2 * * *", job_id="git_blame_stats", name="Git代码归因统计")`

**execute() 主流程**：
1. 获取统计日期（默认昨天）
2. 加载配置文件中的默认 SSH Key
3. 获取待统计仓库列表 (`repo_stats_flag=1`)
4. 对每个仓库获取可用 SSH Key
5. 对每个有可用 SSH Key 的仓库执行统计
6. 汇总结果

**_stat_repository() 子流程**：
1. 使用 `GitCloneService` 克隆仓库
2. 使用 `BlameStatsService` 分析
3. 调用 `BlameStatsDatabase` 保存结果
4. 清理临时目录

---

### 阶段 4：API 接口

#### 4.1 创建仓库和 SSH Key 管理 API

**文件**: `api/routes/stats_repo.py`

**蓝图**: `stats_repo_bp`

**路由**：

```python
# SSH Key 管理
POST   /api/stats/repo/ssh-key           # 上传/添加 SSH Key
GET    /api/stats/repo/ssh-keys          # 列出所有 SSH Keys
DELETE /api/stats/repo/ssh-key/<key_id>  # 删除 SSH Key

# 仓库管理
GET    /api/stats/repo/<repo_id>/ssh-status  # 获取仓库 SSH Key 状态
PUT    /api/stats/repo/<repo_id>/ssh-key     # 关联仓库的 SSH Key
PUT    /api/stats/repo/<repo_id>/stats-flag  # 启用/禁用仓库统计

# 数据查询
GET    /api/stats/blame/repo/<repo_id>       # 获取仓库归因统计数据
GET    /api/stats/blame/file/<repo_id>       # 获取文件归因统计数据
```

#### 4.2 注册新蓝图

**文件**: `api/routes/__init__.py`

添加导入和导出：
```python
from .stats_repo import stats_repo_bp

__all__ = [
    # ...现有蓝图...
    "stats_repo_bp",
]
```

#### 4.3 在 app.py 中注册蓝图

确认新蓝图已被正确注册。

---

### 阶段 5：配置文件

#### 5.1 添加配置项

**文件**: `config.yaml`

在配置文件末尾添加：

```yaml
# Git Blame 统计配置
blame_stats:
  # 默认 SSH Key 配置（可选）
  default_ssh_key_name: "default-git-blame"
  default_ssh_key_public: "${DEFAULT_SSH_PUBLIC_KEY}"
  default_ssh_key_private: "${DEFAULT_SSH_PRIVATE_KEY}"

  # 文件过滤配置
  file_filter:
    enabled: false
    mode: code_only  # code_only | all | custom
    extensions:
      - .py
      - .js
      - .ts

scheduler:
  # ...现有配置...
  jobs:
    # ...现有任务...
    git_blame_stats:
      cron: "0 2 * * *"
      enabled: true
```

#### 5.2 环境变量

在 `.env.example` 中添加：
```
# Git Blame 统计默认 SSH Key（可选）
DEFAULT_SSH_PUBLIC_KEY=
DEFAULT_SSH_PRIVATE_KEY=
```

---

### 阶段 6：测试与验证

#### 6.1 单元测试

创建测试文件验证：
- SSH Key 加密/解密
- Git clone 功能
- Blame 输出解析
- Notes 查询逻辑

#### 6.2 集成测试

1. 上传测试 SSH Key
2. 添加测试仓库并启用统计
3. 手动触发定时任务
4. 验证统计结果保存正确

#### 6.3 运行数据库迁移

```bash
# SQLite
sqlite3 data/ai_stats.db < sql/blame_stats_schema_sqlite.sql

# PostgreSQL（如需要）
psql -U username -d database_name < sql/blame_stats_schema_postgresql.sql
```

---

## 文件清单

### 新增文件

```
core/services/
├── ssh_key_service.py          # SSH Key 管理服务
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
```

### 修改文件

```
core/database/
├── models.py                   # 添加归因统计模型
└── base_db.py                  # 扩展 StatsRepository 模型

api/routes/
└── __init__.py                 # 注册 stats_repo 路由

config.yaml                     # 添加 blame_stats 配置

.env.example                    # 添加 SSH Key 环境变量
```

---

## 实施顺序建议

1. **数据库层**（优先级最高）：模型 → 迁移脚本 → 数据库操作类
2. **核心服务层**：SSH Key → Git Clone → Blame Stats
3. **定时任务层**：创建并注册任务
4. **API 层**：创建蓝图 → 注册路由
5. **配置层**：更新配置文件
6. **测试验证**：单元测试 → 集成测试

---

## 关键技术点

### SSH Key 加密
- 使用 PBKDF2+AES 或 Fernet 加密私钥
- Clone 时解密到临时文件
- 设置文件权限 600

### Git Blame 解析
- 格式：`git blame --line-porcelain <file>`
- 每行输出包含：commit SHA、作者、时间戳
- 批量查询 notes 避免逐行查询

### 聚合策略
- 删除再插入：同一仓库同一日期先删除后插入
- 文件过滤：支持 code_only/all/custom 模式
- 临时目录：使用 `tempfile` 管理临时目录

### 错误处理
- 单个文件失败跳过，继续处理其他文件
- 无可用 SSH Key 跳过仓库，记录警告日志
- 记录详细的错误日志便于排查
