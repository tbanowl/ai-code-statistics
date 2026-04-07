"""
Authorship Notes 数据库操作类

负责 authorship_notes 表的所有操作。
"""

from typing import Dict, List, Optional
from sqlalchemy import select

from .base import session_scope, BaseDatabase
from .models import AuthorshipNotes, gen_xid


class AuthorshipNotesDatabase(BaseDatabase):
    """Authorship Notes 数据库操作类"""


    def create_or_update_note(
        self,
        repo_url: str,
        branch: str,
        commit_sha: str,
        note_blob_oid: str | None,
        content: str,
        author_name: str,
        author_email: str,
    ) -> AuthorshipNotes:
        """创建或更新单个 note

        Args:
            repo_url: 仓库远程 URL
            branch: 分支名称
            commit_sha: 提交 SHA
            note_blob_oid: 原始提交 SHA（rebase/cherry-pick 前）
            content: note 内容
            author_name: 作者名称
            author_email: 作者邮箱

        Returns:
            AuthorshipNotes: 创建或更新后的 note
        """
        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha == commit_sha,
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                # 更新现有记录
                result.branch = branch
                setattr(result, "note_blob_oid", note_blob_oid)
                result.note_content = content
                result.author_name = author_name
                result.author_email = author_email
            else:
                # 创建新记录
                note = AuthorshipNotes(
                    id=gen_xid(),
                    repo_url=repo_url,
                    branch=branch,
                    commit_sha=commit_sha,
                    note_blob_oid=note_blob_oid,
                    note_content=content,
                    author_name=author_name,
                    author_email=author_email,
                )
                session.add(note)

            session.flush()
            return session.execute(stmt).scalar_one()

    def get_note(self, repo_url: str, commit_sha: str) -> Optional[AuthorshipNotes]:
        """获取单个 note

        Args:
            repo_url: 仓库远程 URL
            commit_sha: 提交 SHA

        Returns:
            AuthorshipNotes 或 None
        """
        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha == commit_sha,
            )
            return session.execute(stmt).scalar_one_or_none()

    def batch_get_notes(self, repo_url: str, commit_shas: List[str]) -> Dict[str, List]:
        """批量获取 notes

        Args:
            repo_url: 仓库远程 URL
            commit_shas: 提交 SHA 列表

        Returns:
            dict: {"notes": [dict], "missing": [str]}
        """
        if not commit_shas:
            return {"notes": [], "missing": []}

        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha.in_(commit_shas),
            )
            results = session.execute(stmt).scalars().all()

            found_shas = set(note.commit_sha for note in results)
            notes = [
                {"commit_sha": note.commit_sha, "content": note.note_content}
                for note in results
            ]
            missing = [sha for sha in commit_shas if sha not in found_shas]

        return {"notes": notes, "missing": missing}

    def batch_push_notes(self, repo_url: str, notes_data: List[Dict]) -> Dict[str, int]:
        """批量推送（创建/更新）notes

        Args:
            repo_url: 仓库远程 URL
            notes_data: notes 列表

        Returns:
            dict: {"created": int, "updated": int}
        """
        created = 0
        updated = 0

        with session_scope(self.engine) as session:
            existing_stmt = select(AuthorshipNotes.commit_sha).where(
                AuthorshipNotes.repo_url == repo_url
            )
            existing_shas = set(session.execute(existing_stmt).scalars().all())

            for note_data in notes_data:
                commit_sha = note_data["commit_sha"]

                if commit_sha in existing_shas:
                    # 更新
                    stmt = select(AuthorshipNotes).where(
                        AuthorshipNotes.repo_url == repo_url,
                        AuthorshipNotes.commit_sha == commit_sha,
                    )
                    note = session.execute(stmt).scalar_one()
                    note.branch = note_data["branch"]
                    setattr(
                        note,
                        "note_blob_oid",
                        note_data.get(
                            "original_commit_sha", note_data.get("note_blob_oid")
                        ),
                    )
                    note.note_content = note_data["content"]
                    note.author_name = note_data["author_name"]
                    note.author_email = note_data["author_email"]
                    updated += 1
                else:
                    # 创建
                    note = AuthorshipNotes(
                        id=gen_xid(),
                        repo_url=repo_url,
                        branch=note_data["branch"],
                        commit_sha=commit_sha,
                        note_blob_oid=note_data.get(
                            "original_commit_sha", note_data.get("note_blob_oid")
                        ),
                        note_content=note_data["content"],
                        author_name=note_data["author_name"],
                        author_email=note_data["author_email"],
                    )
                    session.add(note)
                    existing_shas.add(commit_sha)
                    created += 1

        return {"created": created, "updated": updated}

    def list_notes(self, repo_url: str) -> List[str]:
        """列出仓库中所有有注释的提交 SHA

        Args:
            repo_url: 仓库远程 URL

        Returns:
            list: 提交 SHA 列表
        """
        with session_scope(self.engine) as session:
            stmt = (
                select(AuthorshipNotes.commit_sha)
                .where(AuthorshipNotes.repo_url == repo_url)
                .order_by(AuthorshipNotes.commit_sha)
            )
            return list(session.execute(stmt).scalars().all())

    def search_notes(self, repo_url: str, pattern: str) -> List[str]:
        """在注释内容中搜索

        Args:
            repo_url: 仓库远程 URL
            pattern: 搜索模式

        Returns:
            list: 匹配的提交 SHA 列表
        """
        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes.commit_sha).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.note_content.like(f"%{pattern}%"),
            )
            return list(session.execute(stmt).scalars().all())
