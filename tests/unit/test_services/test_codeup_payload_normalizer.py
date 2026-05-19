from core.services.codeup_payload_normalizer import CodeupPayloadNormalizer


def test_normalizes_new_codeup_payload_with_stable_ids():
    payload = {
        "version": "new",
        "object_kind": "merge_request",
        "user": {"aliyun_pk": "u-1"},
        "repository": {"git_http_url": "https://codeup.aliyun.com/org/repo.git"},
        "object_attributes": {
            "biz_id": "mr-biz-42",
            "local_id": 7,
            "id": 99,
            "project_id": "project-1",
            "source_branch": "feature/a",
            "target_branch": "main",
            "merge_commit_sha": "a" * 40,
            "action": "merge",
            "state": "merged",
            "is_update_by_push": False,
        },
        "commits": [{"id": "b" * 40}, {"sha": "c" * 40}],
    }

    event = CodeupPayloadNormalizer().normalize(payload)

    assert event.repo_url == "https://codeup.aliyun.com/org/repo.git"
    assert event.project_id == "project-1"
    assert event.merge_request_id == "mr-biz-42"
    assert event.source_branch == "feature/a"
    assert event.target_branch == "main"
    assert event.merge_commit_sha == "a" * 40
    assert event.source_commit_shas == ["b" * 40, "c" * 40]
    assert event.event_action == "merge"
    assert event.payload_version_hint == "new"
    assert event.is_update_by_push is False


def test_normalizes_legacy_payload_with_fallbacks():
    payload = {
        "object_kind": "merge_request",
        "project": {"git_http_url": "https://codeup.aliyun.com/org/legacy.git", "id": 123},
        "object_attributes": {
            "iid": 12,
            "source_branch": "feature/legacy",
            "target_branch": "master",
            "merge_commit_sha": "d" * 40,
            "state": "merged_success",
        },
    }

    event = CodeupPayloadNormalizer().normalize(payload)

    assert event.repo_url == "https://codeup.aliyun.com/org/legacy.git"
    assert event.project_id == "123"
    assert event.merge_request_id == "12"
    assert event.event_action == "merged_success"
    assert event.payload_version_hint == "legacy"
    assert event.source_commit_shas == []


def test_missing_repo_url_is_recorded_without_guessing():
    payload = {
        "object_kind": "merge_request",
        "object_attributes": {"iid": 12, "state": "opened"},
    }

    event = CodeupPayloadNormalizer().normalize(payload)

    assert event.repo_url is None
    assert event.merge_request_id == "12"
    assert event.payload_version_hint == "unknown"
