import os
import tempfile

import pytest
from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as db_base
from core.database.stats_db import StatsDatabase
from core.database.authorship_notes_db import compute_note_content_hash
from core.database.blame_stats_db import BlameStatsDatabase
from core.database.base import session_scope
from core.database.models import AuthorshipNotes
from core.database.models import StatsBlameRepo, StatsBlameRepoContributor
from core.database.models import StatsRepository, StatsRepositoryBranch


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def blame_stats_db(temp_db_path):
    loader.config_data = {
        "features": {"enabled": True},
        "git": {"type": "github"},
        "database": {"url": f"sqlite:///{temp_db_path}", "echo": False},
    }
    db_base.global_engine = create_engine(f"sqlite:///{temp_db_path}")
    db = BlameStatsDatabase()
    db_base.Base.metadata.create_all(db.engine)
    return db


def test_get_git_notes_batch_empty(blame_stats_db):
    assert blame_stats_db.get_git_notes_batch([]) == {}


def test_get_git_notes_batch_returns_matching_notes(blame_stats_db):
    with session_scope(blame_stats_db.engine) as session:
        session.add(
            AuthorshipNotes(
                id="noteabc1230000000001",
                repo_url="https://example.com/repo.git",
                branch="main",
                commit_sha="abc123",
                note_blob_oid=None,
                author_name="tester",
                author_email="tester@example.com",
                note_content="note-a",
                content_hash=compute_note_content_hash("note-a"),
                change_seq=1,
            )
        )
        session.add(
            AuthorshipNotes(
                id="notedef4560000000002",
                repo_url="https://example.com/repo.git",
                branch="main",
                commit_sha="def456",
                note_blob_oid=None,
                author_name="tester",
                author_email="tester@example.com",
                note_content="note-b",
                content_hash=compute_note_content_hash("note-b"),
                change_seq=2,
            )
        )

    result = blame_stats_db.get_git_notes_batch(["abc123", "missing"])

    assert result == {"abc123": "note-a"}


def test_get_repository_branches_reads_repository_branch_table(blame_stats_db):
    stats_db = StatsDatabase()
    repo_id = stats_db.get_or_create_repository("https://example.com/repo.git")
    stats_db.ensure_repository_branch(repo_id, "release")
    stats_db.ensure_repository_branch(repo_id, "main")

    assert blame_stats_db.get_repository_branches(repo_id) == ["main", "release"]


def test_repository_branch_soft_delete_excludes_branch_from_stats(blame_stats_db):
    stats_db = StatsDatabase()
    repo_id = stats_db.get_or_create_repository("https://example.com/repo.git")
    stats_db.ensure_repository_branch(repo_id, "main")
    stats_db.ensure_repository_branch(repo_id, "release")

    assert blame_stats_db.mark_repository_branch_deleted(repo_id, "release") is True

    assert blame_stats_db.get_repository_branches(repo_id) == ["main"]
    with session_scope(blame_stats_db.engine) as session:
        row = (
            session.query(StatsRepositoryBranch)
            .filter(StatsRepositoryBranch.repo_id == repo_id)
            .filter(StatsRepositoryBranch.branch_name == "release")
            .one()
        )
        assert row.is_deleted == 1
        assert row.deleted_at is not None


def test_update_repository_last_blame_commit_sha(blame_stats_db):
    stats_db = StatsDatabase()
    repo_id = stats_db.get_or_create_repository("https://example.com/repo.git")

    assert (
        blame_stats_db.update_repository_last_blame_commit_sha(
            repo_id, "abc123def456"
        )
        is True
    )

    with session_scope(blame_stats_db.engine) as session:
        repo = (
            session.query(StatsRepository)
            .filter(StatsRepository.id == repo_id)
            .one()
        )
        assert repo.last_blame_commit_sha == "abc123def456"


def test_update_repository_last_blame_stats_records_commit_and_stat_date(blame_stats_db):
    stats_db = StatsDatabase()
    repo_id = stats_db.get_or_create_repository("https://example.com/repo.git")

    assert (
        blame_stats_db.update_repository_last_blame_stats(
            repo_id, "abc123def456", "20260530"
        )
        is True
    )

    with session_scope(blame_stats_db.engine) as session:
        repo = (
            session.query(StatsRepository)
            .filter(StatsRepository.id == repo_id)
            .one()
        )
        assert repo.last_blame_commit_sha == "abc123def456"
        assert repo.last_stat_date == 20260530


