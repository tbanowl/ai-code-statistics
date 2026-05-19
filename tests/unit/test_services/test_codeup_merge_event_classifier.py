from core.services.codeup_merge_event_classifier import CodeupMergeEventClassifier
from core.services.codeup_payload_normalizer import NormalizedCodeupMergeEvent


def _event(**overrides):
    values = {
        "repo_url": "https://codeup.aliyun.com/org/repo.git",
        "project_id": "100",
        "merge_request_id": "42",
        "source_branch": "feature/a",
        "target_branch": "main",
        "merge_commit_sha": "a" * 40,
        "source_commit_shas": [],
        "event_action": "merged",
        "payload_version_hint": "new",
        "is_update_by_push": False,
        "raw_payload": {},
    }
    values.update(overrides)
    return NormalizedCodeupMergeEvent(**values)


def test_merged_event_is_merge_candidate():
    result = CodeupMergeEventClassifier().classify(_event())
    assert result.event_kind == "merge_candidate"
    assert result.should_enqueue is True
    assert result.http_status == 200


def test_push_update_is_skipped():
    result = CodeupMergeEventClassifier().classify(_event(event_action="update", is_update_by_push=True))
    assert result.event_kind == "push_update"
    assert result.should_enqueue is False
    assert result.skipped_reason == "push_update"


def test_open_event_is_skipped_as_mr_update():
    result = CodeupMergeEventClassifier().classify(_event(event_action="open", merge_commit_sha=None))
    assert result.event_kind == "mr_update"
    assert result.should_enqueue is False
    assert result.skipped_reason == "not_merge_completion"


def test_missing_repo_is_invalid():
    result = CodeupMergeEventClassifier().classify(_event(repo_url=None))
    assert result.event_kind == "invalid"
    assert result.should_enqueue is False
    assert result.http_status == 400
