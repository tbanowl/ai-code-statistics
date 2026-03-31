"""测试 MetricsDatabase 方法"""
import os
import tempfile
import time

import pytest

import core.config.loader as loader
from core.database.metrics_db import MetricsDatabase
from core.database.models import MetricsEventsRaw
from core.database.base import session_scope


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Windows SQLite 文件需要额外时间释放锁
    time.sleep(0.1)
    for _ in range(5):
        try:
            if os.path.exists(path):
                os.unlink(path)
            break
        except PermissionError:
            time.sleep(0.2)


@pytest.fixture
def metrics_db(temp_db_path):
    loader.config_data = {
        "features": {"enabled": True},
        "git": {"type": "github"},
        "database": {"url": f"sqlite:///{temp_db_path}", "echo": False},
    }
    db = MetricsDatabase()
    db.init_db()
    return db


def test_reset_stuck_extracting_records(metrics_db):
    """测试恢复被卡住的原始记录"""
    db = metrics_db

    # 创建测试数据：三条记录，状态分别为 0, 2, 2
    with session_scope(db.engine) as session:
        records = [
            MetricsEventsRaw(id="test1", version=1, event_count=1, payload_json="{}", extract=0, received_at=1234567890000),
            MetricsEventsRaw(id="test2", version=1, event_count=1, payload_json="{}", extract=2, received_at=1234567890000),
            MetricsEventsRaw(id="test3", version=1, event_count=1, payload_json="{}", extract=2, received_at=1234567890000),
        ]
        session.add_all(records)

    # 执行恢复
    reset_count = db.reset_stuck_extracting_records()

    # 验证结果
    assert reset_count == 2
    with session_scope(db.engine) as session:
        records = session.query(MetricsEventsRaw).order_by(MetricsEventsRaw.id).all()
        assert records[0].extract == 0  # 未改变
        assert records[1].extract == 0  # 已恢复
        assert records[2].extract == 0  # 已恢复


def test_get_pending_raw_records_with_cursor(metrics_db):
    """测试带游标的批次查询"""
    db = metrics_db

    # 创建 5 条待处理记录
    with session_scope(db.engine) as session:
        ids = [f"test_cursor_{i}" for i in range(5)]
        records = [
            MetricsEventsRaw(id=ids[i], version=1, event_count=1, payload_json="{}", extract=0, received_at=1234567890000 + i)
            for i in range(5)
        ]
        session.add_all(records)

    # 第一批：查询前 2 条
    batch1 = db.get_pending_raw_records(limit=2, last_id=None)
    assert len(batch1) == 2
    assert batch1[0]['id'] == 'test_cursor_0'
    assert batch1[1]['id'] == 'test_cursor_1'

    # 第二批：使用 last_id 游标获取下 2 条
    last_id = batch1[-1]['id']
    batch2 = db.get_pending_raw_records(limit=2, last_id=last_id)
    assert len(batch2) == 2
    assert batch2[0]['id'] == 'test_cursor_2'
    assert batch2[1]['id'] == 'test_cursor_3'

    # 第三批：最后 1 条
    last_id = batch2[-1]['id']
    batch3 = db.get_pending_raw_records(limit=2, last_id=last_id)
    assert len(batch3) == 1
    assert batch3[0]['id'] == 'test_cursor_4'

    # 第四批：无更多数据
    last_id = batch3[-1]['id']
    batch4 = db.get_pending_raw_records(limit=2, last_id=last_id)
    assert len(batch4) == 0
