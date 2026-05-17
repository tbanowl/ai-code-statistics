from core.database.base import BaseDatabase


def test_base_database_uses_configured_engine():
    """BaseDatabase 应使用测试配置中的全局引擎。"""
    db = BaseDatabase()

    assert db.engine is not None
    assert db.url.startswith("sqlite:///")
