"""Metrics 数据处理服务"""

import json
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timezone
from core.config.logging import Logger
from core.database import MetricsDatabase
from core.database.models import MetricsEventsAgentUsage, MetricsEventsCheckpoint, MetricsEventsCommitted, MetricsEventsInstallHooks
from core.utils.data_uid import gen_commited_uid, gen_checkpoint_uid, gen_agent_usage_uid, gen_install_hooks_uid
from core.utils.repo_url import normalize_repo_url


class MetricsService:
    """Metrics 数据处理服务"""

    def __init__(self):
        self.logger = Logger.get_logger("services.metrics")
        self.database = MetricsDatabase()

    def process_metrics_batch(self, events: List[Dict]) -> List[Dict]:
        """
        批量处理 metrics 事件

        返回失败的事件列表，每个包含 index 和 error
        """
        if not events:
            return []

        batch_id = str(uuid.uuid4())
        received_at = int(datetime.now().timestamp() * 1000)

        # 存储原始数据
        payload_json = json.dumps({"v": 1, "events": events})
        raw_id = self.database.save_metrics_raw(
            version=1,
            event_count=len(events),
            payload_json=payload_json,
            received_at=received_at,
        )

        errors = []

        # 处理每个事件
        for index, event in enumerate(events):
            try:
                self._process_single_event(event, raw_id)
            except Exception as e:
                self.logger.error(f"处理事件 {index} 失败: event data: {event}", e)
                errors.append({"index": index, "error": str(e)})

        return errors

    def _process_single_event(self, event: Dict, raw_id: str):
        """处理单个事件"""
        event_id = event.get("e")
        timestamp = self._event_timestamp_seconds(event)
        commit_date = self._commit_date_from_seconds(timestamp)
        values = event.get("v", {})
        attrs = event.get("a", {})

        now = int(datetime.now().timestamp() * 1000)

        if event_id == 1:  # Committed
            record = MetricsEventsCommitted(
                raw_id =raw_id,
                event_id = 1,
                timestamp= timestamp,
                commit_date=commit_date,
                human_additions= self._get_u32(values, "0"),
                git_diff_deleted_lines= self._get_u32(values, "1"),
                git_diff_added_lines= self._get_u32(values, "2"),
                first_checkpoint_ts= self._get_u64(values, "10"),
                commit_subject= self._get_string(values, "11"),
                commit_body= self._get_string(values, "12"),
                tool_model_pairs= self._get_array(values, "3"),
                mixed_additions= self._get_u32_array(values, "4"),
                ai_additions= self._get_u32_array(values, "5"),
                ai_accepted= self._get_u32_array(values, "6"),
                total_ai_additions= self._get_u32_array(values, "7"),
                total_ai_deletions= self._get_u32_array(values, "8"),
                time_waiting_for_ai= self._get_u64_array(values, "9"),
                mixed_additions_total=self._first_array_int(values, "4"),
                ai_additions_total=self._first_array_int(values, "5"),
                ai_accepted_total=self._first_array_int(values, "6"),
                total_ai_additions_total=self._first_array_int(values, "7"),
                total_ai_deletions_total=self._first_array_int(values, "8"),
                time_waiting_for_ai_total=self._first_array_int(values, "9"),
                git_ai_version= self._get_string(attrs, "0"),
                repo_url= normalize_repo_url(self._get_string(attrs, "1")),
                author= self._get_string(attrs, "2"),
                commit_sha= self._get_string(attrs, "3"),
                base_commit_sha= self._get_string(attrs, "4"),
                branch= self._get_string(attrs, "5"),
                tool= self._get_string(attrs, "20"),
                model= self._get_string(attrs, "21"),
                prompt_id= self._get_string(attrs, "22"),
                external_prompt_id= self._get_string(attrs, "23"),
                custom_attributes= self._get_string(attrs, "30"),
                created_at= now,
            )
            record.uid = gen_commited_uid(record)
            self.database.upsert_committed_event(record)

        elif event_id == 2:  # AgentUsage
            record = MetricsEventsAgentUsage(
                raw_id = raw_id,
                event_id = 2,
                timestamp = timestamp,
                git_ai_version = self._get_string(attrs, "0"),
                repo_url = normalize_repo_url(self._get_string(attrs, "1")),
                author = self._get_string(attrs, "2"),
                commit_sha = self._get_string(attrs, "3"),
                base_commit_sha = self._get_string(attrs, "4"),
                branch = self._get_string(attrs, "5"),
                tool = self._get_string(attrs, "20"),
                model = self._get_string(attrs, "21"),
                prompt_id = self._get_string(attrs, "22"),
                external_prompt_id = self._get_string(attrs, "23"),
                created_at = now,
            )
            record.uid = gen_agent_usage_uid(record)
            self.database.save_agent_usage_event(record)

        elif event_id == 3:  # InstallHooks
            record = MetricsEventsInstallHooks(
                raw_id = raw_id,
                event_id = 3,
                timestamp = timestamp,
                tool_id = self._get_string(values, "0"),
                status = self._get_string(values, "1"),
                message = self._get_string(values, "2"),
                git_ai_version = self._get_string(attrs, "0"),
                created_at = now,
            )
            record.uid = gen_install_hooks_uid(record)
            self.database.save_install_hooks_event(record)

        elif event_id == 4:  # Checkpoint
            record = MetricsEventsCheckpoint(
                raw_id = raw_id,
                event_id = 4,
                timestamp = timestamp,
                checkpoint_ts = self._get_u64(values, "0"),
                kind = self._get_string(values, "1"),
                file_path = self._get_string(values, "2"),
                lines_added = self._get_u32(values, "3"),
                lines_deleted = self._get_u32(values, "4"),
                lines_added_sloc = self._get_u32(values, "5"),
                lines_deleted_sloc = self._get_u32(values, "6"),
                git_ai_version = self._get_string(attrs, "0"),
                repo_url = normalize_repo_url(self._get_string(attrs, "1")),
                author = self._get_string(attrs, "2"),
                commit_sha = self._get_string(attrs, "3"),
                base_commit_sha = self._get_string(attrs, "4"),
                branch = self._get_string(attrs, "5"),
                tool = self._get_string(attrs, "20"),
                model = self._get_string(attrs, "21"),
                prompt_id = self._get_string(attrs, "22"),
                created_at = now,
            )
            record.checkpoint_ts = record.checkpoint_ts * 1000
            record.uid = gen_checkpoint_uid(record)
            self.database.save_checkpoint_event(record)

        else:
            raise ValueError(f"未知事件类型: {event_id}")

    @staticmethod
    def _event_timestamp_seconds(event: Dict) -> int:
        raw = event.get("t", 0)
        if isinstance(raw, (int, float)):
            return int(raw)
        return 0

    @staticmethod
    def _commit_date_from_seconds(timestamp: int) -> Optional[int]:
        if timestamp <= 0:
            return None
        return int(datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y%m%d"))

    @staticmethod
    def _first_array_int(arr: Dict, pos: str) -> int:
        values = MetricsService._get_array(arr, pos)
        if not values:
            return 0
        first = values[0]
        if isinstance(first, (int, float)):
            return int(first)
        return 0

    @staticmethod
    def _get_u32(arr: Dict, pos: str) -> Optional[int]:
        val = arr.get(pos)
        if val is not None and isinstance(val, (int, float)):
            return int(val)
        return None

    @staticmethod
    def _get_u64(arr: Dict, pos: str) -> Optional[int]:
        val = arr.get(pos)
        if val is not None and isinstance(val, (int, float)):
            return int(val)
        return None

    @staticmethod
    def _get_string(arr: Dict, pos: str) -> Optional[str]:
        val = arr.get(pos)
        if val is not None:
            if isinstance(val, str):
                return val
            if isinstance(val, bool):
                return "true" if val else "false"
        return None

    @staticmethod
    def _get_array(arr: Dict, pos: str) -> List:
        val = arr.get(pos)
        if isinstance(val, list):
            return val
        return []

    @staticmethod
    def _get_u32_array(arr: Dict, pos: str) -> List[int]:
        vals = MetricsService._get_array(arr, pos)
        result = []
        for v in vals:
            if isinstance(v, (int, float)):
                result.append(int(v))
        return result

    @staticmethod
    def _get_u64_array(arr: Dict, pos: str) -> List[int]:
        vals = MetricsService._get_array(arr, pos)
        result = []
        for v in vals:
            if isinstance(v, (int, float)):
                result.append(int(v))
        return result

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
                          payload_snippet: str | None):
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
