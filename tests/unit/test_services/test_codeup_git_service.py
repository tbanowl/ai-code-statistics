import subprocess
from pathlib import Path
from importlib import import_module

import pytest


codeup_git_service = import_module("core.services.codeup_git_service")
CodeupGitError = codeup_git_service.CodeupGitError
CodeupGitService = codeup_git_service.CodeupGitService

VALID_PRIVATE_KEY = """-----BEGIN OPENSSH PRIVATE KEY-----
abc123
-----END OPENSSH PRIVATE KEY-----
"""


class FakeRunner:
    def __init__(self, stdout_by_args):
        self.stdout_by_args = stdout_by_args
        self.calls = []

    def __call__(self, args, cwd, timeout, env=None):
        self.calls.append((args, cwd, timeout, env))
        return self.stdout_by_args[tuple(args)]


def test_rev_list_calls_git_rev_list_and_splits_stdout_lines():
    runner = FakeRunner({("git", "rev-list", "base..head"): "abc\ndef\n"})
    service = CodeupGitService(runner=runner)

    result = service.rev_list(Path("/repo"), "base..head")

    assert result == ["abc", "def"]
    assert runner.calls == [(["git", "rev-list", "base..head"], Path("/repo"), 60, None)]


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
        repo_url="codeup.aliyun.com/org/repo",
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
        (["git", "clone", "https://codeup.aliyun.com/org/repo.git", str(tmp_path / "repo")], tmp_path, 12, None),
        (["git", "fetch", "origin", "main", "feature/a", "a" * 40, "b" * 40], tmp_path / "repo", 34, None),
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
        repo_url="codeup.aliyun.com/org/repo",
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
        (["git", "fetch", "origin", "main", "feature/a", "a" * 40, "b" * 40], repo_dir, 34, None),
    ]


def test_ensure_repo_with_private_key_clones_and_fetches_with_git_ssh_command(tmp_path):
    ssh_repo_url = "ssh://git@codeup.aliyun.com/org/repo.git"
    runner = FakeRunner(
        {
            ("git", "clone", ssh_repo_url, str(tmp_path / "repo")): "",
            ("git", "fetch", "origin", "main", "feature/a", "a" * 40, "b" * 40): "",
        }
    )
    service = CodeupGitService(runner=runner)

    result = service.ensure_repo(
        repo_url="codeup.aliyun.com/org/repo",
        repo_dir=tmp_path / "repo",
        target_branch="main",
        source_branch="feature/a",
        merge_commit_sha="a" * 40,
        source_commit_shas=["b" * 40],
        clone_timeout=12,
        fetch_timeout=34,
        private_key=VALID_PRIVATE_KEY,
    )

    assert result == tmp_path / "repo"
    assert len(runner.calls) == 2
    clone_call, fetch_call = runner.calls
    assert clone_call[0] == ["git", "clone", ssh_repo_url, str(tmp_path / "repo")]
    assert fetch_call[0] == ["git", "fetch", "origin", "main", "feature/a", "a" * 40, "b" * 40]
    for _, _, _, env in runner.calls:
        assert env is not None
        ssh_command = env["GIT_SSH_COMMAND"]
        assert "ssh -i" in ssh_command
        assert "StrictHostKeyChecking=no" in ssh_command
        assert "IdentitiesOnly=yes" in ssh_command


def test_repo_url_for_auth_normalizes_scp_style_url_with_private_key():
    service = CodeupGitService()

    result = service._repo_url_for_auth(
        "git@codeup.aliyun.com:org/repo.git",
        VALID_PRIVATE_KEY,
    )

    assert result == "ssh://git@codeup.aliyun.com/org/repo.git"


