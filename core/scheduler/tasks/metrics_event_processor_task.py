"""Metrics 事件处理定时任务"""

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

        # 获取配置
        batch_size = (
            self.config.get("scheduler", {})
            .get("jobs", {})
            .get("metrics_event_processor", {})
            .get("batch_size", 100)
        )

        timeout_minutes = (
            self.config.get("scheduler", {})
            .get("jobs", {})
            .get("metrics_event_processor", {})
            .get("timeout_minutes", 10)
        )

        # 并发安全检查
        from core.database import SchedulerDatabase, MetricsDatabase

        scheduler_db = SchedulerDatabase()

        running_task = scheduler_db.has_running_task(
            "metrics_event_processor", timeout_minutes
        )

        if running_task:
            self.logger.info(
                f"已有任务在处理中（id={running_task['id']}），跳过本次执行"
            )
            return {"success": True, "skipped": True, "skip_reason": "running_task"}

        # # 检查是否有超时任务需要恢复
        # pending_or_running_task = scheduler_db.get_running_task_execution("metrics_event_processor")
        # if pending_or_running_task:
        #     # 有超时任务，恢复 raw 记录状态
        #     db_ = MetricsDatabase()
        #     reset_count = db_.reset_stuck_extracting_records()
        #     if reset_count > 0:
        #         self.logger.warning(f"恢复 {reset_count} 条被卡住的原始记录")
        #     # 标记旧任务为失败
        #     scheduler_db.update_task_execution_status(pending_or_running_task['id'], "failed")

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
            "batches": 0,
        }

        service = MetricsService()

        while True:
            # 获取下一批记录
            pending_records = db.get_pending_raw_records(
                limit=batch_size, last_id=last_id
            )

            if not pending_records:
                break

            batch_count += 1
            self.logger.info(f"处理批次 #{batch_count}: {len(pending_records)} 条记录")

            # 处理这批记录
            for record in pending_records:
                raw_id = record["id"]
                payload_json = record["payload_json"]
                event_count = record["event_count"]

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
                        self.logger.error(
                            f"处理失败: raw_id={raw_id}, error={result.get('error')}"
                        )

                except Exception as e:
                    db.mark_raw_extracted(raw_id, success=False)
                    stats["failed"] += 1
                    self.logger.error(
                        f"处理异常: raw_id={raw_id}, error={str(e)}", exc_info=True
                    )

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
            "batches": stats["batches"],
        }
