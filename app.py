"""
Git AI 代码统计 - 独立 Web 应用 v2.0
统计 GitLab/GitHub 仓库中 AI 生成代码的占比。
"""

from flask import Flask, send_from_directory
import os
import sys
from core.config.loader import load_config_by_path
from core.config.logging import init_logging, setup_flask_logging, Logger
from api.routes.stats import stats_bp
from api.routes.scheduler import scheduler_bp
from api.routes.git_ai import git_ai_bp
from api.routes.git_ai_worker import metrics_bp, cas_bp, oauth_bp, releases_bp
from api.routes.notes import notes_rest_bp
from api.routes.stats_repo import stats_repo_bp
from core.config.swagger import swagger_setup

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# 添加项目根目录到 path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 加载配置
config = load_config_by_path(os.path.join(BASE_DIR, "config.yaml"))

# 初始化日志系统（在加载配置后）
init_logging(config.get("logging", {}), BASE_DIR)
main_logger = Logger.get_logger("app")
main_logger.info("应用启动，Git AI 代码统计工具 v2.0")

# 创建 Flask 应用，设置静态文件目录为编译后的 static
static_dir = os.path.abspath(os.path.join(BASE_DIR, "static"))
app = Flask(__name__, static_folder=static_dir, template_folder=static_dir)

# 配置 Flask 日志
setup_flask_logging(app, config)

# 注册 API 蓝图

app.register_blueprint(stats_bp)
app.register_blueprint(scheduler_bp)
app.register_blueprint(git_ai_bp)
app.register_blueprint(stats_repo_bp)

# 注册 Git-AI Worker 蓝图
app.register_blueprint(metrics_bp)
app.register_blueprint(cas_bp)
app.register_blueprint(oauth_bp)
app.register_blueprint(releases_bp)

# 注册 REST Notes Store 蓝图
app.register_blueprint(notes_rest_bp)

# 初始化 Swagger（如果配置启用）
swagger_setup(app, config, main_logger)

# 启动调度器（如果配置启用）
if config.get("scheduler", {}).get("enabled", False):
    from core.scheduler import AICodeScheduler

    scheduler = AICodeScheduler(config)
    scheduler.start()
    # 将 scheduler 实例存储到 app config 中，供 API 路由使用
    app.config["_scheduler"] = scheduler
else:
    # 如果调度器未启用，设置一个默认值
    app.config["_scheduler"] = None


@app.route("/")
def index():
    """首页 - 返回编译后的 index.html"""
    return send_from_directory(static_dir, "index.html")


@app.route("/<path:filename>")
def static_file(filename):
    """首页 - 返回编译后的 index.html"""
    return send_from_directory(static_dir, filename)


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

elif __name__ == "app":
    main_logger.info("启动服务器...")
    web_config = config.get("web", {})
    port = web_config.get("port", 8888)
    host = web_config.get("host", "0.0.0.0")
    main_logger.info(f"访问地址: http://{host}:{port}")
    main_logger.info(f"健康检查: http://{host}:{port}/health")

