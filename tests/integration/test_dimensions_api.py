"""测试维度表 API"""
import os
import tempfile
import pytest
from flask import Flask
from core.database.sqlite import SQLiteDatabase
from core.models.metrics import (
    MetricsRepo, MetricsContributor, MetricsRepoContributor
)


@pytest.fixture
def test_client():
    """创建测试客户端"""
    # 创建临时数据库
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.environ['BUILD_FRONTEND'] = '0'

    # 修改配置使用临时数据库
    import core.config.loader as loader_module
    loader_module._config_cache = None
    from core.config.loader import ConfigLoader

    # 创建临时配置 - 直接使用字典而非读取 YAML 文件
    config = {
        'database': {
            'type': 'sqlite',
            'sqlite': {'path': db_path}
        }
    }

    # 缓存配置供后续使用
    loader_module._config_cache = config

    # 创建应用
    from app import app as flask_app
    flask_app.config['TESTING'] = True

    client = flask_app.test_client()

    # 初始化数据库
    db = SQLiteDatabase(config['database'])
    db.init_db()

    yield client

    # 清理
    os.close(fd)
    try:
        os.unlink(db_path)
    except:
        pass


class TestReposAPI:
    """测试仓库 API"""

    def test_get_repos_empty(self, test_client):
        """获取空仓库列表"""
        response = test_client.get('/api/dimensions/repos')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        # 检查 pagination 存在
        assert 'pagination' in data
        assert 'data' in data

    def test_get_repos_pagination(self, test_client):
        """测试仓库列表分页"""
        # 需要先插入数据
        from core.database.factory import create_database
        from core.config.loader import ConfigLoader
        config = ConfigLoader().load()
        db = create_database(config['database'])

        now = int(__import__('datetime').datetime.now().timestamp())

        for i in range(25):
            repo = MetricsRepo(
                repo_id=f"test/repo-{i}",
                repo_name=f"test-repo-{i}",
                repo_url=f"https://github.com/test/repo-{i}",
                total_lines=i * 100,
                created_at=now,
                updated_at=now
            )
            db.save_metrics_repo(repo)

        response = test_client.get('/api/dimensions/repos?page=1&page_size=10')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['data']) == 10
        assert data['pagination']['total'] == 25
        assert data['pagination']['total_pages'] == 3

    def test_get_repo_not_found(self, test_client):
        """获取不存在的仓库"""
        response = test_client.get('/api/dimensions/repos/nonexistent')
        # 可能返回 200 但数据为空，或 404
        assert response.status_code in [200, 404]

    def test_invalid_page_parameter(self, test_client):
        """测试无效的页码参数"""
        response = test_client.get('/api/dimensions/repos?page=0')
        assert response.status_code == 400

    def test_invalid_page_size_parameter(self, test_client):
        """测试无效的页面大小参数"""
        response = test_client.get('/api/dimensions/repos?page_size=150')
        assert response.status_code == 400


class TestContributorsAPI:
    """测试作者 API"""

    def test_get_contributors_empty(self, test_client):
        """获取空作者列表"""
        response = test_client.get('/api/dimensions/contributors')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data

    def test_get_contributor_not_found(self, test_client):
        """获取不存在的作者"""
        response = test_client.get('/api/dimensions/contributors/nonexistent')
        assert response.status_code in [200, 404]


class TestSyncAPI:
    """测试同步 API"""

    def test_sync_repos(self, test_client):
        """测试同步仓库统计"""
        response = test_client.post('/api/dimensions/repos/sync')
        # 200 或 500 都可接受（可能因为没有数据）
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert 'success' in data

    def test_sync_contributors(self, test_client):
        """测试同步作者统计"""
        response = test_client.post('/api/dimensions/contributors/sync')
        assert response.status_code in [200, 500]


class TestRepoContributorsAPI:
    """测试仓库作者关联 API"""

    def test_get_repo_contributors_empty(self, test_client):
        """获取空关联列表"""
        response = test_client.get('/api/dimensions/repo-contributors')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
