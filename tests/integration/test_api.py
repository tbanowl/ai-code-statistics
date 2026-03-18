import pytest
from app import app


@pytest.fixture
def client():
    """测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    """测试健康检查"""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'


def test_get_projects(client):
    """测试获取项目列表"""
    response = client.get('/api/v1/projects/')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data


def test_get_departments(client):
    """测试获取部门列表"""
    response = client.get('/api/v1/projects/departments')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data


def test_get_scheduler_jobs(client):
    """测试获取调度任务"""
    response = client.get('/api/v1/scheduler/jobs')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_analyze_missing_dates(client):
    """测试缺少日期参数"""
    response = client.post('/api/v1/stats/analyze', json={})
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
