from unittest.mock import MagicMock, patch

import importlib.util
import sys
from pathlib import Path


def _load_blame_stats_service_class():
    module_path = (
        Path(__file__).resolve().parents[3] / "core/services/blame_stats_service.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_blame_stats_integration_module", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.BlameStatsService


BlameStatsService = _load_blame_stats_service_class()


def test_analyze_file_blame_integration():
    mock_db = MagicMock()
    mock_db.get_git_notes_batch.return_value = {
        "abc123": 'src/test.py\n  a1b2c3d 1-2\n---\n{"prompts": {"a1b2c3d": {"agent_id": {"tool": "claude"}}}}'
    }

    service = BlameStatsService(mock_db)
    service._run_git_blame = MagicMock(
        return_value="""abc123 1 1 1
author Alice
	first line
abc123 2 2 1
author Alice
	second line
def456 3 3 1
author Bob
	third line"""
    )

    with patch("os.path.getsize", return_value=12):
        result = service.analyze_file_blame(
            "https://example.com/repo.git",
            "/tmp/repo/src/test.py",
            "/tmp/repo",
            "headsha",
        )

    assert result is not None
    assert result.total_lines == 3
    assert result.ai_lines == 2
    assert result.non_ai_lines == 1
    assert result.contributor_stats["Alice"]["ai_lines"] == 2
    assert result.contributor_stats["Bob"]["non_ai_lines"] == 1
