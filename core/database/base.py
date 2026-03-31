"""
SQLAlchemy 基础设施

提供引擎工厂、Session 上下文管理器和模型基类。
"""

import time
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from contextlib import contextmanager
from core.config import load_config
from core.config.logging import Logger

class Base(DeclarativeBase):
    """SQLAlchemy 模型基类"""

    pass


@contextmanager
def session_scope(engine: Engine):
    """
    Session 上下文管理器，自动处理提交和回滚。

    使用方式:
        with session_scope(engine) as session:
            # 执行数据库操作
            session.add(model)
        # 自动提交或回滚
    """
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def now_ts() -> int:
    """返回当前时间戳（毫秒）"""
    return int(time.time() * 1000)


class BaseDatabase:
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
        if BaseDatabase._shared_engine:
            BaseDatabase._shared_engine.dispose()
            BaseDatabase._shared_engine = None
            self.logger.info("数据库连接已关闭")
    

    @contextmanager
    def session_scope(self):
        """
        Session 上下文管理器，自动处理提交和回滚。

        使用方式:
            with session_scope(engine) as session:
                # 执行数据库操作
                session.add(model)
            # 自动提交或回滚
        """
        SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


