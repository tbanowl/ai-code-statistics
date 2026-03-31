# 定时任务系统重构设计文档

**日期**: 2026-03-18
**版本**: 1.0
**状态**: 已批准

## 1. 概述

### 1.1 背景

当前定时任务系统存在以下问题：
- 任务需要在 `app.py` 中显式注册，代码耦合度高
- 任务调度配置依赖 `config.yaml`，缺乏自描述性
- 代码重复，每个任务类都需要自行管理日志、数据库等通用功能

### 1.2 目标

- 使用注解声明调度配置，提高代码可读性
- 通过元类实现自动注册，移除显式注册代码
- 提供任务基类，封装日志、数据库、钩子函数、错误处理等通用能力
- 保留配置文件覆盖能力，提供运行时灵活性

### 1.3 核心原则

- **注解驱动**：任务通过 `@scheduled` 注解声明调度配置
- **自动注册**：元类在类定义时自动注册任务
- **配置覆盖**：注解提供默认值，config.yaml 可选择性覆盖
- **通用能力继承**：基类提供日志、数据库、钩子函数
- **向后兼容**：不影响现有 API 和数据库 Schema

---

## 2. 架构设计

### 2.1 组件图

```
┌─────────────────────────────────────────────────────────────┐
│                        app.py                                │
│                                                            │
│  - 创建 AICodeScheduler 实例                                │
│  - 调用 scheduler.start()                                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ 导入任务类模块
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Task Registry                              │
│  (core/scheduler/registry.py)                                │
│                                                            │
│  - 存储所有已注册的任务类 (job_id -> task_class)             │
│  - 提供 register/get/get_all 方法                           │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ 自动注册
                           │ 元类调用
┌────────────────────────┼──────────────────────────────────┐
│                        │                                     │
│  ┌─────────────────────┴─────────────────────────────────┐  │
│  │            TaskMeta (元类)                            │  │
│  │  (core/scheduler/task_meta.py)                        │  │
│  │                                                        │  │
│  │  - 检测 _schedule_meta 属性                          │  │
│  │  - 自动调用 TaskRegistry.register()                   │  │
│  └────────────────────────────────────────────────────┘   │  │
│                         ▲                                   │  │
│                         │ 继承                              │  │
│  ┌──────────────────────┴────────────────────────────────┐  │
│  │            BaseTask (基类)                            │  │
│  │  (core/scheduler/base.py)                             │  │
│  │                                                        │  │
│  │  - __init__: 初始化 logger/database                   │  │
│  │  - before_execute(): 执行前钩子                       │  │
│  │  - execute(): 抽象方法（子类实现）                     │  │
│  │  - after_execute(): 执行后钩子                        │  │
│  │  - run(): 统一执行入口，包含异常处理                   │  │
│  └────────────────────────────────────────────────────┘   │  │
│                         ▲                                   │  │
│                         │ 使用注解                          │  │
│  ┌──────────────────────┴────────────────────────────────┐  │
│  │         @scheduled (装饰器)                           │  │
│  │  (core/scheduler/scheduled.py)                       │  │
│  │                                                        │  │
│  │  参数: cron, job_id, name, enabled                   │  │
│  │  作用: 将配置存储到 _schedule_meta                    │  │
│  └────────────────────────────────────────────────────┘   │  │
│                        继承 + 注解                         │  │
│  ┌─────────────────────────────────────────────────────┐   │  │
│  │         具体任务类 (e.g., DailyStatsTask)          │   │  │
│  │  (core/scheduler/stats_task.py, dimensions_task.py)  │  │
│  │                                                       │   │  │
│  │  @scheduled(cron="0 2 * * *", ...)                  │   │  │
│  │  class DailyStatsTask(BaseTask, metaclass=TaskMeta):│   │  │
│  │      def execute(self, context): ...                │   │  │
│  └──────────────────────────────────────────────────────┘   │  │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
应用启动
    │
    ├─> 导入任务类模块 (e.g., import core.scheduler.stats_task)
    │
    ├─> TaskMeta.__new__() 被调用
    │   └─> 检测到 _schedule_meta 属性
    │   └─> 调用 TaskRegistry.register(task_class)
    │       └─> 任务类存入 _tasks 字典 (job_id -> task_class)
    │
    ├─> 调度器启动
    │   └─> 遍历 TaskRegistry.get_all()
    │   └─> 对每个任务：
    │       ├─> 获取注解默认配置 (_schedule_meta)
    │       ├─> 合并 config.yaml 覆盖 (scheduler.jobs.{job_id})
    │       ├─> 创建任务实例 (task_class(config))
    │       └─> 添加到 APScheduler (cron, func=instance.run)
    │
    └─> 等待触发时间到达
            │
            └─> APScheduler 触发
                └─> task_instance.run()
                    ├─> before_execute()  # 准备上下文
                    ├─> execute(context)   # 子类实现的具体逻辑
                    ├─> after_execute()    # 清理/通知
                    └─> 异常时捕获并记录日志
```

