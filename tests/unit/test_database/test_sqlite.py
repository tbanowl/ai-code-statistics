import pytest
import os
import tempfile
from datetime import datetime
from core.database.sqlite import SQLiteDatabase
from core.models.stats import StatRecord


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    config = {'path': path}
    db = SQLiteDatabase(config)
    db.init_db()
    yield db
    # 清理
    os.unlink(path)


def test_init_db(temp_db):
    """测试数据库初始化"""
    # 检查表是否存在
    assert temp_db.validate_connection()


def test_save_and_get_stats(temp_db):
    """测试保存和获取统计数据"""
    # Arrange
    stat = StatRecord(
        id="test-id",
        timestamp=datetime.now(),
        total_lines=1000,
        total_ai_lines=500,
        overall_percentage=50.0,
        total_commits=10,
        commits_with_ai=5,
        repos_count=2
    )

    # Act
    stat_id = temp_db.save_stats(stat)

    # Assert
    assert stat_id == "test-id"
    latest = temp_db.get_latest_stat()
    assert latest is not None
    assert latest['id'] == "test-id"
    assert latest['total_lines'] == 1000
    assert latest['total_ai_lines'] == 500


def test_get_stats_history(temp_db):
    """测试获取历史记录"""
    # 创建多条记录
    for i in range(3):
        stat = StatRecord(
            id=f"stat-{i}",
            timestamp=datetime(2026, 3, 10 + i),
            total_lines=100,
            total_ai_lines=50
        )
        temp_db.save_stats(stat)

    # 获取历史记录
    history = temp_db.get_stats_history(limit=2)

    # 验证
    assert len(history) == 2
    assert history[0]['id'] == "stat-2"  # 最新的在前
    assert history[1]['id'] == "stat-1"
