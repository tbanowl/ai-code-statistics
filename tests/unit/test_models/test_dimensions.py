from core.database.models import StatsContributor, StatsRepoContributor, StatsRepository


def test_stats_repository_model_fields():
    repo = StatsRepository(repo_path="owner/repo", repo_name="repo")
    data = repo.to_dict()
    assert data["repo_path"] == "owner/repo"
    assert data["repo_name"] == "repo"


def test_stats_contributor_model_fields():
    contributor = StatsContributor(name="Alice", email="a@example.com")
    data = contributor.to_dict()
    assert data["name"] == "Alice"
    assert data["email"] == "a@example.com"


def test_stats_repo_contributor_model_fields():
    rel = StatsRepoContributor(repo_id="repo-id", contributor_id="contrib-id")
    data = rel.to_dict()
    assert data["repo_id"] == "repo-id"
    assert data["contributor_id"] == "contrib-id"
