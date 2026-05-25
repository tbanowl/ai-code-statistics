"""Git Blame 统计定时任务"""

import os
from os import path
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from uuid import uuid4
from core.scheduler.tasks.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.database import BlameStatsDatabase
from core.services import SshKeyService, GitCloneService, BlameStatsService
from core.config import load_config
from core.database.models import (
    StatsBlameFile,
    StatsBlameRepoContributor,
    StatsBlameRepo,
    StatsBlameFileContributor,
    gen_xid
)

@scheduled(cron="0 2 * * *", job_id="git_blame_stats", name="Git代码归因统计")
class GitBlameStatsTask(BaseTask):
    """Git Blame 统计任务 - 统计仓库中 AI 代码归占比"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.blame_stats_db = BlameStatsDatabase()
        self.ssh_key_service = SshKeyService()
        self.git_clone_service = GitCloneService()
        self.blame_stats_service = BlameStatsService(self.blame_stats_db)

    def execute(self, context: Optional[Dict] = None) -> Dict:
        """执行 Git Blame 统计任务"""
        self.logger.info("开始执行 Git Blame 统计任务")

        # 获取统计日期
        stat_date = context.get("stat_date") if context else None
        if stat_date is None:
            # 默认统计昨天
            yesterday = datetime.now() - timedelta(days=1)
            stat_date = yesterday.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).strftime("%Y%m%d")

        self.logger.info(f"统计日期: stat_date")

        # 加载配置文件中的默认 SSH Key
        default_ssh_key = self.ssh_key_service.load_default_ssh_key_from_config()

        if default_ssh_key:
            self.logger.info(f"已加载默认 SSH Key: {default_ssh_key['key_name']}")
        else:
            self.logger.info("未配置默认 SSH Key")

        # 获取待统计的仓库列表
        repos = self.blame_stats_db.get_repositories_to_stat()
        self.logger.info(f"待统计仓库数量: {len(repos)}")

        if not repos:
            return {
                "success": True,
                "message": "没有需要统计的仓库",
                "stat_date": stat_date,
            }

        # 统计结果汇总
        total_repos = 0
        success_repos = 0
        failed_repos = 0
        skipped_repos = 0

        repos_start_time = time.time()
        for repo in repos:
            repo_id = repo["id"]
            repo_path = repo["repo_path"]
            repo_name = repo.get("repo_name", repo_path)
            repo_ssh_key_id = repo.get("ssh_key_id")

            total_repos += 1
            self.logger.info(f"开始统计仓库: {repo_name} ({repo_path})")

            # 获取仓库可用的 SSH Key
            ssh_key_info = self.ssh_key_service.get_ssh_key_for_repo(repo_ssh_key_id)

            if not ssh_key_info:
                self.logger.warning(f"仓库 {repo_name} 无可用 SSH Key，跳过统计")
                skipped_repos += 1
                continue

            try:
                # 克隆并统计仓库
                repo_start_time = time.time()
                result = self._stat_repository(
                    repo_id, repo_path, stat_date, ssh_key_info
                )
                repo_end_time = time.time()
                elapsed_time = repo_end_time - repo_start_time
                self.logger.info(
                    f"单仓库 AI 代码量统计耗时：{elapsed_time:.4f} 秒，repo：{repo_path}"
                )

                if result:
                    if result.get("skipped"):
                        skipped_repos += 1
                        self.logger.info(
                            f"仓库 {repo_name} 跳过统计: {result.get('skipped_reason')}"
                        )
                    else:
                        success_repos += 1
                        self.logger.info(
                            f"仓库 {repo_name} 统计完成: "
                            f"成功分支 {result.get('success_branches', 0)}/{result.get('total_branches', 0)}"
                        )
                else:
                    failed_repos += 1

            except Exception as e:
                self.logger.error(f"仓库 {repo_name} 统计失败: {e}", exc_info=True)
                failed_repos += 1

        repos_end_time = time.time()
        elapsed_time = repos_end_time - repos_start_time
        self.logger.info(
            f"所有仓库AI代码量统计耗时：{elapsed_time:.4f} 秒，仓库数量：{len(repos)}"
        )

        summary = {
            "success": failed_repos == 0,
            "stat_date": stat_date,
            "total_repos": total_repos,
            "success_repos": success_repos,
            "failed_repos": failed_repos,
            "skipped_repos": skipped_repos,
        }

        self.logger.info(
            f"任务完成: 成功 {success_repos}/{total_repos}, "
            f"失败 {failed_repos}, 跳过 {skipped_repos}"
        )

        return summary

    def _stat_repository(
        self, repo_id: str, repo_path: str, stat_date: str, ssh_key_info: Dict
    ) -> Dict | None:
        """
        统计单个仓库

        Args:
            repo_id: 仓库 ID
            repo_path: 仓库路径（用作 repo_url）
            stat_date: 统计日期
            ssh_key_info: SSH Key 信息

        Returns:
            统计结果或 None
        """
        temp_dir = None
        try:
            # 创建临时目录 - 使用项目目录下的 code-metrics 目录
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            temp_dir = os.path.join(os.path.join(project_root, ".code-metrics"), f"git_blame_{uuid4()}")
            os.makedirs(temp_dir, exist_ok=True)

            # 克隆仓库
            self.logger.info(f"克隆仓库到临时目录: {temp_dir}")

            if not self.git_clone_service.clone_with_ssh_key(
                repo_path,
                ssh_key_info["private_key"],
                temp_dir,
                depth=1,
            ):
                self.logger.error("仓库克隆失败")
                return None

            target_branches = self.blame_stats_db.get_repository_branches(repo_id)
            self.logger.info(
                f"从仓库分支表读取到 {len(target_branches)} 个待统计分支"
            )

            if not target_branches:
                self.logger.warning("仓库分支表没有可统计分支，跳过统计")
                return {
                    "success": True,
                    "total_branches": 0,
                    "success_branches": 0,
                    "failed_branches": 0,
                    "branch_results": {},
                    "skipped": True,
                    "skipped_reason": "no_branches",
                }

            # 获取统计配置
            config = load_config()
            file_filter = config.get("blame_stats", {}).get("file_filter", {})
            repo_url = self.blame_stats_db.get_repository_repo_url(repo_id)

            # 遍历每个分支进行统计
            branch_results = {}
            success_count = 0
            failed_count = 0

            for branch in target_branches:
                self.logger.info(f"开始统计分支: {branch}")

                # 切换分支
                if not self.git_clone_service.checkout_branch(temp_dir, branch):
                    self.logger.warning(f"分支 {branch} 切换失败，跳过")
                    self.blame_stats_db.mark_repository_branch_deleted(repo_id, branch)
                    failed_count += 1
                    continue

                # 统计该分支
                result = self.blame_stats_service.analyze_repository(
                    repo_url, temp_dir, stat_date, file_filter
                )

                if not result:
                    self.logger.error(f"分支 {branch} 分析失败")
                    failed_count += 1
                    continue

                # 保存该分支的统计结果
                self._save_branch_stats(repo_id, stat_date, result)
                self.blame_stats_db.update_repository_last_blame_commit_sha(
                    repo_id, result.commit_sha
                )

                branch_results[branch] = {
                    "total_lines": result.total_lines,
                    "ai_lines": result.ai_lines,
                    "non_ai_lines": result.non_ai_lines,
                    "ai_ratio": round(
                        (result.ai_lines / result.total_lines * 100)
                        if result.total_lines > 0
                        else 0.0,
                        2,
                    ),
                }
                success_count += 1

                self.logger.info(
                    f"分支 {branch} 统计完成: "
                    f"总行数={result.total_lines}, "
                    f"AI 行数={result.ai_lines}, "
                    f"AI 占比={branch_results[branch]['ai_ratio']}%"
                )

            # 返回汇总信息
            return {
                "success": failed_count == 0,
                "total_branches": len(target_branches),
                "success_branches": success_count,
                "failed_branches": failed_count,
                "branch_results": branch_results,
            }

        except Exception as e:
            self.logger.error(f"统计仓库时出错: {e}", exc_info=True)
            return None

        finally:
            # 清理临时目录
            if temp_dir and os.path.exists(temp_dir):
                self.git_clone_service.cleanup_temp_dir(temp_dir)

    def _save_branch_stats(self, repo_id: str, stat_date: str, result) -> None:

        branch = result.branch
        now = int(time.time() * 1000)

        contributor_ids = {}
        for contrib_key in result.contributor_stats:
            contributor_ids[contrib_key] = self.blame_stats_db.get_or_create_contributor(
                "Unknown", None
            )

        ai_ratio = (
            (result.ai_lines / result.total_lines * 100)
            if result.total_lines > 0
            else 0.0
        )
        repo_obj = StatsBlameRepo(
            id=gen_xid(),
            repo_id=repo_id,
            stat_date=stat_date,
            commit_sha=result.commit_sha,
            branch=branch,
            total_lines=result.total_lines,
            ai_lines=result.ai_lines,
            non_ai_lines=result.non_ai_lines,
            ai_ratio=ai_ratio,
            total_files=result.total_files,
            created_at=now,
            updated_at=now,
        )

        file_id_map = {}
        file_objs = []
        for fr in result.files_results:
            fid = gen_xid()
            file_id_map[fr.file_path] = fid
            fr_ratio = (
                (fr.ai_lines / fr.total_lines * 100) if fr.total_lines > 0 else 0.0
            )
            file_objs.append(
                StatsBlameFile(
                    id=fid,
                    repo_id=repo_id,
                    branch=branch,
                    stat_date=stat_date,
                    file_path=fr.file_path,
                    commit_sha=fr.commit_sha,
                    total_lines=fr.total_lines,
                    ai_lines=fr.ai_lines,
                    non_ai_lines=fr.non_ai_lines,
                    ai_ratio=fr_ratio,
                    created_at=now,
                    updated_at=now,
                )
            )

        rc_objs = []
        for contrib_key, stats in result.contributor_stats.items():
            rc_objs.append(
                StatsBlameRepoContributor(
                    id=gen_xid(),
                    repo_id=repo_id,
                    branch=branch,
                    stat_date=stat_date,
                    contributor_id=contributor_ids[contrib_key],
                    contributor_name=contrib_key,
                    contributor_email="",
                    ai_lines=stats["ai_lines"],
                    non_ai_lines=stats["non_ai_lines"],
                    total_lines=stats["total_lines"],
                    created_at=now,
                    updated_at=now,
                )
            )

        fc_objs = []
        for fr in result.files_results:
            fid = file_id_map.get(fr.file_path)
            if not fid:
                continue
            for contrib_key, stats in fr.contributor_stats.items():
                fc_objs.append(
                    StatsBlameFileContributor(
                        id=gen_xid(),
                        file_id=fid,
                        stat_date=stat_date,
                        repo_id=repo_id,
                        branch=branch,
                        file_path=fr.file_path,
                        contributor_id=contributor_ids.get(contrib_key),
                        contributor_name=contrib_key,
                        contributor_email=None,
                        ai_lines=stats["ai_lines"],
                        non_ai_lines=stats["non_ai_lines"],
                        total_lines=stats["total_lines"],
                        created_at=now,
                        updated_at=now,
                    )
                )
        self.blame_stats_db.save_branch_stats_batch(repo_id, branch, stat_date, repo_obj, file_objs, rc_objs, fc_objs)
