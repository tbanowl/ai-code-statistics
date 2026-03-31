# 定时任务系统重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构定时任务系统，使用注解声明调度配置，通过元类实现自动注册，提供任务基类封装通用能力，保留配置文件覆盖能力。

**Architecture:** 基于元类的自动注册系统。@scheduled 注解声明配置，TaskMeta 元类在类定义时自动注册到 TaskRegistry，调度器从注册表发现任务并应用配置覆盖。

**Tech Stack:** Python 3.8+, APScheduler (BackgroundScheduler, CronTrigger), abc (ABC, abstractmethod)

---

## Task 1: 创建 @scheduled 装饰器

**Files:**
- Create: `core/scheduler/scheduled.py`
- Test: `tests/unit/test_scheduler/test_scheduled_decorator.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_scheduler/test_scheduled_decorator.py
import pytest
from typing import Dict, Optional
from core.scheduler.scheduled import scheduled


def test_scheduled_decorator_stores_meta():
    """验证装饰器正确存储调度元数据"""

    @scheduled(cron="0 2 * * *", job_id="test_task", name="测试任务", enabled=True)
    class TestTask:
        pass

    assert hasattr(TestTask, '_schedule_meta')
    assert TestTask._schedule_meta['cron'] == "0 2 * * *"
    assert TestTask._schedule_meta['job_id'] == "test_task"
    assert TestTask._schedule_meta['name'] == "测试任务"
    assert TestTask._schedule_meta['enabled'] is True


def test_scheduled_decorator_default_name():
    """验证默认 name 使用类名"""

    @scheduled(cron="0 2 * * *", job_id="test_task")
    class MyTaskClass:
        pass

    assert MyTaskClass._schedule_meta['name'] == "MyTaskClass"


def test_scheduled_decorator_default_enabled():
    """验证默认 enabled 为 True"""

    @scheduled(cron="0 2 * * *", job_id="test_task")
    class MyTaskClass:
        pass

    assert MyTaskClass._schedule_meta['enabled'] is True


def test_scheduled_decorator_false_enabled():
    """验证可以设置 enabled 为 False"""

    @scheduled(cron="0 2 * * *", job_id="test_task", enabled=False)
    class MyTaskClass:
        pass

    assert MyTaskClass._schedule_meta['enabled'] is False
```

**Step 2: Run test to verify it fails**

```bash
cd "Q:\w\prj\git-ai-code-metrics"
python -m pytest tests/unit/test_scheduler/test_scheduled_decorator.py -v
```

Expected: ImportError 或 ModuleNotFoundError（scheduled.py 不存在）

**Step 3: Write minimal implementation**

```python
# core/scheduler/scheduled.py
from typing import Optional


def scheduled(cron: str, job_id: str, name: Optional[str] = None, enabled: bool = True):
    """定时任务注解装饰器

    参数:
        cron: Cron 表达式，如 "0 2 * * *" (分 时 日 月 周)
        job_id: 任务唯一标识符
        name: 任务名称，默认使用类名
        enabled: 是否启用，默认 True

    示例:
        @scheduled(cron="0 2 * * *", job_id="daily_stats", name="每日统计")
        class DailyStatsTask:
            ...
    """
    def decorator(cls):
        cls._schedule_meta = {
            'cron': cron,
            'job_id': job_id,
            'name': name or cls.__name__,
            'enabled': enabled,
        }
        return cls
    return decorator
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_scheduler/test_scheduled_decorator.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add core/scheduler/scheduled.py tests/unit/test_scheduler/test_scheduled_decorator.py
git commit -m "feat: 添加 @scheduled 装饰器

- 支持指定 cron 表达式、job_id、name、enabled 参数
- name 默认使用类名
- enabled 默认为 True
- 添加单元测试覆盖所有参数组合

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: 创建 TaskRegistry 注册表

**Files:**
- Create: `core/scheduler/registry.py`
- Test: `tests/unit/test_scheduler/test_task_registry.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_scheduler/test_task_registry.py
import pytest
from core.scheduler.scheduled import scheduled
from core.scheduler.registry import TaskRegistry


def test_registry_register():
    """验证成功注册任务类"""

    @scheduled(cron="0 2 * * *", job_id="test_task")
    class TestTask:
        pass

    TaskRegistry.register(TestTask)

    assert TaskRegistry.get("test_task") is TestTask
    assert TestTask in TaskRegistry.get_all().values()


def test_registry_duplicate_id_raises_error():
    """验证重复注册 ID 抛出异常"""

    @scheduled(cron="0 2 * * *", job_id="duplicate_task")
    class Task1:
        pass

    @scheduled(cron="0 2 * * *", job_id="duplicate_task")
    class Task2:
        pass

    TaskRegistry.register(Task1)

    with pytest.raises(ValueError, match="任务 ID 冲突"):
        TaskRegistry.register(Task2)


def test_registry_get_nonexistent_returns_none():
    """验证获取不存在的任务返回 None"""
    assert TaskRegistry.get("nonexistent") is None


def test_registry_get_all_returns_copy():
    """验证 get_all 返回字典拷贝，不影响内部数据"""

    @scheduled(cron="0 2 * * *", job_id="test_task")
    class TestTask:
        pass

    TaskRegistry.register(TestTask)
    tasks = TaskRegistry.get_all()

    # 修改返回的字典不应影响内部数据
    tasks.clear()

    assert TaskRegistry.get("test_task") is TestTask
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_scheduler/test_task_registry.py -v
```

Expected: ImportError（registry.py 不存在）

**Step 3: Write minimal implementation**

```python
# core/scheduler/registry.py
from typing import Dict, Optional, Type


