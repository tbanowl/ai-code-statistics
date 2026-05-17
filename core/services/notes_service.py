"""
REST Notes Store 服务

提供 Authorship Notes 数据的 CRUD 业务逻辑。
"""

import core.config.loader as loader
from core.config.logging import Logger
from core.database.authorship_notes_db import AuthorshipNotesDatabase


class NotesRestService:
    """REST Notes Store 服务"""

    def __init__(self, db_url: str | None = None):
        """初始化 NotesRestService"""
        if db_url:
            loader.config_data = {"database": {"url": db_url, "echo": False}}
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

    def get_note(self, repo_url: str, commit_sha: str):
        """获取单个 note"""
        return self.database.get_note(repo_url=repo_url, commit_sha=commit_sha)

    def batch_get_notes(self, repo_url: str, commit_shas: list):
        """批量获取 notes"""
        return self.database.batch_get_notes(repo_url=repo_url, commit_shas=commit_shas)

    def batch_push_notes(self, repo_url: str, notes_data: list):
        """批量推送（创建/更新）notes"""
        return self.database.batch_push_notes(repo_url=repo_url, notes_data=notes_data)

    def list_notes(
        self,
        repo_url: str,
        since_commit_time: int | None = None,
        since_change_seq: int | None = None,
        limit: int | None = None,
    ):
        return self.database.list_notes(
            repo_url=repo_url,
            since_commit_time=since_commit_time,
            since_change_seq=since_change_seq,
            limit=limit,
        )

    def search_notes(self, repo_url: str, pattern: str):
        """在注释内容中搜索"""
        return self.database.search_notes(repo_url=repo_url, pattern=pattern)

    def close(self):
        self.database.close()
