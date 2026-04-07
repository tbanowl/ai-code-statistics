import pytest
from core.database.base import Database


def test_database_is_abstract():
    """Database 应该是抽象类，不能直接实例化"""
    with pytest.raises(TypeError):
        Database({})
