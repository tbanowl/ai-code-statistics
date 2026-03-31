# 定时任务手动执行功能设计文档

**日期**: 2026-03-19
**状态**: 已批准

## 概述

为 `api/routes/scheduler.py` 添加手动触发定时任务的功能，支持异步执行、并发控制和执行历史查询。

## 需求

- 支持通过 API 手动触发指定 `job_id` 的任务
- 异步执行模式，立即返回 execution_id
- 禁止同一任务并发执行
- 查询执行历史和详细结果
- 支持多种数据库（优先 SQLite，确保可移植性）

## API 接口

### 1. 手动触发任务

**端点**: `POST /api/v1/scheduler/jobs/<job_id>/trigger`

**参数**:
- `job_id` (路径参数): 任务 ID

**响应** (200):
```json
{
  "success": true,
  "data": {
    "execution_id": "123",
    "status": "pending"
  }
}
```

**错误**:
- `404`: 任务不存在
- `409`: 任务正在执行中

### 2. 获取执行历史

**端点**: `GET /api/v1/scheduler/jobs/<job_id>/executions`

**查询参数**:
- `limit`: 返回记录数（默认 10，最大 100）
- `status`: 过滤状态（pending/running/completed/failed）

**响应** (200):
```json
{
  "success": true,
  "data": {
    "executions": [...]
  }
}
```

### 3. 获取执行详情

**端点**: `GET /api/v1/scheduler/jobs/<job_id>/executions/<execution_id>`

**响应** (200):
```json
{
  "success": true,
  "data": {
    "id": "123",
    "job_id": "daily_stats",
    "status": "completed",
    "started_at": "2026-03-19T10:00:00Z",
    "finished_at": "2026-03-19T10:01:30Z",
    "execution_time_ms": 90000,
    "error_message": null
  }
}
```

## 数据库设计

### 表: task_executions

```sql
CREATE TABLE task_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at DATETIME,
    finished_at DATETIME,
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_executions_job_id ON task_executions(job_id);
CREATE INDEX idx_task_executions_created_at ON task_executions(created_at);
```

## 并发控制

触发前检查是否存在同一 `job_id` 的 `status IN ('pending', 'running')` 记录。
如果存在，返回 409 Conflict。

## 执行流程

1. API 收到触发请求
2. 检查并发约束
3. 创建 execution 记录（status = pending）
4. 调用 `APScheduler.trigger_job()` 触发任务
5. 任务通过 `before_execute` 更新为 running
6. 任务完成后通过 `after_execute` 更新结果
7. 异常时捕获并更新为 failed

## 历史记录清理

通过后台任务定期清理旧记录：
- 保留最近 100 条记录
- 或保留最近 30 天的记录

## 实现要点

- 使用 `APScheduler.trigger_job()` 而非直接调用 `task_instance.run()`
- 扩展 `BaseTask` 添加 execution_id 传递机制
- 在 `database.py` 添加 task_executions 相关方法
- 更新 schema SQL 文件