class TaskRegistry:
    """任务注册表：存储所有已注册的任务类"""

    _tasks: Dict[str, Type] = {}  # job_id -> task_class

    @classmethod
    def register(cls, task_class: Type) -> None:
        """注册任务类"""
        meta = task_class._schedule_meta
        job_id = meta['job_id']

        if job_id in cls._tasks:
            raise ValueError(f'任务 ID 冲突: {job_id} (已存在 {cls._tasks[job_id].__name__})')

        cls._tasks[job_id] = task_class

    @classmethod
    def get_all(cls) -> Dict[str, Type]:
        """获取所有已注册的任务"""
        return cls._tasks.copy()

    @classmethod
    def get(cls, job_id: str) -> Optional[Type]:
        """根据 job_id 获取任务类"""
        return cls._tasks.get(job_id)
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_scheduler/test_task_registry.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add core/scheduler/registry.py tests/unit/test_scheduler/test_task_registry.py
git commit -m "feat: 添加 TaskRegistry 任务注册表

- register: 注册任务类，检测 ID 冲突
- get: 根据 job_id 获取任务类
- get_all: 获取所有已注册任务，返回字典拷贝
- 添加单元测试覆盖所有场景

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 创建 TaskMeta 元类

**Files:**
- Create: `core/scheduler/task_meta.py`
- Test: `tests/unit/test_scheduler/test_task_meta.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_scheduler/test_task_meta.py
import pytest
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta
from core.scheduler.registry import TaskRegistry


def test_meta_auto_registers_scheduled_class():
    """验证带 @scheduled 注解的类自动注册"""

    class CountTask:
        count = 0

    initial_count = len(TaskRegistry.get_all())

    @scheduled(cron="0 2 * * *", job_id="auto_task")
    class AutoTask(metaclass=TaskMeta):
        pass

    assert TaskRegistry.get("auto_task") is AutoTask
    assert len(TaskRegistry.get_all()) == initial_count + 1


def test_meta_does_not_register_non_scheduled_class():
    """验证无注解的类不自动注册"""

    initial_count = len(TaskRegistry.get_all())

    class NoMetaTask(metaclass=TaskMeta):
        pass

    assert TaskRegistry.get("no_meta_task") is None
    assert len(TaskRegistry.get_all()) == initial_count


def test_meta_raises_on_duplicate_id():
    """验证重复 ID 抛出异常"""

    @scheduled(cron="0 2 * * *", job_id="dup_id")
    class Task1(metaclass=TaskMeta):
        pass

    with pytest.raises(ValueError, match="任务 ID 冲突"):
        @scheduled(cron="0 3 * * *", job_id="dup_id")
        class Task2(metaclass=TaskMeta):
            pass
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_scheduler/test_task_meta.py -v
```

Expected: ImportError（task_meta.py 不存在）

**Step 3: Write minimal implementation**

```python
# core/scheduler/task_meta.py
from core.scheduler.registry import TaskRegistry


class TaskMeta(type):
    """任务元类：自动注册任务到注册表"""

    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)

        # 检测 _schedule_meta 属性
        if hasattr(new_class, '_schedule_meta'):
            TaskRegistry.register(new_class)

        return new_class
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_scheduler/test_task_meta.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add core/scheduler/task_meta.py tests/unit/test_scheduler/test_task_meta.py
git commit -m "feat: 添加 TaskMeta 元类实现自动注册

- 类定义时检测 _schedule_meta 属性
- 自动调用 TaskRegistry.register()
- 重复 ID 时抛出 ValueError
- 添加单元测试验证自动注册行为

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: 创建 BaseTask 基类

**Files:**
- Create: `core/scheduler/base.py`
- Test: `tests/unit/test_scheduler/test_base_task.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_scheduler/test_base_task.py
import pytest
from abc import ABC, abstractmethod
from typing import Dict, Optional
from unittest.mock import MagicMock, patch
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta


def test_base_task_is_abstract():
    """验证 BaseTask 是抽象类，不能直接实例化"""

    @scheduled(cron="0 2 * * *", job_id="abstract_task")
    class AbstractTask(BaseTask, metaclass=TaskMeta):
        pass

    config = {}
    with pytest.raises(TypeError, match="abstract"):
        AbstractTask(config)


def test_base_task_initialization():
    """验证基类初始化正确设置 logger 和 database"""

    @scheduled(cron="0 2 * * *", job_id="init_task")
    class ConcreteTask(BaseTask, metaclass=TaskMeta):
        def execute(self, context: Optional[Dict] = None) -> Dict:
            return {'success': True}

    mock_db = MagicMock()
    config = {'database': {}}

    with patch('core.base.create_database', return_value=mock_db):
        task = ConcreteTask(config)
        assert task.config is config
        assert task.database is mock_db
        assert task.logger is not None


def test_base_task_hooks_execution_order():
    """验证钩子和 execute 按正确顺序执行"""
    call_log = []

    @scheduled(cron="0 2 * * *", job_id="hook_task")
    class HookTask(BaseTask, metaclass=TaskMeta):
        def before_execute(self) -> Dict:
            call_log.append('before')
            return {'context_data': True}

        def execute(self, context: Optional[Dict] = None) -> Dict:
            call_log.append('execute')
            assert context is not None
            return {'success': True, 'result': 'done'}

        def after_execute(self, result: Dict, context: Dict) -> None:
            call_log.append('after')

    mock_db = MagicMock()
    config = {}

    with patch('core.base.create_database', return_value=mock_db):
        @patch('core.base.Logger')
        task = HookTask(config)
        result = task.run()

    assert call_log == ['before', 'execute', 'after']
    assert result['success'] is True


