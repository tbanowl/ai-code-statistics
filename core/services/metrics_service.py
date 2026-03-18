"""Metrics 数据处理服务"""
import json
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from core.config.logging import Logger


class MetricsService:
    """Metrics 数据处理服务"""

    def __init__(self):
        self.logger = Logger.get_logger('services.metrics')
        from core.database.factory import create_database
        from core.config import ConfigLoader
        config = ConfigLoader().load()
        self.database = create_database(config.get('database', {}))

    def process_metrics_batch(self, events: List[Dict]) -> List[Dict]:
        """
        批量处理 metrics 事件

        返回失败的事件列表，每个包含 index 和 error
        """
        if not events:
            return []

        batch_id = str(uuid.uuid4())
        received_at = int(datetime.now().timestamp())

        # 存储原始数据
        payload_json = json.dumps({'v': 1, 'events': events})
        raw_id = self.database.save_metrics_raw(
            batch_id=batch_id,
            version=1,
            event_count=len(events),
            payload_json=payload_json,
            received_at=received_at
        )

        errors = []

        # 处理每个事件
        for index, event in enumerate(events):
            try:
                self._process_single_event(event, raw_id)
            except Exception as e:
                self.logger.error(f"处理事件 {index} 失败: {e}\nevent data: {event}")
                errors.append({
                    'index': index,
                    'error': str(e)
                })
        
        return errors

    def _process_single_event(self, event: Dict, raw_id: int):
        """处理单个事件"""
        event_id = event.get('e')
        timestamp = event.get('t')
        values = event.get('v', {})
        attrs = event.get('a', {})

        # 导入数据模型
        from core.models.metrics import (
            MetricsCommittedRecord, MetricsCheckpointRecord,
            MetricsAgentUsageRecord, MetricsInstallHooksRecord
        )

        now = int(datetime.now().timestamp())

        if event_id == 1:  # Committed
            record = MetricsCommittedRecord(
                raw_id=raw_id,
                event_id=1,
                timestamp=timestamp,
                human_additions=self._get_u32(values, '0'),
                git_diff_deleted_lines=self._get_u32(values, '1'),
                git_diff_added_lines=self._get_u32(values, '2'),
                first_checkpoint_ts=self._get_u64(values, '10'),
                commit_subject=self._get_string(values, '11'),
                commit_body=self._get_string(values, '12'),
                tool_model_pairs=json.dumps(self._get_array(values, '3')),
                mixed_additions=json.dumps(self._get_u32_array(values, '4')),
                ai_additions=json.dumps(self._get_u32_array(values, '5')),
                ai_accepted=json.dumps(self._get_u32_array(values, '6')),
                total_ai_additions=json.dumps(self._get_u32_array(values, '7')),
                total_ai_deletions=json.dumps(self._get_u32_array(values, '8')),
                time_waiting_for_ai=json.dumps(self._get_u64_array(values, '9')),
                git_ai_version=self._get_string(attrs, '0'),
                repo_url=self._get_string(attrs, '1'),
                author=self._get_string(attrs, '2'),
                commit_sha=self._get_string(attrs, '3'),
                base_commit_sha=self._get_string(attrs, '4'),
                branch=self._get_string(attrs, '5'),
                tool=self._get_string(attrs, '20'),
                model=self._get_string(attrs, '21'),
                prompt_id=self._get_string(attrs, '22'),
                external_prompt_id=self._get_string(attrs, '23'),
                custom_attributes=self._get_string(attrs, '30'),
                created_at=now
            )
            self.database.save_committed_event(record)

        elif event_id == 2:  # AgentUsage
            record = MetricsAgentUsageRecord(
                raw_id=raw_id,
                event_id=2,
                timestamp=timestamp,
                git_ai_version=self._get_string(attrs, '0'),
                repo_url=self._get_string(attrs, '1'),
                author=self._get_string(attrs, '2'),
                commit_sha=self._get_string(attrs, '3'),
                base_commit_sha=self._get_string(attrs, '4'),
                branch=self._get_string(attrs, '5'),
                tool=self._get_string(attrs, '20'),
                model=self._get_string(attrs, '21'),
                prompt_id=self._get_string(attrs, '22'),
                external_prompt_id=self._get_string(attrs, '23'),
                created_at=now
            )
            self.database.save_agent_usage_event(record)

        elif event_id == 3:  # InstallHooks
            record = MetricsInstallHooksRecord(
                raw_id=raw_id,
                event_id=3,
                timestamp=timestamp,
                tool_id=self._get_string(values, '0'),
                status=self._get_string(values, '1'),
                message=self._get_string(values, '2'),
                git_ai_version=self._get_string(attrs, '0'),
                created_at=now
            )
            self.database.save_install_hooks_event(record)

        elif event_id == 4:  # Checkpoint
            record = MetricsCheckpointRecord(   
                raw_id=raw_id,
                event_id=4,
                timestamp=timestamp,
                checkpoint_ts=self._get_u64(values, '0'),
                kind=self._get_string(values, '1'),
                file_path=self._get_string(values, '2'),
                lines_added=self._get_u32(values, '3'),
                lines_deleted=self._get_u32(values, '4'),
                lines_added_sloc=self._get_u32(values, '5'),
                lines_deleted_sloc=self._get_u32(values, '6'),
                git_ai_version=self._get_string(attrs, '0'),
                repo_url=self._get_string(attrs, '1'),
                author=self._get_string(attrs, '2'),
                commit_sha=self._get_string(attrs, '3'),
                base_commit_sha=self._get_string(attrs, '4'),
                branch=self._get_string(attrs, '5'),
                tool=self._get_string(attrs, '20'),
                model=self._get_string(attrs, '21'),
                prompt_id=self._get_string(attrs, '22'),
                created_at=now
            )
            self.database.save_checkpoint_event(record)

        else:
            self.logger.warning(f"未知事件类型: {event_id}")

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
                return 'true' if val else 'false'
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
