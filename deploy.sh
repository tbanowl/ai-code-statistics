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

    docker-compose --version &> /dev/null || docker compose version &> /dev/null
    if [ $? -ne 0 ]; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi

    log_info "Docker: $(docker --version)"
    log_info "Docker Compose: $(docker-compose --version 2>/dev/null || docker compose version)"
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
    echo "  - Web UI: http://localhost"
    echo "  - API 文档: http://localhost/swagger"
    echo "  - 健康检查: http://localhost/health"
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
