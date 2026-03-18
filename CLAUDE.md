# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 Git-AI Metrics API 统计仓库中 AI 生成代码占比的工具 v2.0。项目采用 Flask 后端 + Vue 3 前端架构，支持多数据库。

数据来源：Git-AI 客户端通过 `/worker/metrics/upload` API 上传 Metrics 数据，系统存储到数据库后通过定时任务进行多维度统计分析。

## 核心架构

### 数据库适配器 (`core/database/`)
- `base.py` - 定义 `Database` 抽象基类，包含统一接口：`init_db`, `save_stats`, `get_latest_stat` 以及 Metrics 相关方法
- `factory.py` - 工厂方法 `create_database(config)` 根据配置创建对应数据库实例
- 实现类：`SQLiteDatabase` (sqlite.py), PostgreSQL/MySQL (待实现)

### 数据模型 (`core/models/`)
使用 `@dataclass` 和 `dataclass_json` 库定义数据结构：

**原有统计模型：**
- `StatRecord` - 整体统计数据
- `RepoStatRecord` - 仓库级统计数据
- `ContributorStatRecord` - 贡献者级统计数据
- `RepoContributorStatRecord` - 仓库+贡献者组合统计数据

**Metrics 相关模型：**
- `MetricsRawRecord` - Metrics 原始批次记录
- `MetricsCommittedRecord` - Committed 事件记录
- `MetricsCheckpointRecord` - Checkpoint 事件记录
- `MetricsAgentUsageRecord` - AgentUsage 事件记录
- `MetricsInstallHooksRecord` - InstallHooks 事件记录
- `MetricsDailyStat` - 按天统计
- `MetricsWeeklyStat` - 按周统计
- `MetricsMonthlyStat` - 按月统计
- `MetricsRepoStat` - 按仓库统计
- `MetricsContributorStat` - 按贡献者统计

### 业务服务层 (`core/services/`)
- `MetricsService` - Metrics 数据处理服务
- `OAuthService` - OAuth 设备授权流程服务
- `CasService` - CAS (Content Addressable Storage) 服务

### 路由蓝图 (`api/routes/`)
- `stats_bp` - 统计分析 API 路径前缀 `/api/stats`
- `projects_bp` - 项目管理 API
- `scheduler_bp` - 调度管理 API
- `git_ai_bp` - Git AI 相关 API (用户界面)
- `metrics_bp` - Metrics API 路径前缀 `/worker/metrics`
- `cas_bp` - CAS API 路径前缀 `/worker/cas`
- `oauth_bp` - OAuth API 路径前缀 `/worker/oauth`
- `releases_bp` - Releases API 路径前缀 `/worker/releases`

### 中间件 (`core/middleware/`)
- `auth_required` - 认证装饰器，支持 Authorization Header 或 X-API-Key

### 调度器 (`core/scheduler/`)
定时任务系统使用注解和元类实现自动注册：

- `@scheduled` - 任务装饰器，声明 cron 表达式和任务配置
- `BaseTask` - 任务基类，提供通用能力（logger、database、钩子）
- `TaskMeta` - 元类，自动注册任务到 TaskRegistry
- `TaskRegistry` - 任务注册表，存储所有已注册任务
- `AICodeScheduler` - 调度器，从 TaskRegistry 发现任务并启动

**创建新任务**：

```python
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta

@scheduled(cron="0 2 * * *", job_id="my_task", name="我的任务")
class MyTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context=None):
        self.logger.info('任务开始执行')
        return {'success': True}
```

**配置覆盖**：

```yaml
scheduler:
  enabled: true
  jobs:
    my_task:
      cron: "0 10 * * *"
      enabled: false
```

## 常用命令

### 后端开发
```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 设置必要的密钥

# 启动应用（会自动编译前端）
python app.py
```

### 前端开发
```bash
cd frontend
npm install        # 安装依赖
npm run dev        # 开发模式 (默认端口 5173)
npm run build      # 构建生产版本
npm run preview    # 预览构建结果
```

### 数据库初始化
```bash
# SQLite (默认)
sqlite3 data/ai_stats.db < sql/metrics_schema_sqlite.sql

# PostgreSQL
psql -U username -d database_name < sql/metrics_schema_postgresql.sql
```

### 跳过前端构建
设置环境变量 `BUILD_FRONTEND=0` 或 `BUILD_FRONTEND=false` 可以跳过前端构建（假设已有编译输出）。

## 配置说明

### config.yaml
主要配置文件，使用 YAML 格式，支持环境变量替换（语法：`${VAR_NAME}` 或 `${VAR_NAME:default}`）：
- `features` - 功能开关
- `database` - 数据库配置，支持 sqlite/postgresql/mysql
- `scheduler` - 定时任务配置
- `web` - Web 服务配置（host, port, debug）
- `logging` - 日志配置
- `git_ai` - Git-AI 服务配置（OAuth, CAS, Metrics, Releases）

### Git-AI 配置
```yaml
git_ai:
  enabled: true
  oauth:
    secret_key: ${GIT_AI_OAUTH_SECRET:default-secret-key}
    token_expiry_hours: 1
    refresh_token_expiry_days: 90
  cas:
    enabled: true
    max_objects_per_request: 100
  metrics:
    enabled: true
    max_events_per_batch: 250
  releases:
    enabled: true
    version: ${RELEASE_VERSION:0.0.0}
```

### 配置加载
使用 `ConfigLoader` 类加载配置，该类会：
1. 读取 YAML 文件
2. 递归替换环境变量占位符
3. 验证配置完整性
4. 提供点号分隔路径访问方法 `get('database.type')`

## 关键开发模式

### 添加新的数据库支持
1. 在 `core/database/` 创建新 Database 类继承 `Database`
2. 实现所有抽象方法（包括表结构初始化）
3. 在 `factory.py` 的 `create_database` 函数中添加新类型支持
4. 在 `config.yaml` 中添加对应配置节点

### 添加新的 API 端点
1. 在 `api/routes/` 中创建新的蓝图文件
2. 使用 Blueprint 定义路由和处理器
3. 在 `app.py` 中注册蓝图

## 应用启动流程

1. 检查并构建前端（如果 `BUILD_FRONTEND` 不是 falsy）
2. 加载配置 `config.yaml`（处理环境变量替换）
3. 创建 Flask 应用，静态文件目录指向编译后的 `dist`
4. 注册所有 API 蓝图
5. 如果 `scheduler.enabled=true`，启动调度器并添加定时任务
6. 配置日志并启动服务器

## 数据流

1. **数据接收**: Git-AI 客户端通过 `POST /worker/metrics/upload` 上传 Metrics 数据
2. **数据存储**: 存储到 `metrics_events_raw` (原始 JSON) 和对应的解析表
3. **定时聚合**: 定时任务从 Metrics 原始表读取数据，按不同维度聚合统计
4. **数据查询**: 用户通过前端 API 查询汇总后的统计数据

## 环境变量

可选的环境变量：
- `GIT_AI_OAUTH_SECRET` - OAuth 服务密钥
- `RELEASE_VERSION` - Git-AI 版本号
- `DB_PASSWORD` - 数据库密码（用于 PostgreSQL/MySQL）