---

## 3. 核心组件详细设计

### 3.1 @scheduled 装饰器

**文件**: `core/scheduler/scheduled.py`

```python
from typing import Optional

def scheduled(cron: str, job_id: str, name: Optional[str] = None, enabled: bool = True):
    """定时任务注解装饰器

    参数:
        cron: Cron 表达式，如 "0 2 * * *" (分 时 日 月 周)
        job_id: 任务唯一标识符，用于配置覆盖和日志
        name: 任务名称（可选，默认使用类名）
        enabled: 是否启用（默认 True，可通过 config.yaml 覆盖）

    示例:
        @scheduled(cron="0 2 * * *", job_id="daily_stats", name="每日统计")
        class DailyStatsTask(BaseTask, metaclass=TaskMeta):
            ...
    """
    def decorator(cls):
        # 将调度元数据存储到类属性
        cls._schedule_meta = {
            'cron': cron,
            'job_id': job_id,
            'name': name or cls.__name__,
            'enabled': enabled,
        }
        return cls
    return decorator
```

### 3.2 BaseTask 基类

**文件**: `core/scheduler/base.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Optional
from core.config.logging import Logger
from core.database.factory import create_database

class BaseTask(ABC):
    """定时任务基类

    提供:
    - 统一的配置、日志记录器、数据库访问初始化
    - execute 前后钩子
    - 统一的执行入口和异常处理
    """

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
            默认返回空字典，子类可覆盖

        用途:
            - 准备任务执行所需的环境
            - 预加载数据
            - 记录开始时间等
        """
        return {}

    @abstractmethod
    def execute(self, context: Optional[Dict] = None) -> Dict:
        """任务执行逻辑（子类必须实现）

        参数:
            context: before_execute 返回的上下文字典

        返回:
            包含执行结果的字典
            标准格式: {'success': bool, 'message': str, 'data': {...}, ...}

        异常:
            抛出的任何异常都会被 run 方法捕获并记录
        """
        pass

    def after_execute(self, result: Dict, context: Dict) -> None:
        """执行后钩子

        参数:
            result: execute 方法的返回值
            context: before_execute 返回的上下文

        用途:
            - 清理资源
            - 发送通知
            - 记录执行结果指标
        """
        pass

    def run(self) -> Dict:
        """统一的任务执行入口

        由调度器调用，包含执行流程和异常处理

        执行流程:
            1. 调用 before_execute() 获取上下文
            2. 调用 execute(context) 执行具体逻辑
            3. 调用 after_execute() 进行后续处理
            4. 异常时捕获并记录日志

        返回:
            execute 的返回值，或异常信息 {'success': False, 'error': str}
        """
        try:
            context = self.before_execute()
            result = self.execute(context)
            self.after_execute(result, context)
            return result
        except Exception as e:
            self.logger.error(f'任务执行失败: {e}', exc_info=True)
            return {'success': False, 'error': str(e)}
```

### 3.3 TaskMeta 元类

**文件**: `core/scheduler/task_meta.py`

```python
from core.scheduler.registry import TaskRegistry

class TaskMeta(type):
    """任务元类：自动注册任务到注册表

    当一个类继承 BaseTask 并使用了 @scheduled 注解时，
    元类会检测到 _schedule_meta 属性并自动注册任务。

    工作流程:
        1. 在类定义时 __new__ 方法被调用
        2. 检查类是否有 _schedule_meta 属性（由 @scheduled 设置）
        3. 如果有，调用 TaskRegistry.register() 注册任务
    """

    def __new__(cls, name, bases, attrs):
        # 创建类
        new_class = super().__new__(cls, name, bases, attrs)

        # 检测 _schedule_meta 属性
        if hasattr(new_class, '_schedule_meta'):
            TaskRegistry.register(new_class)

        return new_class
```

