"""repo_url 工具函数单元测试"""

import pytest
from core.utils.repo_url import normalize_repo_url, restore_repo_url, UNKNOWN_REPO


class TestNormalizeRepoUrl:
    """normalize_repo_url 测试"""

    def test_https_url(self):
        assert normalize_repo_url("https://codeup.aliyun.com/org/repo.git") == "codeup.aliyun.com/org/repo"

    def test_http_url(self):
        assert normalize_repo_url("http://codeup.aliyun.com/org/repo.git") == "codeup.aliyun.com/org/repo"

    def test_ssh_url(self):
        assert normalize_repo_url("ssh://git@codeup.aliyun.com/org/repo.git") == "codeup.aliyun.com/org/repo"

    def test_git_at_url(self):
        assert normalize_repo_url("git@codeup.aliyun.com:org/repo.git") == "codeup.aliyun.com/org/repo"

    def test_git_protocol_url(self):
        assert normalize_repo_url("git://codeup.aliyun.com/org/repo.git") == "codeup.aliyun.com/org/repo"

    def test_url_with_port(self):
        assert normalize_repo_url("http://devops.cxmt.com:8022/group/project.git") == "devops.cxmt.com:8022/group/project"

    def test_ssh_url_with_port(self):
        assert normalize_repo_url("ssh://git@devops.cxmt.com:8022/group/project.git") == "devops.cxmt.com:8022/group/project"

    def test_already_normalized(self):
        assert normalize_repo_url("org/repo") == "org/repo"

    def test_none_input(self):
        assert normalize_repo_url(None) == UNKNOWN_REPO

    def test_empty_string(self):
        assert normalize_repo_url("") == UNKNOWN_REPO

    def test_whitespace_only(self):
        assert normalize_repo_url("   ") == UNKNOWN_REPO

    def test_trailing_slash(self):
        assert normalize_repo_url("https://codeup.aliyun.com/org/repo.git/") == "codeup.aliyun.com/org/repo"

    def test_no_git_suffix(self):
        assert normalize_repo_url("https://codeup.aliyun.com/org/repo") == "codeup.aliyun.com/org/repo"

    def test_file_protocol(self):
        assert normalize_repo_url("file:///local/path/repo.git") == "local/path/repo"

    def test_url_with_spaces(self):
        assert normalize_repo_url("  https://codeup.aliyun.com/org/repo.git  ") == "codeup.aliyun.com/org/repo"

    def test_host_only_no_path(self):
        assert normalize_repo_url("https://codeup.aliyun.com") == "codeup.aliyun.com"

    def test_trailing_slash_without_git_suffix(self):
        assert normalize_repo_url("https://codeup.aliyun.com/org/repo/") == "codeup.aliyun.com/org/repo"

    def test_idempotent(self):
        """已归一化的值再次归一化结果不变"""
        normalized = normalize_repo_url("https://codeup.aliyun.com/org/repo.git")
        assert normalize_repo_url(normalized) == normalized


class TestRestoreRepoUrl:
    """restore_repo_url 测试"""

    def test_ssh(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo", "ssh") == "ssh://git@codeup.aliyun.com/org/repo.git"

    def test_https(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo", "https") == "https://codeup.aliyun.com/org/repo.git"

    def test_http(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo", "http") == "http://codeup.aliyun.com/org/repo.git"

    def test_git(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo", "git") == "git://codeup.aliyun.com/org/repo.git"

    def test_default_protocol_is_ssh(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo") == "ssh://git@codeup.aliyun.com/org/repo.git"

    def test_with_port(self):
        assert restore_repo_url("devops.cxmt.com:8022/group/project", "ssh") == "ssh://git@devops.cxmt.com:8022/group/project.git"

    def test_unknown_repo(self):
        assert restore_repo_url(UNKNOWN_REPO, "ssh") == UNKNOWN_REPO

    def test_empty_string(self):
        assert restore_repo_url("", "ssh") == ""

    def test_unknown_protocol_fallback_ssh(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo", "unknown") == "ssh://git@codeup.aliyun.com/org/repo.git"


class TestRoundTrip:
    """往返测试：restore(normalize(x)) 应还原为可用 URL"""

    @pytest.mark.parametrize("raw_url,protocol", [
        ("https://codeup.aliyun.com/org/repo.git", "https"),
        ("http://codeup.aliyun.com/org/repo.git", "http"),
        ("ssh://git@codeup.aliyun.com/org/repo.git", "ssh"),
        ("git@codeup.aliyun.com:org/repo.git", "ssh"),
        ("http://devops.cxmt.com:8022/group/project.git", "http"),
    ])
    def test_round_trip(self, raw_url, protocol):
        normalized = normalize_repo_url(raw_url)
        restored = restore_repo_url(normalized, protocol)
        # 还原后的 URL 应以正确协议开头
        assert restored.startswith(f"{protocol}://")
        assert restored.endswith(".git")
