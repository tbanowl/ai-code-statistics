from core.database.models import (
    MetricsEventsAgentUsage,
    MetricsEventsCheckpoint,
    MetricsEventsCommitted,
    MetricsEventsInstallHooks,
    MetricsEventsRaw,
)


def test_metrics_raw_defaults_and_fields():
    row = MetricsEventsRaw(
        batch_id="batch-1",
        event_count=2,
        payload_json="{}",
        received_at=1710000000000,
    )
    data = row.to_dict()
    assert data["batch_id"] == "batch-1"
    assert data["version"] in (None, 1)
    assert data["event_count"] == 2


def test_metrics_committed_supports_json_fields():
    row = MetricsEventsCommitted(
        raw_id="raw-1",
        timestamp=1710000000000,
        repo_url="https://github.com/o/r",
        author="alice",
        git_diff_added_lines=120,
        ai_additions={"model-a": 50},
        total_ai_additions={"model-a": 50},
    )
    data = row.to_dict()
    assert data["raw_id"] == "raw-1"
    assert data["repo_url"] == "https://github.com/o/r"
    assert data["ai_additions"]["model-a"] == 50


def test_metrics_checkpoint_fields():
    row = MetricsEventsCheckpoint(
        raw_id="raw-1",
        timestamp=1710000000000,
        file_path="src/main.py",
        lines_added=10,
        lines_deleted=2,
    )
    data = row.to_dict()
    assert data["file_path"] == "src/main.py"
    assert data["lines_added"] == 10


def test_metrics_agent_usage_and_install_hooks_defaults():
    usage = MetricsEventsAgentUsage(raw_id="raw-1", timestamp=1710000000000)
    hook = MetricsEventsInstallHooks(
        raw_id="raw-1",
        timestamp=1710000000000,
        tool_id="pre-commit",
        status="success",
    )
    assert usage.event_id in (None, 2)
    assert hook.event_id in (None, 3)
