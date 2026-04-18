# Git AI 代码统计系统

<div align="center">

![Git AI Logo](https://via.placeholder.com/150?text=Git-AI)

**一个基于 Flask 后端 + Vue 3 前端的 AI 生成代码统计分析平台**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3.5+-green.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## 📋 项目简介

Git AI 代码统计系统是一个用于统计 Git 仓库中 AI 生成代码占比的分析平台。该系统由两部分组成：

1. **Git-AI 客户端** - 一个基于 Rust 的 Git 扩展，追踪 AI 生成的代码贡献
2. **Git-AI 代码统计系统** - 一个基于 Flask + Vue 的后端平台，接收、存储和分析 Git-AI 客户端上传的 Metrics 数据

### Git-AI 客户端

Git-AI 是一个生产级的 Git 扩展实现，遵循 [Git AI Standard v3.0.0](git-ai/specs/git_ai_standard_v3.0.0.md) 标准。它通过透明的 Git 代理机制追踪 AI 生成代码：

- **🎯 透明的代码追踪** - 作为 Git 命令的代理，自动记录 AI 生成的代码
- **📝 AI Authorship Logs** - 使用 Git Notes 存储代码归属信息，不修改提交历史
- **🔧 多Agent 支持** - 支持 Claude Code、Cursor、Copilot 等多个 AI 开发工具
- **⚡ 高性能** - 基于 Rust 开发，高效处理大规模代码仓库
- **📊 实时统计** - 实时显示当前分支的 AI 代码占比和统计信息

[安装文档](git-ai/README.md)

### 核心功能

- **📊 多维度统计分析** - 支持按时间（日/周/月）、仓库、贡献者等多维度聚合统计
- **🔄 Metrics 数据处理** - 接收并处理 Git-AI 客户端上传的各类事件数据
- **🔧 Git Blame 统计** - 支持通过 Git Blame 进行代码归属分析
- **📝 Notes 同步服务** - 提供 Git Notes 数据的 REST API 同步接口
- **🔐 OAuth 认证** - 基于设备授权流程的安全认证机制
- **📦 CAS 内容存储** - 内容寻址存储服务
- **⏰ 定时任务调度** - 灵活的任务调度系统，支持任务持久化和配置覆盖
- **📚 自动 API 文档** - 基于 Swagger/OpenAPI 的 API 文档自动生成

## 🛠 技术栈

### 后端统计平台

| 技术 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 后端开发语言 |
| Flask | 3.1.3 | Web 框架 |
| SQLAlchemy | 2.0.36 | ORM 框架 |
| APScheduler | 3.11.2 | 任务调度器 |
| PyMySQL | 1.1.2 | MySQL 数据库驱动 |
| Polars | 1.38.1 | 数据处理库 |
| PyYAML | 6.0.3 | 配置文件解析 |
| Flasgger | 0.9.7.1 | Swagger API 文档生成 |
| Gunicorn | 23.0.0 | WSGI 服务器 |
| Gevent | 25.9.1 | 协程库 |

### Git-AI 客户端

| 技术 | 版本 | 说明 |
|------|------|------|
| Rust | 1.93+ | 核心开发语言 |
| git2 | 0.18+ | Git 库（测试专用） |
| SQLite | - | 本地数据存储 |
| smol | - | 异步运行时 |

### 前端

| 技术 | 版本 | 说明 |
|------|------|------|
| Vue | 3.5+ | 前端框架 |
| Vite | 8.0+ | 构建工具 |
| Element Plus | 2.13+ | UI 组件库 |
| Pinia | 3.0+ | 状态管理 |
| TypeScript | 6.0+ | JavaScript 超集 |
| TailwindCSS | 4.2+ | CSS 框架 |

## 📁 项目结构

```
git-ai-code-metrics/
├── api/                      # API 层
│   ├── routes/              # 路由蓝图
│   │   ├── stats.py        # 统计分析 API
│   │   ├── stats_repo.py   # 仓库统计 API
│   │   ├── system.py       # 系统管理 API
│   │   ├── git_ai_worker.py # Git-AI Worker API
│   │   └── authorship_notes.py # Notes 相关 API
│   └── schemas/             # 数据模型定义
├── core/                     # 核心业务层
│   ├── config/             # 配置加载
│   ├── database/           # 数据库适配器
│   │   ├── base.py        # 数据库抽象基类
│   │   ├── metrics_db.py  # Metrics 数据库
│   │   ├── stats_db.py     # 统计数据库
│   │   ├── blame_stats_db.py # Blame 统计库
│   │   └── ...
│   ├── middleware/         # 中间件
│   ├── scheduler/         # 任务调度器
│   │   ├── tasks/         # 定时任务
│   │   ├── scheduled.py   # 任务装饰器
│   │   └── registry.py    # 任务注册表
│   ├── services/          # 业务服务
│   │   ├── metrics_service.py
│   │   ├── oauth_service.py
│   │   ├── cas_service.py
│   │   ├── notes_service.py
│   │   └── ...
│   └── swagger/           # API 文档生成
├── frontend/               # Vue 3 前端
│   ├── src/              # 源代码
│   ├── locales/          # 国际化配置
│   └── package.json      # 依赖配置
├── docs/                  # 文档
│   ├── swagger/         # Swagger YAML 定义
│   └── api/             # API 文档
├── sql/                   # 数据库脚本
├── tests/                 # 测试代码
├── git-ai/               # Git-AI 客户端项目
│   ├── src/             # Rust 源代码
│   │   ├── commands/   # 命令实现
│   │   ├── core/       # 核心逻辑
│   │   └── main.rs     # 入口文件（二进制分发）
│   ├── specs/          # 规范文档
│   │   └── git_ai_standard_v3.0.0.md
│   ├── agent-support/  # Agent 集成支持
│   │   ├── vscode/    # VS Code 插件
│   │   ├── intellij/  # IntelliJ 插件
│   │   └── opencode/  # OpenCode 插件
│   └── README.md     # 安装说明
├── config.yaml           # 主配置文件
├── requirements.txt      # Python 依赖
├── app.py               # 应用入口
└── gunicorn.conf.py     # Gunicorn 配置
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 20.19+ 或 22.13+
- pnpm 9+
- MySQL 8.0+ 或 SQLite

### 后端启动

```bash
# 1. 克隆项目
git clone <repository-url>
cd git-ai-code-metrics

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate    # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp config.yaml config.yaml.local
# 编辑 config.yaml.local，设置数据库连接等配置

# 5. 初始化数据库（如果使用 SQLite）
# 数据库会在首次运行时自动创建

# 6. 启动应用
python app.py
```

默认访问地址：`http://localhost:8888`

### 前端开发

```bash
cd frontend

# 安装依赖
pnpm install

# 开发模式启动
pnpm dev

# 构建生产版本
pnpm build

# 预览构建结果
pnpm preview
```

前端开发默认地址：`http://localhost:5173`

### Docker 部署

```bash
# 构建镜像
docker build -t git-ai-code-metrics .

# 运行容器
docker run -p 8888:8888 \
  -e DB_URL=mysql://user:pass@host:3306/dbname \
  git-ai-code-metrics
```

### Git-AI 客户端安装

#### Windows 系统

```powershell
# 1. 使用管理员权限打开 PowerShell
# 2. 进入 git-ai 目录
cd git-ai

# 3. 执行安装脚本
powershell -NoProfile -ExecutionPolicy Bypass -Command ./install.ps1

# 4. 如果提示禁止运行脚本，先执行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 5. 重启终端，让环境变量生效
```

#### 验证安装

```bash
# 检查 git-ai 版本
git-ai --version

# 验证 git 路径优先级
where.exe git
# 输出第一行应该是 git-ai 目录下的 git.exe

# 检查登录状态
git-ai login

# 查看 AI 代码统计
git-ai status
```

#### Git-AI 常用命令

| 命令 | 说明 |
|------|------|
| `git-ai blame <file>` | 查看文件中哪些是 AI 生成 |
| `git-ai status` | 显示当前分支的 AI 代码占比 |
| `git-ai login` | 登录 Git-AI 服务器 |
| `git-ai logout` | 登出 Git-AI 服务器 |
| `git-ai install-hooks` | (重新)安装 Git Hooks |

#### Claude Code 集成

Git-AI 通过 Hooks 与 Claude Code 集成，自动追踪 AI 生成的代码。

在 Claude Code 配置中（如 `~/.claude` 目录）添加以下 Hooks 配置：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "command": "git-ai checkpoint claude --hook-input stdin",
            "type": "command"
          }
        ],
        "matcher": "Write|Edit|MultiEdit"
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "command": "git-ai checkpoint claude --hook-input stdin",
            "type": "command"
          }
        ],
        "matcher": "Write|Edit|MultiEdit"
      }
    ]
  }
}
```

## ⚙️ 配置说明

### 主配置文件 (config.yaml)

```yaml
# 数据库配置
database:
  url: ${DB_URL:mysql+pymysql://root:password@localhost:3306/git_ai}
  echo: false

# 定时任务配置
scheduler:
  enabled: true
  timezone: Asia/Shanghai
  job_defaults:
    coalesce: true
    max_instances: 1
    misfire_grace_time: 300

# Web 服务配置
web:
  host: 0.0.0.0
  port: 8888
  debug: false

# Git AI 服务配置
git_ai:
  api_key: git-ai123456789

# 日志配置
logging:
  dir: .logs
  level: INFO
```

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DB_URL` | 数据库连接 URL | - |
| `DB_ECHO` | 是否打印 SQL | `false` |
| `BUILD_FRONTEND` | 是否构建前端 | `true` |

## 📚 API 文档

启动应用后，访问以下地址查看 API 文档：

- **Swagger UI**: `http://localhost:8888/api/docs/`
- **Swagger JSON**: `http://localhost:8888/api/swagger.json`

### 主要 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/stats` | GET | 获取统计数据 |
| `/api/stats/repo` | GET | 获取仓库统计 |
| `/api/scheduler/jobs` | GET | 获取定时任务列表 |
| `/worker/metrics/upload` | POST | 上传 Metrics 数据 |
| `/worker/health` | GET | 健康检查 |
| `/worker/oauth/device` | POST | 设备授权 |
| `/worker/cas/put` | POST | CAS 数据存储 |

详细 API 文档请参考 [`docs/swagger/api/`](docs/swagger/api/) 目录下的 YAML 文件。

## 🔄 Git-AI 数据流

### 核心概念

**Git AI Standard v3.0.0**

Git-AI 遵循标准化的代码归属追踪协议，通过 Git Notes 存储代码归属信息：

1. **Authorship Logs** - 记录哪些代码是由 AI 生成的
2. **Git Notes** - 使用 `refs/notes/ai` 命名空间存储归属信息
3. **不修改历史** - 归属信息作为附加元数据存储，不影响 Git 提交历史

### 数据处理流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ AI Agent    │     │ Git-AI      │     │ Git Repo    │
│ (Claude)    │────▶│ Client      │────▶│ (Commit)    │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
                                    ┌─────────────┐
                                    │ Git Notes   │
                                    │ (refs/notes │
                                    │  /ai)       │
                                    └─────────────┘
                                              │
                                              ▼
                                    ┌─────────────┐
                                    │ Web Server  │
                                    │ (upload)    │
                                    └─────────────┘
                                              │
                                              ▼
                                    ┌─────────────┐
                                    │ Database    │
                                    │ (metrics)   │
                                    └─────────────┘
```

### 工作原理

1. **Checkpoints** - AI Agent 调用 `git-ai checkpoint` 记录代码变更
2. **Working Logs** - 工作日志存储在 `.git/ai/working_logs/`
3. **Commit Hooks** - 提交时生成 Authorship Log 并写入 Git Notes
4. **Upload** - Git-AI 客户端将 Metrics 数据上传到 Web 服务器
5. **Aggregation** - 定时任务聚合数据，生成统计报表

## 🔧 开发指南

### 添加新的定时任务

```python
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled

@scheduled(cron="0 2 * * *", job_id="my_task", name="我的任务")
class MyTask(BaseTask):
    def execute(self, context=None):
        self.logger.info('任务开始执行')
        return {'success': True}
```

### 添加新的 API 端点

在 `api/routes/` 中创建新的蓝图文件：

```python
from flask import Blueprint

my_bp = Blueprint('my', __name__, url_prefix='/api/my')

@my_bp.route('/endpoint', methods=['GET'])
def my_endpoint():
    return {'message': 'Hello!'}
```

然后在 `app.py` 中注册蓝图：

```python
from api.routes import my_bp
app.register_blueprint(my_bp)
```

### 添加新的数据库支持

1. 在 `core/database/` 创建新类继承 `Database`
2. 实现所有抽象方法
3. 在 `core/database/factory.py` 中添加工厂逻辑

## 🦀 Git-AI 客户端开发

### 环境要求

- Rust 1.93+
- nix（推荐，用于开发环境管理）

### 构建与测试

```bash
cd git-ai

# 构建
cargo build                              # debug build
cargo build --release                    # release build
cargo build --features test-support      # debug build with git2

# 测试
cargo test                               # all tests (parallel)
cargo test --test-threads=8              # CI thread count
cargo test <test_name>                   # single test
cargo test --test simple_additions       # single test file

# Lint & Format
cargo clippy                             # lint
cargo fmt -- --check                     # format check
cargo fmt                                # auto-format
```

### 架构概述

Git-AI 客户端采用二进制分发模式，单个二进制文件根据 `argv[0]` 决定行为：

- **`git` 模式** - 作为 Git 命令代理，拦截并处理 Git 命令
- **`git-ai` 模式** - 直接执行 git-ai 子命令（blame、status、checkpoint 等）

### 核心数据流

```
checkpoint --> working log --> authorship note
```

1. **Checkpoint** - AI Agent 调用 `git-ai checkpoint` 记录代码变更
2. **Working Log** - 数据存储在 `.git/ai/working_logs/` 中
3. **Authorship Note** - 提交时生成并作为 Git Note 存储在 `refs/notes/ai`

### 关键目录

- `src/commands/` - Git 命令处理和 Hook
- `src/core/` - 核心业务逻辑
- `src/feature_flags.rs` - 功能开关配置
- `tests/` - 集成测试

详细文档请参考 [`git-ai/AGENTS.md`](git-ai/AGENTS.md)

## 📈 时序图

### Metrics 数据上传与处理流程

```mermaid
sequenceDiagram
    autonumber
    participant Client as Git-AI 客户端
    participant API as Python 服务端<br/>/worker/metrics
    participant RawDB as 原始数据表<br/>metrics_events_raw
    participant Task as 定时任务<br/>MetricsEventProcessor
    participant EventDB as 事件表<br/>metrics_committed等
    participant StatsDB as 统计表<br/>metrics_daily_stat等

    Note over Client,API: 第一阶段：数据上传
    Client->>API: POST /worker/metrics/upload<br/>{events: [...], v: 1}
    API->>RawDB: save_metrics_raw()<br/>extract=0, received_at=timestamp
    RawDB-->>API: raw_id
    API-->>Client: {success: true, raw_id: xxx}

    Note over Task,StatsDB: 第二阶段：定时处理 (每2分钟执行)
    Note over Task: cron="*/2 * * * *" 触发
    Task->>RawDB: get_pending_raw_records(limit=100)
    RawDB-->>Task: [原始记录列表]

    loop 批处理循环
        Task->>RawDB: mark_raw_extracting(raw_id, extract=1)
        Task->>Task: process_raw_event()<br/>解析 events 数组

        Note over Task,EventDB: 解析并存入事件表
        alt event.type == Committed (1)
            Task->>EventDB: save_committed()
        else if event.type == Checkpoint (2)
            Task->>EventDB: save_checkpoint()
        else if event.type == AgentUsage (4)
            Task->>EventDB: save_agent_usage()
        else if event.type == InstallHooks (5)
            Task->>EventDB: save_install_hooks()
        end

        Note over Task,StatsDB: 更新处理状态
        alt 处理成功
            Task->>StatsDB: get_or_create_repository()
            Task->>StatsDB: get_or_create_contributor()
            Task->>StatsDB: ensure_repo_contributor_link()
            Task->>RawDB: mark_raw_extracted(raw_id, success=true, extract=2)
        else 处理失败
            Task->>RawDB: mark_raw_extracted(raw_id, success=false, extract=3)
        end
    end

    Task-->>Task: 处理完成统计<br/>{processed, successful, failed}
```

### Authorship Notes 同步流程

```mermaid
sequenceDiagram
    autonumber
    participant Git as Git 仓库
    participant GitAI as Git-AI 客户端
    participant API as Python 服务端<br/>/worker/authorship_notes
    participant DB as Notes 数据库
    participant User as 用户/IDE

    Note over User,Git: 场景1：提交后同步 Notes
    User->>Git: git commit
    Git->>GitAI: post-commit hook 触发
    GitAI->>GitAI: 读取 .git/ai/working_logs/
    GitAI->>GitAI: 生成 Authorship Log
    GitAI->>Git: git notes --ref=ai add <commit> <log>
    Git-->>GitAI: Notes 写入成功

    Note over GitAI,DB: 尝试推送 Notes
    GitAI->>API: POST /worker/notes/push<br/>{repo_url, notes: [...]}

    API->>DB: create_or_update_note()<br/>(批量插入/更新)
    loop 遍历每个 note
        alt note 不存在
            DB->>DB: INSERT INTO git_notes
        else note 已存在
            DB->>DB: UPDATE git_notes<br/>SET content=..., updated_at=...
        end
    end
    DB-->>API: {created: N, updated: M}
    API-->>GitAI: {ok: true, data: {...}}

    Note over User,Git: 场景2：用户查询 Notes
    User->>GitAI: git-ai blame <file>
    GitAI->>Git: git notes --ref=ai show <commit>

    alt 本地 Notes 不存在
        GitAI->>API: POST /worker/notes/get<br/>{repo_url, commit_sha}
        API->>DB: get_note(repo_url, commit_sha)
        DB-->>API: note 记录
        API-->>GitAI: {ok: true, data: note}
        GitAI->>GitAI: 解析 Authorship Log
        GitAI-->>User: 显示 AI/人类 代码归属
    else 本地 Notes 存在
        GitAI->>GitAI: 直接使用本地的 Authorship Log
        GitAI-->>User: 显示 AI/人类 代码归属
    end

    Note over User,Git: 场景3：批量获取 Notes
    GitAI->>API: POST /worker/notes/batch<br/>{repo_url, commit_shas: [...]}
    API->>DB: batch_get_notes(repo_url, commit_shas)
    DB-->>API: {notes: [...], missing: [...]}
    API-->>GitAI: {ok: true, data: {...}}
    GitAI-->>User: 批量处理并显示
```

### 定时任务调度架构

```mermaid
sequenceDiagram
    autonumber
    participant Config as config.yaml
    participant Scheduler as AICodeScheduler
    participant Registry as TaskRegistry
    participant Task1 as Metrics事件处理任务
    participant Task2 as Git Blame统计任务
    participant Task3 as Cleanup清理任务
    participant DB as 数据库

    Note over Config,Scheduler: 启动阶段
    Config->>Scheduler: 加载配置<br/>{scheduler.enabled=true}
    Scheduler->>Registry: register_all()<br//>扫描 @scheduled 装饰器

    Registry->>Task1: 发现任务<br/>cron="*/2 * * * *"<br/>job_id="metrics_event_processor"
    Registry->>Task2: 发现任务<br/>cron="0 */1 * * *"<br/>job_id="git_blame_stats"
    Registry->>Task3: 发现任务<br/>cron="0 2 * * *"<br/>job_id="cleanup_task"

    Registry-->>Scheduler: 已注册任务列表
    Scheduler->>Scheduler: 启动 APScheduler
    Scheduler-->>Scheduler: 任务调度就绪

    Note over Task1,DB: 运行阶段 - Metrics事件处理
    Note over Task1: 每2分钟触发
    Task1->>DB: 查询 extract=0 的原始数据
    DB-->>Task1: 返回待处理记录

    loop 批处理
        Task1->>DB: 标记 extract=1 (处理中)
        Task1->>Task1: 解析并存储事件
        Task1->>DB: 标记 extract=2 (成功)<br/>或 extract=3 (失败)
    end

    Note over Task2,DB: 运行阶段 - Git Blame统计
    Note over Task2: 每小时触发
    Task2->>Task2: 克隆或更新 Git 仓库
    Task2->>Task2: 执行 git blame
    Task2->>DB: 存储统计结果

    Note over Task3,DB: 运行阶段 - 清理任务
    Note over Task3: 每天2点触发
    Task3->>DB: 删除过期数据
    Task3->>DB: 清理临时文件
```

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/unit/test_database/test_metrics_db.py

# 运行带覆盖率的测试
pytest --cov=core tests/
```

## 📊 数据架构

### 核心数据表

| 表名 | 说明 |
|------|------|
| `metrics_events_raw` | Metrics 原始事件数据 |
| `metrics_committed` | Committed 事件记录 |
| `metrics_checkpoint` | Checkpoint 事件记录 |
| `metrics_daily_stat` | 按天统计 |
| `metrics_weekly_stat` | 按周统计 |
| `metrics_repo_stat` | 按仓库统计 |
| `blame_stats` | Git Blame 统计数据 |
| `git_notes` | Git Notes 数据 |

详细表结构请参考 [`sql/`](sql/) 目录下的 SQL 文件。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 代码规范

- 后端遵循 PEP 8 编码规范
- 前端遵循 ESLint + Prettier 规范
- 提交信息遵循 Conventional Commits 规范

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 📞 联系方式

如有问题或建议，欢迎通过以下方式联系：

- 提交 [Issue](https://github.com/your-repo/issues)
- 发送邮件至 your.email@example.com

---

<div align="center">

**Made with ❤️ by Git AI Team**

</div>
