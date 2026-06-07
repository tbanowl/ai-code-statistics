import os
import tempfile

import pytest
from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as db_base
from core.database.base import session_scope
from core.database.models import (
    MetricsEventsCheckpoint,
    MetricsEventsCommitted,
    MetricsEventsRaw,
    StatsRepository,
)
from core.database.stats_db import StatsDatabase
from core.utils.repo_url import UNKNOWN_REPO


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def stats_db(temp_db_path):
    loader.config_data = {
        "features": {"enabled": True},
        "git": {"type": "github"},
        "database": {"url": f"sqlite:///{temp_db_path}", "echo": False},
    }
    db_base.global_engine = create_engine(f"sqlite:///{temp_db_path}")
    db = StatsDatabase()
    db_base.Base.metadata.create_all(db.engine)
    return db


def test_init_db_creates_engine(stats_db):
    assert stats_db.engine is not None


def test_upsert_and_query_daily_stats(stats_db):
    repo_id = stats_db.get_or_create_repository("https://example.com/org/repo.git")
    stats_db.upsert_daily_stat(
        20260605,
        repo_id,
        "alice",
        "alice@example.com",
        {
            "repo_name": "org/repo",
            "contributor_name": "alice",
            "contributor_email": "alice@example.com",
            "human_additions": 40,
            "unknown_additions": 1,
            "git_diff_deleted_lines": 3,
            "git_diff_added_lines": 120,
            "mixed_additions": 2,
            "ai_additions": 20,
            "ai_accepted": 18,
            "total_ai_additions": 24,
            "total_ai_deletions": 5,
        },
    )

    rows = stats_db.query_daily_stats(
        start_date=20260601,
        end_date=20260630,
        repo_id=repo_id,
        contributor_email="alice@example.com",
        limit=10,
        offset=0,
    )

    assert rows[0]["human_additions"] == 40
    assert rows[0]["unknown_additions"] == 1
    assert rows[0]["git_diff_deleted_lines"] == 3
    assert rows[0]["git_diff_added_lines"] == 120
    assert rows[0]["mixed_additions"] == 2
    assert rows[0]["ai_additions"] == 20
    assert rows[0]["ai_accepted"] == 18
    assert rows[0]["total_ai_additions"] == 24
    assert rows[0]["total_ai_deletions"] == 5


def test_list_repositories_and_contributors(stats_db):
    stats_db.get_or_create_repository("repo/a")
    stats_db.get_or_create_repository("repo/b")
    stats_db.get_or_create_contributor("bob", "bob@example.com")

    repos, total_repos = stats_db.list_repositories(limit=10, offset=0)
    contributors, total_contributors = stats_db.list_contributors(limit=10, offset=0)

    assert total_repos == 2
    assert len(repos) == 2
    assert total_contributors == 1
    assert len(contributors) == 1


def test_get_or_create_repository_extracts_deep_path_levels(stats_db):
    repo_id = stats_db.get_or_create_repository("github.com/L5/L4/L3/L2/L1/R1/R2")

    repo = stats_db.get_repository_by_id(repo_id)

    assert repo["repo_path"] == "github.com/l5/l4/l3/l2/l1/r1/r2"
    assert repo["name_level1"] == "L1"
    assert repo["name_level2"] == "L2"
    assert repo["name_level3"] == "L3"
    assert repo["name_level4"] == "L4"
    assert repo["name_level5"] == "L5"
    assert repo["repo_short_name"] == "r1/r2"


def test_get_or_create_repository_extracts_single_segment_short_name_after_five_levels(stats_db):
    repo_id = stats_db.get_or_create_repository("github.com/L5/L4/L3/L2/L1/R1")

    repo = stats_db.get_repository_by_id(repo_id)

    assert repo["name_level1"] == "L1"
    assert repo["name_level2"] == "L2"
    assert repo["name_level3"] == "L3"
    assert repo["name_level4"] == "L4"
    assert repo["name_level5"] == "L5"
    assert repo["repo_short_name"] == "r1"


def test_get_or_create_repository_extracts_exactly_five_levels(stats_db):
    repo_id = stats_db.get_or_create_repository("github.com/L5/L4/L3/L2/L1")

    repo = stats_db.get_repository_by_id(repo_id)

    assert repo["name_level1"] == "L1"
    assert repo["name_level2"] == "L2"
    assert repo["name_level3"] == "L3"
    assert repo["name_level4"] == "L4"
    assert repo["name_level5"] == "L5"
    assert repo["repo_short_name"] is None


