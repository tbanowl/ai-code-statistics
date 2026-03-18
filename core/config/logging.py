import logging
import logging.handlers
import os
from datetime import datetime
from typing import Dict, Any
from flask import Flask


class Logger:
    """统一日志管理器"""

    _instance = None
    _loggers: Dict[str, logging.Logger] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_logger(cls, name: str = None) -> logging.Logger:
        """获取指定名称的日志记录器

        Args:
            name: 日志记录器名称，通常使用 __name__ 或模块名

        Returns:
            Logger 实例
        """
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            if not logger.handlers:
                # 如果没有处理器，添加一个默认的控制台处理器
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter(
                    '%(asctime)s %(levelname)s %(name)s: %(message)s'
                ))
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
            cls._loggers[name] = logger
        return cls._loggers[name]


def init_logging(config: Dict[str, Any], BASE_DIR: str) -> None:
    """初始化日志配置

    Args:
        config: 日志配置字典
        BASE_DIR: 项目根目录
    """
    log_config = config.get('logging', {})
    log_dir = log_config.get('dir', '.logs')

    # 确保日志目录存在
    abs_log_dir = os.path.join(BASE_DIR, log_dir)
    os.makedirs(abs_log_dir, exist_ok=True)

    # 获取日志级别
    level_name = log_config.get('level', 'INFO').upper()
    log_level = getattr(logging, level_name, logging.INFO)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有的处理器（避免重复添加）
    root_logger.handlers.clear()

    # 日志格式
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)8s] [%(name)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. 添加主日志文件处理器（轮转）
    main_log_file = os.path.join(abs_log_dir, log_config.get('file', 'app.log'))
    file_handler = logging.handlers.RotatingFileHandler(
        filename=main_log_file,
        maxBytes=log_config.get('max_bytes', 10 * 1024 * 1024),  # 默认 10MB
        backupCount=log_config.get('backup_count', 5),
        encoding='utf-8'
    )
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)

    # 2. 添加错误日志文件处理器（只记录 ERROR 及以上）
    if log_config.get('separate_error_file', True):
        error_log_file = os.path.join(abs_log_dir, log_config.get('error_file', 'error.log'))
        error_handler = logging.handlers.RotatingFileHandler(
            filename=error_log_file,
            maxBytes=log_config.get('error_max_bytes', 10 * 1024 * 1024),
            backupCount=log_config.get('error_backup_count', 5),
            encoding='utf-8'
        )
        error_handler.setFormatter(detailed_formatter)
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)

    # 3. 设置第三方库日志级别
    third_party_levels = log_config.get('third_party', {})
    for lib_name, lib_level_str in third_party_levels.items():
        lib_level = getattr(logging, lib_level_str.upper(), logging.WARNING)
        logging.getLogger(lib_name).setLevel(lib_level)

    # 记录初始化信息
    logger = Logger.get_logger('logging')
    logger.info(f"日志系统初始化完成 - 级别: {level_name}, 日志目录: {abs_log_dir}")


def setup_flask_logging(app: Flask, config: Dict[str, Any]) -> None:
    """配置 Flask 应用日志

    Args:
        app: Flask 应用实例
        config: 日志配置字典
    """
    # Flask 应用日志
    logger = Logger.get_logger('flask.app')
    app.logger = logger

    # Werkzeug 日志（请求日志）
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.INFO)

    # 自定义请求日志
    log_config = config.get('logging', {})
    if log_config.get('access_log', True):
        @app.before_request
        def log_request_info():
            from flask import request
            if request.path.startswith('/static/'):
                return
            access_logger = Logger.get_logger('access')
            access_logger.info(
                f"{request.method} {request.path} - {request.remote_addr}"
            )

    @app.teardown_appcontext
    def log_response_info(error):
        if error:
            logger.error(f"请求处理出错: {error}")


def log_exception(logger: logging.Logger, exc: Exception, context: str = ""):
    """记录异常信息

    Args:
        logger: 日志记录器
        exc: 异常对象
        context: 异常上下文描述
    """
    import traceback
    error_msg = f"{context}: {str(exc)}" if context else str(exc)
    logger.error(error_msg, exc_info=exc)
    logger.debug(traceback.format_exc())