### 3.4 TaskRegistry 注册表

**文件**: `core/scheduler/registry.py`

```python
from typing import Dict, Optional, Type

from core.scheduler.base import BaseTask

class TaskRegistry:
    """任务注册表：存储所有已注册的任务类

    采用单例模式，_tasks 类变量在进程生命周期内保持。

    方法:
        - register: 注册任务类
        - get: 根据 job_id 获取任务类
        - get_all: 获取所有已注册任务

    异常:
        - ValueError: 尝试注册重复的 job_id
    """

    _tasks: Dict[str, Type[BaseTask]] = {}  # job_id -> task_class

    @classmethod
    def register(cls, task_class: Type[BaseTask]) -> None:
        """注册任务类

        参数:
            task_class: 任务类，必须具有 _schedule_meta 属性

        异常:
            ValueError: 如果 job_id 已存在
        """
        meta = task_class._schedule_meta
        job_id = meta['job_id']

        if job_id in cls._tasks:
            raise ValueError(f'任务 ID 冲突: {job_id} (已存在 {cls._tasks[job_id].__name__})')

        cls._tasks[job_id] = task_class

    @classmethod
    def get_all(cls) -> Dict[str, Type[BaseTask]]:
        """获取所有已注册的任务

        返回:
            字典拷贝，避免外部修改
        """
        return cls._tasks.copy()

    @classmethod
    def get(cls, job_id: str) -> Optional[Type[BaseTask]]:
        """根据 job_id 获取任务类

        参数:
            job_id: 任务 ID

        返回:
            任务类，不存在时返回 None
        """
        return cls._tasks.get(job_id)
```

### 3.5 调度器更新

**文件**: `core/scheduler/scheduler.py`

主要变更：
- `__init__` 接收 config 参数
- `start()` 方法内部调用 `_register_tasks()`
- 新增 `_register_tasks()` 自动注册逻辑

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Callable, Dict, Optional
from core.config.logging import Logger
from core.scheduler.registry import TaskRegistry

class AICodeScheduler:
    """AI 代码统计定时任务调度器

    职责:
        - 从 TaskRegistry 自动发现任务
        - 应用 config.yaml 覆盖配置
        - 管理任务实例
        - 封装 APScheduler
    """

    def __init__(self, config: Dict):
        self.scheduler = BackgroundScheduler()
        self.config = config
        self.task_instances: Dict[str, BaseTask] = {}  # job_id -> task_instance
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
        """从 TaskRegistry 注册所有任务

        流程:
            1. 获取所有已注册的任务类
            2. 获取注解默认配置
            3. 应用 config.yaml 覆盖
            4. 创建任务实例
            5. 添加到 APScheduler
        """
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
            except ValueError as e:
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

    # stop, remove_job, get_job_status, get_all_jobs 方法保持不变
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

---

## 4. 配置设计

### 4.1 配置文件结构

`config.yaml` 中的 scheduler 节点：

```yaml
scheduler:
  enabled: true              # 是否启用调度器
  timezone: Asia/Shanghai    # 时区
  jobs:
    # 可选：覆盖注解中的默认配置
    daily_stats:
      cron: "0 10 * * *"     # 覆盖注解中的 0 2 * * *
      enabled: false         # 覆盖启用状态
    # dimensions_update 等其他任务使用注解默认值，无需配置
```

**配置规则**：
- `jobs` 是可选的，不存在时所有任务使用注解默认值
- 某个任务的配置不存在时使用注解默认值
- 不支持通过 config 新增任务（新任务必须创建类并使用注解）

### 4.2 配置加载器

**新建文件**: `core/config/scheduler.py`

```python
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

---

## 5. 错误处理

### 5.1 任务执行异常处理

| 场景 | 处理方式 |
|------|---------|
| 任务执行异常 (execute 抛出) | `run()` 捕获并记录日志，返回 `{success: False, error: str}` |
| before_execute 异常 | 同上，不会调用 execute |
| after_execute 异常 | 捕获并记录，不影响 execute 的返回值 |

### 5.2 调度器启动错误处理

| 场景 | 处理方式 |
|------|---------|
| Cron 表达式验证失败 | 跳过该任务，记录错误日志 |
| 任务 ID 冲突 | 元类注册时抛出 `ValueError`，启动失败 |
| 缺少必需的 config 配置 | 基类初始化时使用默认值或抛出异常 |

### 5.3 日志记录规范

```
[时间] [级别] task.{job_id} - 消息