def test_existing_repo_fetches_with_private_key_env(tmp_path):
    repo_dir = tmp_path / "repo"
    (repo_dir / ".git").mkdir(parents=True)
    ssh_repo_url = "ssh://git@codeup.aliyun.com/org/repo.git"
    runner = FakeRunner(
        {
            ("git", "remote", "set-url", "origin", ssh_repo_url): "",
            ("git", "fetch", "origin", "main", "feature/a", "a" * 40): "",
        }
    )
    service = CodeupGitService(runner=runner)

    result = service.ensure_repo(
        repo_url="codeup.aliyun.com/org/repo",
        repo_dir=repo_dir,
        target_branch="main",
        source_branch="feature/a",
        merge_commit_sha="a" * 40,
        source_commit_shas=[],
        clone_timeout=12,
        fetch_timeout=34,
        private_key=VALID_PRIVATE_KEY,
    )

    assert result == repo_dir
    assert len(runner.calls) == 2
    set_url_call, fetch_call = runner.calls
    assert set_url_call[0] == ["git", "remote", "set-url", "origin", ssh_repo_url]
    assert fetch_call[0] == ["git", "fetch", "origin", "main", "feature/a", "a" * 40]
    for _, _, _, env in runner.calls:
        assert env is not None
        assert "GIT_SSH_COMMAND" in env
        assert "abc123" not in env["GIT_SSH_COMMAND"]


def test_ensure_repo_rejects_invalid_private_key(tmp_path):
    service = CodeupGitService(runner=FakeRunner({}))

    with pytest.raises(CodeupGitError, match="Invalid SSH private key"):
        service.ensure_repo(
            repo_url="codeup.aliyun.com/org/repo",
            repo_dir=tmp_path / "repo",
            target_branch="main",
            source_branch="feature/a",
            merge_commit_sha="a" * 40,
            source_commit_shas=[],
            clone_timeout=12,
            fetch_timeout=34,
            private_key="not a key",
        )


def test_run_supports_legacy_three_argument_runner():
    calls = []

    def legacy_runner(args, cwd, timeout):
        calls.append((args, cwd, timeout))
        return "legacy ok\n"

    result = CodeupGitService(runner=legacy_runner)._run(
        ["git", "status"], Path("/repo"), timeout=7
    )

    assert result == "legacy ok\n"
    assert calls == [(["git", "status"], Path("/repo"), 7)]


def test_run_does_not_mask_type_error_from_runner_body():
    def broken_runner(args, cwd, timeout, env=None):
        raise TypeError("runner body failed")

    with pytest.raises(TypeError, match="runner body failed"):
        CodeupGitService(runner=broken_runner)._run(["git", "status"], Path("/repo"))


def test_create_ssh_command_shell_quotes_key_path_with_spaces_and_quotes():
    key_path = "/tmp/codeup key 'quoted'"

    command = CodeupGitService()._create_ssh_command(key_path)

    assert "ssh -i '/tmp/codeup key '\"'\"'quoted'\"'\"''" in command
    assert f'"{key_path}"' not in command


def test_private_key_temp_file_is_cleaned_after_success(tmp_path):
    observed_key_paths = []

    def runner(args, cwd, timeout, env=None):
        assert env is not None
        ssh_command = env["GIT_SSH_COMMAND"]
        key_path = ssh_command.split(" -o ", 1)[0].removeprefix("ssh -i ").strip("'")
        observed_key_paths.append(Path(key_path))
        assert Path(key_path).exists()
        return ""

    service = CodeupGitService(runner=runner)

    result = service._run_with_optional_ssh_key(
        ["git", "fetch", "origin", "main"], tmp_path, 12, VALID_PRIVATE_KEY
    )

    assert result == ""
    assert observed_key_paths
    assert not observed_key_paths[0].exists()


