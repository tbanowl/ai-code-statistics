# 生产环境部署实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 通过 Docker 容器化部署 Git AI 代码统计工具 v2.0 到生产环境，包括 Nginx 反向代理、Flask Web 应用和 PostgreSQL 数据库。

**架构:** 使用 Docker Compose 编排三个服务：Nginx（反向代理）→ Flask（Web 应用）→ PostgreSQL（数据库）。所有服务运行在自定义 Docker 网络中，通过数据卷持久化数据。

**技术栈:** Docker, Docker Compose, Nginx (alpine), Python 3.11, PostgreSQL 15, Gunicorn

---

## Task 1: 创建 Docker 目录结构

**文件:**
- Create: `.docker/nginx/nginx.conf`
- Create: `.dockerignore`

**Step 1: 创建 Docker 目录**

```bash
mkdir -p .docker/nginx
```

**Step 2: 创建 .dockerignore 文件**

```bash
cat > .dockerignore << 'EOF'
# Git
.git
.gitignore
.gitattributes

# 环境变量
.env
.env.*
!.env.example

# 日志
.logs
*.log

# 虚拟环境
venv/
__pycache__/
*.pyc
*.pyo
*.pyd

# IDE
.idea/
.vscode/
*.swp
*.swo

# 测试
.pytest_cache/
.coverage
htmlcov/

# 文档和计划
docs/
plans/

# Docker
.docker/
Dockerfile
docker-compose.yml

# 临时文件
node_modules/
static/
dist/
*.tmp
*.bak
EOF
```

**Step 3: 创建 Nginx 配置目录的占位文件**

```bash
touch .docker/nginx/.gitkeep
```

**Step 4: Commit**

```bash
git add .docker/.gitkeep .dockerignore
git commit -m "feat: 创建 Docker 基础目录结构"
```

---

## Task 2: 编写 Dockerfile

**文件:**
- Create: `Dockerfile`

**Step 1: 编写 Dockerfile**

```bash
cat > Dockerfile << 'EOF'
# 多阶段构建 - 构建阶段
FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --user -r requirements.txt

# 运行阶段
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    gunicorn \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 Python 包
COPY --from=builder /root/.local /root/.local

# 添加 Python 包到 PATH
ENV PATH=/root/.local/bin:$PATH

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# 复制应用代码
COPY --chown=appuser:appuser . .

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)" || exit 1

# 启动命令
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120"]
EOF
```

**Step 2: Commit**

```bash
git add Dockerfile
git commit -m "feat: 添加应用 Dockerfile"
```

---

## Task 3: 编写 Nginx 配置文件

**文件:**
- Create: `.docker/nginx/nginx.conf`
- Modify: `.dockerignore`

**Step 1: 编写 Nginx 配置**

```bash
cat > .docker/nginx/nginx.conf << 'EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    keepalive_timeout 65;
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    server {
        listen 80;
        server_name _;

        # 客户端最大上传大小
        client_max_body_size 50M;

        # 前端静态文件
        location / {
            root /usr/share/nginx/html;
            try_files $uri $uri/ /index.html;

            # 静态资源缓存
            location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
                expires 1y;
                add_header Cache-Control "public, immutable";
            }
        }

        # API 路由代理到 Flask
        location /api/ {
            proxy_pass http://flask:5000/api/;
            proxy_set_buffering off;

            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # 超时设置
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Worker 路由代理到 Flask
        location /worker/ {
            proxy_pass http://flask:5000/worker/;
            proxy_set_buffering off;

            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # 超时设置（上传可能需要更长时间）
            proxy_connect_timeout 300s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
        }

        # Swagger 文档
        location /swagger {
            proxy_pass http://flask:5000/;

            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # 健康检查
        location /health {
            proxy_pass http://flask:5000/health;
            access_log off;
        }

        # 隐藏 Nginx 版本
        server_tokens off;
    }
}
EOF
```

**Step 2: 更新 .dockerignore**

删除占位文件行，确保 Nginx 配置被包含。

**Step 3: Commit**

```bash
git add .docker/nginx/nginx.conf .dockerignore
git commit -m "feat: 添加 Nginx 配置文件"
```

---

## Task 4: 编写 Docker Compose 配置

**文件:**
- Create: `docker-compose.yml`
- Create: `.env.production.example`