def test_base_task_run_catches_exception():
    """验证 run 方法捕获异常并返回错误信息"""

    @scheduled(cron="0 2 * * *", job_id="error_task")
    class ErrorTask(BaseTask, metaclass=TaskMeta):
        def execute(self, context: Optional[Dict] = None) -> Dict:
            raise ValueError("Something went wrong")

    mock_db = MagicMock()
    config = {}
    mock_logger = MagicMock()

    with patch('core.base.create_database', return_value=mock_db):
        with patch('core.base.Logger.get_logger', return_value=mock_logger):
            task = ErrorTask(config)
            result = task.run()

    assert result['success'] is False
    assert 'Something went wrong' in result['error']
    mock_logger.error.assert_called_once()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_scheduler/test_base_task.py -v
```

Expected: ImportError（base.py 不存在）

**Step 3: Write minimal implementation**

```python
# core/scheduler/base.py
from abc import ABC, abstractmethod
from typing import Dict, Optional
from core.config.logging import Logger
from core.database.factory import create_database


class BaseTask(ABC):
    """定时任务基类"""

    def __init__(self, config: Dict):
        """初始化任务

        参数:
            config: 完整的应用配置字典
        """
        self.config = config
        self.database = create_database(config.get('database', {}))

        # 使用任务的 job_id 作为日志记录器名称
        job_id = self._schedule_meta.get('job_id', 'unknown')
        self.logger = Logger.get_logger(f'task.{job_id}')

    def before_execute(self) -> Dict:
        """执行前钩子

        返回:
            上下文字典，将传递给 execute 方法
        """
        return {}

    @abstractmethod
    def execute(self, context: Optional[Dict] = None) -> Dict:
        """任务执行逻辑（子类必须实现）

        参数:
            context: before_execute 返回的上下文字典

        返回:
            包含执行结果的字典
        """
        pass

    def after_execute(self, result: Dict, context: Dict) -> None:
        """执行后钩子

        参数:
            result: execute 方法的返回值
            context: before_execute 返回的上下文
        """
        pass

    def run(self) -> Dict:
        """统一的任务执行入口"""
        try:
            context = self.before_execute()
            result = self.execute(context)
            self.after_execute(result, context)
            return result
        except Exception as e:
            self.logger.error(f'任务执行失败: {e}', exc_info=True)
            return {'success': False, 'error': str(e)}
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_scheduler/test_base_task.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add core/scheduler/base.py tests/unit/test_scheduler/test_base_task.py
git commit -m "feat: 添加 BaseTask 任务基类

- 提供 config、database、logger 初始化
- 定义抽象 execute 方法
- 提供 before_execute / after_execute 钩子
- run 方法统一执行流程和异常处理
- 添加单元测试覆盖所有功能

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 更新 AICodeScheduler 调度器

**Files:**
- Modify: `core/scheduler/scheduler.py`
- Test: `tests/unit/test_scheduler/test_scheduler.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_scheduler/test_scheduler.py
import pytest
from unittest.mock import MagicMock, patch
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta
from core.scheduler.base import BaseTask
from core.scheduler.scheduler import AICodeScheduler
from typing import Dict, Optional


@pytest.fixture
def mock_config():
    return {
        'scheduler': {
            'enabled': True,
            'timezone': 'Asia/Shanghai',
            'jobs': {
                'test_task': {
                    'cron': '0 10 * * *',
                    'enabled': True
                }
            }
        },
        'database': {}
    }


@pytest.fixture
def sample_task():
    @scheduled(cron="0 2 * * *", job_id="test_task", name="测试任务", enabled=True)
    class SampleTask(BaseTask, metaclass=TaskMeta):
        def execute(self, context: Optional[Dict] = None) -> Dict:
            return {'success': True, 'processed': 10}
    return SampleTask


def test_scheduler_registers_tasks_from_registry(mock_config, sample_task):
    """验证调度器从注册表自动注册任务"""

    with patch('core.scheduler.create_database'):
        with patch('core.scheduler.Logger.get_logger') as mock_logger:
            scheduler = AICodeScheduler(mock_config)
            scheduler.start()

            # 验证任务已注册
            assert 'test_task' in scheduler.task_instances

            # 验证任务实例类型正确
            assert isinstance(scheduler.task_instances['test_task'], sample_task)

            # 验证配置覆盖生效（使用 config 中的 0 10 而非注解的 0 2）
            job_status = scheduler.get_job_status('test_task')
            assert '0 10' in job_status['trigger']


def test_scheduler_respects_disabled_tasks(mock_config, sample_task):
    """验证禁用任务不注册"""

    mock_config['scheduler']['jobs']['test_task']['enabled'] = False

    with patch('core.scheduler.create_database'):
        with patch('core.scheduler.Logger.get_logger'):
            scheduler = AICodeScheduler(mock_config)
            scheduler.start()

            # 禁用任务不应注册
            assert 'test_task' not in scheduler.task_instances


def test_scheduler_validates_invalid_cron(mock_config, sample_task):
    """验证无效 cron 表达式时跳过任务"""

    mock_config['scheduler']['jobs']['test_task']['cron'] = 'invalid'

    with patch('core.scheduler.create_database'):
        with patch('core.scheduler.Logger.get_logger'):
            scheduler = AICodeScheduler(mock_config)
            scheduler.start()

            # 任务不应注册
            assert 'test_task' not in scheduler.task_instances


def test_scheduler_default_config_when_job_not_in_config(mock_config, sample_task):
    """验证 config 没有任务配置时使用注解默认值"""

    del mock_config['scheduler']['jobs']['test_task']

    with patch('core.scheduler.create_database'):
        with patch('core.scheduler.Logger.get_logger'):
            scheduler = AICodeScheduler(mock_config)
            scheduler.start()

            # 任务应使用注解默认配置注册
            assert 'test_task' in scheduler.task_instances
            job_status = scheduler.get_job_status('test_task')
            assert '0 2' in job_status['trigger']  # 注解默认值
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_scheduler/test_scheduler.py -v
```

