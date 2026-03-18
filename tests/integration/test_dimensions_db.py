"""测试维度表数据库集成"""
import pytest
from datetime import datetime
from core.database.sqlite import SQLiteDatabase
from core.models.metrics import (
    MetricsRepo, MetricsContributor, MetricsRepoContributor
)


@pytest.fixture(scope='class')
def db_instance():
    """创建内存测试数据库（类级别共享）"""
    config = {'type': 'sqlite', 'sqlite': {'path': ':memory:'}}
    db = SQLiteDatabase(config)
    db.init_db()
    return db


@pytest.fixture(autouse=True)
def clean_tables(db_instance, request):
    """每个测试前自动清空维度表"""
    def clear_dimension_tables():
        with db_instance._get_connection() as conn:
            conn.execute('DELETE FROM metrics_repo_contributors')
            conn.execute('DELETE FROM metrics_contributors')
            conn.execute('DELETE FROM metrics_repos')
            conn.commit()
    clear_dimension_tables()  # 测试前清理
    request.addfinalizer(clear_dimension_tables)  # 测试后也清理


@pytest.fixture
def clean_db(db_instance):
    """提供数据库实例"""
    return db_instance


class TestMetricsRepoDB:
    """测试仓库维度数据库操作"""

    def test_save_and_get_repo(self, clean_db):
        """保存并获取仓库记录"""
        repo = MetricsRepo(
            repo_id="owner/repo",
            repo_name="test-repo",
            repo_url="https://github.com/owner/repo",
            total_lines=1000,
            ai_lines=400,
            human_lines=600,
            ai_percentage=40.0,
            created_at=int(datetime.now().timestamp()),
            updated_at=int(datetime.now().timestamp())
        )

        repo_id = clean_db.save_metrics_repo(repo)
        assert repo_id > 0

        result = clean_db.get_metrics_repo("owner/repo")
        assert result is not None
        assert result['repo_id'] == "owner/repo"
        assert result['repo_name'] == "test-repo"
        assert result['total_lines'] == 1000
        assert result['ai_lines'] == 400

    def test_get_nonexistent_repo(self, clean_db):
        """获取不存在的仓库"""
        result = clean_db.get_metrics_repo("nonexistent/repo")
        assert result is None

    def test_get_repos_pagination(self, clean_db):
        """测试仓库列表分页"""
        now = int(datetime.now().timestamp())

        # 创建 25 个仓库
        for i in range(25):
            repo = MetricsRepo(
                repo_id=f"owner/repo-{i}",
                repo_name=f"test-repo-{i}",
                repo_url=f"https://github.com/owner/repo-{i}",
                total_lines=i * 100,
                created_at=now,
                updated_at=now
            )
            clean_db.save_metrics_repo(repo)

        # 测试第一页
        page1 = clean_db.get_metrics_repos(page=1, page_size=10)
        assert len(page1['data']) == 10
        assert page1['pagination']['total'] == 25
        assert page1['pagination']['total_pages'] == 3

        # 测试第二页
        page2 = clean_db.get_metrics_repos(page=2, page_size=10)
        assert len(page2['data']) == 10

    def test_get_repos_sort_by_ai_lines(self, clean_db):
        """测试按 AI 代码行数排序"""
        now = int(datetime.now().timestamp())

        repos = [
            MetricsRepo(repo_id="a", repo_name="a", repo_url="a",
                       ai_lines=100, created_at=now, updated_at=now),
            MetricsRepo(repo_id="b", repo_name="b", repo_url="b",
                       ai_lines=500, created_at=now, updated_at=now),
            MetricsRepo(repo_id="c", repo_name="c", repo_url="c",
                       ai_lines=300, created_at=now, updated_at=now),
        ]

        for repo in repos:
            clean_db.save_metrics_repo(repo)

        result = clean_db.get_metrics_repos(sort='ai_lines')
        data = result['data']
        assert data[0]['ai_lines'] == 500
        assert data[1]['ai_lines'] == 300
        assert data[2]['ai_lines'] == 100


class TestMetricsContributorDB:
    """测试作者维度数据库操作"""

    def test_save_and_get_contributor(self, clean_db):
        """保存并获取作者记录"""
        contributor = MetricsContributor(
            author="test-user",
            author_email="test@example.com",
            total_lines=500,
            ai_lines=200,
            repos_count=2,
            created_at=int(datetime.now().timestamp()),
            updated_at=int(datetime.now().timestamp())
        )

        id_ = clean_db.save_metrics_contributor(contributor)
        assert id_ > 0

        result = clean_db.get_metrics_contributor("test-user")
        assert result is not None
        assert result['author'] == "test-user"
        assert result['author_email'] == "test@example.com"
        assert result['total_lines'] == 500
        assert result['repos_count'] == 2

    def test_get_contributors_pagination(self, clean_db):
        """测试作者列表分页"""
        now = int(datetime.now().timestamp())

        for i in range(15):
            contributor = MetricsContributor(
                author=f"user-{i}",
                total_lines=i * 50,
                created_at=now,
                updated_at=now
            )
            clean_db.save_metrics_contributor(contributor)

        result = clean_db.get_metrics_contributors(page=1, page_size=5)
        assert len(result['data']) == 5
        assert result['pagination']['total'] == 15


class TestMetricsRepoContributorDB:
    """测试仓库作者关联数据库操作"""

    def test_save_and_get_relation(self, clean_db):
        """保存并获取仓库作者关联"""
        relation = MetricsRepoContributor(
            repo_id="owner/repo",
            author="test-user",
            first_seen_ts=1710000000,
            last_seen_ts=1715000000,
            created_at=1710000000,
            updated_at=1715000000
        )

        id_ = clean_db.save_metrics_repo_contributor(relation)
        assert id_ > 0

        result = clean_db.get_metrics_repo_contributors(
            repo_id="owner/repo", author="test-user"
        )
        assert len(result['data']) == 1
        assert result['data'][0]['repo_id'] == "owner/repo"
        assert result['data'][0]['author'] == "test-user"

    def test_get_relations_by_repo(self, clean_db):
        """按仓库获取关联列表"""
        now = int(datetime.now().timestamp())

        for i in range(3):
            relation = MetricsRepoContributor(
                repo_id="owner/repo",
                author=f"user-{i}",
                created_at=now,
                updated_at=now
            )
            clean_db.save_metrics_repo_contributor(relation)

        result = clean_db.get_metrics_repo_contributors(repo_id="owner/repo")
        assert len(result['data']) == 3
        assert all(r['repo_id'] == "owner/repo" for r in result['data'])

    def test_get_relations_by_author(self, clean_db):
        """按作者获取关联列表"""
        now = int(datetime.now().timestamp())

        for i in range(3):
            relation = MetricsRepoContributor(
                repo_id=f"owner/repo-{i}",
                author="test-user",
                created_at=now,
                updated_at=now
            )
            clean_db.save_metrics_repo_contributor(relation)

        result = clean_db.get_metrics_repo_contributors(author="test-user")
        assert len(result['data']) == 3
        assert all(r['author'] == "test-user" for r in result['data'])