**Step 1: 编写 docker-compose.yml**

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  # PostgreSQL 数据库
  postgres:
    image: postgres:15-alpine
    container_name: git-ai-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-gitai}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-gitai_stats}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./sql:/docker-entrypoint-initdb.d:ro
    networks:
      - git-ai-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-gitai} -d ${POSTGRES_DB:-gitai_stats}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Flask Web 应用
  flask:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        BUILD_FRONTEND: ${BUILD_FRONTEND:-0}
    container_name: git-ai-flask
    restart: unless-stopped
    environment:
      # 数据库配置（覆盖 config.yaml）
      DB_PASSWORD: ${DB_PASSWORD}
      POSTGRES_USER: ${POSTGRES_USER:-gitai}
      POSTGRES_DB: ${POSTGRES_DB:-gitai_stats}
      # 应用配置
      SECRET_KEY: ${GIT_AI_OAUTH_SECRET}
      GIT_AI_OAUTH_SECRET: ${GIT_AI_OAUTH_SECRET}
      RELEASE_VERSION: ${RELEASE_VERSION:-2.0.0}
    volumes:
      # 数据持久化
      - app_data:/app/data
      # 日志映射（可选）
      - app_logs:/app/.logs
    networks:
      - git-ai-network
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:5000/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Nginx 反向代理
  nginx:
    image: nginx:alpine
    container_name: git-ai-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./.docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./static:/usr/share/nginx/html:ro
    networks:
      - git-ai-network
    depends_on:
      flask:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

networks:
  git-ai-network:
    driver: bridge

volumes:
  postgres_data:
    driver: local
  app_data:
    driver: local
  app_logs:
    driver: local
EOF
```

**Step 2: 创建 .env.production.example**

```bash
cat > .env.production.example << 'EOF'
# 数据库配置
DB_PASSWORD=your_secure_password_here
POSTGRES_DB=gitai_stats
POSTGRES_USER=gitai

# 应用配置
SECRET_KEY=your_secret_key_here

# Git-AI 配置
GIT_AI_OAUTH_SECRET=your_oauth_secret_here
RELEASE_VERSION=2.0.0

# 构建配置
BUILD_FRONTEND=0
EOF
```

**Step 3: 创建生产环境变量模板**

```bash
# 创建 .env.production（实际部署时填写真实值）
cp .env.production.example .env.production
```

**Step 4: 更新 .gitignore 确保 .env.production 不被提交**

检查 `.gitignore` 中是否包含 `.env*`，如果已包含则跳过。

**Step 5: Commit**

```bash
git add docker-compose.yml .env.production.example
git commit -m "feat: 添加 Docker Compose 配置"
```

---

## Task 5: 更新应用配置支持 PostgreSQL

**文件:**
- Modify: `config.yaml`

**Step 1: 备份当前配置**

```bash
cp config.yaml config.yaml.backup
```

**Step 2: 更新 config.yaml 数据库配置**

```bash
# 修改 database.url 支持环境变量替换
# 将原来的 SQLite 配置改为以下内容：
sed -i 's|url: sqlite:///data/ai_stats.db|url: postgresql://gitai:${DB_PASSWORD}@postgres:5432/gitai_stats|' config.yaml
```

**Step 3: 更新生产环境配置（关闭 debug 模式）**

```bash
# 将 web.debug 改为 false
sed -i 's/debug: true/debug: false/' config.yaml
```

**Step 4: 移除或注释 database.echo（生产环境不需要 SQL 回显）**

```bash
sed -i 's/^  echo: True/  # echo: True/' config.yaml
```

**Step 5: 验证配置**

```bash
# 检查配置文件修改
git diff config.yaml
```

**Step 6: Commit**

```bash
git add config.yaml
git commit -m "feat: 配置支持 PostgreSQL 数据库"
```

---

## Task 6: 编写部署脚本

**文件:**
- Create: `deploy.sh`

**Step 1: 编写部署脚本**

```bash
cat > deploy.sh << 'EOF'
#!/bin/bash
set -e

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 输出函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 检查 Docker 是否已安装
check_docker() {
    log_info "检查 Docker..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    if ! docker-compose --version &> /dev/null 2>&1; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi

    log_info "Docker: $(docker --version)"
    log_info "Docker Compose: $(docker-compose --version)"
}

# 检查环境变量文件
check_env_file() {
    log_info "检查环境变量文件..."

    if [ ! -f .env.production ]; then
        log_error "未找到 .env.production 文件"
        log_info "请复制 .env.production.example 并填写配置："
        log_info "  cp .env.production.example .env.production"
        exit 1
    fi

    # 检查必需的环境变量
    source .env.production

    if [ -z "$DB_PASSWORD" ]; then
        log_error "DB_PASSWORD 未设置"
        exit 1
    fi

    log_info "环境变量检查通过"
}

# 停止现有服务
stop_services() {
    log_info "停止现有服务..."
    docker-compose down || true
}

# 构建镜像
build_images() {
    log_info "构建镜像..."
    docker-compose build --no-cache
}

# 启动服务
start_services() {
    log_info "启动服务..."
    docker-compose up -d

    log_info "等待服务启动..."
    sleep 5
}

