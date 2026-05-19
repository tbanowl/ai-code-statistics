"""Codeup Merge AI 归属重算定时任务"""

from typing import Any, Callable, Dict, Optional

from core.scheduler.scheduled import scheduled
from core.scheduler.tasks.base import BaseTask
from core.services.codeup_merge_authorship_service import CodeupMergeAuthorshipService


@scheduled(
    cron="*/2 * * * *",
    job_id="codeup_merge_authorship",
    name="Codeup Merge AI归属重算",
)
class CodeupMergeAuthorshipTask(BaseTask):
    """异步处理 Codeup merge webhook 入队后的 AI 归属重算任务。"""

    def __init__(
        self,
        config: Dict,
        service_factory: Optional[Callable[[dict[str, Any]], Any]] = None,
    ):
        super().__init__(config)
        self.service_factory = service_factory

    def execute(self, context: Optional[Dict] = None) -> Dict:
        self.logger.info("开始执行 Codeup Merge AI归属重算任务")

        job_config = self._job_config()
        if not job_config.get("enabled", True):
            self.logger.info("Codeup Merge AI归属重算调度任务已禁用，跳过处理")
            return {"success": True, "processed": 0, "skipped": True}

        codeup_config = self.config.get("codeup_webhook", {})
        batch_size = self._batch_size(job_config)
        service = self._create_service(codeup_config)
        total_processed = 0
        failures = 0
        skipped = 0

        for _ in range(batch_size):
            result = service.process_next_task()
            processed = int(result.get("processed", 0))

            if processed == 0:
                break

            total_processed += processed
            if result.get("skipped"):
                skipped += processed
            if not result.get("success"):
                failures += 1
                self.logger.error(
                    "Codeup Merge AI归属重算子任务失败: %s", result.get("error")
                )

        summary = {
            "success": failures == 0,
            "processed": total_processed,
            "failed": failures,
        }
        if skipped:
            summary["skipped"] = skipped
        self.logger.info(
            "Codeup Merge AI归属重算完成: processed=%s, failed=%s, skipped=%s",
            total_processed,
            failures,
            skipped,
        )
        return summary

    def _job_config(self) -> dict[str, Any]:
        return (
            self.config.get("scheduler", {})
            .get("jobs", {})
            .get("codeup_merge_authorship", {})
        )

    def _batch_size(self, job_config: dict[str, Any]) -> int:
        try:
            batch_size = int(job_config.get("batch_size", 10))
        except (TypeError, ValueError):
            return 1
        return batch_size if batch_size >= 1 else 1

    def _create_service(self, codeup_config: dict[str, Any]) -> Any:
        if self.service_factory is not None:
            return self.service_factory(codeup_config)
        return CodeupMergeAuthorshipService(config=codeup_config)
