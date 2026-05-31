from pathlib import Path
from unittest.mock import MagicMock

from core.services.blame_stats_service import RepoBlameResult
from core.scheduler.tasks.git_blame_stats_task import GitBlameStatsTask
import core.scheduler.tasks.git_blame_stats_task as git_blame_stats_task


class FrozenDateTime:
    @classmethod
    def now(cls):
        from datetime import datetime

        return datetime(2026, 5, 30, 12, 0, 0)


def test_stat_repository_reads_branches_from_repository_branch_table(tmp_path):
    """测试 blame 统计分支来源为 stats_repositories_branch 而非旧配置表"""
    task = GitBlameStatsTask.__new__(GitBlameStatsTask)
    task.logger = MagicMock()
    task.blame_stats_db = MagicMock()
    task.ssh_key_service = MagicMock()
    task.git_clone_service = MagicMock()
    task.blame_stats_service = MagicMock()
    task.config = {"blame_stats": {"repo_cache_dir": str(tmp_path / "stats_repos")}}

    task.git_clone_service.clone_with_ssh_key.return_value = True
    task.blame_stats_db.get_repository_branches.return_value = ["main", "release"]

    task._stat_repository(
        "repo-1",
        "ssh://git@example.com/repo.git",
        "20260517",
        {"private_key": "private-key"},
    )

    task.blame_stats_db.get_repository_branches.assert_called_once_with("repo-1")
    task.blame_stats_db.get_repo_branch_configs.assert_not_called()
    task.git_clone_service.list_branches.assert_not_called()
    task.git_clone_service.match_branches.assert_not_called()
    task.git_clone_service.clone_with_ssh_key.assert_called_once_with(
        "ssh://git@example.com/repo.git",
        "private-key",
        task.git_clone_service.clone_with_ssh_key.call_args.args[2],
        depth=1,
    )
    clone_target = Path(task.git_clone_service.clone_with_ssh_key.call_args.args[2])
    assert clone_target.parent == tmp_path / "stats_repos"
    assert clone_target != tmp_path / "stats_repos"


def test_execute_counts_repository_without_branches_as_skipped():
    task = GitBlameStatsTask.__new__(GitBlameStatsTask)
    task.logger = MagicMock()
    task.ssh_key_service = MagicMock()
    task.blame_stats_db = MagicMock()

    task.ssh_key_service.load_default_ssh_key_from_config.return_value = None
    task.ssh_key_service.get_ssh_key_for_repo.return_value = {
        "private_key": "private-key"
    }
    task.blame_stats_db.get_repositories_to_stat.return_value = [
        {
            "id": "repo-1",
            "repo_path": "ssh://git@example.com/repo.git",
            "repo_name": "repo",
            "ssh_key_id": None,
        }
    ]
    task._stat_repository = MagicMock(
        return_value={
            "success": True,
            "skipped": True,
            "skipped_reason": "no_branches",
            "total_branches": 0,
            "success_branches": 0,
            "failed_branches": 0,
            "branch_results": {},
        }
    )

    result = task.execute({"stat_date": "20260517"})

    assert result["success_repos"] == 0
    assert result["failed_repos"] == 0
    assert result["skipped_repos"] == 1


def test_execute_defaults_stat_date_to_today(monkeypatch):
    monkeypatch.setattr(git_blame_stats_task, "datetime", FrozenDateTime)
    task = GitBlameStatsTask.__new__(GitBlameStatsTask)
    task.logger = MagicMock()
    task.ssh_key_service = MagicMock()
    task.blame_stats_db = MagicMock()

    task.ssh_key_service.load_default_ssh_key_from_config.return_value = None
    task.blame_stats_db.get_repositories_to_stat.return_value = []

    result = task.execute()

    assert result["stat_date"] == "20260530"


def test_stat_repository_skips_when_repository_branch_table_is_empty(tmp_path):
    task = GitBlameStatsTask.__new__(GitBlameStatsTask)
    task.logger = MagicMock()
    task.blame_stats_db = MagicMock()
    task.ssh_key_service = MagicMock()
    task.git_clone_service = MagicMock()
    task.blame_stats_service = MagicMock()
    task.config = {"blame_stats": {"repo_cache_dir": str(tmp_path / "stats_repos")}}

    task.git_clone_service.clone_with_ssh_key.return_value = True
    task.blame_stats_db.get_repository_branches.return_value = []

    result = task._stat_repository(
        "repo-1",
        "ssh://git@example.com/repo.git",
        "20260517",
        {"private_key": "private-key"},
    )

    assert result == {
        "success": True,
        "total_branches": 0,
        "success_branches": 0,
        "failed_branches": 0,
        "branch_results": {},
        "skipped": True,
        "skipped_reason": "no_branches",
    }
    task.git_clone_service.checkout_branch.assert_not_called()
    task.blame_stats_service.analyze_repository.assert_not_called()