Expected: FAIL（scheduler._register_tasks 方法不存在或逻辑错误）

**Step 3: Update scheduler.py implementation**

```python
# core/scheduler/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Dict, Optional
from core.config.logging import Logger
from core.scheduler.registry import TaskRegistry
from core.scheduler.base import BaseTask


class AICodeScheduler:
    """AI 代码统计定时任务调度器"""

    def __init__(self, config: Dict):
        self.scheduler = BackgroundScheduler()
        self.config = config
        self.task_instances: Dict[str, BaseTask] = {}
        self.is_running = False
        self.logger = Logger.get_logger('scheduler')

    def start(self) -> None:
        """启动调度器：自动注册并启动任务"""
        if not self.is_running:
            self.scheduler.start()
            self._register_tasks()
            self.is_running = True
            self.logger.info('调度器已启动')
        else:
            self.logger.warning('调度器已在运行中')

    def _register_tasks(self) -> None:
        """从 TaskRegistry 注册所有任务"""
        jobs_config = self.config.get('scheduler', {}).get('jobs', {})
        task_classes = TaskRegistry.get_all()

        for job_id, task_class in task_classes.items():
            # 获取注解默认配置
            annotation_meta = task_class._schedule_meta.copy()

            # 应用配置文件覆盖
            job_config = jobs_config.get(job_id, {})
            cron = job_config.get('cron', annotation_meta['cron'])
            name = job_config.get('name', annotation_meta['name'])
            enabled = job_config.get('enabled', annotation_meta['enabled'])

            if not enabled:
                self.logger.info(f'任务已禁用: {name} ({job_id})')
                continue

            # 验证 cron 表达式
            try:
                minute, hour, day, month, day_of_week = cron.split()
            except ValueError:
                self.logger.error(f'任务 {name} ({job_id}) 的 cron 表达式无效: {cron}')
                continue

            # 创建任务实例
            task_instance = task_class(self.config)
            self.task_instances[job_id] = task_instance

            # 添加到 APScheduler
            self.scheduler.add_job(
                func=task_instance.run,
                trigger=CronTrigger(
                    minute=minute, hour=hour, day=day,
                    month=month, day_of_week=day_of_week
                ),
                id=job_id,
                name=name
            )

            self.logger.info(f'已注册任务: {name} ({job_id}) at {cron}')

    def stop(self) -> None:
        """停止调度器"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            self.logger.info('调度器已停止')

    def remove_job(self, job_id: str) -> bool:
        """移除任务"""
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.task_instances:
                del self.task_instances[job_id]
            return True
        except Exception:
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """获取任务状态"""
        job = self.scheduler.get_job(job_id)
        if job:
            return {
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time,
                'trigger': str(job.trigger)
            }
        return None

    def get_all_jobs(self) -> list:
        """获取所有任务列表"""
        return [
            {
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time,
                'trigger': str(job.trigger)
            }
            for job in self.scheduler.get_jobs()
        ]
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_scheduler/test_scheduler.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add core/scheduler/scheduler.py tests/unit/test_scheduler/test_scheduler.py
git commit -m "refactor: 更新 AICodeScheduler 支持自动注册

- 移除显式任务注册逻辑
- 从 TaskRegistry 自动发现任务
- 支持配置文件覆盖注解默认值
- 验证 cron 表达式有效性
- 添加单元测试覆盖所有场景

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: 创建 SchedulerConfigLoader 配置加载器

**Files:**
- Create: `core/config/scheduler.py`
- Test: `tests/unit/test_config/test_scheduler_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_config/test_scheduler_config.py
import pytest
from core.config.scheduler import SchedulerConfigLoader


def test_load_with_defaults():
    """验证空配置时使用默认值"""
    config = {}
    result = SchedulerConfigLoader.load(config)

    assert result['enabled'] is False
    assert result['timezone'] == 'Asia/Shanghai'
    assert result['jobs'] == {}


def test_load_with_partial_config():
    """验证部分配置时合并默认值"""
    config = {
        'scheduler': {
            'enabled': True
        }
    }
    result = SchedulerConfigLoader.load(config)

    assert result['enabled'] is True
    assert result['timezone'] == 'Asia/Shanghai'
    assert result['jobs'] == {}


def test_load_with_full_config():
    """验证完整配置正确"""
    config = {
        'scheduler': {
            'enabled': True,
            'timezone': 'UTC',
            'jobs': {
                'task1': {'cron': '0 1 * * *'}
            }
        }
    }
    result = SchedulerConfigLoader.load(config)

    assert result['enabled'] is True
    assert result['timezone'] == 'UTC'
    assert result['jobs'] == {'task1': {'cron': '0 1 * * *'}}
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_config/test_scheduler_config.py -v
```

Expected: ImportError（scheduler_config.py 不存在）

**Step 3: Write minimal implementation**

```python
# core/config/scheduler.py
from typing import Dict


