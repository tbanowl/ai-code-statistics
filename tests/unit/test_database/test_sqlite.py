import os
import tempfile

import pytest
from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as db_base
from core.database.stats_db import StatsDatabase


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
    repo_id = stats_db.get_or_create_repository("owner/repo")
    contributor_id = stats_db.get_or_create_contributor("alice", "alice@example.com")
    stats_db.ensure_repo_contributor_link(repo_id, contributor_id)

    stats_db.upsert_daily_stat(
        1710000000000,
        repo_id,
        contributor_id,
        {
            "repo_name": "owner/repo",
            "contributor_name": "alice",
            "ai_generated_lines": 20,
            "ai_generated_lines_total": 24,
            "ai_accepted_lines": 80,
            "human_lines": 40,
        },
    )

    rows = stats_db.query_daily_stats(
        1709999999000,
        1710000001000,
        repo_id,
        contributor_id,
        limit=10,
        offset=0,
    )
    assert len(rows) == 1
    assert rows[0]["ai_generated_lines"] == 20
    assert rows[0]["ai_accepted_lines"] == 80


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


def test_ensure_repository_branch_upserts_branch(stats_db):
    repo_id = stats_db.get_or_create_repository("repo/a")

    first_id = stats_db.ensure_repository_branch(repo_id, "main")
    second_id = stats_db.ensure_repository_branch(repo_id, " main ")

    assert second_id == first_id
