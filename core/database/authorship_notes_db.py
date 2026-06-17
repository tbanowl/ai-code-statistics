"""Authorship Notes 数据库操作类。"""

import hashlib
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, or_, select
from sqlalchemy.engine import Engine

from core.config import loader
from core.utils.repo_url import normalize_repo_url
from .base import session_scope, BaseDatabase
from .models import AuthorshipNotes, AuthorshipNotesSeq, gen_xid


DEFAULT_LIST_LIMIT = 1000
MAX_LIST_LIMIT = 5000


def compute_note_content_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def normalize_list_limit(limit: int | None) -> int:
    if limit is None or limit <= 0:
        return DEFAULT_LIST_LIMIT
    return min(limit, MAX_LIST_LIMIT)


def active_authorship_note_filter():
    return or_(AuthorshipNotes.status.is_(None), AuthorshipNotes.status == "active")


def apply_active_filter(stmt, include_superseded: bool):
    if include_superseded:
        return stmt
    return stmt.where(active_authorship_note_filter())


class AuthorshipNotesDatabase(BaseDatabase):
    """Authorship Notes 数据库操作类"""

    def __init__(self):
        super().__init__()
        config_data = loader.load_config()
        database_config = config_data.get("database", {})
        db_url = database_config.get("url")
        self._engine = create_engine(db_url, echo=self.echo) if db_url else None

    @property
    def engine(self) -> Engine:
        """获取引擎实例"""
        if self._engine is not None:
            return self._engine
        return super().engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            return
        super().close()

    def _next_change_seq(self, session) -> int:
        seq = AuthorshipNotesSeq()
        session.add(seq)
        session.flush()
        return seq.id

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
        repo_url = normalize_repo_url(repo_url)
        content_hash = compute_note_content_hash(content)

        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha == commit_sha,
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                if result.content_hash != content_hash:
                    result.branch = branch
                    setattr(result, "note_blob_oid", note_blob_oid)
                    result.note_content = content
                    result.content_hash = content_hash
                    result.change_seq = self._next_change_seq(session)
                    result.author_name = author_name
                    result.author_email = author_email
            else:
                note = AuthorshipNotes(
                    id=gen_xid(),
                    repo_url=repo_url,
                    branch=branch,
                    commit_sha=commit_sha,
                    note_blob_oid=note_blob_oid,
                    note_content=content,
                    content_hash=content_hash,
                    change_seq=self._next_change_seq(session),
                    author_name=author_name,
                    author_email=author_email,
                )
                session.add(note)

            session.flush()
            return session.execute(stmt).scalar_one()

    def get_note(
        self, repo_url: str, commit_sha: str, include_superseded: bool = False
    ) -> Optional[AuthorshipNotes]:
        """获取单个 note

        Args:
            repo_url: 仓库远程 URL
            commit_sha: 提交 SHA

        Returns:
            AuthorshipNotes 或 None
        """
        repo_url = normalize_repo_url(repo_url)
        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha == commit_sha,
            )
            stmt = apply_active_filter(stmt, include_superseded)
            return session.execute(stmt).scalar_one_or_none()

    def batch_get_notes(
        self,
        repo_url: str,
        commit_shas: List[str],
        include_superseded: bool = False,
    ) -> Dict[str, List]:
        """批量获取 notes

        Args:
            repo_url: 仓库远程 URL
            commit_shas: 提交 SHA 列表

        Returns:
            dict: {"notes": [dict], "missing": [str]}
        """
        if not commit_shas:
            return {"notes": [], "missing": []}

        repo_url = normalize_repo_url(repo_url)
        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha.in_(commit_shas),
            )
            stmt = apply_active_filter(stmt, include_superseded)
            results = session.execute(stmt).scalars().all()

            found_shas = set(note.commit_sha for note in results)
            notes = [
                {
                    "commit_sha": note.commit_sha,
                    "content": note.note_content,
                    "content_hash": note.content_hash,
                    "change_seq": note.change_seq,
                    "status": note.status,
                    "superseded_by": note.superseded_by,
                    "superseded_at": note.superseded_at,
                    "superseded_rewrite_id": note.superseded_rewrite_id,
                }
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
            dict: {"created": int, "updated": int, "unchanged": int}
        """
        created = 0
        updated = 0
        unchanged = 0
        repo_url = normalize_repo_url(repo_url)

        with session_scope(self.engine) as session:
            for note_data in notes_data:
                commit_sha = note_data["commit_sha"]
                content = note_data["content"]
                content_hash = compute_note_content_hash(content)

                stmt = select(AuthorshipNotes).where(
                    AuthorshipNotes.repo_url == repo_url,
                    AuthorshipNotes.commit_sha == commit_sha,
                )
                note = session.execute(stmt).scalar_one_or_none()

                if note is None:
                    note = AuthorshipNotes(
                        id=gen_xid(),
                        repo_url=repo_url,
                        branch=note_data["branch"],
                        commit_sha=commit_sha,
                        note_blob_oid=note_data.get(
                            "original_commit_sha", note_data.get("note_blob_oid")
                        ),
                        note_content=content,
                        content_hash=content_hash,
                        change_seq=self._next_change_seq(session),
                        author_name=note_data["author_name"],
                        author_email=note_data["author_email"],
                        commit_time=note_data.get("commit_time"),
                    )
                    session.add(note)
                    created += 1
                    continue

                if note.content_hash == content_hash:
                    unchanged += 1
                    continue

                note.branch = note_data["branch"]
                setattr(
                    note,
                    "note_blob_oid",
                    note_data.get("original_commit_sha", note_data.get("note_blob_oid")),
                )
                note.note_content = content
                note.content_hash = content_hash
                note.change_seq = self._next_change_seq(session)
                note.author_name = note_data["author_name"]
                note.author_email = note_data["author_email"]
                note.commit_time = note_data.get("commit_time", 0)
                updated += 1

        return {"created": created, "updated": updated, "unchanged": unchanged}

    def list_notes(
        self,
        repo_url: str,
        since_commit_time: int | None = None,
        since_change_seq: int | None = None,
        limit: int | None = None,
        include_superseded: bool = False,
    ) -> Dict[str, Any]:
        page_limit = normalize_list_limit(limit)
        repo_url = normalize_repo_url(repo_url)

        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(AuthorshipNotes.repo_url == repo_url)
            stmt = apply_active_filter(stmt, include_superseded)

            if since_change_seq is not None:
                stmt = stmt.where(AuthorshipNotes.change_seq > since_change_seq)
                stmt = stmt.order_by(AuthorshipNotes.change_seq)
            else:
                if since_commit_time is not None:
                    stmt = stmt.where(AuthorshipNotes.commit_time >= since_commit_time)
                stmt = stmt.order_by(AuthorshipNotes.commit_sha)

            rows = list(session.execute(stmt.limit(page_limit + 1)).scalars().all())

        has_more = len(rows) > page_limit
        page_rows = rows[:page_limit]
        items = [
            {
                "commit_sha": note.commit_sha,
                "content_hash": note.content_hash,
                "change_seq": note.change_seq,
                "updated_at": note.updated_at,
                "status": note.status,
                "superseded_by": note.superseded_by,
                "superseded_at": note.superseded_at,
                "superseded_rewrite_id": note.superseded_rewrite_id,
            }
            for note in page_rows
        ]
        next_change_seq = items[-1]["change_seq"] if items else since_change_seq or 0

        return {
            "commit_shas": [note.commit_sha for note in page_rows],
            "items": items,
            "next_change_seq": next_change_seq,
            "has_more": has_more,
        }

    def search_notes(
        self, repo_url: str, pattern: str, include_superseded: bool = False
    ) -> List[str]:
        """在注释内容中搜索

        Args:
            repo_url: 仓库远程 URL
            pattern: 搜索模式

        Returns:
            list: 匹配的提交 SHA 列表
        """
        repo_url = normalize_repo_url(repo_url)
        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes.commit_sha).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.note_content.like(f"%{pattern}%"),
            )
            stmt = apply_active_filter(stmt, include_superseded)
            return list(session.execute(stmt).scalars().all())
