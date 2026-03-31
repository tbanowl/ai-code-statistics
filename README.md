# Git AI 代码统计工具 v2.0

团队使用了 Cursor、Copilot 等 AI 工具写代码，本工具基于 Git Notes (`refs/notes/ai`) 统计 AI 生成代码的占比。

## 新版本特性

- 支持多 Git 平台（GitLab、GitHub）
- 支持多数据库（SQLite、PostgreSQL、MySQL）
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

详见 [config.yaml](config.yaml) 文件。

## API 文档

### 统计分析 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/stats/analyze` | 执行统计分析 |
| GET | `/api/v1/stats/latest` | 获取最新统计结果 |
| GET | `/api/v1/stats/history` | 获取统计历史记录 |
| GET | `/api/v1/stats/{stat_id}` | 获取指定统计详情 |

### 项目管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/projects/` | 获取项目列表 |
| GET | `/api/v1/projects/departments` | 获取部门列表 |

### 调度管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/scheduler/jobs` | 获取所有任务 |
| GET | `/api/v1/scheduler/jobs/{job_id}` | 获取任务状态 |

## 项目结构

```
git-ai-code-metrics/
├── app.py              # 应用入口
├── config.yaml         # 配置文件
├── core/               # 核心模块
│   ├── config/         # 配置加载
│   ├── git_providers/  # Git 平台适配器
│   ├── database/       # 数据库适配器
│   ├── models/         # 数据模型
│   ├── scheduler/      # 定时任务
│   └── services/       # 业务逻辑
├── api/                # API 路由
│   ├── routes/         # 路由定义
│   └── schemas/        # 数据结构
├── data/               # 数据目录
├── logs/               # 日志目录
└── tests/              # 测试
```

## License

MIT
