"""
Git AI 代码统计 - 独立 Web 应用 v2.0
统计 GitLab/GitHub 仓库中 AI 生成代码的占比。
"""

from flask import Flask, send_from_directory, request, jsonify
import os
import sys
import subprocess
from core.config.logging import init_logging, setup_flask_logging, Logger

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# 添加项目根目录到 path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 在启动前检查并编译前端
BUILD_FRONTEND = os.getenv("BUILD_FRONTEND", "1").lower() in ("1", "true", "yes", "on")


def build_frontend():
    """编译前端项目"""
    frontend_dir = os.path.join(BASE_DIR, "frontend")
    dist_dir = os.path.join(BASE_DIR, "dist")
    node_modules = os.path.join(frontend_dir, "node_modules")

    if not BUILD_FRONTEND:
        print("BUILD_FRONTEND=0，跳过前端构建")
        if not os.path.exists(dist_dir) or not os.path.exists(
            os.path.join(dist_dir, "index.html")
        ):
            print("警告: dist 目录不存在或未包含 index.html，应用可能无法正常运行")
        return

    print("检查前端项目状态...")

    if not os.path.exists(node_modules):
        print("未检测到 node_modules，正在安装依赖...")
        subprocess.run(["npm", "install"], cwd=frontend_dir, shell=True, check=True)

    if not os.path.exists(dist_dir):
        print("未检测到编译输出，正在编译前端...")
        subprocess.run(
            ["npm", "run", "build"], cwd=frontend_dir, shell=True, check=True
        )
    else:
        # 检查 dist 目录中是否有最新编译的文件
        index_html = os.path.join(dist_dir, "index.html")
        if not os.path.exists(index_html):
            print("编译输出不完整，正在重新编译...")
            subprocess.run(
                ["npm", "run", "build"], cwd=frontend_dir, shell=True, check=True
            )
        else:
            print("前端已编译，跳过构建")


build_frontend()

# 加载配置
from core.config.loader import ConfigLoader

config_loader = ConfigLoader()
config = config_loader.load()

# 初始化日志系统（在加载配置后）
init_logging(config.get("logging", {}), BASE_DIR)
main_logger = Logger.get_logger("app")
main_logger.info(f"应用启动，Git AI 代码统计工具 v2.0")

# 创建 Flask 应用，设置静态文件目录为编译后的 dist
dist_dir = os.path.abspath(os.path.join(BASE_DIR, "dist"))
app = Flask(__name__, static_folder=dist_dir, template_folder=dist_dir)

# 配置 Flask 日志
setup_flask_logging(app, config)

# 注册 API 蓝图
from api.routes.stats import stats_bp
from api.routes.projects import projects_bp
from api.routes.scheduler import scheduler_bp
from api.routes.git_ai import git_ai_bp
from api.routes.git_ai_worker import metrics_bp, cas_bp, oauth_bp, releases_bp
from api.routes.dimensions import dimensions_bp

app.register_blueprint(stats_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(scheduler_bp)
app.register_blueprint(git_ai_bp)
app.register_blueprint(dimensions_bp)

# 注册 Git-AI Worker 蓝图
app.register_blueprint(metrics_bp)
app.register_blueprint(cas_bp)
app.register_blueprint(oauth_bp)
app.register_blueprint(releases_bp)

# 初始化 Swagger（如果配置启用）
swagger_config = config.get("swagger", {})
if swagger_config.get("enabled", False):
    from flasgger import Swagger
    import json

    # 尝试从生成的配置文件加载 Swagger 模板
    swagger_config_file = swagger_config.get("output_path", "swagger_config.json")
    try:
        with open(swagger_config_file, "r", encoding="utf-8") as f:
            swagger_template = json.load(f)
        main_logger.info(f"从 {swagger_config_file} 加载 Swagger 配置")
    except FileNotFoundError:
        main_logger.warning(
            f"Swagger 配置文件不存在: {swagger_config_file}，使用默认配置"
        )
        # 使用默认配置
        swagger_template = {
            "swagger": "2.0",
            "info": {
                "title": swagger_config.get("title", "API"),
                "version": swagger_config.get("version", "1.0.0"),
                "description": swagger_config.get("description", ""),
                "contact": swagger_config.get("contact", {}),
                "license": swagger_config.get("license", {}),
            },
            "host": f"{config.get('web', {}).get('host', '0.0.0.0')}:{config.get('web', {}).get('port', 8888)}",
            "basePath": "/",
            "schemes": ["http", "https"],
            "consumes": ["application/json"],
            "produces": ["application/json"],
            "tags": [
                {"name": "stats", "description": "统计分析 API"},
                {"name": "projects", "description": "项目管理 API"},
                {"name": "scheduler", "description": "调度任务 API"},
                {"name": "git-ai", "description": "Git-AI 用户界面 API"},
                {"name": "dimensions", "description": "维度表 API"},
                {"name": "worker-metrics", "description": "Worker Metrics API"},
                {"name": "worker-cas", "description": "Worker CAS API"},
                {"name": "worker-oauth", "description": "Worker OAuth API"},
                {"name": "worker-releases", "description": "Worker Releases API"},
            ],
            "definitions": {
                "SuccessResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "data": {"type": "object"},
                    },
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "error": {"type": "string", "example": "错误信息"},
                    },
                },
            },
        }

    Swagger(
        app,
        template=swagger_template,
        config={
            "headers": [],
            "specs": [
                {
                    "endpoint": "apispec",
                    "route": "/swagger.json",
                    "rule_filter": lambda rule: True,
                    "model_filter": lambda tag: True,
                }
            ],
            "static_url_path": "/flasgger_static",
            "swagger_ui": True,
            "specs_route": "/swagger",
        },
    )
    main_logger.info(
        "Swagger UI 已启用，访问地址: http://{}:{}/swagger".format(
            config.get("web", {}).get("host", "0.0.0.0"),
            config.get("web", {}).get("port", 8888),
        )
    )

# 启动调度器（如果配置启用）
if config.get("scheduler", {}).get("enabled", False):
    from core.scheduler import AICodeScheduler
    from core.scheduler.dimensions_task import DimensionsUpdateTask
    from core.scheduler.stats_task import DailyStatsTask

    scheduler = AICodeScheduler(config)
    scheduler.start()


@app.route("/")
def index():
    """首页 - 返回编译后的 index.html"""
    return send_from_directory(dist_dir, "index.html")


@app.route("/<path:filename>")
def static_file(filename):
    """首页 - 返回编译后的 index.html"""
    return send_from_directory(dist_dir, filename)


@app.route("/health")
def health():
    """健康检查"""
    return {"status": "ok", "version": "2.0.0"}


if __name__ == "__main__":
    web_config = config.get("web", {})
    port = web_config.get("port", 8888)
    host = web_config.get("host", "0.0.0.0")
    debug = web_config.get("debug", False)

    main_logger.info("启动服务器...")
    main_logger.info(f"访问地址: http://{host}:{port}")
    main_logger.info(f"健康检查: http://{host}:{port}/health")

    app.run(debug=debug, port=port, host=host)

if __name__ == "app":
    main_logger.info("启动服务器...")
    web_config = config.get("web", {})
    port = web_config.get("port", 8888)
    host = web_config.get("host", "0.0.0.0")
    main_logger.info(f"访问地址: http://{host}:{port}")
    main_logger.info(f"健康检查: http://{host}:{port}/health")
