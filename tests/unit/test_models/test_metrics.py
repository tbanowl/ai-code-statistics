"""测试 Metrics 相关数据模型"""
import pytest
from core.models.metrics import (
    MetricsRawRecord,
    MetricsCommittedRecord,
    MetricsCheckpointRecord,
    MetricsAgentUsageRecord,
    MetricsInstallHooksRecord,
    MetricsDailyStat,
    MetricsWeeklyStat,
    MetricsMonthlyStat,
    MetricsRepoStat,
    MetricsContributorStat,
)


class TestMetricsRawRecord:
    """测试 MetricsRawRecord 模型"""

    def test_create_record_with_required_fields(self):
        """创建仅包含必需字段的记录"""
        record = MetricsRawRecord(batch_id="test-batch-123")
        assert record.batch_id == "test-batch-123"
        assert record.version == 1  # 默认值
        assert record.event_count == 0  # 默认值
        assert record.payload_json == ""  # 默认值
        assert record.received_at == 0  # 默认值
        assert record.created_at == 0  # 默认值

    def test_create_record_with_all_fields(self):
        """创建包含所有字段的记录"""
        record = MetricsRawRecord(
            batch_id="test-batch-456",
            version=2,
            event_count=10,
            payload_json='{"test": "data"}',
            received_at=1710000000,
            created_at=1710000005,
        )
        assert record.batch_id == "test-batch-456"
        assert record.version == 2
        assert record.event_count == 10
        assert record.payload_json == '{"test": "data"}'
        assert record.received_at == 1710000000
        assert record.created_at == 1710000005

    def test_serialize_to_dict(self):
        """序列化为字典"""
        record = MetricsRawRecord(batch_id="test-batch")
        data = record.to_dict()
        assert data["batch_id"] == "test-batch"
        assert data["version"] == 1
        assert "event_count" in data

    def test_deserialize_from_dict(self):
        """从字典反序列化"""
        data = {
            "batch_id": "test-batch",
            "version": 3,
            "event_count": 5,
            "payload_json": "{}",
            "received_at": 1000,
            "created_at": 2000,
        }
        record = MetricsRawRecord.from_dict(data)
        assert record.batch_id == "test-batch"
        assert record.version == 3
        assert record.event_count == 5


class TestMetricsCommittedRecord:
    """测试 MetricsCommittedRecord 模型"""

    def test_create_record_with_required_fields(self):
        """创建仅包含必需字段的记录"""
        record = MetricsCommittedRecord(raw_id=1)
        assert record.raw_id == 1
        assert record.event_id == 1  # 默认值
        assert record.timestamp == 0  # 默认值

    def test_create_record_with_ai_additions(self):
        """创建包含 AI 代码添加统计的记录"""
        record = MetricsCommittedRecord(
            raw_id=1,
            timestamp=1710000000,
            human_additions=100,
            git_diff_added_lines=150,
            ai_additions='[50, 10, 5]',
        )
        assert record.raw_id == 1
        assert record.human_additions == 100
        assert record.git_diff_added_lines == 150
        assert record.ai_additions == '[50, 10, 5]'

    def test_serialization_preserves_optional_fields(self):
        """序列化时保留可选字段"""
        record = MetricsCommittedRecord(
            raw_id=1,
            commit_sha="abc123",
            repo_url="https://github.com/test/repo",
            author="test@example.com",
        )
        data = record.to_dict()
        assert data["raw_id"] == 1
        assert data["commit_sha"] == "abc123"
        assert data["repo_url"] == "https://github.com/test/repo"
        assert data["author"] == "test@example.com"


class TestMetricsCheckpointRecord:
    """测试 MetricsCheckpointRecord 模型"""

    def test_create_record_with_file_changes(self):
        """创建包含文件变更的记录"""
        record = MetricsCheckpointRecord(
            raw_id=1,
            timestamp=1710000000,
            checkpoint_ts=1709999900,
            kind="code_edit",
            file_path="src/main.py",
            lines_added=20,
            lines_deleted=5,
        )
        assert record.kind == "code_edit"
        assert record.file_path == "src/main.py"
        assert record.lines_added == 20
        assert record.lines_deleted == 5

    def test_create_record_with_sloc(self):
        """创建包含 SLOC 统计的记录"""
        record = MetricsCheckpointRecord(
            raw_id=1,
            lines_added_sloc=15,
            lines_deleted_sloc=4,
        )
        assert record.lines_added_sloc == 15
        assert record.lines_deleted_sloc == 4