# 健康检查
health_check() {
    log_info "执行健康检查..."

    # 检查 PostgreSQL
    log_info "检查 PostgreSQL..."
    docker-compose exec -T postgres pg_isready -U ${POSTGRES_USER:-gitai} -d ${POSTGRES_DB:-gitai_stats}

    # 检查 Flask
    log_info "检查 Flask 应用..."
    max_attempts=10
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -sf http://localhost/health > /dev/null 2>&1; then
            log_info "Flask 应用健康检查通过"
            break
        fi
        log_warn "等待 Flask 应用启动... ($attempt/$max_attempts)"
        sleep 3
        attempt=$((attempt + 1))
    done

    if [ $attempt -gt $max_attempts ]; then
        log_error "Flask 应用健康检查失败"
        log_info "查看日志: docker-compose logs flask"
        exit 1
    fi

    # 检查 Nginx
    log_info "检查 Nginx..."
    curl -sf http://localhost/health > /dev/null 2>&1
    log_info "Nginx 健康检查通过"
}

# 显示状态
show_status() {
    log_info "服务状态："
    docker-compose ps
}

# 显示访问信息
show_info() {
    echo ""
    log_info "=========================================="
    log_info "部署完成！"
    log_info "=========================================="
    echo ""
    echo "访问地址:"
    echo "  - Web UI: http://$(hostname -I | awk '{print $1}')"
    echo "  - API 文档: http://$(hostname -I | awk '{print $1}')/swagger"
    echo "  - 健康检查: http://$(hostname -I | awk '{print $1}')/health"
    echo ""
    echo "常用命令:"
    echo "  - 查看日志: docker-compose logs -f"
    echo "  - 停止服务: docker-compose down"
    echo "  - 重启服务: docker-compose restart"
    echo "  - 进入容器: docker-compose exec flask bash"
    echo ""
}

# 主流程
main() {
    log_info "开始部署 Git AI 代码统计工具..."
    echo ""

    check_docker
    check_env_file
    stop_services
    build_images
    start_services
    health_check
    show_status
    show_info

    log_info "部署成功！"
}

# 执行主流程
main
EOF
```

**Step 2: 添加执行权限**

```bash
chmod +x deploy.sh
```

**Step 3: Commit**

```bash
git add deploy.sh
git commit -m "feat: 添加一键部署脚本"
```

---

## Task 7: 编写 README 更新

**文件:**
- Modify: `README_ZH.md`

**Step 1: 在 README_ZH.md 末尾添加生产部署章节**

```bash
cat >> README_ZH.md << 'EOF'

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
EOF
```

**Step 2: Commit**

```bash
git add README_ZH.md
git commit -m "docs: 添加生产环境部署文档"
```

---

## Task 8: 验证部署配置

**文件:**
- Test: 验证 Docker 配置文件

**Step 1: 验证 Dockerfile 语法**

```bash
# 尝试构建镜像（不运行）
docker build --no-cache -f Dockerfile --target builder .
```

**预期输出：** 镜像构建成功，无语法错误

**Step 2: 验证 docker-compose.yml 语法**

```bash
docker-compose config
```

**预期输出：** 配置 YAML 语法正确，显示所有服务配置

**Step 3: 验证 Nginx 配置语法**

```bash
docker run --rm -v "$PWD/.docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:alpine nginx -t
```

**预期输出：** `syntax is ok`, `test is successful`

**Step 4: 更新 .dockerignore 确保部署脚本被包含**

```bash
# 检查 deploy.sh 是否被排除
grep -q "deploy.sh" .dockerignore && echo "ERROR: deploy.sh 被 .dockerignore 排除" || echo "OK: deploy.sh 未被排除"
```

**Step 5: Commit**

```bash
git add .dockerignore
git commit -m "fix: 确保 .dockerignore 配置正确"
```

---

## 测试计划

### 单元测试

- Dockerfile 构建测试
- Nginx 配置语法测试
- docker-compose 配置验证

### 集成测试

1. 容器启动顺序验证
2. 服务健康检查
3. 网络连通性测试
4. 数据库初始化验证
5. API 端点可访问性测试

### 部署测试

1. 在本地环境完整执行 `./deploy.sh`
2. 访问 Web UI
3. 测试健康检查端点
4. 验证数据库连接
5. 测试文件上传（/worker/metrics/upload）

---

## 注意事项

1. **首次部署前**：确保已有编译好的前端静态文件，或设置 `BUILD_FRONTEND=0` 跳过前端构建
2. **生产环境**：务必修改 `.env.production` 中的默认密码和密钥
3. **数据持久化**：PostgreSQL 数据存储在 Docker volume 中，删除容器不会丢失数据
4. **HTTPS**：当前配置仅支持 HTTP，如需 HTTPS 请配置 SSL 证书
5. **防火墙**：确保服务器 80/443 端口已开放

---

**变更记录:**
- 2026-03-24: 初始版本
