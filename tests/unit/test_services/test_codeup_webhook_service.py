import json

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


def _new_version_merged_payload():
    return {
        "version": "new",
        "object_attributes": {
            "state": "merged",
            "action": "merge",
            "biz_id": "mr-biz-42",
            "project_id": "1001",
            "source_branch": "feature/codeup",
            "target_branch": "main",
            "merge_commit_sha": "a" * 40,
        },
        "repository": {
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
    assert task.repo_url == "codeup.aliyun.com/org/repo"
    assert task.project_id == "1001"
    assert task.merge_request_id == "42"
    assert task.source_branch == "feature/codeup"
    assert task.target_branch == "main"
    assert task.merge_commit_sha == "a" * 40


def test_new_version_merged_payload_stores_normalizer_fields():
    service = CodeupWebhookService(database=CodeupMergeAuthorshipDatabase())

    result = service.enqueue_merge_event(_new_version_merged_payload())

    assert result["success"] is True
    assert result["created"] is True

    task = CodeupMergeAuthorshipDatabase().get_task(result["task_id"])
    assert task is not None
    assert task.event_kind == "merge_candidate"
    assert task.payload_version_hint == "new"
    assert task.normalized_payload is not None
    normalized = json.loads(task.normalized_payload)
    assert normalized["repo_url"] == "codeup.aliyun.com/org/repo"
    assert normalized["merge_request_id"] == "mr-biz-42"


def test_open_payload_returns_skipped_mr_update():
    service = CodeupWebhookService(database=CodeupMergeAuthorshipDatabase())
    payload = _merged_payload()
    payload["object_attributes"]["state"] = "open"

    result = service.enqueue_merge_event(payload)

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["reason"] == "not_merge_completion"
    assert result["event_kind"] == "mr_update"


def test_missing_merge_commit_sha_on_merged_returns_skipped():
    service = CodeupWebhookService(database=CodeupMergeAuthorshipDatabase())
    payload = _merged_payload()
    del payload["object_attributes"]["merge_commit_sha"]

    result = service.enqueue_merge_event(payload)

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["event_kind"] == "mr_update"


def test_missing_repo_url_raises_invalid_payload():
    service = CodeupWebhookService(database=CodeupMergeAuthorshipDatabase())
    payload = {
        "object_attributes": {
            "iid": 42,
            "state": "merged",
            "source_branch": "feature/a",
            "target_branch": "main",
            "merge_commit_sha": "a" * 40,
        },
    }

    with pytest.raises(InvalidCodeupPayload, match="missing_required_identity"):
        service.enqueue_merge_event(payload)


def test_missing_merge_request_id_raises_invalid_payload():
    service = CodeupWebhookService(database=CodeupMergeAuthorshipDatabase())
    payload = {
        "object_attributes": {
            "state": "merged",
            "source_branch": "feature/a",
            "target_branch": "main",
            "merge_commit_sha": "a" * 40,
        },
        "project": {
            "id": 1001,
            "git_http_url": "https://codeup.aliyun.com/org/repo.git",
        },
    }

    with pytest.raises(InvalidCodeupPayload, match="missing_required_identity"):
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


def test_push_update_event_is_skipped():
    service = CodeupWebhookService(database=CodeupMergeAuthorshipDatabase())
    payload = _merged_payload()
    payload["object_attributes"]["is_update_by_push"] = True

    result = service.enqueue_merge_event(payload)

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["event_kind"] == "push_update"
    assert result["reason"] == "push_update"
