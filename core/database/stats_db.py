import json
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, or_

from .base import BaseDatabase, now_ts, session_scope
from core.utils.repo_url import normalize_repo_url, UNKNOWN_REPO
from .models import (
    AuthorshipNotes,
    MetricsEventsCheckpoint,
    MetricsEventsCommitted,
    StatsContributor,
    StatsDailyStat,
    StatsRepositoryBranch,
    StatsRepoContributor,
    StatsRepository,
)


class StatsDatabase(BaseDatabase):
    
    @staticmethod
    def _parse_json_field(value: object) -> object:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    @staticmethod
    def _first_metric_value(value: object) -> int:
        value = StatsDatabase._parse_json_field(value)
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, list):
            if not value:
                return 0
            return StatsDatabase._first_metric_value(value[0])
        if isinstance(value, dict):
            if not value:
                return 0
            return StatsDatabase._first_metric_value(next(iter(value.values())))
        if isinstance(value, str):
            return int(value) if value.isdigit() else 0
        return 0

    @staticmethod
    def _format_tool_model_pairs(value: object) -> str:
        value = StatsDatabase._parse_json_field(value)
        if not isinstance(value, list) or len(value) <= 1:
            return "-"

        def stringify(item: object) -> str:
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                for key in ("tool", "name"):
                    current = item.get(key)
                    if isinstance(current, str) and current.strip():
                        return current.strip()
                return json.dumps(item, ensure_ascii=False)
            return str(item)

        display_items = [stringify(item).strip() for item in value[1:]]
        display_items = [item for item in display_items if item]
        return ", ".join(display_items) if display_items else "-"


    @staticmethod
    def _metric_total(value: object) -> int:
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception:
                return int(value) if value.isdigit() else 0
            return StatsDatabase._metric_total(parsed)
        if isinstance(value, list):
            if not value:
                return 0
            first = value[0]
            return int(first) if isinstance(first, (int, float)) else 0
        if isinstance(value, dict):
            if not value:
                return 0
            first = next(iter(value.values()))
            return int(first) if isinstance(first, (int, float)) else 0
        return 0

    def get_latest_stat_date(self) -> Optional[int]:
        with session_scope(self.engine) as session:
            return session.query(func.max(StatsDailyStat.stat_date)).scalar()

    def consolidate_unknown_repositories(self) -> Optional[str]:
        with session_scope(self.engine) as session:
            unknown_path = UNKNOWN_REPO
            bad_rows = (
                session.query(StatsRepository)
                .filter(
                    or_(
                        func.trim(func.coalesce(StatsRepository.repo_path, "")) == "",
                        func.trim(func.coalesce(StatsRepository.repo_name, "")) == "",
                    )
                )
                .all()
            )

            unknown = (
                session.query(StatsRepository)
                .filter(StatsRepository.repo_path == unknown_path)
                .first()
            )

            if unknown is None and not bad_rows:
                return None

            if unknown is None:
                unknown = StatsRepository(
                    repo_path=unknown_path, repo_name=unknown_path
                )
                session.add(unknown)
                session.flush()
            elif (unknown.repo_name or "").strip() != unknown_path:
                unknown.repo_name = unknown_path
                unknown.updated_at = now_ts()
                session.flush()

            for row in bad_rows:
                if row.id == unknown.id:
                    continue

                daily_rows = (
                    session.query(StatsDailyStat)
                    .filter(StatsDailyStat.repo_id == row.id)
                    .all()
                )
                for daily in daily_rows:
                    target = (
                        session.query(StatsDailyStat)
                        .filter(StatsDailyStat.repo_id == unknown.id)
                        .filter(StatsDailyStat.contributor_name == daily.contributor_name)
                        .filter(StatsDailyStat.contributor_email == daily.contributor_email)
                        .filter(StatsDailyStat.stat_date == daily.stat_date)
                        .first()
                    )
                    if target is None:
                        daily.repo_id = unknown.id
                        daily.updated_at = now_ts()
                        continue

                    target.ai_lines += int(daily.ai_lines or 0)
                    target.ai_total_lines += int(daily.ai_total_lines or 0)
                    target.ai_accepted_lines += int(daily.ai_accepted_lines or 0)
                    target.human_lines += int(daily.human_lines or 0)
                    target.total_lines += int(daily.total_lines or 0)
                    target.updated_at = now_ts()
                    session.delete(daily)

                links = (
                    session.query(StatsRepoContributor)
                    .filter(StatsRepoContributor.repo_id == row.id)
                    .all()
                )
                for link in links:
                    dup = (
                        session.query(StatsRepoContributor)
                        .filter(StatsRepoContributor.repo_id == unknown.id)
                        .filter(
                            StatsRepoContributor.contributor_id == link.contributor_id
                        )
                        .first()
                    )
                    if dup is None:
                        link.repo_id = unknown.id
                        link.updated_at = now_ts()
                    else:
                        session.delete(link)

                session.delete(row)

            session.flush()
            return unknown.id

    def get_repository_consolidation_report(self) -> Dict:
        with session_scope(self.engine) as session:
            unknown = (
                session.query(StatsRepository)
                .filter(StatsRepository.repo_path == UNKNOWN_REPO)
                .first()
            )

            bad_rows = (
                session.query(StatsRepository)
                .filter(
                    or_(
                        func.trim(func.coalesce(StatsRepository.repo_path, "")) == "",
                        func.trim(func.coalesce(StatsRepository.repo_name, "")) == "",
                    )
                )
                .order_by(StatsRepository.created_at.desc())
                .all()
            )

            items: List[Dict] = []
            for row in bad_rows:
                daily_count = (
                    session.query(func.count(StatsDailyStat.id))
                    .filter(StatsDailyStat.repo_id == row.id)
                    .scalar()
                    or 0
                )
                link_count = (
                    session.query(func.count(StatsRepoContributor.id))
                    .filter(StatsRepoContributor.repo_id == row.id)
                    .scalar()
                    or 0
                )
                items.append(
                    {
                        "id": row.id,
                        "repo_path": row.repo_path,
                        "repo_name": row.repo_name,
                        "daily_stats_refs": int(daily_count),
                        "repo_contributor_refs": int(link_count),
                    }
                )

            unknown_refs = {"daily_stats": 0, "repo_contributors": 0}
            if unknown is not None:
                unknown_refs["daily_stats"] = int(
                    session.query(func.count(StatsDailyStat.id))
                    .filter(StatsDailyStat.repo_id == unknown.id)
                    .scalar()
                    or 0
                )
                unknown_refs["repo_contributors"] = int(
                    session.query(func.count(StatsRepoContributor.id))
                    .filter(StatsRepoContributor.repo_id == unknown.id)
                    .scalar()
                    or 0
                )

            return {
                "unknown_repository": unknown.to_dict() if unknown else None,
                "unknown_repository_refs": unknown_refs,
                "invalid_repositories_count": len(items),
                "invalid_repositories": items,
            }

    @staticmethod
    def _extract_repo_name(repo_path: str) -> str:
        raw = (repo_path or "").strip()
        if not raw:
            return UNKNOWN_REPO
        if raw == UNKNOWN_REPO:
            return raw

        value = raw
        if value.endswith(".git"):
            value = value[:-4]

        if value.startswith("git@"):
            parts = value.split(":", 1)
            if len(parts) == 2:
                value = parts[1]
        elif "://" in value:
            value = value.split("://", 1)[1]
            if "/" in value:
                value = value.split("/", 1)[1]

        value = value.strip("/")

        # Drop leading host segment (e.g. "github.com/org/repo" -> "org/repo").
        # A segment is considered a host if it contains '.' or ':'.
        if "/" in value:
            first, rest = value.split("/", 1)
            if ("." in first or ":" in first) and rest.strip("/"):
                value = rest.strip("/")

        return value or UNKNOWN_REPO

    @staticmethod
    def _extract_repo_name_parts(repo_path: str) -> Dict[str, Optional[str]]:
        repo_name = StatsDatabase._extract_repo_name(repo_path)
        result = {
            "name_level1": None,
            "name_level2": None,
            "name_level3": None,
            "name_level4": None,
            "name_level5": None,
            "repo_short_name": None,
        }
        if not repo_name or repo_name == UNKNOWN_REPO:
            result["repo_short_name"] = repo_name
            return result

        parts = [part for part in repo_name.split("/") if part]
        if not parts:
            result["repo_short_name"] = UNKNOWN_REPO
            return result

        if len(parts) >= 5:
            level_parts = parts[:5]
            result["name_level1"] = level_parts[-1].upper()
            result["name_level2"] = level_parts[-2].upper()
            result["name_level3"] = level_parts[-3].upper()
            result["name_level4"] = level_parts[-4].upper()
            result["name_level5"] = level_parts[-5].upper()
            result["repo_short_name"] = "/".join(parts[5:]) or None
            return result

        for index, part in enumerate(parts[:-1], start=1):
            result[f"name_level{index}"] = part.upper()
        result["repo_short_name"] = parts[-1]
        return result

    @staticmethod
    def _apply_repo_name_parts(row: StatsRepository, parts: Dict[str, Optional[str]]) -> None:
        for field, value in parts.items():
            setattr(row, field, value)

    @staticmethod
    def _parse_author(author: Optional[str]) -> Tuple[str, Optional[str]]:
        raw = (author or "").strip()
        if not raw:
            return "unknown", None

        match = re.match(r"^\s*([^<]+?)\s*<([^>]+)>\s*$", raw)
        if match:
            name = match.group(1).strip() or "unknown"
            email = match.group(2).strip() or None
            return name, email

        return raw, None

    def query_committed_events(
        self,
        start_ts: int,
        end_ts: int,
        repo_url: Optional[str] = None,
        author: Optional[str] = None,
        require_authorship_notes: bool = False,
    ) -> List[Dict]:
        with session_scope(self.engine) as session:
            normalized_repo_url = normalize_repo_url(repo_url) if repo_url else None
            query = (
                session.query(MetricsEventsCommitted)
                .filter(MetricsEventsCommitted.timestamp >= start_ts)
                .filter(MetricsEventsCommitted.timestamp <= end_ts)
            )
            if normalized_repo_url:
                query = query.filter(MetricsEventsCommitted.repo_url == normalized_repo_url)
            if author:
                author_key = author.strip()
                query = query.filter(
                    or_(
                        MetricsEventsCommitted.author == author_key,
                        MetricsEventsCommitted.author.like(f"{author_key} <%"),
                    )
                )
            if require_authorship_notes:
                query = query.filter(MetricsEventsCommitted.commit_sha.isnot(None))
                query = query.filter(func.trim(MetricsEventsCommitted.commit_sha) != "")
            rows = query.all()

            if require_authorship_notes:
                note_keys = {
                    (normalize_repo_url(row.repo_url), (row.commit_sha or "").strip())
                    for row in rows
                    if (row.commit_sha or "").strip()
                }
                if not note_keys:
                    rows = []
                else:
                    note_repo_urls = {repo_url for repo_url, _commit_sha in note_keys}
                    note_commit_shas = {commit_sha for _repo_url, commit_sha in note_keys}
                    matching_notes = (
                        session.query(AuthorshipNotes.repo_url, AuthorshipNotes.commit_sha)
                        .filter(AuthorshipNotes.repo_url.in_(note_repo_urls))
                        .filter(AuthorshipNotes.commit_sha.in_(note_commit_shas))
                        .all()
                    )
                    matching_note_keys = {
                        (normalize_repo_url(repo_url), (commit_sha or "").strip())
                        for repo_url, commit_sha in matching_notes
                    }
                    rows = [
                        row
                        for row in rows
                        if (
                            normalize_repo_url(row.repo_url),
                            (row.commit_sha or "").strip(),
                        )
                        in matching_note_keys
                    ]

            items: List[Dict] = []
            for row in rows:
                author_name, author_email = self._parse_author(row.author)
                items.append(
                    {
                        "repo_url": normalize_repo_url(row.repo_url),
                        "commit_sha": (row.commit_sha or "").strip(),
                        "timestamp": int(row.timestamp or 0),
                        "author": author_name,
                        "author_uid": (row.author or "").strip() or author_name,
                        "author_email": author_email,
                        "tool_model_pairs_total": self._metric_total(row.tool_model_pairs),
                        "mixed_additions_total": self._metric_total(row.mixed_additions),
                        "human_additions": int(row.human_additions or 0),
                        "git_diff_added_lines": int(row.git_diff_added_lines or 0),
                        "ai_additions": self._metric_total(row.ai_additions),
                        "ai_accepted_lines": self._metric_total(row.ai_accepted),
                        "total_ai_additions_total": self._metric_total(row.total_ai_additions),
                        "total_ai_deletions_total": self._metric_total(row.total_ai_deletions),
                        "git_ai_version": row.git_ai_version,
                    }
                )
            return items


    def get_committed_events_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        repo_url: Optional[str] = None,
        author: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Dict:
        with session_scope(self.engine) as session:
            query = session.query(MetricsEventsCommitted)

            if start_ts is not None:
                query = query.filter(MetricsEventsCommitted.timestamp >= start_ts)
            if end_ts is not None:
                query = query.filter(MetricsEventsCommitted.timestamp <= end_ts)
            if repo_url:
                normalized_repo_url = normalize_repo_url(repo_url)
                query = query.filter(
                    MetricsEventsCommitted.repo_url.contains(normalized_repo_url)
                )
            if author:
                author_key = author.strip()
                query = query.filter(
                    or_(
                        MetricsEventsCommitted.author.contains(author_key),
                        MetricsEventsCommitted.author == author_key,
                        MetricsEventsCommitted.author.like(f"{author_key} <%"),
                    )
                )
            if branch:
                query = query.filter(
                    MetricsEventsCommitted.branch.contains(branch.strip())
                )

            total = query.count()
            rows = (
                query.order_by(MetricsEventsCommitted.timestamp.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )

            items: List[Dict] = []
            for row in rows:
                author_name, _author_email = self._parse_author(row.author)
                items.append(
                    {
                        "id": row.id,
                        "repo_url": row.repo_url or "",
                        "author": author_name,
                        "branch": row.branch or "",
                        "timestamp": row.timestamp,
                        "human_additions": int(row.human_additions or 0),
                        "git_diff_deleted_lines": int(row.git_diff_deleted_lines or 0),
                        "git_diff_added_lines": int(row.git_diff_added_lines or 0),
                        "first_checkpoint_ts": row.first_checkpoint_ts,
                        "commit_subject": row.commit_subject or "",
                        "commit_body": row.commit_body or "",
                        "tool_model_pairs": self._format_tool_model_pairs(
                            row.tool_model_pairs
                        ),
                        "mixed_additions": self._first_metric_value(
                            row.mixed_additions
                        ),
                        "ai_additions": self._first_metric_value(row.ai_additions),
                        "ai_accepted": self._first_metric_value(row.ai_accepted),
                        "total_ai_additions": self._first_metric_value(
                            row.total_ai_additions
                        ),
                        "total_ai_deletions": self._first_metric_value(
                            row.total_ai_deletions
                        ),
                        "base_commit_sha": row.base_commit_sha or "",
                        "git_ai_version": row.git_ai_version or "",
                    }
                )

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items,
            }

    def query_checkpoint_events(
        self,
        start_ts: int,
        end_ts: int,
        repo_url: Optional[str] = None,
        author: Optional[str] = None,
    ) -> List[Dict]:
        with session_scope(self.engine) as session:
            query = (
                session.query(MetricsEventsCheckpoint)
                .filter(MetricsEventsCheckpoint.timestamp >= start_ts)
                .filter(MetricsEventsCheckpoint.timestamp <= end_ts)
                .filter(MetricsEventsCheckpoint.kind == "ai_agent")
            )
            if repo_url:
                query = query.filter(
                    MetricsEventsCheckpoint.repo_url == normalize_repo_url(repo_url)
                )
            if author:
                author_key = author.strip()
                query = query.filter(
                    or_(
                        MetricsEventsCheckpoint.author == author_key,
                        MetricsEventsCheckpoint.author.like(f"{author_key} <%"),
                    )
                )
            rows = query.all()
            items = []
            for row in rows:
                author_name, _ = self._parse_author(row.author)
                items.append(
                    {
                        "repo_url": row.repo_url or "",
                        "author": author_name,
                        "author_uid": (row.author or "").strip() or author_name,
                        "lines_added": int(row.lines_added or 0),
                        "lines_added_sloc": int(
                            row.lines_added_sloc
                            if row.lines_added_sloc is not None
                            else row.lines_added or 0
                        ),
                        "git_ai_version": row.git_ai_version,
                    }
                )
            return items

    def get_or_create_repository(self, repo_path: str) -> str:
        self.consolidate_unknown_repositories()
        normalized_path = normalize_repo_url(repo_path)
        extracted_name = self._extract_repo_name(normalized_path)
        name_parts = self._extract_repo_name_parts(normalized_path)

        with session_scope(self.engine) as session:
            row = (
                session.query(StatsRepository)
                .filter(func.lower(StatsRepository.repo_path) == normalized_path)
                .first()
            )
            if row:
                if row.repo_path != normalized_path:
                    row.repo_path = normalized_path
                current_name = (row.repo_name or "").strip()
                if not current_name or current_name == row.repo_path:
                    row.repo_name = extracted_name
                self._apply_repo_name_parts(row, name_parts)
                row.updated_at = now_ts()
                session.flush()
                return row.id

            record = StatsRepository(
                repo_path=normalized_path, repo_name=extracted_name, **name_parts
            )
            session.add(record)
            session.flush()
            return record.id

    def update_repository_last_daily_aggregation_commit_sha(
        self, repo_id: str, commit_sha: str
    ) -> bool:
        normalized_sha = (commit_sha or "").strip()
        if not normalized_sha:
            return False

        with session_scope(self.engine) as session:
            row = (
                session.query(StatsRepository)
                .filter(StatsRepository.id == repo_id)
                .first()
            )
            if row is None:
                return False

            row.last_daily_aggregation_commit_sha = normalized_sha
            row.updated_at = now_ts()
            session.flush()
            return True

    def get_or_create_contributor(
        self, name: str, email: Optional[str]
    ) -> str:
        normalized_name = (name or "unknown").strip() or "unknown"
        normalized_email = (email or "").strip() or None

        with session_scope(self.engine) as session:
            row = (
                session.query(StatsContributor)
                .filter(StatsContributor.name == name)
                .first()
            )
            if row:
                current_name = (row.name or "").strip()
                if not current_name and normalized_name:
                    row.name = normalized_name
                if not (row.email or "").strip() and normalized_email:
                    row.email = normalized_email
                row.updated_at = now_ts()
                session.flush()
                return row.id

            record = StatsContributor(
                name=normalized_name,
                email=normalized_email,
            )
            session.add(record)
            session.flush()
            return record.id

    def ensure_repo_contributor_link(self, repo_id: str, contributor_id: str) -> str:
        with session_scope(self.engine) as session:
            row = (
                session.query(StatsRepoContributor)
                .filter(StatsRepoContributor.repo_id == repo_id)
                .filter(StatsRepoContributor.contributor_id == contributor_id)
                .first()
            )
            if row:
                return row.id

            record = StatsRepoContributor(
                repo_id=repo_id, contributor_id=contributor_id
            )
            session.add(record)
            session.flush()
            return record.id

    def ensure_repository_branch(self, repo_id: str, branch_name: str) -> str:
        normalized_branch = (branch_name or "").strip()
        if not normalized_branch:
            raise ValueError("branch_name 不能为空")

        with session_scope(self.engine) as session:
            row = (
                session.query(StatsRepositoryBranch)
                .filter(StatsRepositoryBranch.repo_id == repo_id)
                .filter(StatsRepositoryBranch.branch_name == normalized_branch)
                .first()
            )
            if row:
                row.is_deleted = 0
                row.deleted_at = None
                row.updated_at = now_ts()
                session.flush()
                return row.id

            record = StatsRepositoryBranch(
                repo_id=repo_id,
                branch_name=normalized_branch,
                is_deleted=0,
                deleted_at=None,
            )
            session.add(record)
            session.flush()
            return record.id

    def upsert_daily_stat(
        self,
        stat_date: int,
        repo_id: str,
        contributor_name: str,
        contributor_email: Optional[str],
        stats: Dict,
    ) -> str:
        with session_scope(self.engine) as session:
            row = (
                session.query(StatsDailyStat)
                .filter(StatsDailyStat.stat_date == stat_date)
                .filter(StatsDailyStat.repo_id == repo_id)
                .filter(StatsDailyStat.contributor_name == contributor_name)
                .filter(StatsDailyStat.contributor_email == contributor_email)
                .first()
            )

            if row is None:
                row = StatsDailyStat(
                    stat_date=stat_date,
                    repo_id=repo_id,
                    contributor_name=contributor_name,
                    contributor_email=contributor_email,
                )
                session.add(row)

            row.repo_name = stats.get("repo_name", "")
            row.contributor_name = stats.get("contributor_name", contributor_name)
            row.contributor_email = stats.get("contributor_email", contributor_email)
            row.ai_lines = int(stats.get("ai_lines", 0))
            row.ai_total_lines = int(stats.get("ai_total_lines", row.ai_lines))
            row.ai_accepted_lines = int(stats.get("ai_accepted_lines", 0))
            row.human_lines = int(stats.get("human_lines", 0))
            row.total_lines = int(stats.get("total_lines", 0))
            row.updated_at = now_ts()

            session.flush()
            return row.id

    def list_repositories(self, limit: int, offset: int) -> Tuple[List[Dict], int]:
        self.consolidate_unknown_repositories()
        with session_scope(self.engine) as session:
            total = session.query(StatsRepository).count()
            rows = (
                session.query(StatsRepository)
                .order_by(StatsRepository.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [r.to_dict() for r in rows], total

    def get_repositories(
        self, page: int = 1, page_size: int = 20, keyword: Optional[str] = None
    ) -> Dict:
        self.consolidate_unknown_repositories()
        with session_scope(self.engine) as session:
            query = session.query(StatsRepository)
            if keyword:
                like = f"%{keyword}%"
                query = query.filter(StatsRepository.repo_name.like(like))\
                .filter(StatsRepository.repo_path.like(like))
                
            query = query.filter(StatsRepository.repo_name != UNKNOWN_REPO).order_by(StatsRepository.created_at.desc())
            total = query.count()
            rows = query.offset((page - 1) * page_size).limit(page_size).all()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [r.to_dict() for r in rows],
            }

    def get_repository_by_id(self, repo_id: str) -> Optional[Dict]:
        self.consolidate_unknown_repositories()
        with session_scope(self.engine) as session:
            row = (
                session.query(StatsRepository)
                .filter(StatsRepository.id == repo_id)
                .first()
            )
            return row.to_dict() if row else None

    def list_contributors(self, limit: int, offset: int) -> Tuple[List[Dict], int]:
        with session_scope(self.engine) as session:
            total = session.query(StatsContributor).count()
            rows = (
                session.query(StatsContributor)
                .order_by(StatsContributor.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [r.to_dict() for r in rows], total

    def get_contributors(
        self, page: int = 1, page_size: int = 20, keyword: Optional[str] = None
    ) -> Dict:
        with session_scope(self.engine) as session:
            query = session.query(StatsContributor)
            if keyword:
                like = f"%{keyword}%"
                query = query.filter(
                    or_(
                        StatsContributor.name.like(like),
                        StatsContributor.email.like(like)
                    )
                )
            query = query.order_by(StatsContributor.created_at.desc())
            total = query.count()
            rows = query.offset((page - 1) * page_size).limit(page_size).all()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [r.to_dict() for r in rows],
            }

    def get_contributor_by_id(self, contributor_id: str) -> Optional[Dict]:
        with session_scope(self.engine) as session:
            row = (
                session.query(StatsContributor)
                .filter(StatsContributor.id == contributor_id)
                .first()
            )
            return row.to_dict() if row else None

    def query_daily_stats(
        self,
        start_date: int,
        end_date: int,
        repo_id: Optional[str],
        contributor_email: Optional[str],
        limit: int,
        offset: int,
    ) -> List[Dict]:
        self.consolidate_unknown_repositories()
        with session_scope(self.engine) as session:
            query = (
                session.query(StatsDailyStat)
                .filter(StatsDailyStat.stat_date >= start_date)
                .filter(StatsDailyStat.stat_date <= end_date)
            )
            if repo_id:
                query = query.filter(StatsDailyStat.repo_id == repo_id)
            if contributor_email:
                query = query.filter(StatsDailyStat.contributor_email == contributor_email)

            rows = (
                query.join(
                    StatsRepository, StatsRepository.id == StatsDailyStat.repo_id
                )
                .with_entities(
                    StatsDailyStat,
                    StatsRepository.repo_name,
                )
                .order_by(StatsDailyStat.stat_date.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            items: List[Dict] = []
            for stat, repo_name in rows:
                item = stat.to_dict()
                item["repo_name"] = repo_name or UNKNOWN_REPO
                item["contributor_name"] = item.get("contributor_name") or "unknown"
                items.append(item)
            return items

    def get_daily_stats_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[int] = None,
        end_date: Optional[int] = None,
        repo_id: Optional[str] = None,
        contributor_email: Optional[str] = None,
    ) -> Dict:
        self.consolidate_unknown_repositories()
        with session_scope(self.engine) as session:
            query = session.query(StatsDailyStat)
            if start_date is not None:
                query = query.filter(StatsDailyStat.stat_date >= start_date)
            if end_date is not None:
                query = query.filter(StatsDailyStat.stat_date <= end_date)
            if repo_id:
                query = query.filter(StatsDailyStat.repo_id == repo_id)
            if contributor_email:
                query = query.filter(StatsDailyStat.contributor_email == contributor_email)

            total = query.count()
            rows = (
                query.join(
                    StatsRepository, StatsRepository.id == StatsDailyStat.repo_id
                )
                .with_entities(
                    StatsDailyStat,
                    StatsRepository.repo_name,
                )
                .order_by(StatsDailyStat.stat_date.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )

            items: List[Dict] = []
            for stat, repo_name in rows:
                item = stat.to_dict()
                item["repo_name"] = repo_name or UNKNOWN_REPO
                item["contributor_name"] = item.get("contributor_name") or "unknown"
                items.append(item)

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items,
            }

    def get_aggregated_stats(
        self,
        start_date: int,
        end_date: int,
        repo_id: Optional[str] = None,
        contributor_email: Optional[str] = None,
        granularity: str = "daily",
    ) -> List[Dict]:
        self.consolidate_unknown_repositories()
        with session_scope(self.engine) as session:
            query = (
                session.query(
                    StatsDailyStat.stat_date,
                    func.sum(StatsDailyStat.ai_lines).label("ai_lines"),
                    func.sum(StatsDailyStat.ai_accepted_lines).label(
                        "ai_accepted_lines"
                    ),
                    func.sum(StatsDailyStat.human_lines).label("human_lines"),
                    func.sum(StatsDailyStat.total_lines).label("total_lines"),
                )
                .filter(StatsDailyStat.stat_date >= start_date)
                .filter(StatsDailyStat.stat_date <= end_date)
            )

            if repo_id:
                query = query.filter(StatsDailyStat.repo_id == repo_id)
            if contributor_email:
                query = query.filter(StatsDailyStat.contributor_email == contributor_email)

            rows = (
                query.group_by(StatsDailyStat.stat_date)
                .order_by(StatsDailyStat.stat_date)
                .all()
            )

        items: List[Dict] = []
        for row in rows:
            accepted = int(row.ai_accepted_lines or 0)
            human = int(row.human_lines or 0)
            items.append(
                {
                    "stat_date": int(row.stat_date),
                    "ai_lines": int(row.ai_lines or 0),
                    "ai_accepted_lines": accepted,
                    "human_lines": human,
                    "total_lines": int(row.total_lines or 0),
                }
            )

        if granularity in ("weekly", "monthly"):
            return self._group_by_granularity(items, granularity)
        return items

    def _group_by_granularity(self, items: List[Dict], granularity: str) -> List[Dict]:
        grouped: Dict[str, Dict] = {}
        for item in items:
            dt = datetime.fromtimestamp(item["stat_date"] / 1000)
            if granularity == "weekly":
                year, week, _ = dt.isocalendar()
                key = f"{year}-W{week:02d}"
                monday = dt - timedelta(days=dt.weekday())
                period_ts = int(
                    monday.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ).timestamp()
                    * 1000
                )
            else:
                key = f"{dt.year}-{dt.month:02d}"
                period_ts = int(
                    dt.replace(
                        day=1, hour=0, minute=0, second=0, microsecond=0
                    ).timestamp()
                    * 1000
                )

            if key not in grouped:
                grouped[key] = {
                    "period": key,
                    "stat_date": period_ts,
                    "ai_lines": 0,
                    "ai_accepted_lines": 0,
                    "human_lines": 0,
                    "total_lines": 0,
                }
            grouped[key]["ai_lines"] += item["ai_lines"]
            grouped[key]["ai_accepted_lines"] += item["ai_accepted_lines"]
            grouped[key]["human_lines"] += item["human_lines"]
            grouped[key]["total_lines"] += item["total_lines"]

        result = []
        for value in grouped.values():
            result.append(value)
        return sorted(result, key=lambda x: x["stat_date"])
