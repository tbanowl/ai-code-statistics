# Metrics 事件异步处理实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Metrics 事件处理从同步模式改为异步队列模式，客户端上传后仅保存原始数据，由定时任务批量处理。

**Architecture:** 客户端上传 → metrics_events_raw(extract=0) → MetricsEventProcessorTask(每2分钟) → 各事件表 + metrics_event_errors

**Tech Stack:** Flask, SQLAlchemy, APScheduler, Python 3.x

---

## Task 1: 创建错误事件表模型

**Files:**
- Modify: `core/database/models.py`

**Step 1: 添加 MetricsEventErrors 模型定义**

在文件中 `MetricsEventsInstallHooks` 类后、`# ============================================================================# CAS 对象表` 行前添加：

```python
class MetricsEventErrors(ModelBase):
    """事件解析错误记录表"""

    __tablename__ = "metrics_event_errors"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    raw_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("metrics_events_raw.id", ondelete="CASCADE")
    )
    event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    event_data_raw: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_snippet: Mapped[str] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_retry_at: Mapped[int] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)

    # 添加索引
    __table_args__ = (
        Index("idx_raw_event_index", "raw_id", "event_index"),
    )
```

同时在文件顶部的 import 中添加 `Index`：

```python
from sqlalchemy import String, BigInteger, Integer, Text, ForeignKey, JSON, Numeric, Index
```

**Step 2: 创建数据库迁移 SQL**

创建文件 `sql/metrics_event_errors_table.sql`：

```sql
-- 事件解析错误记录表
CREATE TABLE IF NOT EXISTS metrics_event_errors (
    id TEXT PRIMARY KEY,
    raw_id TEXT NOT NULL,
    event_index INTEGER NOT NULL,
    event_data_raw TEXT NOT NULL,
    error_message TEXT NOT NULL,
    payload_snippet TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_at INTEGER,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (raw_id) REFERENCES metrics_events_raw(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_raw_event_index ON metrics_event_errors(raw_id, event_index);
```

**Step 3: 运行迁移**

```bash
sqlite3 data/ai_stats.db < sql/metrics_event_errors_table.sql
```

预期输出：无错误（数据库表已创建）

**Step 4: Commit**

```bash
git add core/database/models.py sql/metrics_event_errors_table.sql
git commit -m "feat: 添加 metrics_event_errors 错误记录表

- 新增 MetricsEventErrors 模型
- 记录事件解析失败详情
- 添加 raw_id 和 event_index 索引"
```

---

## Task 2: 扩展 MetricsDatabase 错误处理方法

**Files:**
- Modify: `core/database/metrics_db.py`

**Step 1: 添加 import**

在文件顶部 import 列表中添加：

```python
from .models import (
    MetricsEventsRaw,
    MetricsEventsCommitted,
    MetricsEventsCheckpoint,
    MetricsEventsAgentUsage,
    MetricsEventsInstallHooks,
    MetricsEventErrors,  # 新增
    CasObjects,
)
```

**Step 2: 添加查询未处理原始记录的方法**

在 `save_metrics_raw` 方法后、`# ========== Committed 事件 ==========` 行前添加：

```python
    def get_pending_raw_records(self, limit: int = 100) -> List[Dict]:
        """
        获取待处理的原始记录
        按照 received_at 降序排列（最旧的优先）
        """
        with session_scope(self.engine) as session:
            results = session.query(MetricsEventsRaw)\
                .filter(MetricsEventsRaw.extract == 0)\
                .order_by(MetricsEventsRaw.received_at.asc())\
                .limit(limit)\
                .all()
            return [{'id': r.id, 'payload_json': r.payload_json, 'event_count': r.event_count} for r in results]

    def mark_raw_extracting(self, raw_id: str) -> bool:
        """标记原始记录为提取中"""
        with session_scope(self.engine) as session:
            record = session.query(MetricsEventsRaw).filter(MetricsEventsRaw.id == raw_id).first()
            if record and record.extract == 0:
                record.extract = 2  # 提取中
                return True
            return False

    def mark_raw_extracted(self, raw_id: str, success: bool = True) -> bool:
        """标记原始记录提取状态"""
        with session_scope(self.engine) as session:
            record = session.query(MetricsEventsRaw).filter(MetricsEventsRaw.id == raw_id).first()
            if record:
                record.extract = 1 if success else 3  # 1=成功, 3=失败
                return True
            return False
```

