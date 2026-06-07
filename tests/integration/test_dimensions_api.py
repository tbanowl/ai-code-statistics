from unittest.mock import MagicMock, patch

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_list_repositories_api(client):
    with patch("api.routes.stats.StatsDatabase") as db_cls:
        db_cls.return_value.get_repositories.return_value = {
            "items": [{"id": "r1", "repo_path": "owner/repo"}],
            "total": 1,
            "page": 1,
            "page_size": 10,
        }
        resp = client.get("/api/stats/repositories?limit=10&offset=0")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["pagination"]["total"] == 1
    assert data["pagination"]["page_size"] == 10
    assert data["data"][0]["repo_path"] == "owner/repo"


def test_list_contributors_api(client):
    with patch("api.routes.stats.StatsDatabase") as db_cls:
        db_cls.return_value.get_contributors.return_value = {
            "items": [{"id": "c1", "name": "alice"}],
            "total": 1,
            "page": 1,
            "page_size": 5,
        }
        resp = client.get("/api/stats/contributors?limit=5&offset=0")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["pagination"]["total"] == 1
    assert data["data"][0]["name"] == "alice"


def test_repository_consolidation_report_api(client):
    with patch("api.routes.stats.StatsDatabase") as db_cls:
        db_cls.return_value.get_repository_consolidation_report.return_value = {
            "unknown_repository": {
                "id": "u1",
                "repo_path": "未知仓库",
                "repo_name": "未知仓库",
            },
            "unknown_repository_refs": {"daily_stats": 2, "repo_contributors": 1},
            "invalid_repositories_count": 1,
            "invalid_repositories": [
                {
                    "id": "bad1",
                    "repo_path": "",
                    "repo_name": "",
                    "daily_stats_refs": 1,
                    "repo_contributor_refs": 1,
                }
            ],
        }
        resp = client.get("/api/stats/repositories/consolidation-report")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["unknown_repository"]["repo_path"] == "未知仓库"
    assert data["data"]["invalid_repositories_count"] == 1


def test_query_daily_stats_api(client):
    with patch("api.routes.stats.StatsDatabase") as db_cls:
        db_cls.return_value.get_daily_stats_paginated.return_value = {
            "items": [{"ai_accepted": 2, "human_additions": 3}],
            "total": 1,
            "page": 1,
            "page_size": 20,
        }
        resp = client.get("/api/stats/daily?start_date=1&end_date=2")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"][0]["ai_accepted"] == 2


def test_aggregate_stats_api(client):
    with patch("api.routes.stats.StatsDatabase") as db_cls:
        db = db_cls.return_value
        db.get_aggregated_stats.return_value = [
            {
                "stat_date": 20260605,
                "ai_additions": 30,
                "ai_accepted": 25,
                "human_additions": 75,
                "git_diff_added_lines": 100,
            },
            {
                "stat_date": 20260606,
                "ai_additions": 80,
                "ai_accepted": 75,
                "human_additions": 25,
                "git_diff_added_lines": 100,
            },
        ]
        db.query_committed_events.return_value = [
            {"ai_accepted": 0},
            {"ai_accepted": 2},
            {"ai_accepted": 1},
        ]
        resp = client.post(
            "/api/stats/aggregate",
            json={"start_date": 1, "end_date": 2},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_commits"] == 3
    assert data["ai_commits"] == 2
    assert data["total_lines"] == 200
    assert data["ai_lines"] == 100
    assert data["ai_lines_pct"] == 50.0


def test_stats_query_returns_filter_names(client):
    with patch("api.routes.stats.StatsDatabase") as db_cls:
        db = db_cls.return_value
        db.get_aggregated_stats.return_value = [
            {
                "stat_date": 20260605,
                "ai_additions": 30,
                "ai_accepted": 25,
                "human_additions": 75,
                "git_diff_added_lines": 100,
            },
            {
                "stat_date": 20260606,
                "ai_additions": 80,
                "ai_accepted": 75,
                "human_additions": 25,
                "git_diff_added_lines": 100,
            }
        ]
        db.get_repository_by_id.return_value = {
            "id": "r1",
            "repo_name": "org/repo",
        }
        db.get_contributor_by_id.return_value = {
            "id": "c1",
            "name": "Alice",
        }

        resp = client.get(
            "/api/stats/?start_date=1&end_date=2&repo_id=r1&contributor_id=c1"
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["filters"]["repo_name"] == "org/repo"
    assert data["data"]["filters"]["contributor_name"] == "Alice"
    assert data["data"]["summary"]["total_ai_generated"] == 110
    assert data["data"]["summary"]["total_ai_accepted"] == 100
    assert data["data"]["summary"]["total_human"] == 100
    assert data["data"]["summary"]["total_lines"] == 200
    assert data["data"]["summary"]["avg_ai_percentage"] == 50.0


def test_trigger_aggregate_with_filters(client):
    scheduler = MagicMock()
    scheduler.trigger_job_with_execution.return_value = "exec-1"

    old_scheduler = app.config.get("_scheduler")
    app.config["_scheduler"] = scheduler
    try:
        with patch("api.routes.stats.StatsDatabase") as db_cls:
            db_cls.return_value.get_repository_by_id.return_value = {
                "id": "r1",
                "repo_path": "owner/repo",
            }
            db_cls.return_value.get_contributor_by_id.return_value = {
                "id": "c1",
                "name": "Alice",
                "contributor_uid": "alice",
            }

            resp = client.post(
                "/api/stats/stats/aggregate",
                json={
                    "start_date": 1000,
                    "end_date": 2000,
                    "repo_id": "r1",
                    "contributor_id": "c1",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        scheduler.trigger_job_with_execution.assert_called_once_with(
            "daily_aggregation",
            {
                "start_date": 1000,
                "end_date": 2000,
                "repo_url": "owner/repo",
                "contributor": "alice",
            },
        )
    finally:
        app.config["_scheduler"] = old_scheduler


def test_trigger_aggregate_rejects_invalid_filters(client):
    scheduler = MagicMock()
    scheduler.trigger_job_with_execution.return_value = "exec-1"

    old_scheduler = app.config.get("_scheduler")
    app.config["_scheduler"] = scheduler
    try:
        with patch("api.routes.stats.StatsDatabase") as db_cls:
            db_cls.return_value.get_repository_by_id.return_value = None
            resp = client.post("/api/stats/stats/aggregate", json={"repo_id": "missing"})

        assert resp.status_code == 404
        data = resp.get_json()
        assert data["success"] is False
        assert data["error"] == "repo_id not found"
        scheduler.trigger_job_with_execution.assert_not_called()
    finally:
        app.config["_scheduler"] = old_scheduler
