from unittest.mock import MagicMock

from core.scheduler.tasks.git_blame_stats_task import GitBlameStatsTask


def test_stat_repository_reads_branches_from_repository_branch_table(tmp_path):
    """测试 blame 统计分支来源为 stats_repositories_branch 而非旧配置表"""
    task = GitBlameStatsTask.__new__(GitBlameStatsTask)
    task.logger = MagicMock()
    task.blame_stats_db = MagicMock()
    task.ssh_key_service = MagicMock()
    task.git_clone_service = MagicMock()
    task.blame_stats_service = MagicMock()

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
