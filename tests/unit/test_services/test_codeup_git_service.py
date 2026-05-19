import subprocess
from pathlib import Path
from importlib import import_module

import pytest


codeup_git_service = import_module("core.services.codeup_git_service")
CodeupGitError = codeup_git_service.CodeupGitError
CodeupGitService = codeup_git_service.CodeupGitService


class FakeRunner:
    def __init__(self, stdout_by_args):
        self.stdout_by_args = stdout_by_args
        self.calls = []

    def __call__(self, args, cwd, timeout):
        self.calls.append((args, cwd, timeout))
        return self.stdout_by_args[tuple(args)]


def test_rev_list_calls_git_rev_list_and_splits_stdout_lines():
    runner = FakeRunner({("git", "rev-list", "base..head"): "abc\ndef\n"})
    service = CodeupGitService(runner=runner)

    result = service.rev_list(Path("/repo"), "base..head")

    assert result == ["abc", "def"]
    assert runner.calls == [(["git", "rev-list", "base..head"], Path("/repo"), 60)]


def test_commit_metadata_parses_author_and_commit_time():
    sha = "a" * 40
    runner = FakeRunner(
        {
            (
                "git",
                "show",
                "-s",
                "--format=%an%x00%ae%x00%ct",
                sha,
            ): "Ada Lovelace\x00ada@example.com\x001715555555\n"
        }
    )
    service = CodeupGitService(runner=runner)

    result = service.commit_metadata(Path("/repo"), sha)

    assert result == {
        "author_name": "Ada Lovelace",
        "author_email": "ada@example.com",
        "commit_time": 1715555555,
    }


def test_changed_files_splits_name_only_diff_output():
    runner = FakeRunner(
        {("git", "diff", "--name-only", "base", "head"): "app.py\ncore/a.py\n"}
    )
    service = CodeupGitService(runner=runner)

    result = service.changed_files(Path("/repo"), "base", "head")

    assert result == ["app.py", "core/a.py"]


def test_show_file_lines_returns_file_content_lines_at_commit():
    runner = FakeRunner({("git", "show", "abc1234:app.py"): "one\ntwo\n"})
    service = CodeupGitService(runner=runner)

    result = service.show_file_lines(Path("/repo"), "abc1234", "app.py")

    assert result == ["one", "two"]


def test_ensure_repo_clones_then_fetches_required_refs_and_commits(tmp_path):
    runner = FakeRunner(
        {
            ("git", "clone", "https://codeup.aliyun.com/org/repo.git", str(tmp_path / "repo")): "",
            ("git", "fetch", "origin", "main", "feature/a", "a" * 40, "b" * 40): "",
        }
    )
    service = CodeupGitService(runner=runner)

    result = service.ensure_repo(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        repo_dir=tmp_path / "repo",
        target_branch="main",
        source_branch="feature/a",
        merge_commit_sha="a" * 40,
        source_commit_shas=["b" * 40],
        clone_timeout=12,
        fetch_timeout=34,
    )

    assert result == tmp_path / "repo"
    assert runner.calls == [
        (["git", "clone", "https://codeup.aliyun.com/org/repo.git", str(tmp_path / "repo")], tmp_path, 12),
        (["git", "fetch", "origin", "main", "feature/a", "a" * 40, "b" * 40], tmp_path / "repo", 34),
    ]


def test_ensure_repo_existing_repo_fetches_required_refs_and_commits(tmp_path):
    repo_dir = tmp_path / "repo"
    (repo_dir / ".git").mkdir(parents=True)
    runner = FakeRunner(
        {
            ("git", "fetch", "origin", "main", "feature/a", "a" * 40, "b" * 40): "",
        }
    )
    service = CodeupGitService(runner=runner)

    result = service.ensure_repo(
        repo_url="https://codeup.aliyun.com/org/repo.git",
        repo_dir=repo_dir,
        target_branch="main",
        source_branch="feature/a",
        merge_commit_sha="a" * 40,
        source_commit_shas=["b" * 40],
        clone_timeout=12,
        fetch_timeout=34,
    )

    assert result == repo_dir
    assert runner.calls == [
        (["git", "fetch", "origin", "main", "feature/a", "a" * 40, "b" * 40], repo_dir, 34),
    ]


def test_merge_base_and_rev_list_commands_support_source_sha_derivation():
    runner = FakeRunner(
        {
            ("git", "merge-base", "feature/a", "main"): "c" * 40 + "\n",
            ("git", "rev-list", "c" * 40 + "..feature/a"): "b" * 40 + "\n" + "d" * 40 + "\n",
        }
    )
    service = CodeupGitService(runner=runner)

    base = service.merge_base(Path("/repo"), "feature/a", "main")
    commits = service.rev_list(Path("/repo"), f"{base}..feature/a")

    assert base == "c" * 40
    assert commits == ["b" * 40, "d" * 40]
    assert runner.calls == [
        (["git", "merge-base", "feature/a", "main"], Path("/repo"), 60),
        (["git", "rev-list", "c" * 40 + "..feature/a"], Path("/repo"), 60),
    ]


@pytest.mark.parametrize("revision_range", ["", "   ", "-n1"])
def test_rev_list_rejects_empty_or_option_like_revision_ranges(revision_range):
    service = CodeupGitService(runner=FakeRunner({}))

    with pytest.raises(CodeupGitError, match="revision_range"):
        service.rev_list(Path("/repo"), revision_range)


