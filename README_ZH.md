# Git AI 代码统计工具

团队用了 Cursor、Copilot 等 AI 写代码，但说不清「到底多少代码是 AI 写的」。本工具基于 [git-ai](https://github.com/git-ai-project/git-ai) 写入的 Git Notes（`refs/notes/ai`），从 GitLab 拉取提交与 AI 归属数据，按时间范围、仓库或部门统计 **AI 代码占比**，用一张表、一张图把结果摊开，方便做复盘、汇报和趋势观察。

<img width="2120" height="1020" alt="image" src="https://github.com/user-attachments/assets/65e7f32d-9258-41d8-a4eb-3f0e91261f50" />


![image.png](https://fastly.jsdelivr.net/gh/skrphp/img0@main/2026/02/12/1770864283238-0b7c0dfb-35f7-4f24-87b0-1faf0c3fb5e7.png)

**项目基于：[git-ai](https://github.com/git-ai-project/git-ai)**（追踪 AI 生成代码的 Git 扩展）及其 [Git AI Standard](https://github.com/git-ai-project/git-ai) 约定。

## 功能

- 按日期范围统计多仓库的 AI 代码占比
- 支持部门/分组配置，按组筛选仓库
- 总体统计 + 各仓库详情（行数、提交数、占比）
- **可展开查看提交明细**：点击仓库卡片展开，查看每个 commit 的 AI 代码详情
- **智能提交搜索**：超过 5 个 commit 时自动显示搜索框，支持按 commit ID 或消息内容实时过滤
- 深色主题 Web 界面，日期选择、结果图表展示

## 环境要求

- Python 3.8+
- GitLab 实例（含 Git Notes `refs/notes/ai` 数据，如 Cursor / 其他 AI 编码工具写入的 AI 行数信息）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制示例配置并填写 GitLab 令牌：

```bash
cp .env.example .env
# 编辑 .env，设置 GITLAB_PRIVATE_TOKEN
```

| 变量 | 必填 | 说明 |
|------|------|------|
| `GITLAB_PRIVATE_TOKEN` | 是 | GitLab Personal Access Token，需 `read_api`、`read_repository` |
| `GITLAB_BASE_URL` | 否 | GitLab 地址，默认 `https://gitlab.com` |
| `GIT_AI_REPOS_CONFIG` | 否 | 仓库配置 JSON 路径，默认项目根目录 `repos_config.json` |

### 3. 配置仓库列表

编辑 `repos_config.json`：

**简单格式（无分组）：**

```json
{
  "repos": [
    {
      "id": "123456",
      "name": "我的项目",
      "branch": "main"
    }
  ]
}
```

**按部门分组：**

```json
{
  "前端": [
    { "id": "111", "name": "web-app", "branch": "main" }
  ],
  "后端": [
    { "id": "222", "name": "api-server", "branch": "master" }
  ]
}
```

- `id`：GitLab 项目 ID（项目主页或 URL 中的 project id）
- `name`：展示名称
- `branch`：要统计的分支

### 4. 启动服务

```bash
python app.py
```

浏览器访问 **http://127.0.0.1:8888**，选择时间范围与部门（若有），点击「开始统计」即可。

## 使用界面

### 查看统计结果

统计完成后，你会看到：
- **总体概览**：AI 代码总占比、代码行数、提交数
- **仓库卡片**：每个仓库显示 AI 占比、进度条、提交统计

### 查看提交明细

**点击任意仓库卡片**即可展开，查看每个 commit 的详细信息：
- 提交消息和 SHA 值
- 作者和日期
- 新增行数 vs AI 生成行数
- 每个 commit 的 AI 占比

### 搜索提交记录

当某个仓库的提交数**超过 5 个**时，会自动显示搜索框：
- **按 commit ID 过滤**：输入 SHA 的任意部分（如 `a3f2b`）
- **按消息内容过滤**：搜索提交消息（如 `修复bug`、`添加功能`）
- **实时过滤**：输入时即时更新结果
- **动态计数**：显示符合搜索条件的提交数量
- **清除搜索**：删除搜索文本即可恢复显示所有提交

## 工作原理

1. **Commits**：GitLab API 获取指定时间范围内各仓库、分支的提交列表及 `additions`/`deletions`。
2. **AI Notes**：对每个 commit 请求 `refs/notes/ai` 下的 Note 文件；若存在则解析其中的 JSON。
3. **统计**：汇总各 commit 的 `accepted_lines`（AI 接受行数）与 `additions`（总新增行数），计算占比。

AI 数据格式需与 Cursor 等工具写入的 Git Notes 一致（含 `prompts` 及每个 prompt 的 `accepted_lines` 等字段）。

## 项目结构

```
.
├── app.py              # Flask 入口
├── git_ai_stats.py     # 统计与 API 逻辑
├── index.html          # 前端页面
├── repos_config.json   # 仓库配置（需自行配置）
├── requirements.txt
├── .env.example
├── README.md
└── README_ZH.md
```

## License

MIT

## 生产环境部署

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB 可用内存
- 至少 5GB 可用磁盘空间

### 快速部署

1. **克隆代码**

```bash
git clone <repository-url>
cd git-ai-code-metrics
```

2. **配置环境变量**

```bash
cp .env.production.example .env.production
# 编辑 .env.production 填写配置
nano .env.production
```

**必需配置：**
- `DB_PASSWORD`: PostgreSQL 数据库密码
- `SECRET_KEY`: Flask 会话密钥（建议随机生成）
- `GIT_AI_OAUTH_SECRET`: OAuth 服务密钥

3. **构建前端（如静态文件不存在）**

```bash
cd frontend
pnpm install
pnpm build
cd ..
```

4. **一键部署**

```bash
./deploy.sh
```

### 手动部署

如果 `deploy.sh` 不可用，可以手动执行：

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 服务管理

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f [service_name]

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 进入应用容器
docker-compose exec flask bash

# 进入数据库容器
docker-compose exec postgres psql -U gitai -d gitai_stats
```

### 数据备份

```bash
# 备份数据库
docker-compose exec postgres pg_dump -U gitai gitai_stats > backup.sql

# 恢复数据库
docker-compose exec -T postgres psql -U gitai gitai_stats < backup.sql
```

### 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose build
docker-compose up -d
```

### 故障排查

**服务无法启动：**

```bash
# 查看服务日志
docker-compose logs [service_name]

# 进入容器检查
docker-compose exec flask bash
```

**健康检查失败：**

```bash
# 检查网络连接
docker network ls
docker network inspect git-ai-code-metrics_git-ai-network
```

**数据库连接失败：**

```bash
# 检查数据库是否启动
docker-compose ps postgres

# 测试数据库连接
docker-compose exec postgres pg_isready -U gitai
