from datetime import datetime
from core.models.stats import StatRecord, RepoStatRecord, ContributorStatRecord, RepoContributorStatRecord


def test_stat_record_creation():
    now = datetime.now()
    record = StatRecord(
        id="test-id",
        timestamp=now,
        total_lines=1000,
        total_ai_lines=500
    )
    assert record.id == "test-id"
    assert record.total_lines == 1000
    assert record.overall_percentage == 0.0  # 计算前默认值


def test_repo_stat_record_creation():
    now = datetime.now()
    record = RepoStatRecord(
        id="repo-id",
        stat_id="stat-id",
        repo_name="test-repo",
        repo_id="123",
        provider_type="gitlab",
        branch="main"
    )
    assert record.repo_name == "test-repo"
    assert record.provider_type == "gitlab"


def test_stat_record_serialization():
    now = datetime.now()
    record = StatRecord(
        id="test-id",
        timestamp=now,
        total_lines=1000,
        total_ai_lines=500
    )
    json_data = record.to_dict()
    assert json_data['id'] == "test-id"
    assert json_data['total_lines'] == 1000

