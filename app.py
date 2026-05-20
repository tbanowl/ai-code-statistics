"""
Git AI 代码统计 - 独立 Web 应用 v2.0
统计 GitLab/GitHub 仓库中 AI 生成代码的占比。
"""

from flask import Flask, send_from_directory
import os
import sys
from core.config.loader import load_config_by_path

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

from core.config.logging import init_logging, setup_flask_logging, Logger
from api.routes.stats import stats_bp
from api.routes.stats_repo import stats_repo_bp
from api.routes.scheduler import scheduler_bp
from api.routes.git_ai import git_ai_bp
from api.routes.git_ai_worker import metrics_bp, cas_bp, oauth_bp, releases_bp
from api.routes.authorship_notes import git_notes_rest_bp, authorship_notes_rest_bp
from api.routes.codeup_webhook import codeup_webhook_bp
from api.routes.otel_receiver import otel_receiver_bp
from api.routes.system import system_bp
from core.config.swagger import swagger_setup

# 初始化日志系统（在加载配置后）
init_logging(config.get("logging", {}), BASE_DIR)
main_logger = Logger.get_logger("app")
main_logger.info("应用启动，Git AI 代码统计工具 v2.0")

# 创建 Flask 应用，设置静态文件目录
static_dir = os.path.abspath(os.path.join(BASE_DIR, "frontend_static"))
# 禁用 Flask 默认的静态文件处理，使用自定义路由
app = Flask(__name__, static_folder=None, static_url_path=None)

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
app.register_blueprint(git_notes_rest_bp)
app.register_blueprint(authorship_notes_rest_bp)
app.register_blueprint(codeup_webhook_bp)
app.register_blueprint(system_bp)

# 注册 OTLP Logs Receiver 蓝图
app.register_blueprint(otel_receiver_bp)

# 初始化 Swagger（如果配置启用）
swagger_setup(app, config, main_logger)


def _running_under_pytest() -> bool:
    return "pytest" in sys.modules


# 启动调度器（如果配置启用）
if config.get("scheduler", {}).get("enabled", False):
    from core.scheduler import AICodeScheduler

    scheduler = AICodeScheduler(config)
    if not _running_under_pytest():
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


@app.route("/favicon.ico")
def favicon():
    """favicon 文件"""
    return send_from_directory(static_dir, "favicon.ico")


@app.route("/static/<path:filename>")
def serve_static(filename):
    """提供静态文件服务 - 处理 /static/ 路径下的所有文件"""
    return send_from_directory(os.path.join(static_dir, "static"), filename)


@app.route("/<path:path>")
def catch_all(path):
    """
    Catch-all 路由 - 处理所有未匹配的路由
    1. 如果是静态文件，直接返回
    2. 如果是 API 请求，返回 404
    3. 其他情况返回 index.html (支持 Vue Router 历史)
    """
    # 检查是否是静态文件请求（有扩展名的文件或存在于 static 目录）
    full_path = os.path.join(static_dir, path)

    # 如果文件存在于 static_dir，直接返回
    if os.path.isfile(full_path):
        return send_from_directory(static_dir, path)

    # 如果是 API 请求且未被蓝图处理，返回 404
    if path.startswith("api/"):
        main_logger.warning(f"API endpoint not found: {path}")
        return {"error": "API endpoint not found"}, 404

    # 其他所有请求 → 返回 index.html，交给 Vue Router 处理
    main_logger.debug(f"Serving index.html for path: {path}")
    return send_from_directory(static_dir, "index.html")


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