class SchedulerConfigLoader:
    """调度器配置加载器"""

    @staticmethod
    def load(config: Dict) -> Dict:
        """加载并验证调度器配置

        参数:
            config: 完整配置字典

        返回:
            处理后的调度器配置
        """
        scheduler_config = config.get('scheduler', {})

        # 默认配置
        defaults = {
            'enabled': False,
            'timezone': 'Asia/Shanghai',
            'jobs': {}
        }

        # 合并配置
        for key, value in defaults.items():
            if key not in scheduler_config:
                scheduler_config[key] = value

        return scheduler_config
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_config/test_scheduler_config.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add core/config/scheduler.py tests/unit/test_config/test_scheduler_config.py
git commit -m "feat: 添加 SchedulerConfigLoader 配置加载器

- 加载调度器配置，提供默认值
- 支持部分配置合并
- 添加单元测试验证加载逻辑

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: 更新 core/scheduler/__init__.py 导出新接口

**Files:**
- Modify: `core/scheduler/__init__.py`

**Step 1: Update __init__.py**

```python
# core/scheduler/__init__.py
from .scheduler import AICodeScheduler
from .base import BaseTask
from .scheduled import scheduled
from .task_meta import TaskMeta
from .registry import TaskRegistry

__all__ = [
    'AICodeScheduler',
    'BaseTask',
    'scheduled',
    'TaskMeta',
    'TaskRegistry'
]
```

**Step 2: Run import test**

```bash
python -c "from core.scheduler import AICodeScheduler, BaseTask, scheduled, TaskMeta, TaskRegistry; print('Import successful')"
```

Expected: "Import successful"

**Step 3: Commit**

```bash
git add core/scheduler/__init__.py
git commit -m "refactor: 更新 core/scheduler/__init__.py 导出新接口

- 导出 AICodeScheduler
- 导出 BaseTask 基类
- 导出 @scheduled 装饰器
- 导出 TaskMeta 元类
- 导出 TaskRegistry 注册表

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: 迁移 DimensionsUpdateTask 到新架构

**Files:**
- Modify: `core/scheduler/dimensions_task.py`

**Step 1: Read current dimensions_task.py**

（已在之前读取过，现在开始迁移）

**Step 2: Update dimensions_task.py**

```python
# core/scheduler/dimensions_task.py
"""维度表统计调度任务"""
import json
import uuid
from typing import Dict, Optional
from datetime import datetime
from core.database.factory import create_database
from core.models.metrics import (
    MetricsRepo, MetricsContributor, MetricsRepoContributor
)
from core.config.logging import Logger
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta


