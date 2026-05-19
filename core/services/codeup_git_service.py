import subprocess
import re
from pathlib import Path
from typing import Callable


GitRunner = Callable[[list[str], Path, int], str]
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
    ) -> Path:
        self._validate_repo_url(repo_url)
        self._validate_ref(target_branch, "target_branch")
        self._validate_ref(source_branch, "source_branch")
        self._validate_commit_sha(merge_commit_sha)
        for source_commit_sha in source_commit_shas:
            self._validate_commit_sha(source_commit_sha)

        if (repo_dir / ".git").exists():
            self._fetch_required_refs(
                repo_dir,
                target_branch,
                source_branch,
                merge_commit_sha,
                source_commit_shas,
                fetch_timeout,
            )
            return repo_dir

        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        self._run(["git", "clone", repo_url, str(repo_dir)], repo_dir.parent, clone_timeout)
        self._fetch_required_refs(
            repo_dir,
            target_branch,
            source_branch,
            merge_commit_sha,
            source_commit_shas,
            fetch_timeout,
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

    def _run(self, args: list[str], cwd: Path, timeout: int = 60) -> str:
        if self.runner is not None:
            return self.runner(args, cwd, timeout)

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
            )
            return result.stdout
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr or exc.stdout or str(exc)
            raise CodeupGitError(f"git command failed: {detail}") from exc
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            raise CodeupGitError(f"git command failed: {exc}") from exc

    def _fetch_required_refs(
        self,
        repo_dir: Path,
        target_branch: str,
        source_branch: str,
        merge_commit_sha: str,
        source_commit_shas: list[str],
        timeout: int,
    ) -> None:
        refs = self._unique_refs(
            [target_branch, source_branch, merge_commit_sha, *source_commit_shas]
        )
        self._run(["git", "fetch", "origin", *refs], repo_dir, timeout)

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
