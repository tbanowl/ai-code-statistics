# Metrics 事件处理任务循环批处理优化实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 MetricsEventProcessorTask 从单批次处理改为循环批处理，并增加超时恢复机制。

**Architecture:** 使用 `id` 游标分页实现循环批处理，结合 `task_executions` 表实现并发安全检查和超时恢复。

**Tech Stack:** Flask, SQLAlchemy, APScheduler

---

## 实施前置检查

### Step 1: 确认当前分支和代码状态

```bash
git status
git log --oneline -5
```

预期：确保在正确分支上工作，没有未提交的改动

---

## Task 1: 添加 MetricsDatabase.reset_stuck_extracting_records 方法

**Files:**
- Modify: `core/database/metrics_db.py`

**Step 1: 编写测试文件**

创建测试文件 `tests/test_metrics_db.py`:

```python
"""测试 MetricsDatabase 方法"""
import pytest
from core.database import MetricsDatabase
from core.database.models import MetricsEventsRaw


def test_reset_stuck_extracting_records(tmp_engine):
    """测试恢复被卡住的原始记录"""
    from core.database.base import session_scope

    # 创建测试数据：三条记录，状态分别为 0, 2, 2
    with session_scope(tmp_engine) as session:
        records = [
            MetricsEventsRaw(id="test1", version=1, event_count=1, payload_json="{}", extract=0, received_at=1234567890000),
            MetricsEventsRaw(id="test2", version=1, event_count=1, payload_json="{}", extract=2, received_at=1234567890000),
            MetricsEventsRaw(id="test3", version=1, event_count=1, payload_json="{}", extract=2, received_at=1234567890000),
        ]
        session.add_all(records)

    # 执行恢复
    db = MetricsDatabase()
    db.engine = tmp_engine  # 注入测试引擎
    reset_count = db.reset_stuck_extracting_records()

    # 验证结果
    assert reset_count == 2
    with session_scope(tmp_engine) as session:
        records = session.query(MetricsEventsRaw).order_by(MetricsEventsRaw.id).all()
        assert records[0].extract == 0  # 未改变
        assert records[1].extract == 0  # 已恢复
        assert records[2].extract == 0  # 已恢复
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_metrics_db.py::test_reset_stuck_extracting_records -v
```

预期：FAIL，提示方法不存在

**Step 3: 在 MetricsDatabase 中实现方法**

在 `core/database/metrics_db.py` 的 `MetricsDatabase` 类中添加方法：

```python
def reset_stuck_extracting_records(self) -> int:
    """
    将所有 extract=2（处理中）的记录重置为 extract=0（未处理）
    用于任务超时后的恢复

    Returns:
        重置的记录数
    """
    from .base_db import BaseDatabase
    with session_scope(self.engine) as session:
        records = (
            session.query(MetricsEventsRaw)
            .filter(MetricsEventsRaw.extract == 2)
            .all()
        )
        count = len(records)
        for record in records:
            record.extract = 0
        return count
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/test_metrics_db.py::test_reset_stuck_extracting_records -v
```

预期：PASS

**Step 5: 提交**

