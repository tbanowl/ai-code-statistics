import json

import core.config.loader as loader
import core.database.base as database_base
from core.database.base import Base
from core.database.models import CodeupMergeAuthorshipTask
from core.database.codeup_merge_authorship_db import CodeupMergeAuthorshipDatabase
from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql


def setup_function():
    loader.config_data = {"database": {"url": "sqlite:///:memory:", "echo": False}}
    database_base.global_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(database_base.global_engine)


def _create(db):
    return _create_with_project_id(db, "1001")


def _create_with_project_id(db, project_id):
    return db.create_or_update_task(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        project_id=project_id,
        merge_request_id="42",
        source_branch="feature/a",
        target_branch="main",
        merge_commit_sha="a" * 40,
        source_commit_shas=["b" * 40, "c" * 40],
        payload={"object_attributes": {"iid": 42}},
        event_kind="merge_request",
        payload_version_hint="v1",
        normalized_payload={"title": "PR title", "action": "merge"},
        merge_type="squash",
    )


def _create_minimal(db, **overrides):
    defaults = dict(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        project_id="1001",
        merge_request_id="99",
        source_branch="feature/min",
        target_branch="main",
        merge_commit_sha="d" * 40,
        source_commit_shas=["e" * 40],
        payload={"object_attributes": {"iid": 99}},
    )
    defaults.update(overrides)
    return db.create_or_update_task(**defaults)


def test_create_or_update_task_creates_pending_task():
    task, created = _create(CodeupMergeAuthorshipDatabase())
    assert created is True
    assert task.status == "pending"
    assert task.attempts == 0
    assert json.loads(task.source_commit_shas) == ["b" * 40, "c" * 40]


def test_create_or_update_task_allows_missing_project_id():
    task, created = _create_with_project_id(CodeupMergeAuthorshipDatabase(), None)
    assert created is True
    assert task.project_id is None
    assert task.status == "pending"


def test_create_or_update_task_is_idempotent_for_same_merge():
    db = CodeupMergeAuthorshipDatabase()
    first, first_created = _create(db)
    second, second_created = _create(db)
    assert first_created is True
    assert second_created is False
    assert second.id == first.id


def test_duplicate_failed_task_resets_attempts_and_becomes_claimable():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create(db)
    for _ in range(3):
        claimed = db.claim_next_task(max_attempts=3)
        assert claimed is not None
        db.mark_failed(claimed.id, "temporary failure")
    assert db.claim_next_task(max_attempts=3) is None

    duplicate, created = _create(db)
    retry_claim = db.claim_next_task(max_attempts=3)

    assert created is False
    assert duplicate.id == task.id
    assert retry_claim is not None
    assert retry_claim.id == task.id
    assert retry_claim.status == "processing"
    assert retry_claim.attempts == 1


def test_update_existing_task_after_duplicate_insert_race_requeues_failed_task():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create(db)
    db.mark_failed(task.id, "raced insert")

    updated = db._update_existing_task_after_duplicate_insert(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        project_id="1002",
        merge_request_id="42",
        source_branch="feature/b",
        target_branch="release",
        merge_commit_sha="a" * 40,
        source_commit_shas_json=json.dumps(["d" * 40], ensure_ascii=False, sort_keys=True),
        payload_json=json.dumps({"object_attributes": {"iid": 42, "title": "retry"}}, ensure_ascii=False, sort_keys=True),
    )

    assert updated.id == task.id
    assert updated.project_id == "1002"
    assert updated.source_branch == "feature/b"
    assert updated.target_branch == "release"
    assert updated.status == "pending"
    assert updated.attempts == 0
    assert updated.last_error is None


def test_claim_next_task_marks_processing_and_increments_attempts():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create(db)
    claimed = db.claim_next_task(max_attempts=3)
    assert claimed is not None
    assert claimed.id == task.id
    assert claimed.status == "processing"
    assert claimed.attempts == 1
    assert db.claim_next_task(max_attempts=3) is None


def test_claim_next_task_retries_failed_task_under_max_attempts():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create(db)
    first_claim = db.claim_next_task(max_attempts=3)
    assert first_claim is not None
    db.mark_failed(first_claim.id, "temporary failure")

    retry_claim = db.claim_next_task(max_attempts=3)

    assert retry_claim is not None
    assert retry_claim.id == task.id
    assert retry_claim.status == "processing"
    assert retry_claim.attempts == 2


