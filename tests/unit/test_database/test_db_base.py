import core.config.loader as loader

from core.database.base import BaseDatabase


def test_base_database_uses_configured_database_url():
    loader.config_data = {"database": {"url": "sqlite:///:memory:", "echo": False}}

    db = BaseDatabase()

    assert str(db.engine.url) == "sqlite:///:memory:"