class TestMetricsAgentUsageRecord:
    """测试 MetricsAgentUsageRecord 模型"""

    def test_create_minimal_record(self):
        """创建最小记录"""
        record = MetricsAgentUsageRecord(raw_id=1)
        assert record.raw_id == 1
        assert record.event_id == 2  # AgentUsage 默认事件 ID

    def test_create_record_with_tool_model(self):
        """创建包含工具和模型信息的记录"""
        record = MetricsAgentUsageRecord(
            raw_id=1,
            tool="claude",
            model="claude-4-opus-20250514",
            prompt_id="prompt-123",
        )
        assert record.tool == "claude"
        assert record.model == "claude-4-opus-20250514"
        assert record.prompt_id == "prompt-123"


class TestMetricsInstallHooksRecord:
    """测试 MetricsInstallHooksRecord 模型"""

    def test_create_record(self):
        """创建安装 Hooks 事件记录"""
        record = MetricsInstallHooksRecord(
            raw_id=1,
            timestamp=1710000000,
            tool_id="pre-commit",
            status="success",
            message="Hooks installed successfully",
        )
        assert record.tool_id == "pre-commit"
        assert record.status == "success"
        assert record.message == "Hooks installed successfully"


class TestMetricsDailyStat:
    """测试 MetricsDailyStat 模型"""

    def test_create_daily_stat(self):
        """创建每日统计"""
        record = MetricsDailyStat(
            date="2026-03-17",
            date_ts=1710662400,
            total_lines=1000,
            ai_lines=450,
            total_commits=10,
        )
        assert record.date == "2026-03-17"
        assert record.total_lines == 1000
        assert record.ai_lines == 450
        assert record.ai_percentage == 0.0  # 默认值，需要手动计算

    def test_calculate_ai_percentage(self):
        """计算 AI 代码占比"""
        record = MetricsDailyStat(
            date="2026-03-17",
            date_ts=1710662400,
            total_lines=1000,
            ai_lines=450,
            ai_percentage=45.0,  # 手动设置
        )
        assert record.ai_percentage == 45.0


class TestMetricsWeeklyStat:
    """测试 MetricsWeeklyStat 模型"""

    def test_create_weekly_stat(self):
        """创建每周统计"""
        record = MetricsWeeklyStat(
            year=2026,
            week=11,
            week_start="2026-03-17",
            week_start_ts=1710662400,
            week_end="2026-03-23",
            week_end_ts=1711267200,
            total_lines=5000,
            ai_lines=2000,
        )
        assert record.year == 2026
        assert record.week == 11
        assert record.week_start == "2026-03-17"
        assert record.total_lines == 5000
        assert record.ai_lines == 2000


class TestMetricsMonthlyStat:
    """测试 MetricsMonthlyStat 模型"""

    def test_create_monthly_stat(self):
        """创建每月统计"""
        record = MetricsMonthlyStat(
            year=2026,
            month=3,
            month_start="2026-03-01",
            month_start_ts=1710000000,
            month_end="2026-03-31",
            month_end_ts=1714454400,
            total_lines=20000,
            ai_lines=8000,
        )
        assert record.year == 2026
        assert record.month == 3
        assert record.total_lines == 20000
        assert record.ai_lines == 8000


class TestMetricsRepoStat:
    """测试 MetricsRepoStat 模型"""

    def test_create_repo_stat(self):
        """创建仓库统计"""
        record = MetricsRepoStat(
            repo_id="repo-123",
            repo_name="my-repo",
            repo_url="https://github.com/user/my-repo",
            provider_type="github",
            branch="main",
            total_lines=3000,
            ai_lines=1200,
        )
        assert record.repo_id == "repo-123"
        assert record.repo_name == "my-repo"
        assert record.provider_type == "github"
        assert record.branch == "main"


class TestMetricsContributorStat:
    """测试 MetricsContributorStat 模型"""

    def test_create_daily_contributor_stat(self):
        """创建每日贡献者统计"""
        record = MetricsContributorStat(
            author="user@example.com",
            granularity="daily",
            date="2026-03-17",
            date_ts=1710662400,
            total_commits=5,
            total_lines=500,
            ai_lines=200,
        )
        assert record.author == "user@example.com"
        assert record.granularity == "daily"
        assert record.date == "2026-03-17"

    def test_create_weekly_contributor_stat(self):
        """创建每周贡献者统计"""
        record = MetricsContributorStat(
            author="user@example.com",
            granularity="weekly",
            year_week="2026-W11",
            date_ts=1710662400,
        )
        assert record.granularity == "weekly"
        assert record.year_week == "2026-W11"

    def test_create_monthly_contributor_stat(self):
        """创建每月贡献者统计"""
        record = MetricsContributorStat(
            author="user@example.com",
            granularity="monthly",
            year_month="2026-03",
            date_ts=1710000000,
        )
        assert record.granularity == "monthly"
        assert record.year_month == "2026-03"