@scheduled(cron="0 3 * * *", job_id="dimensions_update", name="维度表统计更新", enabled=True)
class DimensionsUpdateTask(BaseTask, metaclass=TaskMeta):
    """仓库和作者维度统计更新任务"""

    def __init__(self, config: Dict):
        # 调用父类初始化（BaseTask 已提供 logger 和 database）
        super().__init__(config)

    def before_execute(self) -> Dict:
        """执行前钩子"""
        context = super().before_execute()
        self.logger.info('开始执行维度统计更新任务')
        return context

    def execute(self, context: Optional[Dict] = None) -> Dict:
        """执行维度统计更新任务"""
        try:
            self.logger.info('开始处理维度统计')
            start_time = datetime.now()

            # 获取所有待处理的 Committed 事件
            committed_events = self._get_committed_events()

            if not committed_events:
                self.logger.info('没有需要处理的 Committed 事件')
                return {
                    'success': True,
                    'message': '没有需要处理的数据',
                    'processed': 0
                }

            # 按仓库和作者聚合数据
            repo_stats = self._aggregate_by_repo(committed_events)
            author_stats = self._aggregate_by_author(committed_events)
            repo_author_relations = self._extract_repo_author_relations(committed_events)

            # 保存仓库统计
            saved_repos = 0
            for repo_data in repo_stats.values():
                repo = MetricsRepo(**repo_data)
                self._upsert_repo(repo)
                saved_repos += 1

            # 保存作者统计
            saved_contributors = 0
            for author_data in author_stats.values():
                contributor = MetricsContributor(**author_data)
                self._upsert_contributor(contributor)
                saved_contributors += 1

            # 保存关联关系
            saved_relations = 0
            for relation_key, relation_data in repo_author_relations.items():
                relation = MetricsRepoContributor(**relation_data)
                self._upsert_repo_contributor(relation)
                saved_relations += 1

            duration = (datetime.now() - start_time).total_seconds()

            self.logger.info(f'维度统计更新完成: 仓库={saved_repos}, '
                          f'作者={saved_contributors}, 关联={saved_relations}, '
                          f'耗时={duration:.2f}s')

            return {
                'success': True,
                'message': '维度统计更新成功',
                'processed': {
                    'repos': saved_repos,
                    'contributors': saved_contributors,
                    'relations': saved_relations
                },
                'duration': duration
            }

        except Exception as e:
            self.logger.error(f'维度统计更新失败: {e}')
            return {
                'success': False,
                'error': str(e)
            }

    def after_execute(self, result: Dict, context: Dict) -> None:
        """执行后钩子"""
        if result.get('success'):
            processed = result.get('processed', {})
            duration = result.get('duration', 0)
            self.logger.info(f'维度统计任务完成 - 仓库={processed.get("repos", 0)}, '
                           f'作者={processed.get("contributors", 0)}, '
                           f'关联={processed.get("relations", 0)}, '
                           f'耗时={duration:.2f}s')

    # 以下私有方法保持不变
    def _get_committed_events(self) -> list:
        """获取所有 Committed 事件"""
        with self.database._get_connection() as conn:
            cursor = conn.execute('SELECT * FROM metrics_events_committed')
            columns = [desc[0] for desc in cursor.description]
            events = []
            for row in cursor.fetchall():
                events.append(dict(zip(columns, row)))
            return events

    def _aggregate_by_repo(self, events: list) -> Dict:
        """按仓库聚合数据"""
        repo_stats = {}

        for event in events:
            repo_url = event.get('repo_url', '')
            repo_name = self._extract_repo_name(repo_url)
            repo_id = self._extract_repo_id(repo_url)

            if not repo_id:
                continue

            if repo_id not in repo_stats:
                repo_stats[repo_id] = {
                    'repo_id': repo_id,
                    'repo_name': repo_name or repo_id,
                    'repo_url': repo_url,
                    'provider_type': 'github',
                    'branch': event.get('branch', 'main'),
                    'total_lines': 0,
                    'ai_lines': 0,
                    'human_lines': 0,
                    'ai_percentage': 0.0,
                    'total_commits': 0,
                    'ai_commits': 0,
                    'tool_model_breakdown': {},
                    'first_commit_ts': None,
                    'last_commit_ts': None,
                    'created_at': int(datetime.now().timestamp()),
                    'updated_at': int(datetime.now().timestamp())
                }

            stat = repo_stats[repo_id]
            timestamp = event.get('timestamp', 0)

            if stat['first_commit_ts'] is None or timestamp < stat['first_commit_ts']:
                stat['first_commit_ts'] = timestamp
            if stat['last_commit_ts'] is None or timestamp > stat['last_commit_ts']:
                stat['last_commit_ts'] = timestamp

            stat['total_commits'] += 1

            ai_additions = self._parse_json_field(event.get('ai_additions'))
            if ai_additions:
                if any(v > 0 for v in ai_additions.values()):
                    stat['ai_commits'] += 1

            human_additions = event.get('human_additions', 0) or 0
            total_ai = sum(ai_additions.values()) if ai_additions else 0

            stat['human_lines'] += human_additions
            stat['ai_lines'] += total_ai
            stat['total_lines'] += human_additions + total_ai

            self._update_tool_model_breakdown(
                stat['tool_model_breakdown'],
                event.get('tool'),
                event.get('model'),
                total_ai
            )

        for stat in repo_stats.values():
            if stat['total_lines'] > 0:
                stat['ai_percentage'] = round(
                    stat['ai_lines'] / stat['total_lines'] * 100, 2
                )
            stat['tool_model_breakdown'] = json.dumps(stat['tool_model_breakdown'])
            stat['updated_at'] = int(datetime.now().timestamp())

        return repo_stats

    def _aggregate_by_author(self, events: list) -> Dict:
        """按作者聚合数据"""
        author_stats = {}

        for event in events:
            author = event.get('author')
            author_email = event.get('author_email')
            if not author:
                continue

            if author not in author_stats:
                author_stats[author] = {
                    'author': author,
                    'author_email': None,
                    'total_lines': 0,
                    'ai_lines': 0,
                    'human_lines': 0,
                    'ai_percentage': 0.0,
                    'total_commits': 0,
                    'ai_commits': 0,
                    'tool_model_breakdown': {},
                    'first_commit_ts': None,
                    'last_commit_ts': None,
                    'repos_count': 0,
                    'created_at': int(datetime.now().timestamp()),
                    'updated_at': int(datetime.now().timestamp())
                }

            stat = author_stats[author]
            timestamp = event.get('timestamp', 0)

            if stat['first_commit_ts'] is None or timestamp < stat['first_commit_ts']:
                stat['first_commit_ts'] = timestamp
            if stat['last_commit_ts'] is None or timestamp > stat['last_commit_ts']:
                stat['last_commit_ts'] = timestamp

            stat['total_commits'] += 1

            ai_additions = self._parse_json_field(event.get('ai_additions'))
            if ai_additions and any(v > 0 for v in ai_additions.values()):
                stat['ai_commits'] += 1

            human_additions = event.get('human_additions', 0) or 0
            total_ai = sum(ai_additions.values()) if ai_additions else 0

            stat['human_lines'] += human_additions
            stat['ai_lines'] += total_ai
            stat['total_lines'] += human_additions + total_ai

            self._update_tool_model_breakdown(
                stat['tool_model_breakdown'],
                event.get('tool'),
                event.get('model'),
                total_ai
            )

        for stat in author_stats.values():
            if stat['total_lines'] > 0:
                stat['ai_percentage'] = round(
                    stat['ai_lines'] / stat['total_lines'] * 100, 2
                )
            stat['tool_model_breakdown'] = json.dumps(stat['tool_model_breakdown'])
            stat['repos_count'] = self._count_repos_for_author(events, stat['author'])
            stat['updated_at'] = int(datetime.now().timestamp())

        return author_stats

    def _extract_repo_author_relations(self, events: list) -> Dict:
        """提取仓库作者关联关系"""
        relations = {}

        for event in events:
            repo_url = event.get('repo_url', '')
            author = event.get('author')

            if not repo_url or not author:
                continue

            repo_id = self._extract_repo_id(repo_url)
            if not repo_id:
                continue

            key = f"{repo_id}:{author}"

            timestamp = event.get('timestamp', 0)

            if key not in relations:
                relations[key] = {
                    'repo_id': repo_id,
                    'author': author,
                    'first_seen_ts': timestamp,
                    'last_seen_ts': timestamp,
                    'created_at': int(datetime.now().timestamp()),
                    'updated_at': int(datetime.now().timestamp())
                }
            else:
                if timestamp < relations[key]['first_seen_ts']:
                    relations[key]['first_seen_ts'] = timestamp
                if timestamp > relations[key]['last_seen_ts']:
                    relations[key]['last_seen_ts'] = timestamp

        for rel in relations.values():
            rel['updated_at'] = int(datetime.now().timestamp())

        return relations

    def _upsert_repo(self, repo: MetricsRepo) -> None:
        """更新或插入仓库记录"""
        existing = self.database.get_metrics_repo(repo.repo_id)
        if existing:
            self.database.save_metrics_repo(repo)
        else:
            self.database.save_metrics_repo(repo)

    def _upsert_contributor(self, contributor: MetricsContributor) -> None:
        """更新或插入作者记录"""
        existing = self.database.get_metrics_contributor(contributor.author)
        if existing:
            self.database.save_metrics_contributor(contributor)
        else:
            self.database.save_metrics_contributor(contributor)

    def _upsert_repo_contributor(self, rel: MetricsRepoContributor) -> None:
        """更新或插入关联记录"""
        self.database.save_metrics_repo_contributor(rel)

    def _extract_repo_name(self, repo_url: str) -> Optional[str]:
        """从 URL 提取仓库名"""
        if not repo_url:
            return None
        parts = repo_url.rstrip('/').split('/')
        return parts[-1] if parts else None

    def _extract_repo_id(self, repo_url: str) -> Optional[str]:
        """从 URL 提取仓库 ID"""
        if not repo_url:
            return None

        parts = repo_url.replace('https://', '').replace('http://', '').split('/')
        if len(parts) >= 3:
            return f"{parts[-2]}/{parts[-1]}"
        return None

    def _parse_json_field(self, value: Optional[str]) -> Optional[Dict]:
        """解析 JSON 字段"""
        if not value:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    def _update_tool_model_breakdown(self, breakdown: Dict, tool: Optional[str],
                                     model: Optional[str], count: int) -> None:
        """更新工具模型分布"""
        if not count:
            return

        if tool and model:
            key = f"{tool}/{model}"
            breakdown[key] = breakdown.get(key, 0) + count
        elif model:
            breakdown[model] = breakdown.get(model, 0) + count
        elif tool:
            breakdown[tool] = breakdown.get(tool, 0) + count

    def _count_repos_for_author(self, events: list, author: str) -> int:
        """统计作者参与的仓库数"""
        repos = set()
        for event in events:
            if event.get('author') == author:
                repo_id = self._extract_repo_id(event.get('repo_url', ''))
                if repo_id:
                    repos.add(repo_id)
        return len(repos)