```bash
git add core/database/metrics_db.py tests/test_metrics_db.py
git commit -m "feat: 添加 MetricsDatabase.reset_stuck_extracting_records 方法

用于恢复任务超时后被卡住的原始记录

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: 修改 MetricsDatabase.get_pending_raw_records 支持 id 游标分页

**Files:**
- Modify: `core/database/metrics_db.py:42-53`

**Step 1: 编写测试**

在 `tests/test_metrics_db.py` 中添加：

```python
def test_get_pending_raw_records_with_cursor(tmp_engine):
    """测试带游标的批次查询"""
    from core.database.base import session_scope

    # 创建 5 条待处理记录
    with session_scope(tmp_engine) as session:
        ids = [f"test_cursor_{i}" for i in range(5)]
        records = [
            MetricsEventsRaw(id=ids[i], version=1, event_count=1, payload_json="{}", extract=0, received_at=1234567890000 + i)
            for i in range(5)
        ]
        session.add_all(records)

    db = MetricsDatabase()
    db.engine = tmp_engine

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
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_metrics_db.py::test_get_pending_raw_records_with_cursor -v
```

预期：FAIL，方法不支持 `last_id` 参数

**Step 3: 修改 get_pending_raw_records 方法**

将 `core/database/metrics_db.py` 中的方法修改为：

```python
def get_pending_raw_records(self, limit: int = 100, last_id: str = None) -> List[Dict]:
    """
    获取待处理的原始记录
    使用 id 游标分页，确保处理顺序一致

    Args:
        limit: 每批获取的记录数
        last_id: 游标，用于分页（获取 id > last_id 的记录）

    Returns:
        记录列表
    """
    from .base_db import BaseDatabase
    with session_scope(self.engine) as session:
        query = session.query(MetricsEventsRaw)\
            .filter(MetricsEventsRaw.extract == 0)\
            .order_by(MetricsEventsRaw.id.asc())\
            .limit(limit)

        if last_id:
            query = query.filter(MetricsEventsRaw.id > last_id)

        results = query.all()
        return [{'id': r.id, 'payload_json': r.payload_json, 'event_count': r.event_count} for r in results]
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/test_metrics_db.py::test_get_pending_raw_records_with_cursor -v
```

预期：PASS

**Step 5: 提交**

```bash
git add core/database/metrics_db.py tests/test_metrics_db.py
git commit -m "feat: MetricsDatabase.get_pending_raw_records 支持 id 游标分页

添加 last_id 参数用于批次递进式查询

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 添加 SchedulerDatabase.has_running_task 方法

**Files:**
- Modify: `core/database/scheduler_db.py`

**Step 1: 编写测试**

创建测试文件 `tests/test_scheduler_db.py`:

```python
"""测试 SchedulerDatabase 方法"""
import time
import pytest
from core.database import SchedulerDatabase
from core.database.models import TaskExecution
from core.database.base import now_ts, session_scope


def test_has_running_task_no_running(tmp_engine):
    """测试没有运行中的任务"""
    db = SchedulerDatabase()
    db.engine = tmp_engine

    result = db.has_running_task("test_job", timeout_minutes=10)
    assert result is None


def test_has_running_task_running_not_timeout(tmp_engine):
    """测试运行中且未超时的任务"""
    with session_scope(tmp_engine) as session:
        execution = TaskExecution(
            job_id="test_job",
            status="running",
            started_at=now_ts() - 1000  # 刚开始，未超时
        )
        session.add(execution)

    db = SchedulerDatabase()
    db.engine = tmp_engine

    result = db.has_running_task("test_job", timeout_minutes=10)
    assert result is not None
    assert result['status'] == 'running'


def test_has_running_task_running_timeout(tmp_engine):
    """测试运行中但已超时的任务"""
    with session_scope(tmp_engine) as session:
        execution = TaskExecution(
            job_id="test_job",
            status="running",
            started_at=now_ts() - 11 * 60 * 1000  # 11 分钟前，超时
        )
        session.add(execution)

    db = SchedulerDatabase()
    db.engine = tmp_engine

    result = db.has_running_task("test_job", timeout_minutes=10)
    assert result is None  # 超时任务被标记为失败，返回 None 表示可以继续
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_scheduler_db.py -v
```

预期：FAIL，方法不存在

**Step 3: 实现 has_running_task 方法**

在 `core/database/scheduler_db.py` 的 `SchedulerDatabase` 类中添加方法：

