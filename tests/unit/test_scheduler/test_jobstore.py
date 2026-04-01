"""APScheduler JobStore 持久化功能单元测试"""

import pytest
from unittest.mock import patch
from core.scheduler.scheduler import AICodeScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore


@pytest.fixture
def mock_config_with_jobstore():
    """配置了 JobStore 的模拟配置"""
    return {
        "scheduler": {
            "enabled": True,
            "timezone": "Asia/Shanghai",
            "jobstore": {"type": "sqlalchemy"},
            "job_defaults": {
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 300,
            },
            "jobs": {"test_task": {"cron": "0 2 * * *", "enabled": True}},
        },
        "database": {"url": "sqlite:///:memory:"},
    }


@pytest.fixture
def mock_config_without_jobstore():
    """未配置 JobStore 的模拟配置"""
    return {
        "scheduler": {
            "enabled": True,
            "timezone": "Asia/Shanghai",
            "jobs": {"test_task": {"cron": "0 2 * * *", "enabled": True}},
        },
        "database": {"url": "sqlite:///:memory:"},
    }


def test_jobstore_initialization_with_sqlalchemy(mock_config_with_jobstore):
    """测试 SQLAlchemy JobStore 初始化成功"""
    with patch("core.config.logging.Logger.get_logger"):
        scheduler = AICodeScheduler(mock_config_with_jobstore)

        # 验证 JobStore 已配置
        assert scheduler.scheduler._jobstores is not None
        assert "default" in scheduler.scheduler._jobstores

        # 验证是 SQLAlchemyJobStore
        jobstore = scheduler.scheduler._jobstores["default"]
        assert isinstance(jobstore, SQLAlchemyJobStore)

        # 验证 job_defaults 配置生效
        assert scheduler.scheduler._job_defaults["coalesce"] is True
        assert scheduler.scheduler._job_defaults["max_instances"] == 1
        assert scheduler.scheduler._job_defaults["misfire_grace_time"] == 300


def test_jobstore_not_configured_uses_memory(mock_config_without_jobstore):
    """测试未配置 JobStore 时使用内存模式"""
    with patch("core.config.logging.Logger.get_logger"):
        scheduler = AICodeScheduler(mock_config_without_jobstore)

        # 验证 jobstores 为空字典（使用默认内存存储）
        assert scheduler.scheduler._jobstores == {}


def test_jobstore_with_unsupported_type():
    """测试不支持的 JobStore 类型时降级到内存模式"""
    config = {
        "scheduler": {
            "enabled": True,
            "timezone": "Asia/Shanghai",
            "jobstore": {
                "type": "redis"  # 不支持
            },
            "jobs": {},
        },
        "database": {},
    }

    with patch("core.config.logging.Logger.get_logger"):
        scheduler = AICodeScheduler(config)

        # 验证 jobstores 为空字典
        assert scheduler.scheduler._jobstores == {}


def test_get_engine_from_db_uses_scheduler_db():
    """测试 _get_engine_from_db 方法使用 SchedulerDatabase 的 engine"""
    config = {
        "scheduler": {"enabled": True, "jobstore": {"type": "sqlalchemy"}, "jobs": {}},
        "database": {"url": "sqlite:///:memory:"},
    }

    with patch("core.config.logging.Logger.get_logger"):
        scheduler = AICodeScheduler(config)

        # 调用 _get_engine_from_db
        engine = scheduler._get_engine_from_db()

        # 验证返回了一个 engine 实例
        assert engine is not None
        # 验证 engine 是 SQLAlchemy Engine 实例
        from sqlalchemy import Engine

        assert isinstance(engine, Engine)
        # 验证 URL 正确
        assert str(engine.url).startswith("sqlite")


def test_job_defaults_default_values():
    """测试未配置 job_defaults 时使用默认值"""
    config = {
        "scheduler": {"enabled": True, "jobstore": {"type": "sqlalchemy"}, "jobs": {}},
        "database": {},
    }

    with patch("core.config.logging.Logger.get_logger"):
        scheduler = AICodeScheduler(config)

        # 验证默认值
        assert scheduler.scheduler._job_defaults["coalesce"] is True
        assert scheduler.scheduler._job_defaults["max_instances"] == 1
        assert scheduler.scheduler._job_defaults["misfire_grace_time"] == 300


def test_timezone_configuration():
    """测试时区配置生效"""
    config = {
        "scheduler": {
            "enabled": True,
            "timezone": "America/New_York",
            "jobstore": {"type": "sqlalchemy"},
            "jobs": {},
        },
        "database": {},
    }

    with patch("core.config.logging.Logger.get_logger"):
        scheduler = AICodeScheduler(config)

        # 验证时区配置 - ZoneInfo 对象可转换为字符串比较
        assert str(scheduler.scheduler.timezone) == "America/New_York"


def test_jobstore_initialization_failure_fallback():
    """测试 JobStore 初始化失败时降级到内存模式"""
    config = {
        "scheduler": {"enabled": True, "jobstore": {"type": "sqlalchemy"}, "jobs": {}},
        "database": {},
    }

    # Mock _get_engine_from_db 抛出异常
    with patch("core.config.logging.Logger.get_logger"):
        with patch.object(
            AICodeScheduler,
            "_get_engine_from_db",
            side_effect=Exception("Database error"),
        ):
            scheduler = AICodeScheduler(config)

            # 验证降级到内存模式（空字典）
            assert scheduler.scheduler._jobstores == {}
