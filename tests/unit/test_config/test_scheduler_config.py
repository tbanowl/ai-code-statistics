import pytest
from core.config.scheduler import SchedulerConfigLoader


def test_load_with_defaults():
    config = {}
    result = SchedulerConfigLoader.load(config)

    assert result["enabled"] is False
    assert result["timezone"] == "Asia/Shanghai"
    assert result["jobs"] == {}


def test_load_with_partial_config():
    config = {"scheduler": {"enabled": True}}
    result = SchedulerConfigLoader.load(config)

    assert result["enabled"] is True
    assert result["timezone"] == "Asia/Shanghai"
    assert result["jobs"] == {}


def test_load_with_full_config():
    config = {
        "scheduler": {
            "enabled": True,
            "timezone": "UTC",
            "jobs": {"task1": {"cron": "0 1 * * *"}},
        }
    }
    result = SchedulerConfigLoader.load(config)

    assert result["enabled"] is True
    assert result["timezone"] == "UTC"
    assert result["jobs"] == {"task1": {"cron": "0 1 * * *"}}