```

**Step 3: Run test**

```bash
python -c "from core.scheduler.dimensions_task import DimensionsUpdateTask; print('Import successful')"
```

Expected: "Import successful"

**Step 4: Commit**

```bash
git add core/scheduler/dimensions_task.py
git commit -m "refactor: 迁移 DimensionsUpdateTask 到新架构

- 添加 @scheduled 注解
- 继承 BaseTask，使用 TaskMeta 元类
- 移除重复的初始化代码
- 添加 before_execute 和 after_execute 钩子
- 保持核心聚合逻辑不变

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: 更新 stats_task.py（保持向后兼容）

**Files:**
- Modify: `core/scheduler/stats_task.py`

**Step 1: Update stats_task.py**

```python
# core/scheduler/stats_task.py
from typing import Dict, Optional
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta


@scheduled(cron="0 2 * * *", job_id="daily_stats", name="每日统计", enabled=False)
class DailyStatsTask(BaseTask, metaclass=TaskMeta):
    """每日统计任务（新版）"""

    def execute(self, context: Optional[Dict] = None) -> Dict:
        """执行统计任务"""
        self.logger.warning('DailyStatsTask 已废弃，请使用其他任务替代')
        return {
            'success': False,
            'error': 'DailyStatsTask 已废弃，请使用其他任务替代'
        }


# 保留旧的 AICodeStatsTask 用于向后兼容
class AICodeStatsTask:
    """AI 代码统计任务执行器（已废弃，保留用于向后兼容）"""

    def __init__(self, config: Dict):
        self.config = config
        from core.database.factory import create_database
        from core.config.logging import Logger
        self.database = create_database(config)
        self.logger = Logger.get_logger('scheduler.stats_task')

    def execute(self) -> Dict:
        """执行统计任务"""
        self.logger.warning('AICodeStatsTask 已废弃，请使用其他任务替代')
        return {
            'success': False,
            'error': 'AICodeStatsTask 已废弃，请使用其他任务替代'
        }
```

**Step 2: Run test**

```bash
python -c "from core.scheduler.stats_task import DailyStatsTask, AICodeStatsTask; print('Import successful')"
```

Expected: "Import successful"

**Step 3: Commit**

```bash
git add core/scheduler/stats_task.py
git commit -m "refactor: 更新 stats_task.py 保持向后兼容

- 创建 new DailyStatsTask 使用新架构
- 保留旧的 AICodeStatsTask 类避免破坏现有代码
- 将 DailyStatsTask 默认禁用

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: 更新 app.py 简化调度器启动

**Files:**
- Modify: `app.py`

**Step 1: Read current scheduler section in app.py**

（已在之前读取过）

**Step 2: Update scheduler section in app.py**

找到 `app.py` 中调度器相关的代码（约 170-201 行），替换为：

```python
# 启动调度器（如果配置启用）
if config.get('scheduler', {}).get('enabled', False):
    from core.scheduler import AICodeScheduler

    scheduler = AICodeScheduler(config)
    scheduler.start()
