from core.database.models import (
    StatsContributor,
    StatsDailyStat,
    StatsRepoContributor,
    StatsRepository,
    gen_xid,
)


def test_gen_xid_returns_20_char_id():
    xid = gen_xid()
    assert isinstance(xid, str)
    assert len(xid) == 20


def test_stats_repository_defaults_and_dict():
    row = StatsRepository(repo_path="owner/repo", repo_name="repo")
    data = row.to_dict()
    assert data["repo_path"] == "owner/repo"
    assert data["repo_name"] == "repo"


def test_stats_contributor_defaults_and_dict():
    row = StatsContributor(name="alice", email="alice@example.com")
    data = row.to_dict()
    assert data["name"] == "alice"
    assert data["email"] == "alice@example.com"


def test_stats_repo_contributor_and_daily_stat_fields():
    link = StatsRepoContributor(repo_id="repo-id", contributor_id="contrib-id")
    daily = StatsDailyStat(
        stat_date=1710000000000,
        repo_id="repo-id",
        contributor_name="alice",
        contributor_email="alice@example.com",
    )
    assert link.repo_id == "repo-id"
    assert link.contributor_id == "contrib-id"
    assert daily.contributor_email == "alice@example.com"


def test_stats_daily_stat_new_metric_columns():
    columns = {c.name for c in StatsDailyStat.__table__.columns}
    expected = {
        "human_additions",
        "unknown_additions",
        "git_diff_deleted_lines",
        "git_diff_added_lines",
        "mixed_additions",
        "ai_additions",
        "ai_accepted",
        "total_ai_additions",
        "total_ai_deletions",
    }
    removed = {
        "ai_lines",
        "ai_total_lines",
        "ai_accepted_lines",
        "human_lines",
        "total_lines",
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"
    assert not removed.intersection(columns)

    daily = StatsDailyStat(stat_date=20260605, repo_id="r1")
    assert daily.human_additions in (None, 0)
    assert daily.ai_additions in (None, 0)
    assert daily.total_ai_additions in (None, 0)


def test_stats_repository_daily_aggregation_id_column():
    columns = {c.name for c in StatsRepository.__table__.columns}
    assert "last_daily_aggregation_id" in columns
    assert "last_daily_aggregation_commit_sha" not in columns