```python
def has_running_task(self, job_id: str, timeout_minutes: int = 10) -> Optional[Dict]:
    """
    检查是否有正在运行的任务

    Args:
        job_id: 任务 ID
        timeout_minutes: 超时阈值（分钟）

    Returns:
        None - 没有运行中的任务，可以开始执行
        Dict - 正在运行的任务信息
    """
    from .base import now_ts

    with session_scope(self.engine) as session:
        execution = (
            session.query(TaskExecution)
            .filter(TaskExecution.job_id == job_id)
            .filter(TaskExecution.status.in_(["pending", "running"]))
            .first()
        )

        if not execution:
            return None

        # 检查是否超时
        execution_dict = execution.to_dict()
        started_at = execution_dict.get('started_at') or execution_dict.get('created_at', 0)
        timeout_ms = timeout_minutes * 60 * 1000

        if now_ts() - started_at > timeout_ms:
            # 超时，标记为失败
            execution.status = "failed"
            execution.updated_at = now_ts()
            if not execution.finished_at:
                execution.finished_at = now_ts()
            return None  # 返回 None 表示可以继续执行

        return execution_dict  # 未超时，返回任务信息
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/test_scheduler_db.py -v
```

预期：PASS

**Step 5: 提交**

```bash
git add core/database/scheduler_db.py tests/test_scheduler_db.py
git commit -m "feat: 添加 SchedulerDatabase.has_running_task 方法

用于检查是否有正在运行的任务，支持超时检测

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: 修改 MetricsEventProcessorTask.execute 方法支持循环批处理

**Files:**
- Modify: `core/scheduler/tasks/metrics_event_processor_task.py:16-98`

**Step 1: 创建任务配置文件**

在项目根目录创建 `tests/fixtures/scheduler_config.yaml`:

```yaml
scheduler:
  enabled: true
  jobs:
    metrics_event_processor:
      cron: "*/2 * * * *"
      batch_size: 10
      timeout_minutes: 10
```

**Step 2: 编写集成测试**

创建测试文件 `tests/test_metrics_event_processor_task.py`:

```python
"""测试 MetricsEventProcessorTask"""
import pytest
from core.scheduler.tasks.metrics_event_processor_task import MetricsEventProcessorTask
from core.config import load_config


def test_task_no_pending_records(mocker):
    """测试没有待处理记录时的执行"""
    # Mock 配置
    config = {
        'scheduler': {
            'jobs': {
                'metrics_event_processor': {
                    'batch_size': 100,
                    'timeout_minutes': 10
                }
            }
        }
    }

    # Mock 数据库
    mock_scheduler_db = mocker.patch('core.database.SchedulerDatabase')
    mock_scheduler_instance = mock_scheduler_db.return_value
    mock_scheduler_instance.has_running_task.return_value = None

    mock_metrics_db = mocker.patch('core.database.MetricsDatabase')
    mock_metrics_instance = mock_metrics_db.return_value
    mock_metrics_instance.get_pending_raw_records.return_value = []

    # 执行任务
    task = MetricsEventProcessorTask()
    task.config = config
    result = task.execute()

    # 验证结果
    assert result['success'] is True
    assert result['processed'] == 0
    assert result['batches'] == 0
    mock_scheduler_instance.has_running_task.assert_called_once_with("metrics_event_processor", 10)


def test_task_skipped_when_running(mocker):
    """测试有运行中任务时跳过执行"""
    config = {
        'scheduler': {
            'jobs': {
                'metrics_event_processor': {
                    'batch_size': 100,
                    'timeout_minutes': 10
                }
            }
        }
    }

    mock_scheduler_db = mocker.patch('core.database.SchedulerDatabase')
    mock_scheduler_instance = mock_scheduler_db.return_value
    mock_scheduler_instance.has_running_task.return_value = {
        'id': 'exec1',
        'status': 'running'
    }

    task = MetricsEventProcessorTask()
    task.config = config
    result = task.execute()

    assert result['success'] is True
    assert result['skipped'] is True
    assert result['skip_reason'] == 'running_task'
