import json
from importlib import import_module


MergeAuthorshipCalculator = import_module(
    "core.services.merge_authorship_calculator"
).MergeAuthorshipCalculator


TARGET_NOTE = (
    'app.py\n'
    '  target_prompt 1-2\n'
    '---\n'
    '{"schema_version":"3","prompts":{"target_prompt":{}}}'
)

SOURCE_NOTE = (
    'app.py\n'
    '  source_prompt 2-3\n'
    '---\n'
    '{"schema_version":"3","prompts":{"source_prompt":{}}}'
)


def _split_note(content):
    body, metadata = content.split('\n---\n', 1)
    return body, json.loads(metadata)


def test_merge_notes_keeps_target_priority_and_adds_source_lines():
    calculator = MergeAuthorshipCalculator()

    result = calculator.merge_notes(
        target_note=TARGET_NOTE,
        source_notes=[SOURCE_NOTE],
        final_files={"app.py": ["line 1", "line 2", "line 3"]},
    )

    body, metadata = _split_note(result)

    assert "app.py" in body
    assert "  target_prompt 1-2" in body
    assert "  source_prompt 3" in body
    assert "source_prompt 2" not in body
    assert set(metadata["prompts"].keys()) == {"target_prompt", "source_prompt"}


def test_missing_source_notes_do_not_fail_or_change_target_output():
    calculator = MergeAuthorshipCalculator()

    result = calculator.merge_notes(
        target_note=TARGET_NOTE,
        source_notes=[None, ""],
        final_files={"app.py": ["line 1", "line 2"]},
    )

    body, metadata = _split_note(result)

    assert "  target_prompt 1-2" in body
    assert "source_prompt" not in body
    assert set(metadata["prompts"].keys()) == {"target_prompt"}
