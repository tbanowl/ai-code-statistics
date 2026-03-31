# 生产环境部署设计文档

**日期**: 2026-03-24
**版本**: 1.0
**作者**: Claude Code

---

## 1. 概述

本文档定义 Git AI 代码统计工具 v2.0 的生产环境部署方案。采用 Docker 容器化部署，包含 Nginx 反向代理、Flask Web 应用和 PostgreSQL 数据库，使用 Docker Compose 编排。

### 1.1 目标

- 实现一键部署和更新
- 确保数据持久化和高可用性
- 提供安全的网络隔离
- 支持无缝回滚

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      宿主机 / 服务器                      │
│                                                         │
│  ┌──────────────┐       ┌──────────────┐              │
│  │    Nginx     │───────│   Flask      │              │
│  │  (80/443)    │       │   (5000)     │              │
│  └──────────────┘       └──────────────┘              │
│         │                        │                      │
│         └────────────────────────┘                      │
│                    Docker 网络 (git-ai-network)       │
│                                │                       │
│                       ┌──────────────┐                │
│                       │ PostgreSQL   │                │
│                       │  (5432)      │                │
│                       └──────────────┘                │
└─────────────────────────────────────────────────────────┘
                     数据卷持久化
```

### 2.2 服务说明

| 服务 | 镜像 | 端口 | 作用 | 依赖 |
|------|------|------|------|------|
| Nginx | nginx:alpine | 80/443 | 反向代理、静态文件、HTTPS | Flask 应用 |
| Flask | git-ai-stats | 5000 | Web 应用 API | PostgreSQL |
| PostgreSQL | postgres:15-alpine | 5432 | 数据库 | 无 |

## 3. 文件结构

```
git-ai-code-metrics/
├── .docker/
│   ├── nginx/
│   │   └── nginx.conf          # Nginx 配置
│   └── postgres/               # PostgreSQL 初始化脚本（可选）
├── docker-compose.yml          # Docker Compose 配置
├── Dockerfile                  # 应用镜像构建文件
├── .dockerignore               # Docker 构建忽略文件
├── .env.production             # 生产环境变量
├── config.yaml                 # 应用配置（数据库 URL 需调整）
└── deploy.sh                   # 一键部署脚本
```

## 4. Dockerfile 设计

### 4.1 基础镜像

使用 `python:3.11-slim` 作为基础镜像，确保镜像体积小且包含运行所需依赖。

### 4.2 构建步骤

1. 安装系统依赖（GCC、PostgreSQL 客户端库）
2. 安装 Python 依赖
3. 复制应用代码
4. 创建非 root 用户
5. 配置 Gunicorn 作为 WSGI 服务器

### 4.3 关键要点

- 使用多阶段构建减小镜像体积
- 确保静态文件已编译
- 数据库 URL 通过环境变量覆盖配置文件

## 5. Nginx 配置设计

### 5.1 主要功能

- 前端静态文件服务
- API 请求代理（`/api/*` 和 `/worker/*`）
- HTTP/HTTPS 协议处理
- WebSocket 支持预留

### 5.2 关键指令

- `proxy_pass` 反向代理到 Flask 容器
- 静态文件缓存设置
- 请求头转发（`X-Real-IP`, `X-Forwarded-For` 等）

## 6. 数据库迁移设计

### 6.1 Schema 转换

使用项目现有文件 `sql/metrics_schema_postgresql.sql`。

### 6.2 配置更新

`config.yaml` 中的数据库 URL：
```yaml
database:
  url: postgresql://gitai:${DB_PASSWORD}@postgres:5432/gitai_stats
```

### 6.3 数据持久化

PostgreSQL 容器使用命名卷 `postgres_data` 持久化数据。

## 7. 环境变量设计

### 7.1 生产环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `DB_PASSWORD` | PostgreSQL 密码 | 随机生成 |
| `POSTGRES_DB` | 数据库名称 | gitai_stats |
| `POSTGRES_USER` | 数据库用户名 | gitai |
| `SECRET_KEY` | Flask 会话密钥 | 随机生成 |
| `GIT_AI_OAUTH_SECRET` | OAuth 服务密钥 | 从环境获取 |
| `RELEASE_VERSION` | 版本号 | 2.0.0 |

### 7.2 配置文件

使用 `.env.production` 文件管理环境变量，不提交到 git。

## 8. 部署流程

### 8.1 首次部署

1. 克隆代码到服务器
2. 复制并配置 `.env.production`
3. 运行 `docker-compose up -d` 启动所有服务
4. 验证健康检查 `curl http://localhost/health`

### 8.2 更新部署

1. 拉取最新代码
2. 重新构建镜像：`docker-compose build`
3. 滚动更新：`docker-compose up -d`
4. 数据库迁移（如有 schema 变更）

### 8.3 回滚方案

```bash
# 回滚到上一版本
git revert HEAD
docker-compose build
docker-compose up -d
```

## 9. 日志与监控

### 9.1 日志管理

- 所有容器日志通过 Docker `docker-compose logs` 统一查看
- 应用日志写入 `.logs` 目录（可通过 volume 映射）

### 9.2 健康检查

| 服务 | 检查方式 |
|------|----------|
| Nginx | 检查 80 端口 |
| Flask | `/health` 端点 |
| PostgreSQL | 数据库连接检测 |

### 9.3 备份策略

PostgreSQL 数据卷定期通过 `pg_dump` 备份到外部存储。

## 10. 安全性设计

### 10.1 网络安全

- 只暴露 80/443 端口
- 数据库仅在内网 Docker 网络中通信
- 使用自定义网络隔离服务

### 10.2 HTTPS 支持

Nginx 支持 Lets Encrypt 证书（需额外配置 certbot）。

### 10.3 容器安全

- 容器内应用以非 root 用户运行
- 使用 `.dockerignore` 排除敏感文件和目录

### 10.4 数据安全

- 敏感配置通过环境变量传递
- `.env.production` 不提交到 git
- 数据库密码随机生成

## 11. 部署脚本

### 11.1 deploy.sh 功能

- 检查 Docker 是否已安装
- 检查 `.env.production` 是否存在
- 构建和启动服务
- 等待服务健康
- 显示部署状态

### 11.2 使用方式

```bash
chmod +x deploy.sh
./deploy.sh
```

## 12. 后续优化方向

1. **CI/CD 集成**：与 GitLab CI/CD 或 GitHub Actions 集成
2. **自动化备份**：定时备份 PostgreSQL 数据
3. **监控告警**：集成 Prometheus + Grafana
4. **HTTPS 自动化**：集成 Certbot 自动续期

## 13. 变更记录

| 日期 | 版本 | 说明 | 作者 |
|------|------|------|------|
| 2026-03-24 | 1.0 | 初始版本 | Claude Code |
