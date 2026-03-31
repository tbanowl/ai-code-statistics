import json
from unittest.mock import MagicMock, patch

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def mocked_scheduler():
    scheduler = MagicMock()
    scheduler.get_all_jobs.return_value = [{"id": "daily_aggregation", "name": "daily"}]
    scheduler.get_job_status.return_value = {
        "id": "daily_aggregation",
        "trigger": "cron",
    }
    scheduler.scheduler_db.get_task_executions.return_value = [{"id": "e1"}]
    scheduler.scheduler_db.get_task_execution.return_value = {
        "id": "e1",
        "job_id": "daily_aggregation",
    }
    app.config["_scheduler"] = scheduler
    return scheduler


class TestSchedulerAPI:
    def test_get_jobs(self, client, mocked_scheduler):
        response = client.get("/api/v1/scheduler/jobs")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["data"]["jobs"][0]["id"] == "daily_aggregation"

    def test_trigger_nonexistent_job(self, client, mocked_scheduler):
        with patch("core.scheduler.registry.TaskRegistry.get", return_value=None):
            response = client.post("/api/v1/scheduler/jobs/trigger?jobId=nonexistent")
        assert response.status_code == 404

    def test_trigger_job_success(self, client, mocked_scheduler):
        mocked_scheduler.trigger_job_with_execution.return_value = "e-123"
        with patch("core.scheduler.registry.TaskRegistry.get", return_value=object()):
            response = client.post(
                "/api/v1/scheduler/jobs/trigger?jobId=daily_aggregation"
            )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["data"]["execution_id"] == "e-123"

    def test_trigger_job_concurrent(self, client, mocked_scheduler):
        mocked_scheduler.trigger_job_with_execution.return_value = None
        mocked_scheduler.scheduler_db.get_running_task_execution.return_value = {
            "id": "running-1"
        }
        with patch("core.scheduler.registry.TaskRegistry.get", return_value=object()):
            response = client.post(
                "/api/v1/scheduler/jobs/trigger?jobId=daily_aggregation"
            )
        assert response.status_code == 409

    def test_get_executions(self, client, mocked_scheduler):
        response = client.get(
            "/api/v1/scheduler/jobs/history/executions?jobId=daily_aggregation"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert len(data["data"]["executions"]) == 1

    def test_get_execution_detail(self, client, mocked_scheduler):
        response = client.get(
            "/api/v1/scheduler/jobs/execution-detail?jobId=daily_aggregation&executionId=e1"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["data"]["id"] == "e1"

    def test_get_execution_not_found(self, client, mocked_scheduler):
        mocked_scheduler.scheduler_db.get_task_execution.return_value = None
        response = client.get(
            "/api/v1/scheduler/jobs/execution-detail?jobId=daily_aggregation&executionId=none"
        )
        assert response.status_code == 404
