"""Git Blame 统计数据库操作类"""

import time
from core.config.logging import Logger
from core.database.base import BaseDatabase, session_scope
from core.database.models import (
    AuthorshipNotes,
    StatsBlameFile,
    StatsBlameFileContributor,
    StatsBlameRepo,
    StatsBlameRepoContributor,
    StatsRepoBranchConfig,
    StatsRepositoryBranch,
    StatsRepository,
    StatsContributor,
    gen_xid
)

class BlameStatsDatabase(BaseDatabase):
    """Blame 统计数据库操作类"""

    def __init__(self):
        """
        初始化 Blame Stats 数据库操作类

        Args:
            database: 数据库实例
        """
        super().__init__()
        self.logger = Logger.get_logger("database.blame_stats")

    # ============================================================================
    # 仓库管理
    # ============================================================================

    def update_repository_stats_flag(self, repo_id: str, repo_stats_flag: int) -> bool:
        """
        更新仓库的统计标志

        Args:
            repo_id: 仓库 ID
            repo_stats_flag: 是否启用统计 (0 或 1)

        Returns:
            是否更新成功
        """
        with session_scope(self.engine) as session:
            repo = (
                session.query(StatsRepository)
                .filter(StatsRepository.id == repo_id)
                .first()
            )

            if not repo:
                return False

            repo.repo_stats_flag = repo_stats_flag
            repo.updated_at = int(time.time() * 1000)
            return True

    def update_repository_ssh_key(self, repo_id: str, ssh_key_id: str) -> bool:
        """
        更新仓库的 SSH Key

        Args:
            repo_id: 仓库 ID
            ssh_key_id: SSH Key ID

        Returns:
            是否更新成功
        """
        with session_scope(self.engine) as session:
            repo = (
                session.query(StatsRepository)
                .filter(StatsRepository.id == repo_id)
                .first()
            )

            if not repo:
                return False

            repo.ssh_key_id = ssh_key_id
            repo.updated_at = int(time.time() * 1000)
            return True

    def get_repositories_to_stat(self) -> list:
        """
        获取需要统计的仓库列表

        Returns:
            仓库列表
        """
        with session_scope(self.engine) as session:
            repos = (
                session.query(StatsRepository)
                .filter(StatsRepository.repo_stats_flag == 1)
                .all()
            )

            return [
                {
                    "id": repo.id,
                    "repo_path": repo.repo_path,
                    "repo_name": repo.repo_name,
                    "ssh_key_id": repo.ssh_key_id,
                }
                for repo in repos
            ]

    def get_repository_by_id(self, repo_id: str):
        """
        根据 ID 获取仓库

        Args:
            repo_id: 仓库 ID

        Returns:
            仓库对象
        """
        with session_scope(self.engine) as session:
            return (
                session.query(StatsRepository)
                .filter(StatsRepository.id == repo_id)
                .first()
            )

    def get_repository_repo_url(self, repo_id: str) -> str:
        """
        获取仓库的 repo_path（用作 repo_url）

        Args:
            repo_id: 仓库 ID

        Returns:
            仓库路径字符串
        """
        with session_scope(self.engine) as session:
            repo = (
                session.query(StatsRepository)
                .filter(StatsRepository.id == repo_id)
                .first()
            )

            if not repo:
                return ""

            return repo.repo_path

    def get_repo_branch_configs(self, repo_id: str) -> list:
        """
        获取仓库的分支配置（仅返回已启用的配置）

        Args:
            repo_id: 仓库 ID

        Returns:
            分支配置列表（仅包含 enabled=1 的配置）
        """
        with session_scope(self.engine) as session:
            configs = (
                session.query(StatsRepoBranchConfig)
                .filter(
                    StatsRepoBranchConfig.repo_id == repo_id,
                    StatsRepoBranchConfig.enabled == 1,
                )
                .all()
            )

            return [
                {
                    "id": c.id,
                    "branch_pattern": c.branch_pattern,
                    "pattern_type": c.pattern_type,
                    "enabled": c.enabled,
                }
                for c in configs
            ]

    def get_repository_branches(self, repo_id: str) -> list[str]:
        """从仓库实际分支表获取分支名称列表。"""
        with session_scope(self.engine) as session:
            rows = (
                session.query(StatsRepositoryBranch)
                .filter(StatsRepositoryBranch.repo_id == repo_id)
                .order_by(StatsRepositoryBranch.branch_name.asc())
                .all()
            )

            return [row.branch_name for row in rows if (row.branch_name or "").strip()]

    def save_repo_branch_config(
        self,
        repo_id: str,
        branch_pattern: str,
        pattern_type: str = "exact",
        enabled: int = 1,
    ) -> str:
        """
        保存分支配置（如果已存在相同的 repo_id + branch_pattern，则更新现有记录）

        Args:
            repo_id: 仓库 ID
            branch_pattern: 分支模式
            pattern_type: 模式类型
            enabled: 是否启用

        Returns:
            配置 ID
        """
        now = int(time.time() * 1000)

        with session_scope(self.engine) as session:
            # 检查是否存在相同的 (repo_id, branch_pattern)
            existing = (
                session.query(StatsRepoBranchConfig)
                .filter(
                    StatsRepoBranchConfig.repo_id == repo_id,
                    StatsRepoBranchConfig.branch_pattern == branch_pattern,
                )
                .first()
            )

            if existing:
                # 更新现有记录
                existing.pattern_type = pattern_type
                existing.enabled = enabled
                existing.updated_at = now
                session.flush()
                return existing.id
            else:
                # 创建新记录
                config = StatsRepoBranchConfig(
                    id=gen_xid(),
                    repo_id=repo_id,
                    branch_pattern=branch_pattern,
                    pattern_type=pattern_type,
                    enabled=enabled,
                    created_at=now,
                    updated_at=now,
                )
                session.add(config)
                session.flush()
                return config.id

    def delete_repo_branch_configs(self, repo_id: str) -> None:
        """
        删除仓库的所有分支配置

        Args:
            repo_id: 仓库 ID
        """
        with session_scope(self.engine) as session:
            session.query(StatsRepoBranchConfig).filter(
                StatsRepoBranchConfig.repo_id == repo_id
            ).delete()

    def get_all_repo_branch_configs(self, repo_id: str) -> list:
        with session_scope(self.engine) as session:
            configs = (
                session.query(StatsRepoBranchConfig)
                .filter(StatsRepoBranchConfig.repo_id == repo_id)
                .all()
            )
            return [
                {
                    "id": c.id,
                    "branch_pattern": c.branch_pattern,
                    "pattern_type": c.pattern_type,
                    "enabled": c.enabled,
                }
                for c in configs
            ]

    def update_repo_branch_config_by_id(
        self,
        config_id: str,
        branch_pattern: str,
        pattern_type: str,
        enabled: int,
    ) -> bool:
        with session_scope(self.engine) as session:
            config = (
                session.query(StatsRepoBranchConfig)
                .filter(StatsRepoBranchConfig.id == config_id)
                .first()
            )
            if not config:
                return False
            config.branch_pattern = branch_pattern
            config.pattern_type = pattern_type
            config.enabled = enabled
            config.updated_at = int(time.time() * 1000)
            return True

    def delete_repo_branch_config_by_id(self, config_id: str) -> bool:
        with session_scope(self.engine) as session:
            deleted = (
                session.query(StatsRepoBranchConfig)
                .filter(StatsRepoBranchConfig.id == config_id)
                .delete()
            )
            return deleted > 0

    # ============================================================================
    # 删除当天统计结果
    # ============================================================================

    def delete_daily_repo_stats(self, repo_id: str, stat_date: int) -> None:
        """
        删除仓库级别的当天统计结果

        Args:
            repo_id: 仓库 ID
            stat_date: 统计日期
        """
        with session_scope(self.engine) as session:
            session.query(StatsBlameRepo).filter(
                StatsBlameRepo.repo_id == repo_id, StatsBlameRepo.stat_date == stat_date
            ).delete()

    def delete_daily_file_stats(self, repo_id: str, stat_date: int) -> None:
        """
        删除文件级别的当天统计结果

        Args:
            repo_id: 仓库 ID
            stat_date: 统计日期
        """
        with session_scope(self.engine) as session:
            session.query(StatsBlameFile).filter(
                StatsBlameFile.repo_id == repo_id, StatsBlameFile.stat_date == stat_date
            ).delete()

    def delete_daily_repo_contributor_stats(self, repo_id: str, stat_date: int) -> None:
        """
        删除仓库贡献者级别的当天统计结果

        Args:
            repo_id: 仓库 ID
            stat_date: 统计日期
        """
        with session_scope(self.engine) as session:
            session.query(StatsBlameRepoContributor).filter(
                StatsBlameRepoContributor.repo_id == repo_id,
                StatsBlameRepoContributor.stat_date == stat_date,
            ).delete()

    def delete_daily_file_contributor_stats(self, repo_id: str, stat_date: int) -> None:
        """
        删除文件贡献者级别的当天统计结果

        Args:
            repo_id: 仓库 ID
            stat_date: 统计日期
        """
        with session_scope(self.engine) as session:
            session.query(StatsBlameFileContributor).filter(
                StatsBlameFileContributor.repo_id == repo_id,
                StatsBlameFileContributor.stat_date == stat_date,
            ).delete()

    # ============================================================================
    # 保存统计结果
    # ============================================================================

    def save_repo_blame_stats(
        self,
        repo_id: str,
        stat_date: str,
        commit_sha: str,
        branch: str,
        total_lines: int,
        ai_lines: int,
        non_ai_lines: int,
        total_files: int,
    ) -> str:
        """
        保存仓库级 blame 统计结果

        Returns:
            统计记录 ID
        """
        ai_ratio = (ai_lines / total_lines * 100) if total_lines > 0 else 0.0
        now = int(time.time() * 1000)

        with session_scope(self.engine) as session:
            # 先删除当天旧数据
            session.query(StatsBlameRepo).filter(
                StatsBlameRepo.repo_id == repo_id,
                StatsBlameRepo.stat_date == stat_date,
                StatsBlameRepo.branch == branch,
            ).delete()

            # 插入新数据
            stats = StatsBlameRepo(
                id=gen_xid(),
                repo_id=repo_id,
                stat_date=stat_date,
                commit_sha=commit_sha,
                branch=branch,
                total_lines=total_lines,
                ai_lines=ai_lines,
                non_ai_lines=non_ai_lines,
                ai_ratio=ai_ratio,
                total_files=total_files,
                created_at=now,
                updated_at=now,
            )
            session.add(stats)
            session.flush()

            return stats.id

    def save_file_blame_stats(
        self,
        repo_id: str,
        branch: str,
        stat_date: str,
        file_path: str,
        commit_sha: str,
        total_lines: int,
        ai_lines: int,
        non_ai_lines: int,
    ) -> str:
        """
        保存文件级 blame 统计结果

        Returns:
            文件统计记录 ID
        """
        ai_ratio = (ai_lines / total_lines * 100) if total_lines > 0 else 0.0
        now = int(time.time() * 1000)

        with session_scope(self.engine) as session:
            # 先删除当天旧数据
            session.query(StatsBlameFile).filter(
                StatsBlameFile.repo_id == repo_id,
                StatsBlameFile.stat_date == stat_date,
                StatsBlameFile.file_path == file_path,
                StatsBlameFile.branch == branch,
            ).delete()

            # 插入新数据
            stats = StatsBlameFile(
                id=gen_xid(),
                repo_id=repo_id,
                branch=branch,
                stat_date=stat_date,
                file_path=file_path,
                commit_sha=commit_sha,
                total_lines=total_lines,
                ai_lines=ai_lines,
                non_ai_lines=non_ai_lines,
                ai_ratio=ai_ratio,
                created_at=now,
                updated_at=now,
            )
            session.add(stats)
            session.flush()

            return stats.id

    def save_repo_contributor_stats(
        self,
        repo_id: str,
        branch: str,
        stat_date: str,
        contributor_id: str,
        contributor_name: str,
        contributor_email: str,
        ai_lines: int,
        non_ai_lines: int,
        total_lines: int,
    ) -> str:
        """
        保存仓库贡献者 blame 统计结果

        Returns:
            贡献者统计记录 ID
        """
        now = int(time.time() * 1000)

        with session_scope(self.engine) as session:
            # 先删除当天旧数据
            session.query(StatsBlameRepoContributor).filter(
                StatsBlameRepoContributor.repo_id == repo_id,
                StatsBlameRepoContributor.stat_date == stat_date,
                StatsBlameRepoContributor.contributor_id == contributor_id,
                StatsBlameRepoContributor.branch == branch,
            ).delete()

            # 插入新数据
            stats = StatsBlameRepoContributor(
                id=gen_xid(),
                repo_id=repo_id,
                branch=branch,
                stat_date=stat_date,
                contributor_id=contributor_id,
                contributor_name=contributor_name,
                contributor_email=contributor_email,
                ai_lines=ai_lines,
                non_ai_lines=non_ai_lines,
                total_lines=total_lines,
                created_at=now,
                updated_at=now,
            )
            session.add(stats)
            session.flush()

            return stats.id

    def save_file_contributor_stats(
        self,
        file_id: str,
        stat_date: int,
        repo_id: str,
        branch: str,
        file_path: str,
        contributor_id: str,
        contributor_name: str,
        contributor_email: str,
        ai_lines: int,
        non_ai_lines: int,
        total_lines: int,
    ) -> str:
        """
        保存文件贡献者 blame 统计结果

        Returns:
            贡献者统计记录 ID
        """
        now = int(time.time() * 1000)

        with session_scope(self.engine) as session:
            # 先删除当天旧数据
            session.query(StatsBlameFileContributor).filter(
                StatsBlameFileContributor.file_id == file_id,
                StatsBlameFileContributor.stat_date == stat_date,
                StatsBlameFileContributor.contributor_id == contributor_id,
                StatsBlameFileContributor.branch == branch,
            ).delete()

            # 插入新数据
            stats = StatsBlameFileContributor(
                id=gen_xid(),
                file_id=file_id,
                stat_date=stat_date,
                repo_id=repo_id,
                branch=branch,
                file_path=file_path,
                contributor_id=contributor_id,
                contributor_name=contributor_name,
                contributor_email=contributor_email,
                ai_lines=ai_lines,
                non_ai_lines=non_ai_lines,
                total_lines=total_lines,
                created_at=now,
                updated_at=now,
            )
            session.add(stats)
            session.flush()

            return stats.id

    def save_branch_stats_batch(self, repo_id: str, branch: str, stat_date: str, repo_obj, file_objs, rc_objs, fc_objs) -> None:
        """
        以仓库+分支为维度，在单个事务内保存所有统计数据。
        先检查当天数据是否存在，存在则删除，再批量插入（每批 1000 条）。
        """
        BATCH_SIZE = 1000

        with session_scope(self.engine) as session:
            exists = (
                session.query(StatsBlameRepo)
                .filter(
                    StatsBlameRepo.repo_id == repo_id,
                    StatsBlameRepo.stat_date == stat_date,
                    StatsBlameRepo.branch == branch,
                )
                .first()
            )

            if exists:
                session.query(StatsBlameRepo).filter(
                    StatsBlameRepo.repo_id == repo_id,
                    StatsBlameRepo.stat_date == stat_date,
                    StatsBlameRepo.branch == branch,
                ).delete()
                session.query(StatsBlameFile).filter(
                    StatsBlameFile.repo_id == repo_id,
                    StatsBlameFile.stat_date == stat_date,
                    StatsBlameFile.branch == branch,
                ).delete()
                session.query(StatsBlameRepoContributor).filter(
                    StatsBlameRepoContributor.repo_id == repo_id,
                    StatsBlameRepoContributor.stat_date == stat_date,
                    StatsBlameRepoContributor.branch == branch,
                ).delete()
                session.query(StatsBlameFileContributor).filter(
                    StatsBlameFileContributor.repo_id == repo_id,
                    StatsBlameFileContributor.stat_date == stat_date,
                    StatsBlameFileContributor.branch == branch,
                ).delete()

            session.add(repo_obj)
            for i in range(0, len(file_objs), BATCH_SIZE):
                session.bulk_save_objects(file_objs[i : i + BATCH_SIZE])
            for i in range(0, len(rc_objs), BATCH_SIZE):
                session.bulk_save_objects(rc_objs[i : i + BATCH_SIZE])
            for i in range(0, len(fc_objs), BATCH_SIZE):
                session.bulk_save_objects(fc_objs[i : i + BATCH_SIZE])

    def save_batch_file_contributor_stats(self, stats_list: list) -> int:
        """
        批量保存文件贡献者统计结果

        Args:
            stats_list: 统计结果列表

        Returns:
            保存的记录数量
        """
        now = int(time.time() * 1000)

        with session_scope(self.engine) as session:
            count = 0
            for stats in stats_list:
                # 先删除当天旧数据
                session.query(StatsBlameFileContributor).filter(
                    StatsBlameFileContributor.file_id == stats["file_id"],
                    StatsBlameFileContributor.stat_date == stats["stat_date"],
                    StatsBlameFileContributor.contributor_id == stats["contributor_id"],
                    StatsBlameFileContributor.branch == stats["branch"],
                ).delete()

                # 插入新数据
                stat = StatsBlameFileContributor(
                    id=gen_xid(),
                    file_id=stats["file_id"],
                    stat_date=stats["stat_date"],
                    repo_id=stats["repo_id"],
                    branch=stats["branch"],
                    file_path=stats["file_path"],
                    contributor_id=stats["contributor_id"],
                    contributor_name=stats["contributor_name"],
                    contributor_email=stats["contributor_email"],
                    ai_lines=stats["ai_lines"],
                    non_ai_lines=stats["non_ai_lines"],
                    total_lines=stats["total_lines"],
                    created_at=now,
                    updated_at=now,
                )
                session.add(stat)
                count += 1

            return count

    # ============================================================================
    # 贡献者管理
    # ============================================================================

    def get_or_create_contributor(self, name: str, email: str | None) -> str:
        """
        获取或创建贡献者

        Args:
            name: 贡献者姓名
            email: 贡献者邮箱

        Returns:
            贡献者 ID
        """
        # 通过 email 查找
        if email:
            with session_scope(self.engine) as session:
                contrib = (
                    session.query(StatsContributor)
                    .filter(StatsContributor.email == email)
                    .first()
                )
                if contrib:
                    return contrib.id

        # 通过 name 和 email 组合查找
        with session_scope(self.engine) as session:
            contrib = (
                session.query(StatsContributor)
                .filter(StatsContributor.name == name)
                .first()
            )
            if contrib:
                return contrib.id

        # 创建新的贡献者
        now = int(time.time() * 1000)
        with session_scope(self.engine) as session:
            contrib = StatsContributor(
                id=gen_xid(),
                name=name,
                email=email,
                created_at=now,
                updated_at=now,
            )
            session.add(contrib)
            session.flush()

            return contrib.id

    # ============================================================================
    # 查询方法
    # ============================================================================

    def get_repo_blame_stats(
        self, repo_id: str, start_date: int | None, end_date: int | None
    ) -> list:
        """
        查询仓库归因统计数据

        Args:
            repo_id: 仓库 ID
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            统计数据列表
        """
        with session_scope(self.engine) as session:
            query = session.query(StatsBlameRepo).filter(
                StatsBlameRepo.repo_id == repo_id
            )

            if start_date:
                query = query.filter(StatsBlameRepo.stat_date >= start_date)
            if end_date:
                query = query.filter(StatsBlameRepo.stat_date <= end_date)

            query = query.order_by(StatsBlameRepo.stat_date.desc())

            stats = query.all()

            return [
                {
                    "id": s.id,
                    "repo_id": s.repo_id,
                    "stat_date": s.stat_date,
                    "commit_sha": s.commit_sha,
                    "branch": s.branch,
                    "total_lines": s.total_lines,
                    "ai_lines": s.ai_lines,
                    "non_ai_lines": s.non_ai_lines,
                    "ai_ratio": float(s.ai_ratio) if s.ai_ratio else 0.0,
                    "total_files": s.total_files,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                }
                for s in stats
            ]

    def get_file_blame_stats(self, repo_id: str, stat_date: str | None) -> list:
        """
        查询文件归因统计数据

        Args:
            repo_id: 仓库 ID
            stat_date: 统计日期（可选）

        Returns:
            文件统计数据列表
        """
        with session_scope(self.engine) as session:
            query = session.query(StatsBlameFile).filter(
                StatsBlameFile.repo_id == repo_id
            )

            if stat_date:
                query = query.filter(StatsBlameFile.stat_date == stat_date)

            query = query.order_by(StatsBlameFile.ai_lines.desc())

            stats = query.all()

            return [
                {
                    "id": s.id,
                    "repo_id": s.repo_id,
                    "branch": s.branch,
                    "stat_date": s.stat_date,
                    "file_path": s.file_path,
                    "commit_sha": s.commit_sha,
                    "total_lines": s.total_lines,
                    "ai_lines": s.ai_lines,
                    "non_ai_lines": s.non_ai_lines,
                    "ai_ratio": float(s.ai_ratio) if s.ai_ratio else 0.0,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                }
                for s in stats
            ]

    def get_git_notes_batch(self, commit_shas: list[str]) -> dict[str, str]:
        if not commit_shas:
            return {}


        with session_scope(self.engine) as session:
            notes = (
                session.query(AuthorshipNotes)
                .filter(AuthorshipNotes.commit_sha.in_(commit_shas))
                .all()
            )

            return {note.commit_sha: note.note_content for note in notes}

    def get_repo_contributor_stats(self, repo_id: str, stat_date: int | None) -> list:
        """
        查询仓库贡献者归因统计数据

        Args:
            repo_id: 仓库 ID
            stat_date: 统计日期（可选）

        Returns:
            贡献者统计数据列表
        """
        with session_scope(self.engine) as session:
            query = session.query(StatsBlameRepoContributor).filter(
                StatsBlameRepoContributor.repo_id == repo_id
            )

            if stat_date:
                query = query.filter(StatsBlameRepoContributor.stat_date == stat_date)

            query = query.order_by(StatsBlameRepoContributor.ai_lines.desc())

            stats = query.all()

            return [
                {
                    "id": s.id,
                    "repo_id": s.repo_id,
                    "branch": s.branch,
                    "stat_date": s.stat_date,
                    "contributor_id": s.contributor_id,
                    "contributor_name": s.contributor_name,
                    "contributor_email": s.contributor_email,
                    "ai_lines": s.ai_lines,
                    "non_ai_lines": s.non_ai_lines,
                    "total_lines": s.total_lines,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                }
                for s in stats
            ]

    def get_blame_repo_stats_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: int | None = None,
        end_date: int | None = None,
        repo_id: str | None = None,
    ) -> dict:
        with session_scope(self.engine) as session:
            query = session.query(StatsBlameRepo)
            if start_date is not None:
                query = query.filter(StatsBlameRepo.stat_date >= start_date)
            if end_date is not None:
                query = query.filter(StatsBlameRepo.stat_date <= end_date)
            if repo_id:
                query = query.filter(StatsBlameRepo.repo_id == repo_id)

            total = query.count()
            rows = (
                query.join(
                    StatsRepository, StatsRepository.id == StatsBlameRepo.repo_id
                )
                .with_entities(StatsBlameRepo, StatsRepository.repo_name)
                .order_by(StatsBlameRepo.stat_date.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [
                    {
                        "id": s.id,
                        "repo_id": s.repo_id,
                        "repo_name": repo_name or "未知仓库",
                        "stat_date": s.stat_date,
                        "branch": s.branch,
                        "ai_lines": s.ai_lines,
                        "non_ai_lines": s.non_ai_lines,
                        "total_lines": s.total_lines,
                        "ai_ratio": float(s.ai_ratio) if s.ai_ratio else 0.0,
                    }
                    for s, repo_name in rows
                ],
            }