```

**Step 3: 运行测试验证失败**

```bash
pytest tests/test_metrics_event_processor_task.py -v
```

预期：FAIL，任务逻辑不支持循环批处理和并发检查

**Step 4: 修改 execute 方法**

将 `core/scheduler/tasks/metrics_event_processor_task.py` 中的 `execute` 方法替换为：

```python
def execute(self, context: Optional[Dict] = None) -> Dict:
    self.logger.info("开始执行 Metrics 事件处理任务")

    # 获取配置
    batch_size = self.config.get("scheduler", {})\
        .get("jobs", {})\
        .get("metrics_event_processor", {})\
        .get("batch_size", 100)

    timeout_minutes = self.config.get("scheduler", {})\
        .get("jobs", {})\
        .get("metrics_event_processor", {})\
        .get("timeout_minutes", 10)

    # 并发安全检查
    from core.database import SchedulerDatabase, MetricsDatabase
    scheduler_db = SchedulerDatabase()

    running_task = scheduler_db.has_running_task("metrics_event_processor", timeout_minutes)

    if running_task:
        self.logger.info(f"已有任务在处理中（id={running_task['id']}），跳过本次执行")
        return {"success": True, "skipped": True, "skip_reason": "running_task"}

    # 检查是否有超时任务需要恢复
    pending_or_running_task = scheduler_db.get_running_task_execution("metrics_event_processor")
    if pending_or_running_task:
        # 有超时任务，恢复 raw 记录状态
        db = MetricsDatabase()
        reset_count = db.reset_stuck_extracting_records()
        if reset_count > 0:
            self.logger.warning(f"恢复 {reset_count} 条被卡住的原始记录")
        # 标记旧任务为失败
        scheduler_db.update_task_execution_status(pending_or_running_task['id'], "failed")

    db = MetricsDatabase()

    # 循环批处理
    last_id = None
    batch_count = 0

    # 初始化统计
    stats = {
        "total": 0,
        "successful": 0,
        "failed": 0,
        "total_events": 0,
        "error_events": 0,
        "batches": 0
    }

    service = MetricsService()

    while True:
        # 获取下一批记录
        pending_records = db.get_pending_raw_records(limit=batch_size, last_id=last_id)

        if not pending_records:
            break

        batch_count += 1
        self.logger.info(f"处理批次 #{batch_count}: {len(pending_records)} 条记录")

        # 处理这批记录
        for record in pending_records:
            raw_id = record['id']
            payload_json = record['payload_json']
            event_count = record['event_count']

            # 标记为处理中
            if not db.mark_raw_extracting(raw_id):
                self.logger.warning(f"原始记录 {raw_id} 正在被其他进程处理，跳过")
                continue

            try:
                # 处理原始事件
                result = service.process_raw_event(raw_id, payload_json)

                # 根据结果更新状态
                if result.get("success"):
                    db.mark_raw_extracted(raw_id, success=True)
                    stats["successful"] += 1
                    stats["total_events"] += result.get("events_processed", 0)
                    stats["error_events"] += result.get("error_count", 0)
                else:
                    db.mark_raw_extracted(raw_id, success=False)
                    stats["failed"] += 1
                    self.logger.error(f"处理失败: raw_id={raw_id}, error={result.get('error')}")

            except Exception as e:
                db.mark_raw_extracted(raw_id, success=False)
                stats["failed"] += 1
                self.logger.error(f"处理异常: raw_id={raw_id}, error={str(e)}", exc_info=True)

            # 更新 last_id 游标
            last_id = raw_id
            stats["total"] += 1

    stats["batches"] = batch_count

    self.logger.info(
        f"Metrics 事件处理完成: "
        f"批次={stats['batches']}, "
        f"总计={stats['total']}, "
        f"成功={stats['successful']}, "
        f"失败={stats['failed']}, "
        f"总事件={stats['total_events']}, "
        f"错误事件={stats['error_events']}"
    )

    return {
        "success": True,
        "processed": stats["total"],
        "successful": stats["successful"],
        "failed": stats["failed"],
        "total_events": stats["total_events"],
        "error_events": stats["error_events"],
        "batches": stats["batches"]
    }
