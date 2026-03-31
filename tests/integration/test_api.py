import pytest
from app import app


@pytest.fixture
def client():
    """测试客户端"""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"


def test_get_scheduler_jobs(client):
    response = client.get("/api/v1/scheduler/jobs")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True


def test_stats_v2_daily_missing_dates(client):
    response = client.get("/api/v2/stats/daily")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "data" in data