def test_mark_success_and_failure_updates_status_fields():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create(db)
    db.mark_failed(task.id, "fetch failed")
    failed_task = db.get_task(task.id)
    assert failed_task is not None
    assert failed_task.status == "failed"
    assert failed_task.last_error == "fetch failed"
    db.mark_success(task.id, {"created": 1, "updated": 2})
    successful_task = db.get_task(task.id)
    assert successful_task is not None
    assert successful_task.status == "success"
    assert successful_task.result_summary is not None
    assert json.loads(successful_task.result_summary) == {"created": 1, "updated": 2}


def test_create_or_update_task_persists_new_fields():
    db = CodeupMergeAuthorshipDatabase()
    task, created = _create(db)
    assert created is True
    assert task.event_kind == "merge_request"
    assert task.payload_version_hint == "v1"
    assert json.loads(task.normalized_payload) == {"title": "PR title", "action": "merge"}
    assert task.merge_type == "squash"
    assert task.skipped_reason is None


def test_normalized_payload_uses_mysql_longtext_for_large_normalized_events():
    column_type = CodeupMergeAuthorshipTask.__table__.c.normalized_payload.type

    assert column_type.compile(dialect=mysql.dialect()) == "LONGTEXT"


def test_create_or_update_task_persists_skipped_reason_on_insert():
    db = CodeupMergeAuthorshipDatabase()
    task, created = db.create_or_update_task(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        project_id="1001",
        merge_request_id="55",
        source_branch="feature/x",
        target_branch="main",
        merge_commit_sha="f" * 40,
        source_commit_shas=["g" * 40],
        payload={"object_attributes": {"iid": 55}},
        skipped_reason="target branch excluded",
    )
    assert created is True
    assert task.skipped_reason == "target branch excluded"
    assert task.status == "pending"


def test_create_or_update_task_skipped_reason_preserved_on_duplicate_update():
    db = CodeupMergeAuthorshipDatabase()
    first, _ = db.create_or_update_task(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        project_id="1001",
        merge_request_id="77",
        source_branch="feature/y",
        target_branch="main",
        merge_commit_sha="h" * 40,
        source_commit_shas=["i" * 40],
        payload={"object_attributes": {"iid": 77}},
        skipped_reason="branch policy",
    )
    assert first.skipped_reason == "branch policy"
    second, second_created = db.create_or_update_task(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        project_id="1001",
        merge_request_id="77",
        source_branch="feature/y",
        target_branch="main",
        merge_commit_sha="h" * 40,
        source_commit_shas=["i" * 40],
        payload={"object_attributes": {"iid": 77}},
        skipped_reason="branch policy",
    )
    assert second_created is False
    assert second.skipped_reason == "branch policy"


def test_create_or_update_task_without_optional_new_fields():
    db = CodeupMergeAuthorshipDatabase()
    task, created = _create_minimal(db)
    assert created is True
    assert task.event_kind is None
    assert task.payload_version_hint is None
    assert task.normalized_payload is None
    assert task.merge_type is None
    assert task.skipped_reason is None


def test_mark_skipped_sets_status_and_reason():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create(db)
    db.mark_skipped(task.id, reason="target branch excluded by policy")
    refreshed = db.get_task(task.id)
    assert refreshed is not None
    assert refreshed.status == "skipped"
    assert refreshed.skipped_reason == "target branch excluded by policy"


def test_mark_skipped_with_merge_type():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create_minimal(db)
    db.mark_skipped(task.id, reason="not a squash merge", merge_type="normal")
    refreshed = db.get_task(task.id)
    assert refreshed is not None
    assert refreshed.status == "skipped"
    assert refreshed.skipped_reason == "not a squash merge"
    assert refreshed.merge_type == "normal"


def test_update_merge_type():
    db = CodeupMergeAuthorshipDatabase()
    task, _ = _create_minimal(db)
    assert task.merge_type is None
    db.update_merge_type(task.id, merge_type="squash")
    refreshed = db.get_task(task.id)
    assert refreshed is not None
    assert refreshed.merge_type == "squash"
    db.update_merge_type(task.id, merge_type="normal")
    refreshed2 = db.get_task(task.id)
    assert refreshed2 is not None
    assert refreshed2.merge_type == "normal"


def test_duplicate_update_preserves_new_fields():
    db = CodeupMergeAuthorshipDatabase()
    first, _ = _create(db)
    assert first.merge_type == "squash"
    assert first.event_kind == "merge_request"
    _, second_created = _create(db)
    assert second_created is False
    refreshed = db.get_task(first.id)
    assert refreshed is not None
    assert refreshed.merge_type == "squash"
    assert refreshed.event_kind == "merge_request"
