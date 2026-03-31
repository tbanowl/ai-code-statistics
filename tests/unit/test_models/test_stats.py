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
    row = StatsContributor(contributor_uid="alice@example.com", name="alice")
    data = row.to_dict()
    assert data["contributor_uid"] == "alice@example.com"
    assert data["name"] == "alice"


def test_stats_repo_contributor_and_daily_stat_fields():
    link = StatsRepoContributor(repo_id="repo-id", contributor_id="contrib-id")
    daily = StatsDailyStat(
        stat_date=1710000000000, repo_id="repo-id", contributor_id="contrib-id"
    )
    assert link.repo_id == "repo-id"
    assert link.contributor_id == "contrib-id"
    assert daily.ai_generated_lines in (None, 0)
    assert daily.ai_accepted_lines in (None, 0)