def test_stat_repository_marks_missing_branch_deleted(tmp_path):
    task = GitBlameStatsTask.__new__(GitBlameStatsTask)
    task.logger = MagicMock()
    task.blame_stats_db = MagicMock()
    task.ssh_key_service = MagicMock()
    task.git_clone_service = MagicMock()
    task.blame_stats_service = MagicMock()
    task.config = {"blame_stats": {"repo_cache_dir": str(tmp_path / "stats_repos")}}

    task.git_clone_service.clone_with_ssh_key.return_value = True
    task.blame_stats_db.get_repository_branches.return_value = ["main"]
    task.git_clone_service.checkout_branch.return_value = False

    result = task._stat_repository(
        "repo-1",
        "ssh://git@example.com/repo.git",
        "20260517",
        {"private_key": "private-key"},
    )

    assert result["failed_branches"] == 1
    task.blame_stats_db.mark_repository_branch_deleted.assert_called_once_with(
        "repo-1", "main"
    )
    task.blame_stats_service.analyze_repository.assert_not_called()


def test_stat_repository_records_last_blame_commit_sha_and_stat_date_after_success(tmp_path):
    task = GitBlameStatsTask.__new__(GitBlameStatsTask)
    task.logger = MagicMock()
    task.blame_stats_db = MagicMock()
    task.ssh_key_service = MagicMock()
    task.git_clone_service = MagicMock()
    task.blame_stats_service = MagicMock()
    task._save_branch_stats = MagicMock()
    task.config = {"blame_stats": {"repo_cache_dir": str(tmp_path / "stats_repos")}}

    task.git_clone_service.clone_with_ssh_key.return_value = True
    task.blame_stats_db.get_repository_branches.return_value = ["main"]
    task.blame_stats_db.get_repository_repo_url.return_value = (
        "ssh://git@example.com/repo.git"
    )
    task.git_clone_service.checkout_branch.return_value = True
    task.blame_stats_service.analyze_repository.return_value = RepoBlameResult(
        stat_date="20260517",
        commit_sha="abc123def456",
        branch="main",
        total_lines=10,
        ai_lines=4,
        non_ai_lines=6,
        total_files=1,
        files_results=[],
        contributor_stats={},
    )

    result = task._stat_repository(
        "repo-1",
        "ssh://git@example.com/repo.git",
        "20260517",
        {"private_key": "private-key"},
    )

    assert result["success_branches"] == 1
    task.blame_stats_db.update_repository_last_blame_stats.assert_called_once_with(
        "repo-1", "abc123def456", "20260517"
    )


def test_repo_path_defaults_to_stats_repos_cache_child():
    task = GitBlameStatsTask.__new__(GitBlameStatsTask)
    task.config = {"blame_stats": {"repo_cache_dir": ".cache/stats_repos"}}

    first_path = task._repo_path("ssh://git@example.com/repo.git")
    second_path = task._repo_path("ssh://git@example.com/other.git")

    assert first_path.parent == Path(".cache/stats_repos")
    assert second_path.parent == Path(".cache/stats_repos")
    assert first_path != Path(".cache/stats_repos")
    assert first_path != second_path


def test_save_branch_stats_saves_only_repo_and_person_rows():
    task = GitBlameStatsTask.__new__(GitBlameStatsTask)
    task.blame_stats_db = MagicMock()

    class FileResult:
        file_path = "src/app.py"
        total_lines = 10
        ai_lines = 4
        non_ai_lines = 6
        commit_sha = "abc123def456"
        contributor_stats = {
            "Alice": {
                "ai_lines": 4,
                "non_ai_lines": 6,
                "total_lines": 10,
                "email": None,
            }
        }

    result = RepoBlameResult(
        stat_date="20260530",
        commit_sha="abc123def456",
        branch="main",
        total_lines=10,
        ai_lines=4,
        non_ai_lines=6,
        total_files=1,
        files_results=[FileResult()],
        contributor_stats={
            "Alice": {
                "ai_lines": 4,
                "non_ai_lines": 6,
                "total_lines": 10,
                "email": None,
            }
        },
    )

    task._save_branch_stats("repo-1", "20260530", result)

    args = task.blame_stats_db.save_branch_stats_batch.call_args.args
    assert len(args) == 5
    assert args[0:3] == ("repo-1", "main", "20260530")
    repo_obj = args[3]
    contributor_objs = args[4]
    assert repo_obj.total_lines == 10
    assert len(contributor_objs) == 1
    assert contributor_objs[0].contributor_name == "Alice"
    assert contributor_objs[0].contributor_email == ""