def test_private_key_temp_file_is_cleaned_after_failure(tmp_path):
    observed_key_paths = []

    def runner(args, cwd, timeout, env=None):
        assert env is not None
        ssh_command = env["GIT_SSH_COMMAND"]
        key_path = ssh_command.split(" -o ", 1)[0].removeprefix("ssh -i ").strip("'")
        observed_key_paths.append(Path(key_path))
        assert Path(key_path).exists()
        raise RuntimeError("git failed")

    service = CodeupGitService(runner=runner)

    with pytest.raises(RuntimeError, match="git failed"):
        service._run_with_optional_ssh_key(
            ["git", "fetch", "origin", "main"], tmp_path, 12, VALID_PRIVATE_KEY
        )

    assert observed_key_paths
    assert not observed_key_paths[0].exists()


def test_private_key_is_not_in_ssh_command_and_file_mode_is_0600(tmp_path):
    secret_marker = "abc123"

    def runner(args, cwd, timeout, env=None):
        assert env is not None
        ssh_command = env["GIT_SSH_COMMAND"]
        key_path = ssh_command.split(" -o ", 1)[0].removeprefix("ssh -i ").strip("'")
        assert secret_marker not in ssh_command
        assert Path(key_path).read_text(encoding="utf-8") == VALID_PRIVATE_KEY
        assert Path(key_path).stat().st_mode & 0o777 == 0o600
        return ""

    result = CodeupGitService(runner=runner)._run_with_optional_ssh_key(
        ["git", "fetch", "origin", "main"], tmp_path, 12, VALID_PRIVATE_KEY
    )

    assert result == ""


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
        (["git", "merge-base", "feature/a", "main"], Path("/repo"), 60, None),
        (["git", "rev-list", "c" * 40 + "..feature/a"], Path("/repo"), 60, None),
    ]


def test_merge_base_uses_remote_tracking_ref_when_source_branch_is_not_local():
    source_branch = "git-ai-1"
    merge_sha = "a" * 40
    base_sha = "c" * 40
    calls = []

    def runner(args, cwd, timeout, env=None):
        calls.append((args, cwd, timeout, env))
        if args == ["git", "merge-base", source_branch, merge_sha]:
            raise CodeupGitError("git command failed: fatal: Not a valid object name git-ai-1")
        if args == ["git", "merge-base", f"origin/{source_branch}", merge_sha]:
            return f"{base_sha}\n"
        raise AssertionError(f"unexpected git args: {args}")

    service = CodeupGitService(runner=runner)

    result = service.merge_base(Path("/repo"), source_branch, merge_sha)

    assert result == base_sha
    assert calls == [
        (["git", "merge-base", source_branch, merge_sha], Path("/repo"), 60, None),
        (["git", "merge-base", f"origin/{source_branch}", merge_sha], Path("/repo"), 60, None),
    ]


