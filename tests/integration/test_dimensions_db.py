import os
import tempfile

import pytest

import core.config.loader as loader
from core.database.metrics_db import MetricsDatabase
from core.database.stats_db import StatsDatabase
from core.scheduler.tasks.daily_aggregation_task import DailyAggregationTask
from core.database.base import session_scope
from core.database.models import (
    StatsContributor,
    StatsDailyStat,
    StatsRepoContributor,
    StatsRepository,
)


@pytest.fixture
def db_url():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield f"sqlite:///{path}"
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def setup_dbs(db_url):
    loader.config_data = {
        "features": {"enabled": True},
        "git": {"type": "github"},
        "database": {"url": db_url, "echo": False},
    }
    metrics_db = MetricsDatabase()
    stats_db = StatsDatabase()
    metrics_db.init_db()
    return metrics_db, stats_db


def test_query_committed_and_checkpoint_events(setup_dbs):
    metrics_db, stats_db = setup_dbs

    raw_id = metrics_db.save_metrics_raw(
        batch_id="b1",
        version=1,
        event_count=2,
        payload_json="{}",
        received_at=1710000000000,
    )
    metrics_db.save_committed_event(
        {
            "raw_id": raw_id,
            "timestamp": 1710000000001,
            "repo_url": "repo/a",
            "author": "alice <alice@example.com>",
            "human_additions": 6,
            "git_diff_added_lines": 10,
            "git_diff_deleted_lines": 2,
            "ai_additions": [3, 1],
            "total_ai_additions": [3, 1],
        }
    )
    metrics_db.save_checkpoint_event(
        {
            "raw_id": raw_id,
            "timestamp": 1710000000002,
            "repo_url": "repo/a",
            "author": "alice <alice@example.com>",
            "kind": "ai_agent",
            "lines_added": 5,
            "lines_added_sloc": 3,
        }
    )

    committed = stats_db.query_committed_events(1710000000000, 1710000000010)
    checkpoints = stats_db.query_checkpoint_events(1710000000000, 1710000000010)

    assert len(committed) == 1
    assert committed[0]["repo_url"] == "repo/a"
    assert committed[0]["author"] == "alice"
    assert committed[0]["author_email"] == "alice@example.com"
    assert committed[0]["ai_accepted_lines"] == 3
    assert committed[0]["human_additions"] == 6
    assert len(checkpoints) == 1
    assert checkpoints[0]["author"] == "alice"
    assert checkpoints[0]["lines_added"] == 5
    assert checkpoints[0]["lines_added_sloc"] == 3


def test_repository_contributor_and_daily_stats_flow(setup_dbs):
    _, stats_db = setup_dbs

    repo_id = stats_db.get_or_create_repository("https://github.com/org/repo-a.git")
    contributor_id = stats_db.get_or_create_contributor("alice", "alice@example.com")
    stats_db.ensure_repo_contributor_link(repo_id, contributor_id)
    stats_db.upsert_daily_stat(
        1710000000000,
        repo_id,
        contributor_id,
        {
            "repo_name": "org/repo-a",
            "contributor_name": "alice",
            "ai_generated_lines": 20,
            "ai_generated_lines_total": 24,
            "ai_accepted_lines": 60,
            "human_lines": 40,
        },
    )

    repos, repo_total = stats_db.list_repositories(limit=10, offset=0)
    contributors, contributor_total = stats_db.list_contributors(limit=10, offset=0)
    daily = stats_db.query_daily_stats(
        start_date=1709999999000,
        end_date=1710000001000,
        repo_id=repo_id,
        contributor_id=contributor_id,
        limit=10,
        offset=0,
    )

    assert repo_total == 1
    assert contributor_total == 1
    assert repos[0]["repo_path"] == "https://github.com/org/repo-a.git"
    assert repos[0]["repo_name"] == "org/repo-a"
    assert contributors[0]["name"] == "alice"
    assert len(daily) == 1
    assert daily[0]["ai_accepted_lines"] == 60
    assert daily[0]["repo_name"] == "org/repo-a"
    assert daily[0]["contributor_name"] == "alice"


def test_repository_fallback_unknown(setup_dbs):
    _, stats_db = setup_dbs

    repo_id = stats_db.get_or_create_repository("")
    repo = stats_db.get_repository_by_id(repo_id)

    assert repo is not None
    assert repo["repo_path"] == "未知仓库"
    assert repo["repo_name"] == "未知仓库"


def test_consolidate_empty_repository_rows(setup_dbs):
    _, stats_db = setup_dbs

    with session_scope(stats_db.engine) as session:
        unknown = StatsRepository(repo_path="未知仓库", repo_name="未知仓库")
        bad_repo = StatsRepository(repo_path="", repo_name="")
        contributor = StatsContributor(
            contributor_uid="alice@example.com",
            name="alice",
            email="alice@example.com",
        )
        session.add_all([unknown, bad_repo, contributor])
        session.flush()

        session.add(
            StatsDailyStat(
                stat_date=1710000000000,
                repo_id=bad_repo.id,
                contributor_id=contributor.id,
                ai_generated_lines=1,
                ai_generated_lines_total=2,
                ai_accepted_lines=3,
                human_lines=4,
            )
        )
        session.add(
            StatsRepoContributor(repo_id=bad_repo.id, contributor_id=contributor.id)
        )

    unknown_id = stats_db.consolidate_unknown_repositories()

    with session_scope(stats_db.engine) as session:
        bad = (
            session.query(StatsRepository)
            .filter(StatsRepository.repo_path == "")
            .first()
        )
        assert bad is None

        daily = session.query(StatsDailyStat).all()
        assert len(daily) == 1
        assert daily[0].repo_id == unknown_id

        links = session.query(StatsRepoContributor).all()
        assert len(links) == 1
        assert links[0].repo_id == unknown_id


def test_aggregation_range_does_not_create_empty_repository(setup_dbs):
    metrics_db, stats_db = setup_dbs

    with session_scope(stats_db.engine) as session:
        session.add(StatsRepository(repo_path="", repo_name=""))

    raw_id = metrics_db.save_metrics_raw(
        batch_id="b2",
        version=1,
        event_count=1,
        payload_json="{}",
        received_at=1772323200000,
    )
    metrics_db.save_committed_event(
        {
            "raw_id": raw_id,
            "timestamp": 1772323200000,
            "repo_url": "",
            "author": "alice <alice@example.com>",
            "human_additions": 2,
            "git_diff_added_lines": 8,
            "git_diff_deleted_lines": 1,
            "ai_additions": [3, 1],
            "total_ai_additions": [3, 1],
        }
    )

    task = DailyAggregationTask(loader.config_data)
    task.execute(
        {
            "start_date": 1772294400000,
            "end_date": 1774195199999,
        }
    )

    with session_scope(stats_db.engine) as session:
        bad_count = (
            session.query(StatsRepository)
            .filter(
                (StatsRepository.repo_path == "") | (StatsRepository.repo_name == "")
            )
            .count()
        )
        assert bad_count == 0

        unknown = (
            session.query(StatsRepository)
            .filter(StatsRepository.repo_path == "未知仓库")
            .first()
        )
        assert unknown is not None
