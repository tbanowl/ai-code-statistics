from importlib import import_module
from types import SimpleNamespace


_policy = import_module("core.services.merge_authorship_policy")
MergeAuthorshipPolicy = _policy.MergeAuthorshipPolicy


MERGE_SHA = "a" * 40
SOURCE_SHA = "b" * 40


def _resolution(merge_type, source_commit_shas=None):
    if source_commit_shas is None:
        source_commit_shas = [SOURCE_SHA]
    return SimpleNamespace(merge_type=merge_type, source_commit_shas=source_commit_shas)


def _source_note(prompt_id="source_prompt"):
    return f'app.py\n  {prompt_id} 1-2\n---\n{{"schema_version":"3","prompts":{{"{prompt_id}":{{}}}}}}'


def test_standard_merge_succeeds_without_upserting_notes():
    result = MergeAuthorshipPolicy().apply(
        resolution=_resolution("standard_merge"),
        target_note=_source_note("target_prompt"),
        source_notes=[_source_note()],
        final_files={"app.py": ["line 1", "line 2"]},
        output_commit_sha=MERGE_SHA,
    )

    assert result.notes_to_upsert == []
    assert result.skipped_reason is None


def test_fast_forward_skips_without_guessing_output_commit():
    result = MergeAuthorshipPolicy().apply(
        resolution=_resolution("fast_forward"),
        target_note=None,
        source_notes=[_source_note()],
        final_files={"app.py": ["line 1", "line 2"]},
        output_commit_sha=None,
    )

    assert result.notes_to_upsert == []
    assert result.skipped_reason == "fast_forward_no_merge_authorship_rewrite"


def test_unknown_skips_without_guessing():
    result = MergeAuthorshipPolicy().apply(
        resolution=_resolution("unknown", []),
        target_note=None,
        source_notes=[],
        final_files={},
        output_commit_sha=MERGE_SHA,
    )

    assert result.notes_to_upsert == []
    assert result.skipped_reason == "unknown_merge_type"


def test_squash_merge_upserts_output_note_when_output_commit_available():
    result = MergeAuthorshipPolicy().apply(
        resolution=_resolution("squash_merge", [SOURCE_SHA, "c" * 40]),
        target_note=None,
        source_notes=[_source_note(), None],
        final_files={"app.py": ["line 1", "line 2", "line 3"]},
        output_commit_sha=MERGE_SHA,
    )

    assert result.skipped_reason is None
    assert len(result.notes_to_upsert) == 1
    note = result.notes_to_upsert[0]
    assert note.commit_sha == MERGE_SHA
    assert note.content.startswith("app.py\n  source_prompt 1-2\n---\n")


def test_squash_merge_skips_when_output_commit_missing():
    result = MergeAuthorshipPolicy().apply(
        resolution=_resolution("squash_merge"),
        target_note=None,
        source_notes=[_source_note()],
        final_files={"app.py": ["line 1", "line 2"]},
        output_commit_sha=None,
    )

    assert result.notes_to_upsert == []
    assert result.skipped_reason == "missing_output_commit_sha"


def test_rebase_merge_upserts_output_note_when_output_commit_available():
    result = MergeAuthorshipPolicy().apply(
        resolution=_resolution("rebase_merge"),
        target_note=None,
        source_notes=[_source_note()],
        final_files={"app.py": ["line 1", "line 2"]},
        output_commit_sha=MERGE_SHA,
    )

    assert result.skipped_reason is None
    assert [note.commit_sha for note in result.notes_to_upsert] == [MERGE_SHA]


def test_unrecognized_merge_type_skips_conservatively():
    result = MergeAuthorshipPolicy().apply(
        resolution=_resolution("octopus_like"),
        target_note=None,
        source_notes=[_source_note()],
        final_files={"app.py": ["line 1", "line 2"]},
        output_commit_sha=MERGE_SHA,
    )

    assert result.notes_to_upsert == []
    assert result.skipped_reason == "unsupported_merge_type"
