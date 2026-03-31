# APScheduler JobStore 持久化设计

## 概述

为基于 APScheduler 的调度器添加 JobStore 持久化能力，使用 SQLAlchemyJobStore 将任务定义和调度状态持久化到数据库，实现应用重启后任务自动恢复和调度状态保留。

## 背景

### 当前状态

项目使用 APScheduler 3.11.2 作为定时任务调度器，通过 `@scheduled` 装饰器定义任务，使用 `BackgroundScheduler` 运行。当前没有配置 JobStore，所有调度状态仅存在于内存中，应用重启后任务需要重新注册。

### 问题

- 应用重启后任务需要重新注册，调度器无法恢复上次的状态
- 缺少任务下次运行时间的持久化能力
- 无法追踪任务的调度历史

## 设计目标

1. **任务定义持久化** - 应用重启后自动恢复所有已注册任务
2. **调度状态保留** - 保留任务的下次运行时间、触发器状态
3. **向后兼容** - 不影响现有的 task_executions 表和业务逻辑
4. **数据库复用** - 使用与业务相同的数据库（SQLite/PostgreSQL）
5. **配置化** - 通过 config.yaml 可配置 JobStore 行为

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Application (Flask)                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              AICodeScheduler                           │  │
│  │  ┌─────────────┐         ┌─────────────────────────┐  │  │
│  │  │ JobStore    │         │ Task Executions (业务)  │  │  │
│  │  │ (调度状态)  │         │  (执行历史/监控)         │  │  │
│  │  └──────┬──────┘         └─────────────────────────┘  │  │
│  │         │                                                  │  │
│  │         ├─► apscheduler_jobs (任务定义、下次运行时间)      │  │
│  │         └─► task_executions (执行记录、错误堆栈)           │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  SchedulerDatabase                     │  │
│  │                    (业务监控)                          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 职责划分

**apscheduler_jobs 表：**
- 任务定义（trigger, func, args）
- 下次运行时间
- 调度器内部状态

**task_executions 表（现有）：**
- 每次执行的历史记录
- 执行状态（pending/running/completed/failed）
- 执行耗时和错误信息

### 核心组件

#### 1. AICodeScheduler 初始化改造

修改 `core/scheduler/scheduler.py` 中的 `__init__` 方法：

```python
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

class AICodeScheduler:
    def __init__(self, config: Dict):
        # 配置 JobStore
        engine = self._get_engine_from_db()
        jobstores = {
            'default': SQLAlchemyJobStore(engine=engine)
        }

        # 配置默认任务行为
        job_defaults = config.get('scheduler', {}).get('job_defaults', {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300
        })

        # 创建调度器时传入 jobstores 和 job_defaults
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            job_defaults=job_defaults,
            timezone=config.get('scheduler', {}).get('timezone', 'Asia/Shanghai')
        )
        # ... 其余初始化代码
```

#### 2. 配置扩展 (`config.yaml`)

```yaml
scheduler:
  enabled: true
  timezone: Asia/Shanghai

  # JobStore 配置
  jobstore:
    type: sqlalchemy
    # tablename: apscheduler_jobs  # 可选，默认为 apscheduler_jobs

  # 任务默认行为配置
  job_defaults:
    coalesce: true              # 合并错过的执行
    max_instances: 1            # 每个任务最多同时运行 1 个实例
    misfire_grace_time: 300    # 错过执行的宽限时间（秒）

  jobs:
    daily_aggregation:
      enabled: true
      cron: "0 2 * * *"
    metrics_event_processor:
      enabled: true
      cron: "*/2 * * * *"
```

#### 3. 数据库结构

**apscheduler_jobs 表（APScheduler 自动创建）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(191) | 任务唯一标识 |
| next_run_time | datetime | 下次运行时间 |
| job_state | BLOB | 任务序列化状态 |

**索引：**
- `idx_apscheduler_jobs_next_run_time` - 按下次运行时间查询

### 数据流

#### 启动流程

```
1. 初始化 SchedulerDatabase ┐
2. 创建 AICodeScheduler    │
3. 配置 SQLAlchemyJobStore  ├─► 使用现有 engine
4. Scheduler.start()        │
5. _register_tasks()        ┘
   └─► 从 apscheduler_jobs 加载现有任务
   └─► 扫描 @scheduled 注解
   └─► 新任务写入 JobStore
```

#### 运行时流程

```
任务触发
  ├─► 执行前：创建 task_executions 记录（现有）
  ├─► 执行：运行任务逻辑
  ├─► 执行后：更新 task_executions 状态（现有）
  └─► JobStore 自动更新 next_run_time
```

#### 重启恢复流程

```
应用重启
  ├─► JobStore 从数据库恢复任务
  ├─► 重新扫描 @scheduled 注解
  ├─► 对比任务定义
  ├─► 新任务：添加到 JobStore
  ├─► 修改的任务：更新 JobStore
  └─► 删除的任务：从 JobStore 移除（可选）
```

## SQL 脚本

### SQLite 脚本

APScheduler 支持自动建表，但提供 DDL 供文档化和审计：

```sql
CREATE TABLE IF NOT EXISTS apscheduler_jobs (
    id VARCHAR(191) NOT NULL,
    next_run_time REAL,
    job_state BLOB NOT NULL,
    PRIMARY KEY (id)
);
```

### PostgreSQL 脚本

```sql
CREATE TABLE IF NOT EXISTS apscheduler_jobs (
    id VARCHAR(191) NOT NULL,
    next_run_time TIMESTAMP WITH TIME ZONE,
    job_state BYTEA NOT NULL,
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_apscheduler_jobs_next_run_time
ON apscheduler_jobs (next_run_time);
```

## 错误处理

1. **JobStore 连接失败**
   - 降级到内存模式（移除 jobstores 配置）
   - 记录警告日志

2. **数据库表不存在**
   - APScheduler 支持自动创建
   - 提供手动 DDL 脚本供审计

3. **任务注册冲突**
   - 默认行为：更新现有任务
   - 可配置：跳过或抛出异常

## 测试策略

### 单元测试

- JobStore 初始化验证
- 配置解析逻辑
- Engine 复用验证

### 集成测试

- 任务持久化和恢复
- 重启后调度状态保留
- 手动触发后的 next_run_time 更新

### 数据库兼容性测试

- SQLite 表结构创建和操作
- PostgreSQL 表结构创建和操作

## 迁移策略

1. 开发环境验证
2. 测试环境部署
3. 生产环境灰度发布

### 兼容性

- 向后兼容：现有数据和功能不受影响
- 可选特性：配置 `scheduler.jobstore.type` 可禁用持久化

## 实施计划

1. 修改 `AICodeScheduler` 构造函数
2. 添加配置支持
3. 创建 SQL 脚本
4. 编写测试
5. 文档更新

## 参考资料

- APScheduler 文档: https://apscheduler.readthedocs.io/
- SQLAlchemy 文档: https://docs.sqlalchemy.org/
