import os
import tempfile

import pytest
import yaml

import core.config.loader as loader


@pytest.fixture(autouse=True)
def reset_config_cache():
    loader.config_data = {}
    yield
    loader.config_data = {}


@pytest.fixture
def temp_config_file():
    fd, path = tempfile.mkstemp(suffix=".yaml")
    config_data = {
        "features": {"enabled": True},
        "git": {
            "type": "gitlab",
            "gitlab": {
                "base_url": "https://gitlab.example.com",
                "private_token": "${TEST_TOKEN}",
            },
        },
        "database": {"url": "sqlite:///./tmp-test.db", "echo": False},
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f)
    os.close(fd)
    yield path
    os.unlink(path)


def test_load_config_by_path_with_env_substitution(temp_config_file, monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", "token-123")
    config = loader.load_config_by_path(temp_config_file)
    assert config["features"]["enabled"] is True
    assert config["git"]["type"] == "gitlab"
    assert config["git"]["gitlab"]["private_token"] == "token-123"


def test_load_config_uses_cached_data(temp_config_file):
    first = loader.load_config_by_path(temp_config_file)
    second = loader.load_config_by_path(None)
    assert second is first


def test_load_config_invalid_raises(tmp_path):
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "features": {"enabled": False},
                "git": {"type": "unknown"},
                "database": {"url": "sqlite:///./x.db"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        loader.load_config_by_path(str(config_path))
