"""
REST Notes Store 服务

提供 Authorship Notes 数据的 CRUD 业务逻辑。
"""

from core.config.logging import Logger
from core.database.notes_db import NotesDatabase


class NotesRestService:
    """REST Notes Store 服务"""

    def __init__(self):
        """初始化 NotesRestService"""
        self.logger = Logger.get_logger('services.notes')
        self.database = NotesDatabase()

    def create_or_update_note(
        self,
        repo_url: str,
        branch: str,
        commit_sha: str,
        note_blob_oid: str,
        content: str,
        author_name: str,
        author_email: str
    ):
        """创建或更新单个 note"""
        return self.database.create_or_update_note(
            repo_url=repo_url,
            branch=branch,
            commit_sha=commit_sha,
            note_blob_oid=note_blob_oid,
            content=content,
            author_name=author_name,
            author_email=author_email
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

    def list_notes(self, repo_url: str):
        """列出仓库中所有有注释的提交 SHA"""
        return self.database.list_notes(repo_url=repo_url)

    def search_notes(self, repo_url: str, pattern: str):
        """在注释内容中搜索"""
        return self.database.search_notes(repo_url=repo_url, pattern=pattern)
