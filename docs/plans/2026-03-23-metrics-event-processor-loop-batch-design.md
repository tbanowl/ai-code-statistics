# Metrics 事件处理任务循环批处理优化设计

**日期**: 2026-03-23
**作者**: Claude Code
**版本**: 1.0

## 概述

将 `MetricsEventProcessorTask` 从单批次处理改为循环批处理模式，直到所有待处理数据都被处理为止。同时增强并发安全性，防止任务超时导致的数据卡死问题。

## 背景

当前实现每 2 分钟执行一次，每次处理一批（默认 100 条）记录后任务即结束。如果积压数据量大，处理进度缓慢。

**目标**：
- 单次任务执行循环处理直到没有待处理数据
- 增强并发安全性，防止重复处理
- 支持超时恢复机制

## 架构设计

### 核心逻辑

使用 `id` 游标分页实现批次递进：

```python
last_id = None
while True:
    # 获取下一批记录（id > last_id）
    batch = db.get_pending_raw_records(limit=batch_size, last_id=last_id)
    if not batch:
        break

    for record in batch:
        # 处理记录
        last_id = record['id']
```

### 并发安全

#### 超时机制

检查 `task_executions` 表中的 running/pending 状态任务：

| 状态 | 处理方式 |
|------|----------|
| 运行中 + 未超时 | 跳过本次执行 |
| 运行中 + 超时 | 标记失败，恢复数据，继续执行 |
| 无运行中任务 | 正常执行 |

超时判断规则：

```
if now_ts() - task.started_at > timeout_minutes * 60 * 1000:
    # 超时，恢复数据
```

#### 数据恢复

超时后自动执行：

1. 将 `metrics_events_raw.extract=2` 的记录恢复为 `extract=0`
2. 将 `task_executions` 状态标记为 `failed`

## 数据库改动

### MetricsDatabase

#### 新增方法

`has_extracting_records() -> bool`（废弃，改用 task_executions）

`reset_stuck_extracting_records() -> int`

```
将所有 extract=2（处理中）的记录重置为 extract=0（未处理）
用于任务超时后的恢复
返回重置的记录数
```

#### 修改方法

`get_pending_raw_records(limit=100, last_id=None)`

新增 `last_id` 参数用于游标分页。

### SchedulerDatabase

#### 新增方法

`has_running_task(job_id, timeout_minutes=10) -> Optional[Dict]`

```
检查是否有正在运行且未超时的任务

Returns:
    None - 没有运行中的任务，可以开始执行
    Dict - 正在运行的任务信息
```

## 任务层改动

### MetricsEventProcessorTask.execute()

修改要点：

1. 超时配置（默认 10 分钟，可配置）
2. 检查 `task_executions` 表判断是否跳过
3. 恢复超时任务卡住的数据
4. 循环批次处理直到 `pending_records` 为空
5. 返回统计信息包含批次数量

### 配置

```yaml
scheduler:
  jobs:
    metrics_event_processor:
      batch_size: 100           # 每批处理的记录数
      timeout_minutes: 10       # 任务超时阈值（分钟）
```

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 单条记录处理失败 | 标记 `extract=3`，记录日志，继续处理下一条 |
| 任务超时 | 下次执行自动恢复 `extract=2` 的记录 |
| 进程异常退出 | 下次执行检测超时，自动恢复并继续 |
| 并发重复执行 | 通过 `task_executions` 表防止 |

## 数据流

```
定时触发 (每 2 分钟)
    │
    ▼
检查 task_executions 是否有 running 任务
    │
    ├─ 超时/无任务 ──> 恢复卡住的 raw 记录 ──> 继续
    │
    └─ 正在运行 ──> 跳过本次执行
                        │
                        ▼
            循环批次处理 (while batch 非空)
                        │
                        ▼
            查询 extract=0 的记录 (使用 id 游标)
                        │
                        ▼
            迭代处理: 0 → 2 → 1/3
                        │
                        ▼
                    继续下一批
```

## 影响范围

| 文件 | 改动类型 |
|------|----------|
| `core/database/metrics_db.py` | 新增 1 方法，修改 1 方法 |
| `core/database/scheduler_db.py` | 新增 1 方法 |
| `core/scheduler/tasks/metrics_event_processor_task.py` | 修改 execute 方法 |
| `config.yaml` | 可选配置 |

## 测试策略

### 单元测试
- `get_pending_raw_records` 测试 id 游标分页
- `has_running_task` 测试超时判断
- `reset_stuck_extracting_records` 测试状态恢复

### 集成测试
- 正常流程：小批量数据循环处理
- 并发场景：多实例启动，只有一个执行
- 超时恢复：模拟超时，验证下次执行恢复
- 大数据量：验证循环处理大量积压数据

## 迁移路径

无需 DDL 变更，纯代码改动。部署流程：

1. 部署新代码
2. 可选：手动清理遗留的超时任务（调用 `reset_running_executions_for_testing()`）

## 参考资料

- XID 时间戳排序特性
- APScheduler 并发处理模式
- `task_executions` 表结构
