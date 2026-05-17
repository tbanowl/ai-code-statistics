import pytest
from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as database_base
from core.database.base import Base
from core.database.codeup_merge_authorship_db import CodeupMergeAuthorshipDatabase
from core.services.codeup_webhook_service import (
    CodeupWebhookService,
    InvalidCodeupPayload,
)


def setup_function():
    loader.config_data = {"database": {"url": "sqlite:///:memory:", "echo": False}}
    database_base.global_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(database_base.global_engine)


def _merged_payload():
    return {
        "object_attributes": {
            "state": "merged",
            "iid": 42,
            "source_branch": "feature/codeup",
            "target_branch": "main",
            "merge_commit_sha": "a" * 40,
        },
        "project": {
            "id": 1001,
            "git_http_url": "https://codeup.aliyun.com/org/repo.git",
        },
        "commits": [
            {"id": "b" * 40},
            {"sha": "c" * 40},
        ],
    }


def test_merged_payload_creates_task():
    service = CodeupWebhookService(database=CodeupMergeAuthorshipDatabase())

    result = service.enqueue_merge_event(_merged_payload())

    assert result["success"] is True
    assert result["skipped"] is False
    assert result["created"] is True
    assert result["task_id"]
    assert result["status"] == "pending"

    task = CodeupMergeAuthorshipDatabase().get_task(result["task_id"])
    assert task is not None
    assert task.repo_url == "https://codeup.aliyun.com/org/repo.git"
    assert task.project_id == "1001"
    assert task.merge_request_id == "42"
    assert task.source_branch == "feature/codeup"
    assert task.target_branch == "main"
    assert task.merge_commit_sha == "a" * 40


def test_non_merged_payload_returns_skipped_not_merged():
    service = CodeupWebhookService(database=CodeupMergeAuthorshipDatabase())
    payload = _merged_payload()
    payload["object_attributes"]["state"] = "opened"

    result = service.enqueue_merge_event(payload)

    assert result == {"success": True, "skipped": True, "reason": "not_merged"}


def test_missing_merge_commit_sha_raises_invalid_payload():
    service = CodeupWebhookService(database=CodeupMergeAuthorshipDatabase())
    payload = _merged_payload()
    del payload["object_attributes"]["merge_commit_sha"]

    with pytest.raises(InvalidCodeupPayload, match="merge_commit_sha"):
        service.enqueue_merge_event(payload)


def test_duplicate_payload_returns_same_task_id_and_not_created():
    service = CodeupWebhookService(database=CodeupMergeAuthorshipDatabase())
    payload = _merged_payload()

    first = service.enqueue_merge_event(payload)
    second = service.enqueue_merge_event(payload)

    assert first["created"] is True
    assert second["created"] is False
    assert second["task_id"] == first["task_id"]
    assert second["status"] == "pending"
