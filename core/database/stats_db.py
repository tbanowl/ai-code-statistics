import json
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, or_, text

from .base import BaseDatabase, now_ts, session_scope
from .models import (
    MetricsEventsCheckpoint,
    MetricsEventsCommitted,
    StatsContributor,
    StatsDailyStat,
    StatsRepoContributor,
    StatsRepository,
)


class StatsDatabase(BaseDatabase):
    def __init__(self):
        super().__init__()
        self._ensure_stats_schema_compatibility()

    def _ensure_stats_schema_compatibility(self) -> None:
        if self.engine.dialect.name != "sqlite":
            return

        with self.engine.begin() as conn:
            exists = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='stats_daily_stats'"
                )
            ).fetchone()
            if not exists:
                return

            cols = {
                row[1]
                for row in conn.execute(
                    text("PRAGMA table_info(stats_daily_stats)")
                ).fetchall()
            }
            patch_columns = {
                "repo_name": "ALTER TABLE stats_daily_stats ADD COLUMN repo_name VARCHAR",
                "contributor_name": "ALTER TABLE stats_daily_stats ADD COLUMN contributor_name VARCHAR",
                "ai_generated_lines": "ALTER TABLE stats_daily_stats ADD COLUMN ai_generated_lines INTEGER DEFAULT 0",
                "ai_generated_lines_total": "ALTER TABLE stats_daily_stats ADD COLUMN ai_generated_lines_total INTEGER DEFAULT 0",
                "ai_accepted_lines": "ALTER TABLE stats_daily_stats ADD COLUMN ai_accepted_lines INTEGER DEFAULT 0",
                "human_lines": "ALTER TABLE stats_daily_stats ADD COLUMN human_lines INTEGER DEFAULT 0",
                "ai_percentage": "ALTER TABLE stats_daily_stats ADD COLUMN ai_percentage NUMERIC DEFAULT 0.0",
                "git_ai_version": "ALTER TABLE stats_daily_stats ADD COLUMN git_ai_version VARCHAR(50)",
            }
            for column, ddl in patch_columns.items():
                if column not in cols:
                    conn.execute(text(ddl))

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
            unknown_path = "未知仓库"
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
                        .filter(StatsDailyStat.contributor_id == daily.contributor_id)
                        .filter(StatsDailyStat.stat_date == daily.stat_date)
                        .first()
                    )
                    if target is None:
                        daily.repo_id = unknown.id
                        daily.updated_at = now_ts()
                        continue

                    target.ai_generated_lines += int(daily.ai_generated_lines or 0)
                    target.ai_generated_lines_total += int(
                        daily.ai_generated_lines_total or 0
                    )
                    target.ai_accepted_lines += int(daily.ai_accepted_lines or 0)
                    target.human_lines += int(daily.human_lines or 0)
                    total = int(target.ai_accepted_lines or 0) + int(
                        target.human_lines or 0
                    )
                    target.ai_percentage = (
                        round((int(target.ai_accepted_lines or 0) / total) * 100, 2)
                        if total > 0
                        else 0
                    )
                    if not (target.git_ai_version or "") and (
                        daily.git_ai_version or ""
                    ):
                        target.git_ai_version = daily.git_ai_version
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
                .filter(StatsRepository.repo_path == "未知仓库")
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
    def _normalize_repo_path(repo_path: Optional[str]) -> str:
        value = (repo_path or "").strip()
        return value or "未知仓库"

    @staticmethod
    def _extract_repo_name(repo_path: str) -> str:
        raw = (repo_path or "").strip()
        if not raw:
            return "未知仓库"
        if raw == "未知仓库":
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
        return value or "未知仓库"

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
    ) -> List[Dict]:
        with session_scope(self.engine) as session:
            query = (
                session.query(MetricsEventsCommitted)
                .filter(MetricsEventsCommitted.timestamp >= start_ts)
                .filter(MetricsEventsCommitted.timestamp <= end_ts)
            )
            if repo_url:
                query = query.filter(MetricsEventsCommitted.repo_url == repo_url)
            if author:
                author_key = author.strip()
                query = query.filter(
                    or_(
                        MetricsEventsCommitted.author == author_key,
                        MetricsEventsCommitted.author.like(f"{author_key} <%"),
                    )
                )
            rows = query.all()

            items: List[Dict] = []
            for row in rows:
                author_name, author_email = self._parse_author(row.author)
                items.append(
                    {
                        "repo_url": row.repo_url or "",
                        "author": author_name,
                        "author_uid": (row.author or "").strip() or author_name,
                        "author_email": author_email,
                        "tool_model_pairs_total": self._metric_total(
                            row.tool_model_pairs
                        ),
                        "mixed_additions_total": self._metric_total(
                            row.mixed_additions
                        ),
                        "human_additions": int(row.human_additions or 0),
                        "ai_accepted_lines": self._metric_total(row.ai_accepted),
                        "total_ai_additions_total": self._metric_total(
                            row.total_ai_additions
                        ),
                        "total_ai_deletions_total": self._metric_total(
                            row.total_ai_deletions
                        ),
                        "git_ai_version": row.git_ai_version,
                    }
                )
            return items

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
                query = query.filter(MetricsEventsCheckpoint.repo_url == repo_url)
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
        normalized_path = self._normalize_repo_path(repo_path)
        extracted_name = self._extract_repo_name(normalized_path)

        with session_scope(self.engine) as session:
            row = (
                session.query(StatsRepository)
                .filter(StatsRepository.repo_path == normalized_path)
                .first()
            )
            if row:
                current_name = (row.repo_name or "").strip()
                if not current_name or current_name == row.repo_path:
                    row.repo_name = extracted_name
                    row.updated_at = now_ts()
                    session.flush()
                return row.id

            record = StatsRepository(
                repo_path=normalized_path, repo_name=extracted_name
            )
            session.add(record)
            session.flush()
            return record.id

    def get_or_create_contributor(
        self, name: str, email: Optional[str], contributor_uid: Optional[str] = None
    ) -> str:
        uid = (contributor_uid or email or name or "unknown").strip().lower()
        normalized_name = (name or "unknown").strip() or "unknown"
        normalized_email = (email or "").strip() or None

        with session_scope(self.engine) as session:
            row = (
                session.query(StatsContributor)
                .filter(StatsContributor.contributor_uid == uid)
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
                contributor_uid=uid,
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

    def upsert_daily_stat(
        self, stat_date: int, repo_id: str, contributor_id: str, stats: Dict
    ) -> str:
        with session_scope(self.engine) as session:
            row = (
                session.query(StatsDailyStat)
                .filter(StatsDailyStat.stat_date == stat_date)
                .filter(StatsDailyStat.repo_id == repo_id)
                .filter(StatsDailyStat.contributor_id == contributor_id)
                .first()
            )

            if row is None:
                row = StatsDailyStat(
                    stat_date=stat_date, repo_id=repo_id, contributor_id=contributor_id
                )
                session.add(row)

            row.repo_name = stats.get("repo_name", "")
            row.contributor_name = stats.get("contributor_name", "")
            row.ai_generated_lines = int(stats.get("ai_generated_lines", 0))
            row.ai_generated_lines_total = int(
                stats.get("ai_generated_lines_total", row.ai_generated_lines)
            )
            row.ai_accepted_lines = int(stats.get("ai_accepted_lines", 0))
            row.human_lines = int(stats.get("human_lines", 0))
            row.git_ai_version = stats.get("git_ai_version", "")
            total = row.ai_accepted_lines + row.human_lines
            row.ai_percentage = (
                round((row.ai_accepted_lines / total) * 100, 2) if total > 0 else 0
            )
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
                query = query.filter(
                    or_(
                        StatsRepository.repo_name.like(like),
                        StatsRepository.repo_path.like(like),
                    )
                )
            query = query.order_by(StatsRepository.created_at.desc())
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
                        StatsContributor.email.like(like),
                        StatsContributor.contributor_uid.like(like),
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
        contributor_id: Optional[str],
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
            if contributor_id:
                query = query.filter(StatsDailyStat.contributor_id == contributor_id)

            rows = (
                query.join(
                    StatsRepository, StatsRepository.id == StatsDailyStat.repo_id
                )
                .join(
                    StatsContributor,
                    StatsContributor.id == StatsDailyStat.contributor_id,
                )
                .with_entities(
                    StatsDailyStat,
                    StatsRepository.repo_name,
                    StatsContributor.name,
                )
                .order_by(StatsDailyStat.stat_date.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            items: List[Dict] = []
            for stat, repo_name, contributor_name in rows:
                item = stat.to_dict()
                item["repo_name"] = repo_name or "未知仓库"
                item["contributor_name"] = contributor_name or "unknown"
                items.append(item)
            return items

    def get_daily_stats_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[int] = None,
        end_date: Optional[int] = None,
        repo_id: Optional[str] = None,
        contributor_id: Optional[str] = None,
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
            if contributor_id:
                query = query.filter(StatsDailyStat.contributor_id == contributor_id)

            total = query.count()
            rows = (
                query.join(
                    StatsRepository, StatsRepository.id == StatsDailyStat.repo_id
                )
                .join(
                    StatsContributor,
                    StatsContributor.id == StatsDailyStat.contributor_id,
                )
                .with_entities(
                    StatsDailyStat,
                    StatsRepository.repo_name,
                    StatsContributor.name,
                )
                .order_by(StatsDailyStat.stat_date.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )

            items: List[Dict] = []
            for stat, repo_name, contributor_name in rows:
                item = stat.to_dict()
                item["repo_name"] = repo_name or "未知仓库"
                item["contributor_name"] = contributor_name or "unknown"
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
        contributor_id: Optional[str] = None,
        granularity: str = "daily",
    ) -> List[Dict]:
        self.consolidate_unknown_repositories()
        with session_scope(self.engine) as session:
            query = (
                session.query(
                    StatsDailyStat.stat_date,
                    func.sum(StatsDailyStat.ai_generated_lines).label(
                        "ai_generated_lines"
                    ),
                    func.sum(StatsDailyStat.ai_accepted_lines).label(
                        "ai_accepted_lines"
                    ),
                    func.sum(StatsDailyStat.human_lines).label("human_lines"),
                )
                .filter(StatsDailyStat.stat_date >= start_date)
                .filter(StatsDailyStat.stat_date <= end_date)
            )

            if repo_id:
                query = query.filter(StatsDailyStat.repo_id == repo_id)
            if contributor_id:
                query = query.filter(StatsDailyStat.contributor_id == contributor_id)

            rows = (
                query.group_by(StatsDailyStat.stat_date)
                .order_by(StatsDailyStat.stat_date)
                .all()
            )

        items: List[Dict] = []
        for row in rows:
            accepted = int(row.ai_accepted_lines or 0)
            human = int(row.human_lines or 0)
            total = accepted + human
            items.append(
                {
                    "stat_date": int(row.stat_date),
                    "ai_generated_lines": int(row.ai_generated_lines or 0),
                    "ai_accepted_lines": accepted,
                    "human_lines": human,
                    "ai_percentage": round((accepted / total) * 100, 2)
                    if total > 0
                    else 0,
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
                    "ai_generated_lines": 0,
                    "ai_accepted_lines": 0,
                    "human_lines": 0,
                }
            grouped[key]["ai_generated_lines"] += item["ai_generated_lines"]
            grouped[key]["ai_accepted_lines"] += item["ai_accepted_lines"]
            grouped[key]["human_lines"] += item["human_lines"]

        result = []
        for value in grouped.values():
            total = value["ai_accepted_lines"] + value["human_lines"]
            value["ai_percentage"] = (
                round((value["ai_accepted_lines"] / total) * 100, 2) if total > 0 else 0
            )
            result.append(value)
        return sorted(result, key=lambda x: x["stat_date"])
