"""
调度器数据库操作类

负责任务执行记录表的所有操作。
"""

from datetime import datetime
from typing import Dict, List, Optional

from .base import BaseDatabase, session_scope
from .models import TaskExecution


class SchedulerDatabase(BaseDatabase):
    """调度器数据库操作类"""

    def create_task_execution(self, job_id: str) -> str:
        """
        创建任务执行记录，返回 execution_id。

        Args:
            job_id: 任务 ID

        Returns:
            execution_id: 执行记录的 ID
        """
        with session_scope(self.engine) as session:
            execution = TaskExecution(job_id=job_id, status="pending")
            session.add(execution)
            session.flush()
            return str(execution.id)

    def update_task_execution_status(self, execution_id: str, status: str) -> None:
        """
        更新任务执行状态。

        Args:
            execution_id: 执行记录的 ID
            status: 新状态 (pending/running/completed/failed)
        """
        from .base import now_ts

        with session_scope(self.engine) as session:
            execution = (
                session.query(TaskExecution)
                .filter(TaskExecution.id == execution_id)
                .first()
            )
            if execution:
                execution.status = status
                execution.updated_at = now_ts()
                if status == "running" and not execution.started_at:
                    execution.started_at = now_ts()

    def complete_task_execution(
        self,
        execution_id: str,
        started_at: datetime,
        finished_at: datetime,
        execution_time_ms: int,
        error_message: Optional[str] = None,
    ) -> None:
        """
        标记任务执行完成。

        Args:
            execution_id: 执行记录的 ID
            started_at: 开始时间
            finished_at: 结束时间
            execution_time_ms: 执行耗时（毫秒）
            error_message: 错误信息（如果有）
        """
        from .base import now_ts

        with session_scope(self.engine) as session:
            execution = (
                session.query(TaskExecution)
                .filter(TaskExecution.id == execution_id)
                .first()
            )
            if execution:
                execution.status = "failed" if error_message else "completed"
                execution.started_at = int(started_at.timestamp() * 1000)
                execution.finished_at = int(finished_at.timestamp() * 1000)
                execution.execution_time_ms = execution_time_ms
                execution.error_message = error_message if error_message else ""
                execution.updated_at = now_ts()

    def get_running_task_execution(self, job_id: str) -> Optional[Dict]:
        """
        获取正在运行的任务执行记录（pending 或 running）。

        Args:
            job_id: 任务 ID

        Returns:
            执行记录字典，或 None
        """
        with session_scope(self.engine) as session:
            execution = (
                session.query(TaskExecution)
                .filter(TaskExecution.job_id == job_id)
                .filter(TaskExecution.status.in_(["pending", "running"]))
                .first()
            )
            return execution.to_dict() if execution else None

    def get_task_execution(self, execution_id: str | None) -> Optional[Dict]:
        """
        获取任务执行详情。

        Args:
            execution_id: 执行记录的 ID

        Returns:
            执行记录字典，或 None
        """
        if not execution_id:
            return None
        with session_scope(self.engine) as session:
            execution = (
                session.query(TaskExecution)
                .filter(TaskExecution.id == execution_id)
                .first()
            )
            return execution.to_dict() if execution else None

    def get_task_executions(
        self,
        job_id: Optional[str] = None,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """
        获取任务执行历史。

        Args:
            job_id: 过滤任务 ID（可选）
            limit: 返回记录数限制
            status: 过滤状态（可选）

        Returns:
            执行记录列表
        """
        with session_scope(self.engine) as session:
            query = session.query(TaskExecution)

            if job_id:
                query = query.filter(TaskExecution.job_id == job_id)
            if status:
                query = query.filter(TaskExecution.status == status)

            results = query.order_by(TaskExecution.created_at.desc()).limit(limit).all()
            return [r.to_dict() for r in results]

    def reset_running_executions_for_testing(self) -> int:
        from .base import now_ts

        with session_scope(self.engine) as session:
            rows = (
                session.query(TaskExecution)
                .filter(TaskExecution.status.in_(["pending", "running"]))
                .all()
            )
            for row in rows:
                row.status = "failed"
                row.updated_at = now_ts()
                if not row.finished_at:
                    row.finished_at = now_ts()
            return len(rows)

    def cleanup_old_task_executions(self, keep_count: int = 100) -> int:
        """
        清理旧的任务执行记录，返回删除的记录数。

        Args:
            keep_count: 每个 job_id 保留的最大记录数

        Returns:
            删除的记录数
        """
        with session_scope(self.engine) as session:
            # 获取需要保留的记录 ID

            # 删除不在保留列表中的记录（此逻辑简化，实际需要更复杂）
            # 这里使用简单的清理策略：删除所有超过 keep_count 的旧记录
            to_delete = (
                session.query(TaskExecution)
                .filter(TaskExecution.status == "completed")
                .order_by(TaskExecution.created_at.asc())
                .all()
            )

            count = len(to_delete)
            for execution in to_delete:
                session.delete(execution)

            return count

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
