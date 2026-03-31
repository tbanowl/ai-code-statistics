# Metrics 事件异步处理设计

**日期**：2026-03-23
**类型**：架构优化
**状态**：已批准

## 概述

将 Metrics 事件处理从同步模式改为异步队列模式。客户端上传数据后仅保存原始数据，由定时任务批量解析并写入各事件表。

## 背景与动机

当前 `metrics_service.py` 在 API 请求时同步解析 Metrics 事件，存在以下问题：
- 处理时间不确定，影响 API 响应速度
- 大批量数据可能导致请求超时
- 错误处理不够灵活

改为异步处理后：
- API 响应更快
- 可以更好地控制处理节奏
- 错误更易于追踪和重试

## 架构设计

### 当前架构

```
客户端上传 → /worker/metrics/upload
              ↓
        MetricsService.process_metrics_batch() [同步处理]
              ↓
        ┌─────────────────────────────────────┐
        │ metrics_events_raw (extract=1)      │
        │ metrics_events_committed           │
        │ metrics_events_checkpoint          │
        │ metrics_events_agent_usage         │
        │ metrics_events_install_hooks       │
        └─────────────────────────────────────┘
              ↓
        DailyAggregationTask [每天凌晨2点]
              ↓
        stats_daily_stats
```

### 目标架构

```
客户端上传 → /worker/metrics/upload
              ↓
        ┌─────────────────────────────────────┐
        │ metrics_events_raw (extract=0)     │ ← 仅存储原始数据
        └─────────────────────────────────────┘
              ↓
        MetricsEventProcessorTask [每1-2分钟]
              ↓
        ├─ 提取成功 → extract=1
        │     ├─ metrics_events_committed
        │     ├─ metrics_events_checkpoint
        │     ├─ metrics_events_agent_usage
        │     └─ metrics_events_install_hooks
        │
        └─ 提取失败 → extract=3
              └─ metrics_event_errors
```

### 核心组件

1. **MetricsEventProcessorTask** - 定时处理任务
2. **MetricsService（重构）** - 保留事件解析逻辑，移除同步处理
3. **MetricsEventErrors** - 新增错误记录表
4. **API 简化** - upload 端点仅保存原始数据

## 数据库变更

### 新增表：`metrics_event_errors`

记录事件解析失败的详细信息：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String(20) | 主键，XID |
| `raw_id` | String(20) | 原始 batch ID，外键关联 `metrics_events_raw.id` |
| `event_index` | Integer | 事件在 batch 中的索引位置 |
| `event_data_raw` | Text | 失败的原始事件数据（JSON） |
| `error_message` | Text | 错误消息 |
| `payload_snippet` | Text | 原始 batch 的 payload 片段（用于调试） |
| `retry_count` | Integer | 重试次数，默认 0 |
| `last_retry_at` | BigInteger | 最后重试时间戳（毫秒） |
| `created_at` | BigInteger | 创建时间戳 |

### 约束

- `raw_id` 字段添加外键约束
- 添加索引：`(raw_id, event_index)`

### `metrics_events_raw` 的 extract 字段

| 值 | 说明 |
|----|------|
| 0 | 未提取（默认） |
| 1 | 提取成功 |
| 2 | 提取中（处理中） |
| 3 | 提取失败 |

## 定时任务设计

### 新增任务：`MetricsEventProcessorTask`

**任务配置**：
- **Cron 表达式**：`*/2 * * * *`（每 2 分钟执行一次）
- **Job ID**：`metrics_event_processor`
- **名称**：Metrics 事件处理任务

### 执行流程

1. 查询未处理的 raw 记录（`WHERE extract=0 ORDER BY received_at ASC LIMIT 100`）
2. 对每条 raw 记录：
   - 标记 `extract=2`
   - 解析 payload_json
   - 提取成功：写入各事件表，标记 `extract=1`
   - 提取失败：写入 `metrics_event_errors`，标记 `extract=3`
3. 返回统计信息

## API 修改

### 新的 API 响应格式

```json
{
  "success": true,
  "raw_id": "abc123xyz",
  "event_count": 5,
  "message": "Metrics raw data received, processing scheduled",
  "received_at": 1712345678000
}
```

### `MetricsService` 方法调整

```python
# 新方法：由定时任务调用
def process_raw_event(self, raw_id: str, payload_json: str) -> Dict:
    """处理单个 raw 记录，返回处理结果"""
```

## 错误处理策略

| 场景 | extract 状态 | 是否记录 errors 表 |
|------|-------------|------------------|
| JSON 解码失败 | 3 | 是 |
| 事件类型未知 | 1 | 是 |
| 单个事件解析失败 | 1 | 是 |
| 全部事件成功 | 1 | 否 |

### 日志级别

- **Info**：处理开始/结束、统计信息
- **Warning**：单个事件解析失败、未知事件类型
- **Error**：整个 batch 解析失败、数据库错误

## 配置

### `config.yaml` 新增配置

```yaml
scheduler:
  enabled: true
  jobs:
    metrics_event_processor:
      cron: "*/2 * * * *"
      enabled: true
      batch_size: 100
```

### 可选监控配置

```yaml
scheduler:
  metrics_event_processor:
    max_processing_time_ms: 30000
    alert_on_batch_failure: true
```

## 实施计划（待 writing-plans 技能细化）

1. 创建 `metrics_event_errors` 表
2. 创建 `MetricsEventProcessorTask` 定时任务
3. 重构 `MetricsService.process_raw_event()` 方法
4. 简化 `/worker/metrics/upload` API 端点
5. 更新配置文件
6. 测试验证

## 影响评估

### 兼容性

- 现有的 `metrics_events_raw` 表结构兼容
- `extract` 字段已存在，无需修改
- 各事件表结构不变

### 性能

- API 响应时间显著降低（仅需写入原始数据）
- 定时任务批量处理，数据库操作更高效

### 风险

- 低风险：修改主要集中在新增逻辑，现有数据不受影响
- 可以逐步迁移：新数据使用新流程，旧数据保持原有 extract=1 状态
