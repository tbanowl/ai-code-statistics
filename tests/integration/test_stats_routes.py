from unittest.mock import patch

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_get_committed_report_api(client):
    with patch("api.routes.stats.StatsDatabase") as db_cls:
        db = db_cls.return_value
        db.get_committed_events_paginated.return_value = {
            "items": [
                {
                    "id": "c1",
                    "repo_url": "https://github.com/acme/repo.git",
                    "author": "alice",
                    "branch": "main",
                    "timestamp": 1710000000001,
                    "human_additions": 6,
                    "git_diff_deleted_lines": 2,
                    "git_diff_added_lines": 10,
                    "first_checkpoint_ts": 1710000000002,
                    "commit_subject": "feat: add report",
                    "commit_body": "report body",
                    "tool_model_pairs": "cursor, copilot",
                    "mixed_additions": 5,
                    "ai_additions": 4,
                    "ai_accepted": 3,
                    "total_ai_additions": 9,
                    "total_ai_deletions": 7,
                    "base_commit_sha": "abc123",
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
        }

        resp = client.get(
            "/api/stats/commits?page=1&page_size=20&start_date=1&end_date=2&repo_url=acme&author=alice&branch=main"
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["pagination"] == {"total": 1, "page": 1, "page_size": 20}
    assert data["data"][0]["tool_model_pairs"] == "cursor, copilot"

    db.get_committed_events_paginated.assert_called_once_with(
        page=1,
        page_size=20,
        start_ts=1,
        end_ts=2,
        repo_url="acme",
        author="alice",
        branch="main",
    )