示例:
2026-03-18 10:00:00 [INFO] task.daily_stats - 开始执行任务
2026-03-18 10:00:05 [INFO] task.daily_stats - 任务执行成功，耗时 5.2s
2026-03-18 10:00:05 [ERROR] task.daily_stats - 任务执行失败: connection timeout
```

---

## 6. 测试策略

### 6.1 单元测试

**测试目录结构**：
```
tests/unit/test_scheduler/
├── test_scheduled_decorator.py  # @scheduled 装饰器测试
├── test_base_task.py            # BaseTask 基类测试
├── test_task_meta.py            # TaskMeta 元类测试
├── test_task_registry.py        # TaskRegistry 注册表测试
└── test_scheduler.py            # 调度器集成测试
```

**关键测试用例**：

1. **`@scheduled` 装饰器测试**：
   - 验证 `_schedule_meta` 属性正确存储
   - 验证默认参数（name 使用类名，enabled 默认 True）
   - 验证参数覆盖

2. **`TaskMeta` 元类测试**：
   - 有注解的类自动注册
   - 无注解的类不注册
   - 重复注册 ID 冲突检测

3. **`BaseTask` 基类测试**：
   - `before_execute()` / `after_execute()` 钩子调用顺序
   - `execute()` 返回值正确传递
   - 异常捕获与日志记录
   - 日志记录器和数据库正确初始化

4. **`TaskRegistry` 注册表测试**：
   - `register()` 成功注册
   - `register()` 重复 ID 抛出异常
   - `get()` 返回正确任务类
   - `get_all()` 返回字典拷贝

5. **调度器集成测试**：
   - 配置覆盖功能
   - 禁用任务正确跳过
   - 任务实例正确创建和管理
   - Cron 表达式正确解析

### 6.2 集成测试

- 模拟完整的任务执行流程
- 验证配置覆盖后 cron 表达式正确应用
- 测试多任务并发执行场景
- 使用内存数据库测试数据聚合逻辑

### 6.3 现有任务迁移验证

- 确保 `DimensionsUpdateTask` 继承 `BaseTask` 后功能正常
- 验证数据聚合逻辑保持不变
- 验证数据库操作正常

---

## 7. 迁移计划

### 7.1 文件变更清单

**新增文件**：
```
core/scheduler/
├── base.py               # BaseTask 基类
├── task_meta.py          # TaskMeta 元类
├── registry.py           # TaskRegistry 注册表
└── scheduled.py          # @scheduled 装饰器

core/config/
└── scheduler.py          # 调度器配置加载器
```

**修改文件**：
- `core/scheduler/scheduler.py` - 简化任务注册逻辑
- `core/scheduler/stats_task.py` - 添加注解，继承基类
- `core/scheduler/dimensions_task.py` - 添加注解，继承基类
- `app.py` - 移除显式任务注册代码，简化启动逻辑
- `core/scheduler/__init__.py` - 导出新的公共接口

**可能需要更新的文档**：
- `CLAUDE.md` - 更新调度器部分说明
- `README.md` - 更新使用说明

### 7.2 DimensionsUpdateTask 迁移步骤

```python
# 新的导入
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta

# 添加注解
@scheduled(cron="0 3 * * *", job_id="dimensions_update", name="维度表统计更新", enabled=True)
class DimensionsUpdateTask(BaseTask, metaclass=TaskMeta):
    """仓库和作者维度统计更新任务"""

    # __init__ 不再需要，基类已提供

    # execute 方法保持核心逻辑不变
    def execute(self, context: Optional[Dict] = None) -> Dict:
        # ... 现有实现 ...

    # 可选：添加钩子
    def before_execute(self) -> Dict:
        context = super().before_execute()
        self.logger.info('开始执行维度统计更新任务')
        return context

    def after_execute(self, result: Dict, context: Dict) -> None:
        if result.get('success'):
            processed = result.get('processed', {})
            self.logger.info(f'维度统计更新完成: 仓库={processed.get("repos", 0)}, '
                           f'作者={processed.get("contributors", 0)}, '
                           f'关联={processed.get("relations", 0)}')
