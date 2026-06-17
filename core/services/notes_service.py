"""
REST Notes Store 服务

提供 Authorship Notes 数据的 CRUD 业务逻辑。
"""

from core.config.logging import Logger
from core.database.authorship_notes_db import AuthorshipNotesDatabase
from core.utils.repo_url import normalize_repo_url


class NotesRestService:
    """REST Notes Store 服务"""

    def __init__(self):
        """初始化 NotesRestService"""
        self.logger = Logger.get_logger("services.notes")
        self.database = AuthorshipNotesDatabase()

    def create_or_update_note(
        self,
        repo_url: str,
        branch: str,
        commit_sha: str,
        content: str,
        author_name: str,
        author_email: str,
        note_blob_oid: str | None = None,
        original_commit_sha: str | None = None,
    ):
        """创建或更新单个 note"""
        repo_url = normalize_repo_url(repo_url)
        return self.database.create_or_update_note(
            repo_url=repo_url,
            branch=branch,
            commit_sha=commit_sha,
            note_blob_oid=(
                original_commit_sha
                if original_commit_sha is not None
                else note_blob_oid
            ),
            content=content,
            author_name=author_name,
            author_email=author_email,
        )

    def get_note(
        self, repo_url: str, commit_sha: str, include_superseded: bool = False
    ):
        """获取单个 note"""
        repo_url = normalize_repo_url(repo_url)
        return self.database.get_note(
            repo_url=repo_url,
            commit_sha=commit_sha,
            include_superseded=include_superseded,
        )

    def batch_get_notes(
        self, repo_url: str, commit_shas: list, include_superseded: bool = False
    ):
        """批量获取 notes"""
        repo_url = normalize_repo_url(repo_url)
        return self.database.batch_get_notes(
            repo_url=repo_url,
            commit_shas=commit_shas,
            include_superseded=include_superseded,
        )

    def batch_push_notes(self, repo_url: str, notes_data: list):
        """批量推送（创建/更新）notes"""
        repo_url = normalize_repo_url(repo_url)
        return self.database.batch_push_notes(repo_url=repo_url, notes_data=notes_data)

    def rewrite_notes(
        self,
        repo_url: str,
        rewrite_id: str,
        operation: str,
        branch: str,
        original_head: str | None,
        new_head: str | None,
        mappings: list[dict],
    ):
        repo_url = normalize_repo_url(repo_url)
        return self.database.rewrite_notes(
            repo_url=repo_url,
            rewrite_id=rewrite_id,
            operation=operation,
            branch=branch,
            original_head=original_head,
            new_head=new_head,
            mappings=mappings,
        )

    def list_notes(
        self,
        repo_url: str,
        since_commit_time: int | None = None,
        since_change_seq: int | None = None,
        limit: int | None = None,
        include_superseded: bool = False,
    ):
        repo_url = normalize_repo_url(repo_url)
        return self.database.list_notes(
            repo_url=repo_url,
            since_commit_time=since_commit_time,
            since_change_seq=since_change_seq,
            limit=limit,
            include_superseded=include_superseded,
        )

    def search_notes(
        self, repo_url: str, pattern: str, include_superseded: bool = False
    ):
        """在注释内容中搜索"""
        repo_url = normalize_repo_url(repo_url)
        return self.database.search_notes(
            repo_url=repo_url,
            pattern=pattern,
            include_superseded=include_superseded,
        )

    def close(self):
        self.database.close()