```

**Step 5: 运行测试验证通过**

```bash
pytest tests/test_metrics_event_processor_task.py -v
```

预期：PASS

**Step 6: 提交**

```bash
git add core/scheduler/tasks/metrics_event_processor_task.py tests/test_metrics_event_processor_task.py
git commit -m "feat: MetricsEventProcessorTask 支持循环批处理

- 使用 id 游标分页实现循环批处理
- 添加并发安全检查防止重复执行
- 支持超时恢复机制

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 更新配置文件示例

**Files:**
- Modify: `config.yaml`

**Step 1: 检查配置文件**

```bash
grep -A 5 "metrics_event_processor" config.yaml
```

**Step 2: 添加配置项（如果不存在）**

在 `config.yaml` 的 `scheduler.jobs.metrics_event_processor` 节点添加配置：

```yaml
scheduler:
  enabled: true
  jobs:
    metrics_event_processor:
      batch_size: 100              # 每批处理的记录数
      timeout_minutes: 10          # 任务超时阈值（分钟）
```

**Step 3: 提交**

```bash
git add config.yaml
git commit -m "config: 添加 metrics_event_processor 批处理配置

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: 运行完整测试套件

**Step 1: 运行所有测试**

```bash
pytest tests/ -v
```

预期：所有测试通过

**Step 2: 运行特定模块测试**

```bash
pytest tests/test_metrics_db.py tests/test_scheduler_db.py tests/test_metrics_event_processor_task.py -v
```

预期：所有测试通过

---

## Task 7: 手动验证（可选）

**Step 1: 启动应用**

```bash
python app.py
```

**Step 2: 观察 Scheduler 日志**

确认任务按预期循环处理：

```
处理批次 #1: 100 条记录
Metrics 事件处理完成: 批次=1, 总计=100, 成功=100, ...
```

---

## Task 8: 更新文档

**Files:**
- Modify: `README.md`（如果需要）

**Step 1: 在 README 中添加配置说明**

```yaml
## 配置

### Metrics 事件处理任务

```yaml
scheduler:
  jobs:
    metrics_event_processor:
      batch_size: 100              # 每批处理的记录数
      timeout_minutes: 10          # 任务超时阈值（分钟）
```

- `batch_size`: 每批处理的记录数，默认 100
- `timeout_minutes`: 任务超时阈值（分钟），默认 10。超时会自动恢复卡住的记录
```

**Step 2: 提交**

```bash
git add README.md
git commit -m "docs: 添加 Metrics 事件处理任务配置说明

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: 代码审查和优化

**Step 1: 运行代码质量检查**

```bash
# 如果项目有 lint 规则
flake8 core/database/metrics_db.py core/database/scheduler_db.py core/scheduler/tasks/metrics_event_processor_task.py

# 或者其它静态检查工具
```

**Step 2: 代码审查清单**

- [ ] 所有测试通过
- [ ] 代码符合项目风格
- [ ] 错误处理完善
- [ ] 日志输出清晰
- [ ] 配置项有合理的默认值
- [ ] 并发安全性已测试

**Step 3: 如果发现问题，创建修复任务并重复测试**

---

## 任务完成检查清单

完成以上所有任务后，确认：

- [ ] `test_reset_stuck_extracting_records` 通过
- [ ] `test_get_pending_raw_records_with_cursor` 通过
- [ ] `test_has_running_task_*` 系列测试通过
- [ ] `test_metrics_event_processor_task_*` 系列测试通过
- [ ] 配置文件已更新
- [ ] 完整测试套件通过
- [ ] 文档已更新

---

## 回滚计划

如果实施后发现问题：

```bash
# 回滚到实施前的状态
git reset --hard <commit-before-implementation>

# 或者保留修复，废弃实施
git revert <implementation-commit-range>
```
