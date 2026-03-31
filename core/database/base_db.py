"""
数据库基础类

提供共享的引擎初始化和表结构创建能力。
"""

from sqlalchemy import Engine, create_engine
from core.config import load_config

from .base import Base
from core.config.logging import Logger


class BaseDatabase1:
    """
    数据库基础类，提供引擎和初始化能力。

    所有子类共享同一个引擎实例。
    """

    _shared_engine: Engine | None = None

    def __init__(self):
        self.config = load_config()
        database_config = self.config.get('database')
        if not database_config:
            raise Exception("数据库配置错误")
        self.url = database_config.get('url')
        self.echo = bool(database_config.get('echo', False))
        self.logger = Logger.get_logger('database')

    @classmethod
    def get_shared_engine(cls, url: str, echo: bool = False) -> Engine:
        """
        获取共享的引擎实例。

        同一个 URL 共享同一个引擎，避免重复创建。
        """
        if cls._shared_engine is None or cls._shared_engine.url != url:
            cls._shared_engine = create_engine(
                url,
                echo=echo,
                pool_pre_ping=True,
            )
        return cls._shared_engine

    @property
    def engine(self) -> Engine:
        """获取引擎实例"""
        return self.get_shared_engine(self.url, self.echo)

    def init_db(self) -> None:
        """初始化数据库表结构"""
        Base.metadata.create_all(self.engine)
        self.logger.info(f"数据库表结构初始化完成: {self.url}")

    def close(self) -> None:
        """关闭数据库连接（可选，通常应用关闭时调用）"""
        if BaseDatabase1._shared_engine:
            BaseDatabase1._shared_engine.dispose()
            BaseDatabase1._shared_engine = None
            self.logger.info("数据库连接已关闭")
