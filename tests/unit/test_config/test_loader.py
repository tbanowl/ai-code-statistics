import pytest
import os
import tempfile
import yaml
import json
from core.config.loader import ConfigLoader


@pytest.fixture
def temp_config_file():
    """创建临时配置文件"""
    fd, path = tempfile.mkstemp(suffix='.yaml')
    config_data = {
        'features': {'enabled': True, 'auto_stats': True},
        'git': {'type': 'gitlab', 'gitlab': {'base_url': 'https://gitlab.com', 'private_token': '${TEST_TOKEN}'}},
        'database': {'type': 'sqlite', 'sqlite': {'path': 'data/test.db'}}
    }
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f)
    os.close(fd)
    yield path
    os.unlink(path)


def test_load_config(temp_config_file):
    """测试配置加载"""
    loader = ConfigLoader(temp_config_file)
    config = loader.load()

    assert config['features']['enabled'] is True
    assert config['git']['type'] == 'gitlab'
    assert config['database']['type'] == 'sqlite'


def test_get_config_value(temp_config_file):
    """测试获取配置值"""
    os.environ['TEST_TOKEN'] = 'test-token-123'
    loader = ConfigLoader(temp_config_file)
    config = loader.load()

    assert loader.get('features.enabled') is True
    assert loader.get('git.type') == 'gitlab'
    assert loader.get('git.gitlab.private_token') == 'test-token-123'
    assert loader.get('non.existent.key', 'default') == 'default'


def test_invalid_config():
    """测试无效配置"""
    fd, path = tempfile.mkstemp(suffix='.yaml')
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump({'features': {'enabled': False}, 'git': {'type': 'unknown'}}, f)
    os.close(fd)

    loader = ConfigLoader(path)
    with pytest.raises(ValueError):
        loader.load()

    os.unlink(path)