```

### 7.3 app.py 简化

**变更前**：
```python
# 需要显式导入和注册任务
from core.scheduler.stats_task import AICodeStatsTask
from core.scheduler.dimensions_task import DimensionsUpdateTask

scheduler = AICodeScheduler()
scheduler.start()

# 循环配置，手动选择任务类
for job_config in config.get('scheduler', {}).get('jobs', []):
    if job_config['id'] == 'dimensions_update':
        task = DimensionsUpdateTask(config)
    else:
        task = AICodeStatsTask(config)
    # ... 添加到调度器
```

**变更后**：
```python
# 只需创建并启动调度器
scheduler = AICodeScheduler(config)
scheduler.start()

# 任务会自动注册，无需显式代码
```

### 7.4 向后兼容性保证

- 不影响现有 API 路由
- 数据库 Schema 无需变更
- 外部调用者无感知
- 可通过 `config.yaml` 禁用重构后的任务
- 现有的 `AICodeScheduler` 公共方法保持不变

---

## 8. 使用示例

### 8.1 创建新任务

```python
from typing import Dict, Optional
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta

@scheduled(cron="0 1 * * 0", job_id="weekly_report", name="周报生成")
class WeeklyReportTask(BaseTask, metaclass=TaskMeta):
    """每周生成报告的任务"""

    def execute(self, context: Optional[Dict] = None) -> Dict:
        self.logger.info('开始生成周报')

        # 具体业务逻辑
        # ...

        return {
            'success': True,
            'message': '周报生成成功',
            'report_url': 'http://example.com/report.pdf'
        }
```

### 8.2 配置覆盖

```yaml
# config.yaml
scheduler:
  enabled: true
  jobs:
    # 默认每天凌晨2点运行，这里改为上午10点
    daily_stats:
      cron: "0 10 * * *"
    # 禁用某个任务
    weekly_report:
      enabled: false
```

### 8.3 运行流程

```bash
# 启动应用会自动发现和注册所有任务
python app.py

# 日志输出
2026-03-18 10:00:00 [INFO] scheduler - 调度器已启动
2026-03-18 10:00:00 [INFO] scheduler - 已注册任务: 每日统计 (daily_stats) at 0 10 * * *
2026-03-18 10:00:00 [INFO] scheduler - 已注册任务: 维度表统计更新 (dimensions_update) at 0 3 * * *
```

---

## 9. 优势分析

| 方面 | 重构前 | 重构后 |
|------|--------|--------|
| 任务注册 | 需要在 app.py 中显式注册 | 使用注解，元类自动注册 |
| 配置声明 | 依赖 config.yaml | 注解提供默认配置 |
| 配置覆盖 | 完全依赖 config.yaml | 注解默认 + config 覆盖 |
| 代码重复 | 每个任务自行管理日志/数据库 | 基类统一提供 |
| 扩展性 | 添加任务需修改多处代码 | 只需创建新任务类 |
| 可读性 | 配置和代码分离 | 任务配置和逻辑集中 |
| 调试 | 启动时才发现配置问题 | 类型检查时即发现问题 |

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 元类调试复杂 | 开发效率 | 提供清晰的文档和示例 |
| Cron 表达式错误 | 任务不执行 | 启动时验证，记录详细日志 |
| 向后兼容性问题 | 现有功能受影响 | 充分测试，保持接口不变 |
| ID 冲突 | 启动失败 | 元类检测并抛出明确错误 |
| 配置覆盖理解偏差 | 运行时行为不符 | 明确配置规则，提供示例 |

---

## 11. 后续优化方向

1. **支持更多调度类型**：如 `@interval` 装饰器支持间隔执行
2. **任务依赖**：支持声明任务间的依赖关系
3. **健康检查**：提供任务健康状态 API
4. **任务执行历史**：记录每次执行的结果和耗时
5. **动态热加载**：无需重启即可重新加载任务

---

## 12. 批准

- [x] 架构设计已验证
- [x] 组件设计已明确
- [x] 数据流已清晰
- [x] 错误处理已规划
- [x] 测试策略已制定
- [x] 迁移计划已明确
- [x] 风险已评估

**批准状态**: 已批准
**下一步**: 创建详细实现计划
