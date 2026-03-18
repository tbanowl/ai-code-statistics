import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from core.scheduler.stats_task import AICodeStatsTask


@pytest.fixture
def mock_config():
    return {
        'git': {
            'type': 'gitlab',
            'gitlab': {
                'base_url': 'https://gitlab.example.com',
                'private_token': 'test_token'
            }
        },
        'database': {
            'type': 'sqlite',
            'sqlite': {'path': ':memory:'}
        },
        'repos': {
            'enabled_repos': [
                {'id': '123', 'name': 'test-repo', 'branch': 'main'}
            ]
        }
    }


def test_get_repos_to_analyze(mock_config):
    """测试获取仓库列表"""
    task = AICodeStatsTask(mock_config)
    repos = task._get_repos_to_analyze()

    assert len(repos) == 1
    assert repos[0]['name'] == 'test-repo'
    assert repos[0]['id'] == '123'


@patch('core.git_providers.factory.create_provider')
def test_calculate_stats(mock_create_provider, mock_config):
    """测试统计数据计算"""
    # Mock provider
    mock_provider = Mock()
    mock_provider.get_commits.return_value = [
        {
            'id': 'abc123',
            'author_name': 'John',
            'created_at': '2026-03-11T10:00:00Z',
            'stats': {'additions': 100, 'deletions': 20}
        }
    ]
    mock_provider.get_ai_notes.return_value = {
        'prompts': {'p1': {'accepted_lines': 50}}
    }
    mock_create_provider.return_value = mock_provider

    # 由于 task 已经在 __init__ 中调用 create_provider，需要手动替换
    task = AICodeStatsTask.__new__(AICodeStatsTask)
    task.config = mock_config
    task.repos_config = mock_config.get('repos', [])
    task.git_provider = mock_provider
    task.database = Mock()

    start_date = datetime(2026, 3, 1)
    end_date = datetime(2026, 3, 11)

    results = task._calculate_stats(
        [{'id': '123', 'name': 'test-repo', 'branch': 'main'}],
        start_date,
        end_date
    )

    assert results['total_lines'] == 100
    assert results['total_ai_lines'] == 50
    assert results['overall_percentage'] == 50.0
    assert len(results['repo_details']) == 1
    assert results['repo_details'][0]['name'] == 'test-repo'