def test_get_or_create_repository_extracts_short_path_levels(stats_db):
    repo_id = stats_db.get_or_create_repository("https://github.com/org/team/repo.git")

    repo = stats_db.get_repository_by_id(repo_id)

    assert repo["repo_path"] == "github.com/org/team/repo"
    assert repo["name_level1"] == "ORG"
    assert repo["name_level2"] == "TEAM"
    assert repo["name_level3"] is None
    assert repo["name_level4"] is None
    assert repo["name_level5"] is None
    assert repo["repo_short_name"] == "repo"


def test_get_or_create_repository_backfills_existing_repository_name_parts(stats_db):
    with session_scope(stats_db.engine) as session:
        session.add(
            StatsRepository(
                id="repoexisting0000001",
                repo_path="github.com/L5/L4/L3/L2/L1/R1/R2",
                repo_name="L5/L4/L3/L2/L1/R1/R2",
            )
        )

    repo_id = stats_db.get_or_create_repository("github.com/L5/L4/L3/L2/L1/R1/R2")

    repo = stats_db.get_repository_by_id(repo_id)

    assert repo_id == "repoexisting0000001"
    assert repo["name_level1"] == "L1"
    assert repo["name_level2"] == "L2"
    assert repo["name_level3"] == "L3"
    assert repo["name_level4"] == "L4"
    assert repo["name_level5"] == "L5"
    assert repo["repo_short_name"] == "r1/r2"


def test_ensure_repository_branch_upserts_branch(stats_db):
    repo_id = stats_db.get_or_create_repository("repo/a")

    first_id = stats_db.ensure_repository_branch(repo_id, "main")
    second_id = stats_db.ensure_repository_branch(repo_id, " main ")

    assert second_id == first_id


def test_query_events_normalizes_repo_url_filters(stats_db):
    with session_scope(stats_db.engine) as session:
        raw = MetricsEventsRaw(
            event_count=2,
            payload_json="{}",
            received_at=1000,
        )
        session.add(raw)
        session.flush()
        session.add(
            MetricsEventsCommitted(
                uid="committed-1",
                raw_id=raw.id,
                timestamp=1000,
                repo_url="codeup.aliyun.com/org/repo",
                author="alice <alice@example.com>",
                human_additions=3,
            )
        )
        session.add(
            MetricsEventsCheckpoint(
                uid="checkpoint-1",
                raw_id=raw.id,
                timestamp=1000,
                kind="ai_agent",
                repo_url="codeup.aliyun.com/org/repo",
                author="alice <alice@example.com>",
                lines_added=5,
                lines_added_sloc=4,
            )
        )

    full_url = "https://codeup.aliyun.com/org/repo.git"

    committed = stats_db.query_committed_events(0, 2000, repo_url=full_url)
    checkpoint = stats_db.query_checkpoint_events(0, 2000, repo_url=full_url)
    paginated = stats_db.get_committed_events_paginated(repo_url=full_url)

    assert [item["repo_url"] for item in committed] == ["codeup.aliyun.com/org/repo"]
    assert [item["repo_url"] for item in checkpoint] == ["codeup.aliyun.com/org/repo"]
    assert paginated["total"] == 1
    assert paginated["items"][0]["repo_url"] == "codeup.aliyun.com/org/repo"


class TestExtractRepoName:
    @staticmethod
    def extract(path):
        return StatsDatabase._extract_repo_name(path)

    def test_normalized_host_path(self):
        assert self.extract("github.com/org/repo-a") == "org/repo-a"

    def test_normalized_host_with_port(self):
        assert self.extract("devops.cxmt.com:8022/group/project") == "group/project"

    def test_already_short_path(self):
        assert self.extract("org/repo-a") == "org/repo-a"

    def test_https_url(self):
        assert self.extract("https://github.com/org/repo-a.git") == "org/repo-a"

    def test_git_at_url(self):
        assert self.extract("git@github.com:org/repo-a.git") == "org/repo-a"

    def test_unknown_repo(self):
        assert self.extract(UNKNOWN_REPO) == UNKNOWN_REPO

    def test_empty(self):
        assert self.extract("") == UNKNOWN_REPO

    def test_none(self):
        assert self.extract(None) == UNKNOWN_REPO

    def test_host_only(self):
        assert self.extract("github.com") == "github.com"