def test_rev_list_uses_remote_tracking_ref_when_range_head_branch_is_not_local():
    base_sha = "c" * 40
    source_branch = "git-ai-1"
    head_sha = "b" * 40
    calls = []

    def runner(args, cwd, timeout, env=None):
        calls.append((args, cwd, timeout, env))
        if args == ["git", "rev-list", f"{base_sha}..{source_branch}"]:
            raise CodeupGitError("git command failed: fatal: Not a valid object name git-ai-1")
        if args == ["git", "rev-list", f"{base_sha}..origin/{source_branch}"]:
            return f"{head_sha}\n"
        raise AssertionError(f"unexpected git args: {args}")

    service = CodeupGitService(runner=runner)

    result = service.rev_list(Path("/repo"), f"{base_sha}..{source_branch}")

    assert result == [head_sha]
    assert calls == [
        (["git", "rev-list", f"{base_sha}..{source_branch}"], Path("/repo"), 60, None),
        (["git", "rev-list", f"{base_sha}..origin/{source_branch}"], Path("/repo"), 60, None),
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
                "env": None,
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
        (["git", "show", "-s", "--format=%P", sha], Path("/repo"), 60, None)
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


class TestRepoUrlForAuth:
    """_repo_url_for_auth 对归一化 URL 的还原测试"""

    def test_normalized_no_private_key_returns_https_url(self):
        service = CodeupGitService()
        result = service._repo_url_for_auth("codeup.aliyun.com/org/repo", None)
        assert result == "https://codeup.aliyun.com/org/repo.git"

    def test_normalized_with_private_key_returns_ssh_url(self):
        service = CodeupGitService()
        result = service._repo_url_for_auth("codeup.aliyun.com/org/repo", VALID_PRIVATE_KEY)
        assert result == "ssh://git@codeup.aliyun.com/org/repo.git"

    def test_legacy_https_no_private_key_returns_as_is(self):
        service = CodeupGitService()
        result = service._repo_url_for_auth("https://codeup.aliyun.com/org/repo.git", None)
        assert result == "https://codeup.aliyun.com/org/repo.git"

    def test_legacy_https_with_private_key_returns_ssh_url(self):
        service = CodeupGitService()
        result = service._repo_url_for_auth("https://codeup.aliyun.com/org/repo.git", VALID_PRIVATE_KEY)
        assert result == "ssh://git@codeup.aliyun.com/org/repo.git"

    def test_legacy_http_with_private_key_returns_ssh_url(self):
        service = CodeupGitService()
        result = service._repo_url_for_auth("http://codeup.aliyun.com/org/repo.git", VALID_PRIVATE_KEY)
        assert result == "ssh://git@codeup.aliyun.com/org/repo.git"

    def test_normalized_with_port_no_private_key(self):
        service = CodeupGitService()
        result = service._repo_url_for_auth("devops.cxmt.com:8022/group/project", None)
        assert result == "https://devops.cxmt.com:8022/group/project.git"

    def test_normalized_with_port_with_private_key(self):
        service = CodeupGitService()
        result = service._repo_url_for_auth("devops.cxmt.com:8022/group/project", VALID_PRIVATE_KEY)
        assert result == "ssh://git@devops.cxmt.com:8022/group/project.git"


def test_ensure_repo_normalized_url_with_private_key_uses_ssh_clone(tmp_path):
    ssh_repo_url = "ssh://git@codeup.aliyun.com/org/repo.git"
    runner = FakeRunner(
        {
            ("git", "clone", ssh_repo_url, str(tmp_path / "repo")): "",
            ("git", "fetch", "origin", "main", "feature/a", "a" * 40): "",
        }
    )
    service = CodeupGitService(runner=runner)

    service.ensure_repo(
        repo_url="codeup.aliyun.com/org/repo",
        repo_dir=tmp_path / "repo",
        target_branch="main",
        source_branch="feature/a",
        merge_commit_sha="a" * 40,
        source_commit_shas=[],
        clone_timeout=12,
        fetch_timeout=34,
        private_key=VALID_PRIVATE_KEY,
    )

    clone_call = runner.calls[0]
    assert clone_call[0] == ["git", "clone", ssh_repo_url, str(tmp_path / "repo")]
    assert clone_call[3] is not None
    assert "GIT_SSH_COMMAND" in clone_call[3]


def test_ensure_repo_normalized_url_without_private_key_uses_https_clone(tmp_path):
    https_repo_url = "https://codeup.aliyun.com/org/repo.git"
    runner = FakeRunner(
        {
            ("git", "clone", https_repo_url, str(tmp_path / "repo")): "",
            ("git", "fetch", "origin", "main", "feature/a", "a" * 40): "",
        }
    )
    service = CodeupGitService(runner=runner)

    service.ensure_repo(
        repo_url="codeup.aliyun.com/org/repo",
        repo_dir=tmp_path / "repo",
        target_branch="main",
        source_branch="feature/a",
        merge_commit_sha="a" * 40,
        source_commit_shas=[],
        clone_timeout=12,
        fetch_timeout=34,
    )

    clone_call = runner.calls[0]
    assert clone_call[0] == ["git", "clone", https_repo_url, str(tmp_path / "repo")]
    assert clone_call[3] is None
