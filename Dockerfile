# 单阶段构建
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 备份并配置内网源（跳过GPG验证）
RUN cp /etc/apt/sources.list /etc/apt/sources.list_bak && \
    echo "deb [trusted=yes] http://172.16.13.24/repository/proxy-debian12/ bookworm main non-free non-free-firmware contrib" > /etc/apt/sources.list && \
    echo "deb [trusted=yes] http://172.16.13.24/repository/proxy-debian12/ bookworm-updates main non-free non-free-firmware contrib" >> /etc/apt/sources.list && \
    echo "deb [trusted=yes] http://172.16.13.24/repository/proxy-debian12/ bookworm-backports main non-free non-free-firmware contrib" >> /etc/apt/sources.list

# 设置 pip 源
ENV PIP_INDEX_URL=http://172.16.13.24/repository/pypi-proxy-tencent/simple
ENV PIP_TRUSTED_HOST=172.16.13.24

# 安装依赖（构建和运行）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    libpq-dev \
    libpq5 \
    libmariadb-dev \
    postgresql-client \
    gunicorn \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements-docker.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements-docker.txt --progress-bar off

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# 复制应用代码（注意：这行要在 chown 之后，否则 USER 切换后会复制不了）
COPY --chown=appuser:appuser . .

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)" || exit 1

# 启动命令
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120"]