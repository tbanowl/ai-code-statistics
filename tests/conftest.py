"""Pytest-wide test database defaults.

Some legacy API tests import ``app`` at module import time.  Importing the app
registers routes that construct database helpers immediately, so pytest needs a
safe default database before test modules are collected.
"""

import tempfile

from sqlalchemy import create_engine

import core.config.loader as loader


_test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db.close()
_test_db_url = f"sqlite:///{_test_db.name}"

loader.config_data = {
    "features": {"enabled": True},
    "git": {"type": "github"},
    "database": {"url": _test_db_url, "echo": False},
    "scheduler": {"enabled": False},
    "logging": {"level": "ERROR"},
    "swagger": {"enabled": False},
}

import core.database.base as database_base  # noqa: E402

database_base.global_engine = create_engine(_test_db_url, echo=False)