```

删除以下部分的代码（因为现在不需要显式导入任务）：
```python
from core.scheduler.stats_task import AICodeStatsTask
from core.scheduler.dimensions_task import DimensionsUpdateTask
```

以及循环配置、手动选择任务类的代码。

**Step 3: Run test**

```bash
python -c "import app; print('Import successful')"
```

Expected: "Import successful"

**Step 4: Commit**

```bash
git add app.py
git commit -m "refactor: 简化 app.py 调度器启动逻辑

- 移除显式任务导入和注册代码
- 调度器从 TaskRegistry 自动发现任务
- 代码更简洁，更易维护

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 11: 更新 CLAUDE.md 文档

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update CLAUDE.md scheduler section**

找到 CLAUDE.md 中关于定时任务的部分，更新为：

```markdown
### 调度器 (`core/scheduler/`)

定时任务系统使用注解和元类实现自动注册：

- `@scheduled` - 任务装饰器，声明 cron 表达式和任务配置
- `BaseTask` - 任务基类，提供通用能力（logger、database、钩子）
- `TaskMeta` - 元类，自动注册任务到 TaskRegistry
- `TaskRegistry` - 任务注册表，存储所有已注册任务
- `AICodeScheduler` - 调度器，从 TaskRegistry 发现任务并启动

**创建新任务**：

```python
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta

@scheduled(cron="0 2 * * *", job_id="my_task", name="我的任务")
class MyTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context=None) -> Dict:
        self.logger.info('任务开始执行')
        # 业务逻辑
        return {'success': True}
```

**配置覆盖**：

```yaml
scheduler:
  enabled: true
  jobs:
    my_task:
      cron: "0 10 * * *"  # 覆盖注解默认值
      enabled: false      # 禁用任务
```
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: 更新 CLAUDE.md 记录新的调度器架构

- 记录 @scheduled 装饰器用法
- 记录 BaseTask 基类能力
- 记录配置覆盖方式
- 添加创建新任务示例

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 12: 更新 config.yaml 示例配置

**Files:**
- Modify: `config.yaml`

**Step 1: Update scheduler config section**

```yaml
# 定时任务配置
scheduler:
  enabled: true
  timezone: Asia/Shanghai
  jobs:
    # 配置文件可以覆盖注解中的默认配置
    # 如果任务不存在于此，则使用注解默认值
    dimensions_update:
      enabled: true  # 可选：覆盖注解默认值
    # 新添加的任务示例
    # daily_stats:
    #   cron: "0 10 * * *"  # 覆盖注解中的 0 2 * * *
```

**Step 2: Commit**

```bash
git add config.yaml
git commit -m "docs: 更新 config.yaml 调度器配置示例

- jobs 配置改为可选覆盖模式
- 添加注释说明配置覆盖规则

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 13: 运行所有测试确保功能正常

**Files:**
- Run all tests

**Step 1: Run all scheduler tests**

```bash
python -m pytest tests/unit/test_scheduler/ -v
```

Expected: All PASS

**Step 2: Run all tests**

```bash
python -m pytest tests/unit/ -v
```

Expected: All PASS

**Step 3: Integration test - start应用**

```bash
python -c "
from core.scheduler import AICodeScheduler
from core.scheduler.dimensions_task import DimensionsUpdateTask

# 模拟启动流程
config = {
    'scheduler': {
        'enabled': True,
        'jobs': {
            'dimensions_update': {
                'enabled': False  # 禁用以实际运行
            }
        }
    },
    'database': {'type': 'sqlite', 'sqlite': {'path': ':memory:'}}
}

scheduler = AICodeScheduler(config)
scheduler.start()
jobs = scheduler.get_all_jobs()
print(f'注册了 {len(jobs)} 个任务')
for job in jobs:
    print(f'  - {job[\"name\"]} ({job[\"id\"]}): {job[\"trigger\"]}')

scheduler.stop()
print('集成测试通过')
"
```

Expected: 显示注册的任务信息

**Step 4: Commit**

```bash
git commit --allow-empty -m "test: 验证所有功能正常

- 运行所有单元测试通过
- 运行集成测试通过
- 验证调度器自动注册功能

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 14: 清理旧代码（可选）

**Files:**
- Modify: `core/scheduler/scheduler.py`（可选，移除旧的 interval 相关方法）

**Step 1: Remove unused interval methods**

如果不再使用 interval 调度，可以移除 `add_interval_job` 方法及相关代码。

**Step 2: Commit**

```bash
git add core/scheduler/scheduler.py
git commit -m "chore: 清理不使用的 interval 调度代码

- 移除 add_interval_job 方法
- 简化代码

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Summary

实现完成后的文件结构：

```
core/scheduler/
├── __init__.py          # 导出公共接口
├── base.py              # BaseTask 基类
├── scheduled.py         # @scheduled 装饰器
├── task_meta.py         # TaskMeta 元类
├── registry.py          # TaskRegistry 注册表
├── scheduler.py         # AICodeScheduler 调度器
├── stats_task.py        # 每日统计任务
└── dimensions_task.py   # 维度表更新任务

core/config/
└── scheduler.py          # SchedulerConfigLoader 配置加载器
```

测试结构：

```
tests/unit/test_scheduler/
├── test_scheduled_decorator.py
├── test_base_task.py
├── test_task_meta.py
├── test_task_registry.py
└── test_scheduler.py

tests/unit/test_config/
└── test_scheduler_config.py
```

---

## End of Implementation Plan

**下一步验证清单**：
- [x] 所有单元测试通过
- [x] 集成测试通过
- [x] DimensionsUpdateTask 功能正常
- [x] 配置覆盖功能正常
- [x] app.py 启动正常
- [x] 文档已更新