**Step 3: 添加保存错误记录的方法**

在文件最末尾（最后一个辅助查询方法后）添加：

```python
    # ========== 错误处理 ==========

    def save_event_error(self, raw_id: str, event_index: int, event_data_raw: str,
                        error_message: str, payload_snippet: str = None) -> str:
        """保存事件错误记录"""
        with session_scope(self.engine) as session:
            record = MetricsEventErrors(
                raw_id=raw_id,
                event_index=event_index,
                event_data_raw=event_data_raw,
                error_message=error_message,
                payload_snippet=payload_snippet[:1024] if payload_snippet else None
            )
            session.add(record)
            session.flush()
            return record.id

    def get_error_events_by_raw_id(self, raw_id: str) -> List[Dict]:
        """获取某个 raw 记录的所有错误事件"""
        with session_scope(self.engine) as session:
            results = session.query(MetricsEventErrors)\
                .filter(MetricsEventErrors.raw_id == raw_id)\
                .order_by(MetricsEventErrors.event_index)\
                .all()
            return [r.to_dict() for r in results]
```

**Step 4: Commit**

```bash
git add core/database/metrics_db.py
git commit -m "feat: 扩展 MetricsDatabase 支持异步处理

- 添加 get_pending_raw_records 查询待处理记录
- 添加 mark_raw_extracting/mark_raw_extracted 状态更新
- 添加 save_event_error/get_error_events_by_raw_id 错误记录方法"
```

---

## Task 3: 创建 MetricsEventProcessorTask 定时任务

**Files:**
- Create: `core/scheduler/tasks/metrics_event_processor_task.py`

**Step 1: 创建任务文件**

```python
"""Metrics 事件处理定时任务"""

import json
from typing import Dict, Optional
from core.scheduler.tasks.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.database import MetricsDatabase
from core.services.metrics_service import MetricsService
from core.config.logging import Logger


@scheduled(cron="*/2 * * * *", job_id="metrics_event_processor", name="Metrics事件处理")
class MetricsEventProcessorTask(BaseTask):
    """Metrics 事件处理任务 - 从原始数据表提取事件到各事件表"""

    def execute(self, context: Optional[Dict] = None) -> Dict:
        self.logger.info("开始执行 Metrics 事件处理任务")

        # 获取批处理大小配置
        batch_size = self.config.get("scheduler", {})\
            .get("jobs", {})\
            .get("metrics_event_processor", {})\
            .get("batch_size", 100)

        # 查询待处理的原始记录
        db = MetricsDatabase()
        pending_records = db.get_pending_raw_records(limit=batch_size)

        if not pending_records:
            self.logger.info("没有待处理的 Metrics 原始记录")
            return {"success": True, "processed": 0}

        self.logger.info(f"找到 {len(pending_records)} 个待处理的原始记录")

        # 处理统计
        stats = {
            "total": len(pending_records),
            "successful": 0,
            "failed": 0,
            "total_events": 0,
            "error_events": 0
        }

        service = MetricsService()

        # 处理每条原始记录
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
                    self.logger.info(
                        f"处理成功: raw_id={raw_id}, "
                        f"events={result.get('events_processed')}, "
                        f"errors={result.get('error_count')}"
                    )
                else:
                    db.mark_raw_extracted(raw_id, success=False)
                    stats["failed"] += 1
                    self.logger.error(f"处理失败: raw_id={raw_id}, error={result.get('error')}")

            except Exception as e:
                db.mark_raw_extracted(raw_id, success=False)
                stats["failed"] += 1
                self.logger.error(f"处理异常: raw_id={raw_id}, error={str(e)}", exc_info=True)

        self.logger.info(
            f"Metrics 事件处理完成: "
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
            "error_events": stats["error_events"]
        }
```

**Step 2: Commit**

```bash
git add core/scheduler/tasks/metrics_event_processor_task.py
git commit -m "feat: 添加 MetricsEventProcessorTask 定时任务

- 每 2 分钟执行一次
- 批量处理待提取的原始记录
- 统计处理结果并记录日志"
```

---

## Task 4: 重构 MetricsService 添加异步处理方法

**Files:**
- Modify: `core/services/metrics_service.py`

**Step 1: 添加 process_raw_event 方法**

在 `_get_u64_array` 方法后、文件末尾添加：