@pytest.mark.parametrize("ref", ["", "   ", "-main"])
def test_changed_files_rejects_empty_or_option_like_refs(ref):
    service = CodeupGitService(runner=FakeRunner({}))

    with pytest.raises(CodeupGitError, match="ref"):
        service.changed_files(Path("/repo"), ref, "head")


@pytest.mark.parametrize("commit_sha", ["", "abc123", "g" * 7, "a" * 41, "-abc1234"])
def test_commit_methods_require_safe_hex_sha(commit_sha):
    service = CodeupGitService(runner=FakeRunner({}))

    with pytest.raises(CodeupGitError, match="commit_sha"):
        service.commit_metadata(Path("/repo"), commit_sha)

    with pytest.raises(CodeupGitError, match="commit_sha"):
        service.show_file_lines(Path("/repo"), commit_sha, "app.py")


@pytest.mark.parametrize("file_path", ["", "   ", "/etc/passwd", "../secret", "a/../b", "-file"])
def test_show_file_lines_rejects_unsafe_file_paths(file_path):
    service = CodeupGitService(runner=FakeRunner({}))

    with pytest.raises(CodeupGitError, match="file_path"):
        service.show_file_lines(Path("/repo"), "a" * 7, file_path)


def test_run_rejects_missing_or_non_directory_cwd(tmp_path):
    missing = tmp_path / "missing"
    service = CodeupGitService()

    with pytest.raises(CodeupGitError, match="working directory"):
        service._run(["git", "status"], missing)

    file_path = tmp_path / "file"
    file_path.write_text("not a directory")
    with pytest.raises(CodeupGitError, match="working directory"):
        service._run(["git", "status"], file_path)


def test_run_uses_expected_subprocess_kwargs_without_shell(monkeypatch, tmp_path):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args=kwargs["args"], returncode=0, stdout="ok\n")

    monkeypatch.setattr(codeup_git_service.subprocess, "run", fake_run)

    result = CodeupGitService()._run(["git", "status"], tmp_path, timeout=12)

    assert result == "ok\n"
    assert calls == [
        (
            (),
            {
                "args": ["git", "status"],
                "cwd": tmp_path,
                "timeout": 12,
                "text": True,
                "capture_output": True,
                "check": True,
            },
        )
    ]
    assert "shell" not in calls[0][1]


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, ["git", "status"], stderr="boom"),
        subprocess.TimeoutExpired(["git", "status"], timeout=1),
        FileNotFoundError("git missing"),
    ],
)
def test_run_wraps_subprocess_errors(monkeypatch, tmp_path, error):
    def fake_run(**kwargs):
        raise error

    monkeypatch.setattr(codeup_git_service.subprocess, "run", fake_run)

    with pytest.raises(CodeupGitError, match="git command failed") as exc_info:
        CodeupGitService()._run(["git", "status"], tmp_path)

    assert exc_info.value.__cause__ is error


@pytest.mark.parametrize(
    "stdout",
    ["Ada\x00ada@example.com\n", "Ada\x00ada@example.com\x00not-int\n"],
)
def test_commit_metadata_wraps_malformed_output(stdout):
    runner = FakeRunner(
        {
            (
                "git",
                "show",
                "-s",
                "--format=%an%x00%ae%x00%ct",
                "a" * 7,
            ): stdout
        }
    )
    service = CodeupGitService(runner=runner)

    with pytest.raises(CodeupGitError, match="Malformed commit metadata"):
        service.commit_metadata(Path("/repo"), "a" * 7)


def test_commit_parents_parses_show_format_p_output():
    sha = "a" * 40
    parent1 = "b" * 40
    parent2 = "c" * 40
    runner = FakeRunner(
        {("git", "show", "-s", "--format=%P", sha): f"{parent1} {parent2}\n"}
    )
    service = CodeupGitService(runner=runner)

    result = service.commit_parents(Path("/repo"), sha)

    assert result == [parent1, parent2]
    assert runner.calls == [
        (["git", "show", "-s", "--format=%P", sha], Path("/repo"), 60)
    ]


def test_commit_parents_returns_single_parent_for_ordinary_commit():
    sha = "a" * 40
    parent = "b" * 40
    runner = FakeRunner(
        {("git", "show", "-s", "--format=%P", sha): f"{parent}\n"}
    )
    service = CodeupGitService(runner=runner)

    result = service.commit_parents(Path("/repo"), sha)

    assert result == [parent]


def test_commit_parents_returns_empty_for_root_commit():
    sha = "a" * 40
    runner = FakeRunner(
        {("git", "show", "-s", "--format=%P", sha): "\n"}
    )
    service = CodeupGitService(runner=runner)

    result = service.commit_parents(Path("/repo"), sha)

    assert result == []


@pytest.mark.parametrize("commit_sha", ["", "abc", "g" * 7, "-abc1234"])
def test_commit_parents_rejects_invalid_sha(commit_sha):
    service = CodeupGitService(runner=FakeRunner({}))

    with pytest.raises(CodeupGitError, match="commit_sha"):
        service.commit_parents(Path("/repo"), commit_sha)
