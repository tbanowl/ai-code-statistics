"""测试维度表相关数据模型"""
import pytest
from core.models.metrics import (
    MetricsRepo,
    MetricsContributor,
    MetricsRepoContributor
)


class TestMetricsRepo:
    """测试 MetricsRepo 模型"""

    def test_create_repo_with_required_fields(self):
        """创建仅包含必需字段的仓库记录"""
        repo = MetricsRepo(
            repo_id="owner/repo",
            repo_name="test-repo",
            repo_url="https://github.com/owner/repo"
        )
        assert repo.repo_id == "owner/repo"
        assert repo.repo_name == "test-repo"
        assert repo.repo_url == "https://github.com/owner/repo"
        assert repo.total_lines == 0
        assert repo.ai_lines == 0
        assert repo.human_lines == 0
        assert repo.ai_percentage == 0.0
        assert repo.total_commits == 0
        assert repo.ai_commits == 0

    def test_create_repo_with_all_fields(self):
        """创建包含所有字段的仓库记录"""
        repo = MetricsRepo(
            repo_id="owner/repo",
            repo_name="test-repo",
            repo_url="https://github.com/owner/repo",
            provider_type="github",
            branch="main",
            total_lines=10000,
            ai_lines=3500,
            human_lines=6500,
            ai_percentage=35.0,
            total_commits=150,
            ai_commits=80,
            tool_model_breakdown='{"claude-opus-4-6": {"total_lines": 2000}}',
            first_commit_ts=1710000000,
            last_commit_ts=1715000000,
            created_at=1710000000,
            updated_at=1715000000
        )
        assert repo.repo_id == "owner/repo"
        assert repo.provider_type == "github"
        assert repo.total_lines == 10000
        assert repo.ai_lines == 3500
        assert repo.ai_percentage == 35.0

    def test_serialize_to_dict(self):
        """序列化为字典"""
        repo = MetricsRepo(
            repo_id="owner/repo",
            repo_name="test-repo",
            repo_url="https://github.com/owner/repo"
        )
        data = repo.to_dict()
        assert data["repo_id"] == "owner/repo"
        assert data["repo_name"] == "test-repo"

    def test_deserialize_from_dict(self):
        """从字典反序列化"""
        data = {
            "repo_id": "owner/repo",
            "repo_name": "test-repo",
            "repo_url": "https://github.com/owner/repo",
            "total_lines": 5000,
            "ai_lines": 2000
        }
        repo = MetricsRepo.from_dict(data)
        assert repo.repo_id == "owner/repo"
        assert repo.total_lines == 5000
        assert repo.ai_lines == 2000


class TestMetricsContributor:
    """测试 MetricsContributor 模型"""

    def test_create_contributor_with_required_fields(self):
        """创建仅包含必需字段的作者记录"""
        contributor = MetricsContributor(author="test-user")
        assert contributor.author == "test-user"
        assert contributor.total_lines == 0
        assert contributor.ai_lines == 0
        assert contributor.repos_count == 0

    def test_create_contributor_with_all_fields(self):
        """创建包含所有字段的作者记录"""
        contributor = MetricsContributor(
            author="test-user",
            author_email="test@example.com",
            total_lines=5000,
            ai_lines=2000,
            human_lines=3000,
            ai_percentage=40.0,
            total_commits=50,
            ai_commits=25,
            repos_count=3,
            first_commit_ts=1710000000,
            last_commit_ts=1715000000
        )
        assert contributor.author == "test-user"
        assert contributor.author_email == "test@example.com"
        assert contributor.total_lines == 5000
        assert contributor.repos_count == 3

    def test_serialize_to_dict(self):
        """序列化为字典"""
        contributor = MetricsContributor(author="test-user")
        data = contributor.to_dict()
        assert data["author"] == "test-user"

    def test_deserialize_from_dict(self):
        """从字典反序列化"""
        data = {"author": "test-user", "total_lines": 3000}
        contributor = MetricsContributor.from_dict(data)
        assert contributor.author == "test-user"
        assert contributor.total_lines == 3000


class TestMetricsRepoContributor:
    """测试 MetricsRepoContributor 模型"""

    def test_create_with_required_fields(self):
        """创建仅包含必需字段的关联记录"""
        relation = MetricsRepoContributor(
            repo_id="owner/repo",
            author="test-user"
        )
        assert relation.repo_id == "owner/repo"
        assert relation.author == "test-user"
        assert relation.first_seen_ts is None

    def test_create_with_all_fields(self):
        """创建包含所有字段的关联记录"""
        relation = MetricsRepoContributor(
            repo_id="owner/repo",
            author="test-user",
            first_seen_ts=1710000000,
            last_seen_ts=1715000000,
            created_at=1710000000,
            updated_at=1715000000
        )
        assert relation.repo_id == "owner/repo"
        assert relation.first_seen_ts == 1710000000
        assert relation.last_seen_ts == 1715000000

    def test_serialize_to_dict(self):
        """序列化为字典"""
        relation = MetricsRepoContributor(
            repo_id="owner/repo",
            author="test-user"
        )
        data = relation.to_dict()
        assert data["repo_id"] == "owner/repo"
        assert data["author"] == "test-user"
