import inspect
import os
import shlex
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Callable, Mapping

from core.utils.repo_url import normalize_repo_url, restore_repo_url


GitRunner = Callable[..., str]
SAFE_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")


class CodeupGitError(RuntimeError):
    pass


class CodeupGitService:
    def __init__(self, runner: GitRunner | None = None):
        self.runner = runner

    def ensure_repo(
        self,
        repo_url: str,
        repo_dir: Path,
        target_branch: str,
        source_branch: str,
        merge_commit_sha: str,
        source_commit_shas: list[str],
        clone_timeout: int,
        fetch_timeout: int,
        private_key: str | None = None,
    ) -> Path:
        self._validate_repo_url(repo_url)
        self._validate_ref(target_branch, "target_branch")
        self._validate_ref(source_branch, "source_branch")
        self._validate_commit_sha(merge_commit_sha)
        for source_commit_sha in source_commit_shas:
            self._validate_commit_sha(source_commit_sha)

        if (repo_dir / ".git").exists():
            if private_key is not None:
                origin_url = self._repo_url_for_auth(repo_url, private_key)
                self._run_with_optional_ssh_key(
                    ["git", "remote", "set-url", "origin", origin_url],
                    repo_dir,
                    fetch_timeout,
                    private_key,
                )
            self._fetch_required_refs(
                repo_dir,
                target_branch,
                source_branch,
                merge_commit_sha,
                source_commit_shas,
                fetch_timeout,
                private_key=private_key,
            )
            return repo_dir

        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        clone_url = self._repo_url_for_auth(repo_url, private_key)
        self._run_with_optional_ssh_key(
            ["git", "clone", clone_url, str(repo_dir)],
            repo_dir.parent,
            clone_timeout,
            private_key,
        )
        self._fetch_required_refs(
            repo_dir,
            target_branch,
            source_branch,
            merge_commit_sha,
            source_commit_shas,
            fetch_timeout,
            private_key=private_key,
        )
        return repo_dir

    def merge_base(self, repo_path: Path, source_ref: str, target_ref_or_merge_sha: str) -> str:
        self._validate_ref(source_ref, "source_ref")
        self._validate_ref(target_ref_or_merge_sha, "target_ref_or_merge_sha")
        stdout = self._run(
            ["git", "merge-base", source_ref, target_ref_or_merge_sha], repo_path
        ).strip()
        self._validate_commit_sha(stdout)
        return stdout

    def rev_list(self, repo_path: Path, revision_range: str) -> list[str]:
        self._validate_ref(revision_range, "revision_range")
        stdout = self._run(["git", "rev-list", revision_range], repo_path)
        return stdout.splitlines()

    def show_file_lines(self, repo_path: Path, commit_sha: str, file_path: str) -> list[str]:
        self._validate_commit_sha(commit_sha)
        self._validate_file_path(file_path)
        stdout = self._run(["git", "show", f"{commit_sha}:{file_path}"], repo_path)
        return stdout.splitlines()

    def changed_files(self, repo_path: Path, base_sha: str, head_sha: str) -> list[str]:
        self._validate_ref(base_sha, "base ref")
        self._validate_ref(head_sha, "head ref")
        stdout = self._run(
            ["git", "diff", "--name-only", base_sha, head_sha], repo_path
        )
        return stdout.splitlines()

    def commit_parents(self, repo_path: Path, commit_sha: str) -> list[str]:
        self._validate_commit_sha(commit_sha)
        output = self._run(
            ["git", "show", "-s", "--format=%P", commit_sha],
            repo_path,
        )
        return [parent for parent in output.strip().split() if parent]

    def commit_metadata(self, repo_path: Path, commit_sha: str) -> dict[str, object]:
        self._validate_commit_sha(commit_sha)
        stdout = self._run(
            ["git", "show", "-s", "--format=%an%x00%ae%x00%ct", commit_sha],
            repo_path,
        ).strip()
        try:
            author_name, author_email, commit_time = stdout.split("\x00", 2)
            return {
                "author_name": author_name,
                "author_email": author_email,
                "commit_time": int(commit_time),
            }
        except ValueError as exc:
            raise CodeupGitError(
                f"Malformed commit metadata for commit_sha '{commit_sha}'"
            ) from exc

    def _run_with_optional_ssh_key(
        self,
        args: list[str],
        cwd: Path,
        timeout: int,
        private_key: str | None,
    ) -> str:
        if private_key is None:
            return self._run(args, cwd, timeout)

        normalized_key = self._normalize_private_key(private_key)
        if not self._validate_private_key_format(normalized_key):
            raise CodeupGitError("Invalid SSH private key")

        temp_key_path = self._write_private_key_to_temp(normalized_key)
        try:
            env = os.environ.copy()
            env["GIT_SSH_COMMAND"] = self._create_ssh_command(temp_key_path)
            return self._run(args, cwd, timeout, env=env)
        finally:
            if os.path.exists(temp_key_path):
                os.unlink(temp_key_path)

    def _normalize_private_key(self, private_key: str) -> str:
        key_content = private_key.strip().replace("\\n", "\n").replace("\r\n", "\n")
        if not key_content.endswith("\n"):
            key_content += "\n"
        return key_content

    def _validate_private_key_format(self, private_key: str) -> bool:
        if not private_key or not private_key.strip():
            return False
        key_content = private_key.strip()
        headers = [
            "-----BEGIN RSA PRIVATE KEY-----",
            "-----BEGIN OPENSSH PRIVATE KEY-----",
            "-----BEGIN EC PRIVATE KEY-----",
            "-----BEGIN DSA PRIVATE KEY-----",
            "-----BEGIN PRIVATE KEY-----",
            "-----BEGIN ED25519 PRIVATE KEY-----",
        ]
        footers = [
            "-----END RSA PRIVATE KEY-----",
            "-----END OPENSSH PRIVATE KEY-----",
            "-----END EC PRIVATE KEY-----",
            "-----END DSA PRIVATE KEY-----",
            "-----END PRIVATE KEY-----",
            "-----END ED25519 PRIVATE KEY-----",
        ]
        return any(header in key_content for header in headers) and any(
            footer in key_content for footer in footers
        )

    def _write_private_key_to_temp(self, private_key: str) -> str:
        fd, temp_path = tempfile.mkstemp(prefix="codeup_ssh_key_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as key_file:
                key_file.write(private_key)
            os.chmod(temp_path, 0o600)
            return temp_path
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _create_ssh_command(self, key_file_path: str) -> str:
        return (
            f"ssh -i {shlex.quote(key_file_path)} "
            "-o StrictHostKeyChecking=no "
            "-o UserKnownHostsFile=/dev/null "
            "-o IdentitiesOnly=yes "
            "-o LogLevel=ERROR"
        )

    def _repo_url_for_auth(self, repo_url: str, private_key: str | None) -> str:
        # 检测是否为无协议输入：可能是已归一化 host/path，也可能是 scp-style git@host:path.git。
        has_protocol = repo_url.startswith(("http://", "https://", "ssh://", "git://", "file://"))
        normalized_repo_url = normalize_repo_url(repo_url) if not has_protocol else repo_url

        if private_key is None:
            if not has_protocol:
                return restore_repo_url(normalized_repo_url, "https")
            return repo_url

        # private_key 存在 → 需要 SSH URL
        if not has_protocol:
            return restore_repo_url(normalized_repo_url, "ssh")

        # 兼容旧调用方传入完整 http/https URL 的情况
        if repo_url.startswith(("http://", "https://")):
            ssh_url = repo_url.replace("https://", "ssh://git@", 1).replace(
                "http://", "ssh://git@", 1
            )
            if not ssh_url.endswith(".git"):
                ssh_url += ".git"
            return ssh_url

        return repo_url

    def _run(
        self,
        args: list[str],
        cwd: Path,
        timeout: int = 60,
        env: Mapping[str, str] | None = None,
    ) -> str:
        if self.runner is not None:
            return self._run_with_runner(args, cwd, timeout, env)

        if not cwd.exists() or not cwd.is_dir():
            raise CodeupGitError(f"Invalid git working directory: {cwd}")

        try:
            result = subprocess.run(
                args=args,
                cwd=cwd,
                timeout=timeout,
                text=True,
                capture_output=True,
                check=True,
                env=env,
            )
            return result.stdout
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr or exc.stdout or str(exc)
            raise CodeupGitError(f"git command failed: {detail}") from exc
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            raise CodeupGitError(f"git command failed: {exc}") from exc

    def _run_with_runner(
        self,
        args: list[str],
        cwd: Path,
        timeout: int,
        env: Mapping[str, str] | None,
    ) -> str:
        if self.runner is None:
            raise CodeupGitError("Git runner is not configured")

        if self._runner_accepts_env(self.runner):
            return self.runner(args, cwd, timeout, env)
        return self.runner(args, cwd, timeout)

    def _runner_accepts_env(self, runner: GitRunner) -> bool:
        try:
            signature = inspect.signature(runner)
        except (TypeError, ValueError):
            return True

        positional_count = 0
        for parameter in signature.parameters.values():
            if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
                return True
            if parameter.kind is inspect.Parameter.VAR_KEYWORD:
                return True
            if parameter.name == "env":
                return True
            if parameter.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                positional_count += 1
        return positional_count >= 4

    def _fetch_required_refs(
        self,
        repo_dir: Path,
        target_branch: str,
        source_branch: str,
        merge_commit_sha: str,
        source_commit_shas: list[str],
        timeout: int,
        private_key: str | None = None,
    ) -> None:
        refs = self._unique_refs(
            [target_branch, source_branch, merge_commit_sha, *source_commit_shas]
        )
        self._run_with_optional_ssh_key(
            ["git", "fetch", "origin", *refs], repo_dir, timeout, private_key
        )

    def _unique_refs(self, refs: list[str]) -> list[str]:
        unique = []
        for ref in refs:
            if ref and ref not in unique:
                unique.append(ref)
        return unique

    def _validate_repo_url(self, repo_url: str) -> None:
        if not repo_url or not repo_url.strip() or repo_url.startswith("-"):
            raise CodeupGitError(f"Invalid repo_url: {repo_url!r}")

    def _validate_ref(self, ref: str, field_name: str) -> None:
        if not ref or not ref.strip() or ref.startswith("-"):
            raise CodeupGitError(f"Invalid git {field_name}: {ref!r}")

    def _validate_commit_sha(self, commit_sha: str) -> None:
        if not SAFE_SHA_PATTERN.fullmatch(commit_sha or ""):
            raise CodeupGitError(f"Invalid commit_sha: {commit_sha!r}")

    def _validate_file_path(self, file_path: str) -> None:
        if not file_path or not file_path.strip() or file_path.startswith("-"):
            raise CodeupGitError(f"Invalid file_path: {file_path!r}")

        path = Path(file_path)
        if path.is_absolute() or ".." in path.parts:
            raise CodeupGitError(f"Invalid file_path: {file_path!r}")
