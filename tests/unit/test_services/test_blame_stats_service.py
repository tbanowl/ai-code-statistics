import importlib.util
import sys
from pathlib import Path


def _load_blame_stats_service_class():
    module_path = (
        Path(__file__).resolve().parents[3] / "core/services/blame_stats_service.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_blame_stats_service_module", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.BlameStatsService


BlameStatsService = _load_blame_stats_service_class()


def test_parse_line_ranges_single():
    service = BlameStatsService(None)
    assert service._parse_line_ranges("16") == [(16, 16)]


def test_parse_line_ranges_range():
    service = BlameStatsService(None)
    assert service._parse_line_ranges("6-8") == [(6, 8)]


def test_parse_line_ranges_multiple():
    service = BlameStatsService(None)
    assert service._parse_line_ranges("6-8,10-12,16") == [(6, 8), (10, 12), (16, 16)]


def test_parse_git_note_content_basic():
    service = BlameStatsService(None)
    note_content = """src/main.py
  a1b2c3d 6-8,10
---
{"prompts": {"a1b2c3d": {"agent_id": {"tool": "claude"}}}}"""

    attestations, prompts = service._parse_git_note_content(note_content)

    assert "src/main.py" in attestations
    assert "a1b2c3d" in attestations["src/main.py"]
    assert attestations["src/main.py"]["a1b2c3d"] == [(6, 8), (10, 10)]
    assert prompts["a1b2c3d"]["agent_id"]["tool"] == "claude"


def test_parse_git_note_content_multiple_files():
    service = BlameStatsService(None)
    note_content = """src/main.py
  a1b2c3d 1-5
src/utils.py
  e4f5g6h 10,15-20
---
{"prompts": {"a1b2c3d": {"agent_id": {"tool": "claude"}}, "e4f5g6h": {"agent_id": {"tool": "cursor"}}}}"""

    attestations, prompts = service._parse_git_note_content(note_content)

    assert len(attestations) == 2
    assert "src/main.py" in attestations
    assert "src/utils.py" in attestations
    assert prompts["e4f5g6h"]["agent_id"]["tool"] == "cursor"


def test_is_ai_line_match():
    service = BlameStatsService(None)
    notes_cache = {
        "abc123": (
            {"src/main.py": {"a1b2c3d": [(6, 8), (10, 12)]}},
            {"a1b2c3d": {"agent_id": {"tool": "claude"}}},
        )
    }

    is_ai, author = service._is_ai_line(7, "src/main.py", "abc123", notes_cache)

    assert is_ai is True
    assert author == "claude"


def test_is_ai_line_no_match():
    service = BlameStatsService(None)
    notes_cache = {
        "abc123": (
            {"src/main.py": {"a1b2c3d": [(6, 8)]}},
            {"a1b2c3d": {"agent_id": {"tool": "claude"}}},
        )
    }

    is_ai, author = service._is_ai_line(15, "src/main.py", "abc123", notes_cache)

    assert is_ai is False
    assert author is None


def test_parse_blame_porcelain():
    service = BlameStatsService(None)
    blame_output = """abc123 1 1 1
author Alice
	line content"""

    result = service._parse_blame_porcelain(blame_output)

    assert result[1]["commit"] == "abc123"
    assert result[1]["author"] == "Alice"