def test_save_branch_stats_batch_keeps_multiple_branches(blame_stats_db):
    repo_id = "repo-branch-stats-1"
    stat_date = "20260517"

    def repo_obj(branch: str) -> StatsBlameRepo:
        return StatsBlameRepo(
            id=f"repo-{branch}",
            repo_id=repo_id,
            stat_date=stat_date,
            commit_sha=f"{branch[:4]}123",
            branch=branch,
            total_lines=10,
            ai_lines=4,
            non_ai_lines=6,
            total_files=1,
        )

    def contributor_obj(branch: str) -> StatsBlameRepoContributor:
        return StatsBlameRepoContributor(
            id=f"contrib-{branch}",
            repo_id=repo_id,
            branch=branch,
            stat_date=stat_date,
            contributor_name="Alice",
            contributor_email="alice@example.com",
            ai_lines=4,
            non_ai_lines=6,
            total_lines=10,
        )

    blame_stats_db.save_branch_stats_batch(
        repo_id,
        "main",
        stat_date,
        repo_obj("main"),
        [contributor_obj("main")],
    )
    blame_stats_db.save_branch_stats_batch(
        repo_id,
        "release",
        stat_date,
        repo_obj("release"),
        [contributor_obj("release")],
    )

    with session_scope(blame_stats_db.engine) as session:
        branches = [
            row.branch
            for row in session.query(StatsBlameRepo)
            .filter(StatsBlameRepo.repo_id == repo_id)
            .order_by(StatsBlameRepo.branch.asc())
            .all()
        ]
        contributor_branches = [
            row.branch
            for row in session.query(StatsBlameRepoContributor)
            .filter(StatsBlameRepoContributor.repo_id == repo_id)
            .order_by(StatsBlameRepoContributor.branch.asc())
            .all()
        ]

    assert branches == ["main", "release"]
    assert contributor_branches == ["main", "release"]


def test_save_branch_stats_batch_replaces_repo_and_person_rows_without_file_rows(blame_stats_db):
    repo_id = "repo-person-stats-1"
    stat_date = "20260530"

    def repo_obj(total_lines: int) -> StatsBlameRepo:
        return StatsBlameRepo(
            id=f"repo-{total_lines}",
            repo_id=repo_id,
            stat_date=stat_date,
            commit_sha=f"abc{total_lines}",
            branch="main",
            total_lines=total_lines,
            ai_lines=4,
            non_ai_lines=total_lines - 4,
            total_files=1,
        )

    def contributor_obj(total_lines: int) -> StatsBlameRepoContributor:
        return StatsBlameRepoContributor(
            id=f"contrib-{total_lines}",
            repo_id=repo_id,
            branch="main",
            stat_date=stat_date,
            contributor_name="Alice",
            contributor_email="",
            ai_lines=4,
            non_ai_lines=total_lines - 4,
            total_lines=total_lines,
        )

    blame_stats_db.save_branch_stats_batch(
        repo_id,
        "main",
        stat_date,
        repo_obj(10),
        [contributor_obj(10)],
    )
    blame_stats_db.save_branch_stats_batch(
        repo_id,
        "main",
        stat_date,
        repo_obj(12),
        [contributor_obj(12)],
    )

    with session_scope(blame_stats_db.engine) as session:
        repo_rows = (
            session.query(StatsBlameRepo)
            .filter(StatsBlameRepo.repo_id == repo_id)
            .all()
        )
        contributor_rows = (
            session.query(StatsBlameRepoContributor)
            .filter(StatsBlameRepoContributor.repo_id == repo_id)
            .all()
        )

    assert len(repo_rows) == 1
    assert repo_rows[0].total_lines == 12
    assert len(contributor_rows) == 1
    assert contributor_rows[0].total_lines == 12


def test_repo_and_contributor_query_payloads_exclude_removed_fields(blame_stats_db):
    repo_id = "repo-query-fields-1"
    stat_date = "20260530"

    blame_stats_db.save_branch_stats_batch(
        repo_id,
        "main",
        stat_date,
        StatsBlameRepo(
            id="repo-query-row-1",
            repo_id=repo_id,
            stat_date=stat_date,
            commit_sha="abc123",
            branch="main",
            total_lines=10,
            ai_lines=4,
            non_ai_lines=6,
            total_files=1,
        ),
        [
            StatsBlameRepoContributor(
                id="contrib-query-row-1",
                repo_id=repo_id,
                branch="main",
                stat_date=stat_date,
                contributor_name="Alice",
                contributor_email="",
                ai_lines=4,
                non_ai_lines=6,
                total_lines=10,
            )
        ],
    )

    repo_payload = blame_stats_db.get_repo_blame_stats(repo_id, None, None)[0]
    contributor_payload = blame_stats_db.get_repo_contributor_stats(repo_id, 20260530)[0]

    assert "ai_ratio" not in repo_payload
    assert "contributor_id" not in contributor_payload
