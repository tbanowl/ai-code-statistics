"""测试 SchedulerDatabase 方法"""
import os
import tempfile
import time

import pytest

import core.config.loader as loader
from core.database import SchedulerDatabase
from core.database.models import TaskExecution
from core.database.base import session_scope, now_ts


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
def scheduler_db(temp_db_path):
    loader.config_data = {
        "features": {"enabled": True},
        "git": {"type": "github"},
        "database": {"url": f"sqlite:///{temp_db_path}", "echo": False},
    }
    db = SchedulerDatabase()
    db.init_db()
    return db


def test_has_running_task_no_running(scheduler_db):
    """测试没有运行中的任务"""
    db = scheduler_db

    result = db.has_running_task("test_job", timeout_minutes=10)
    assert result is None


def test_has_running_task_running_not_timeout(scheduler_db):
    """测试运行中且未超时的任务"""
    db = scheduler_db

    with session_scope(db.engine) as session:
        execution = TaskExecution(
            job_id="test_job",
            status="running",
            started_at=now_ts() - 1000  # 刚开始，未超时
        )
        session.add(execution)

    result = db.has_running_task("test_job", timeout_minutes=10)
    assert result is not None
    assert result['status'] == 'running'


def test_has_running_task_running_timeout(scheduler_db):
    """测试运行中但已超时的任务"""
    db = scheduler_db

    with session_scope(db.engine) as session:
        execution = TaskExecution(
            job_id="test_job",
            status="running",
            started_at=now_ts() - 11 * 60 * 1000  # 11 分钟前，超时
        )
        session.add(execution)

    result = db.has_running_task("test_job", timeout_minutes=10)
    assert result is None  # 超时任务被标记为失败，返回 None 表示可以继续


def test_has_running_task_pending_timeout(scheduler_db):
    """测试 pending 状态但已超时的任务"""
    db = scheduler_db

    with session_scope(db.engine) as session:
        execution = TaskExecution(
            job_id="test_job",
            status="pending",
            created_at=now_ts() - 11 * 60 * 1000  # 11 分钟前，超时
        )
        session.add(execution)

    result = db.has_running_task("test_job", timeout_minutes=10)
    assert result is None  # 超时任务被标记为失败


def test_has_running_task_different_job(scheduler_db):
    """测试查询不同 job_id 的任务"""
    db = scheduler_db

    with session_scope(db.engine) as session:
        execution = TaskExecution(
            job_id="other_job",
            status="running",
            started_at=now_ts() - 1000
        )
        session.add(execution)

    result = db.has_running_task("test_job", timeout_minutes=10)
    assert result is None