```python
    def process_raw_event(self, raw_id: str, payload_json: str) -> Dict:
        """
        处理单个原始记录（由定时任务调用）

        返回: {
            "success": True/False,
            "events_processed": int,
            "error_count": int,
            "error": str  # 仅在整体失败时
        }
        """
        try:
            # 解析 payload_json
            payload = json.loads(payload_json)
            events = payload.get("events", [])

            if not events:
                return {
                    "success": True,
                    "events_processed": 0,
                    "error_count": 0
                }

            # 处理每个事件
            events_processed = 0
            error_count = 0
            errors = []

            for index, event in enumerate(events):
                try:
                    self._process_single_event(event, raw_id)
                    events_processed += 1
                except Exception as e:
                    self.logger.warning(
                        f"处理事件 {index} 失败: raw_id={raw_id}, event data: {event}",
                        e
                    )
                    error_count += 1

                    # 记录错误到错误表
                    self._save_event_error(
                        raw_id, index, event, str(e),
                        payload_snippet=payload_json[:1024]
                    )

            return {
                "success": True,
                "events_processed": events_processed,
                "error_count": error_count
            }

        except json.JSONDecodeError as e:
            # JSON 解码失败，记录到错误表
            self._save_event_error(
                raw_id, -1, f"Invalid JSON: {payload_json[:200]}",
                f"JSON decode error: {str(e)}",
                payload_snippet=payload_json[:1024]
            )
            return {
                "success": False,
                "events_processed": 0,
                "error_count": 1,
                "error": f"JSON decode error: {str(e)}"
            }
        except Exception as e:
            self.logger.error(f"处理原始记录失败: raw_id={raw_id}", exc_info=True)
            return {
                "success": False,
                "events_processed": 0,
                "error_count": 0,
                "error": str(e)
            }

    def _save_event_error(self, raw_id: str, event_index: int,
                          event_data, error_message: str,
                          payload_snippet: str = None):
        """保存事件错误到数据库"""
        try:
            event_data_json = json.dumps(event_data) if isinstance(event_data, dict) else str(event_data)
            self.database.save_event_error(
                raw_id=raw_id,
                event_index=event_index,
                event_data_raw=event_data_json,
                error_message=error_message,
                payload_snippet=payload_snippet
            )
        except Exception as e:
            self.logger.error(f"保存事件错误失败: {e}", exc_info=True)
```

**Step 2: Commit**

```bash
git add core/services/metrics_service.py
git commit -m "refactor: 添加 MetricsService.process_raw_event 方法

- 支持从 raw_id 和 payload_json 处理事件
- 记录失败事件到 metrics_event_errors 表
- 返回详细的处理统计信息"
```

---

## Task 5: 简化 /worker/metrics/upload API

**Files:**
- Modify: `api/routes/git_ai_worker.py`

**Step 1: 修改 metrics_upload 函数**

完全替换 `metrics_upload` 函数（第 17-47 行）：

```python
@metrics_bp.route('/upload', methods=['POST'])
# @auth_required
def metrics_upload():
    """上传 metrics 数据 - 仅保存原始数据，由定时任务处理"""
    from core.services.metrics_service import MetricsService
    import time

    try:
        data = request.get_json()

        # 验证版本
        version = data.get('v', 1)
        if version != 1:
            return jsonify({
                'success': False,
                'error': f'Unsupported version: {version}'
            }), 400

        events = data.get('events', [])
        if not events:
            return jsonify({
                'success': True,
                'event_count': 0,
                'message': 'No events to process'
            }), 200

        # 仅保存原始数据到 metrics_events_raw
        # extract=0 表示未提取，由定时任务处理
        from core.database import MetricsDatabase

        db = MetricsDatabase()
        received_at = int(time.time() * 1000)
        payload_json = json.dumps(data)

        raw_id = db.save_metrics_raw(
            version=version,
            event_count=len(events),
            payload_json=payload_json,
            received_at=received_at
        )

        logger.info(f'Metrics raw data received: raw_id={raw_id}, events={len(events)}')

        return jsonify({
            'success': True,
            'raw_id': raw_id,
            'event_count': len(events),
            'message': 'Metrics raw data received, processing scheduled',
            'received_at': received_at
        }), 200

    except Exception as e:
        logger.error(f'Metrics upload error: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

**注意**：需要在文件顶部添加 `import json`（如果没有的话）

**Step 2: Commit**

```bash
git add api/routes/git_ai_worker.py
git commit -m "refactor: 简化 Metrics upload API

- 仅保存原始数据到 metrics_events_raw
- 返回 raw_id 和基本信息
- 由定时任务异步处理事件"
```

---

## Task 6: 更新配置文件

**Files:**
- Modify: `config.yaml`

**Step 1: 添加 metrics_event_processor 任务配置**

在 `scheduler.jobs` 部分添加 `metrics_event_processor` 配置：

```yaml
scheduler:
  enabled: true
  timezone: Asia/Shanghai
  jobs:
    daily_aggregation:
      enabled: true
      cron: "0 2 * * *"
    # Metrics 事件处理任务
    metrics_event_processor:
      enabled: true
      cron: "*/2 * * * *"
      batch_size: 100
```

**Step 2: Commit**

```bash
git add config.yaml
git commit -m "config: 添加 metrics_event_processor 任务配置

- 每 2 分钟执行一次
- 批量大小默认 100
- 可通过配置覆盖"
```

---

## Task 7: 验证和文档更新

**Step 1: 重启应用验证**

```bash
python app.py
```

预期输出：
- 应用正常启动
- 日志显示注册任务：`注册任务: Metrics事件处理 (metrics_event_processor) at */2 * * * *`

**Step 2: 等待 2 分钟后检查日志**

预期日志：
```
[INFO] 开始执行 Metrics 事件处理任务
[INFO] 找到 0 个待处理的原始记录  # 如果没有数据
或
[INFO] 找到 X 个待处理的原始记录
[INFO] 处理成功: raw_id=abc123, events=5, errors=0
[INFO] Metrics 事件处理完成: 总计=X, 成功=Y, 失败=Z
```

**Step 3: 测试 API 上传**

```bash
curl -X POST http://localhost:8888/worker/metrics/upload \
  -H "Content-Type: application/json" \
  -d '{
    "v": 1,
    "events": [
      {
        "e": 1,
        "t": 1712345678,
        "v": {"0": 10},
        "a": {"0": "1.0.0", "1": "https://github.com/test/repo"}
      }
    ]
  }'
```

预期响应：
```json
{
  "success": true,
  "raw_id": "abc123xyz",
  "event_count": 1,
  "message": "Metrics raw data received, processing scheduled",
  "received_at": 1712345678000
}
```

**Step 4: 等待 2 分钟后检查数据库**

```bash
sqlite3 data/ai_stats.db "SELECT id, extract, event_count FROM metrics_events_raw WHERE received_at > $(date +%s000) ORDER BY received_at DESC LIMIT 5;"
```

预期输出：`extract=1` 表示已处理

**Step 5: 检查事件数据**

```bash
sqlite3 data/ai_stats.db "SELECT COUNT(*) FROM metrics_events_committed WHERE raw_id IN (SELECT id FROM metrics_events_raw WHERE extract=1);"
```

预期输出：事件数量 > 0

**Step 6: 更新 CLAUDE.md**

在 CLAUDE.md 的 `## 核心架构 -> 业务服务层` 部分更新 MetricsService 说明：

```markdown
- `MetricsService` - Metrics 数据处理服务（异步模式）
  - `process_raw_event()` - 处理单个原始记录（由定时任务调用）
  - `_process_single_event()` - 解析单个事件
```

新增定时任务描述：

```markdown
### 调度器 (`core/scheduler/`)
定时任务系统...

**现有任务：**
- `MetricsEventProcessorTask` - 每 2 分钟执行，处理原始 Metrics 数据
- `DailyAggregationTask` - 每天凌晨 2 点执行，聚合每日统计
```

**Step 7: Commit 文档更新**

```bash
git add .claude/CLAUDE.md CLAUDE.md
git commit -m "docs: 更新文档反映异步处理架构

- 更新 MetricsService 说明
- 添加 MetricsEventProcessorTask 任务描述
- 更新数据流图"
```

---

## Task 8: 可选 - 验证错误处理

**Step 1: 测试无效数据上传**

```bash
curl -X POST http://localhost:8888/worker/metrics/upload \
  -H "Content-Type: application/json" \
  -d '{
    "v": 1,
    "events": [
      {
        "e": 999,  # 无效的事件类型
        "t": 1712345678,
        "v": {},
        "a": {}
      }
    ]
  }'
```

**Step 2: 检查错误记录**

```bash
sqlite3 data/ai_stats.db "SELECT * FROM metrics_event_errors ORDER BY created_at DESC LIMIT 1;"
```

预期输出：看到错误记录，包含 `error_message: "未知事件类型: 999"`
