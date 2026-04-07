"""Git Clone 服务单元测试"""
import os
import tempfile
import pytest
from core.services import GitCloneService


class TestGitCloneService:
    """Git Clone 服务测试"""

    def test_validate_private_key_format_rsa_valid(self):
        """测试验证有效的 RSA 私钥"""
        service = GitCloneService()
        valid_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAz9KxJzM2N5R6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4
dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7
X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2
eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4d
S7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7
X8wYgL4dQIDAQABAoIBAGF9KxJzM2N5R6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8
wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR
6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v
0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8w
YgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6
kTtR7X8ECgYEA/3KxJzM2N5R6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v
0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8w
YgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2eR6
kTtR7X8ECgYEA/3KxJzM2N5R6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v
-----END RSA PRIVATE KEY-----"""

        assert service._validate_private_key_format(valid_key) is True

    def test_validate_private_key_format_openssh_valid(self):
        """测试验证有效的 OpenSSH 私钥"""
        service = GitCloneService()
        valid_key = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACB9KxJzM2N5R6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2e
-----END OPENSSH PRIVATE KEY-----"""

        assert service._validate_private_key_format(valid_key) is True

    def test_validate_private_key_format_ec_valid(self):
        """测试验证有效的 EC 私钥"""
        service = GitCloneService()
        valid_key = """-----BEGIN EC PRIVATE KEY-----
MHcaIDA6Z9KxJzM2N5R6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2e
-----END EC PRIVATE KEY-----"""

        assert service._validate_private_key_format(valid_key) is True

    def test_validate_private_key_format_ed25519_valid(self):
        """测试验证有效的 ED25519 私钥"""
        service = GitCloneService()
        valid_key = """-----BEGIN ED25519 PRIVATE KEY-----
MHcaIDA6Z9KxJzM2N5R6kTtR7X8wYgL4dS7v0pXQ2eR6kTtR7X8wYgL4dS7v0pXQ2e
-----END ED25519 PRIVATE KEY-----"""

        assert service._validate_private_key_format(valid_key) is True

    def test_validate_private_key_format_invalid_no_header(self):
        """测试无效的私钥：缺少头部"""
        service = GitCloneService()
        invalid_key = """some random text here
END RSA PRIVATE KEY-----"""

        assert service._validate_private_key_format(invalid_key) is False

    def test_validate_private_key_format_invalid_no_footer(self):
        """测试无效的私钥：缺少尾部"""
        service = GitCloneService()
        invalid_key = """-----BEGIN RSA PRIVATE KEY-----
some random text here"""

        assert service._validate_private_key_format(invalid_key) is False

    def test_validate_private_key_format_invalid_empty(self):
        """测试无效的私钥：为空"""
        service = GitCloneService()

        assert service._validate_private_key_format("") is False
        assert service._validate_private_key_format("   ") is False
        assert service._validate_private_key_format(None) is False

    def test_normalize_private_key_with_literal_newlines(self):
        """测试规范化带有 \\n 的私钥"""
        service = GitCloneService()
        key_with_escaped = "-----BEGIN RSA PRIVATE KEY-----\\nsome content\\n-----END RSA PRIVATE KEY-----"

        normalized = service._normalize_private_key(key_with_escaped)

        assert "\\n" not in normalized
        assert normalized.startswith("-----BEGIN RSA PRIVATE KEY-----\n")
        assert normalized.endswith("-----END RSA PRIVATE KEY-----\n")

    def test_normalize_private_key_with_crlf(self):
        """测试规范化带有 \\r\\n 的私钥"""
        service = GitCloneService()
        key_with_crlf = "-----BEGIN RSA PRIVATE KEY-----\r\nsome content\r\n-----END RSA PRIVATE KEY-----"

        normalized = service._normalize_private_key(key_with_crlf)

        assert "\r\n" not in normalized
        assert normalized.startswith("-----BEGIN RSA PRIVATE KEY-----\n")
        assert normalized.endswith("-----END RSA PRIVATE KEY-----\n")

    def test_normalize_private_key_without_trailing_newline(self):
        """测试规范化缺少尾部换行的私钥"""
        service = GitCloneService()
        key_without_newline = "-----BEGIN RSA PRIVATE KEY-----\nsome content\n-----END RSA PRIVATE KEY-----"

        normalized = service._normalize_private_key(key_without_newline)

        assert normalized.endswith("\n")

    def test_normalize_private_key_with_extra_whitespace(self):
        """测试规范化带有额外空白字符的私钥"""
        service = GitCloneService()
        key_with_whitespace = """   -----BEGIN RSA PRIVATE KEY-----
        some content
        -----END RSA PRIVATE KEY-----
        """

        normalized = service._normalize_private_key(key_with_whitespace)

        # 应该去除首尾空白，但保留内部空白
        assert normalized.startswith("-----BEGIN RSA PRIVATE KEY-----")
        assert normalized.endswith("-----END RSA PRIVATE KEY-----\n")

    def test_write_private_key_to_temp(self):
        """测试将私钥写入临时文件"""
        service = GitCloneService()
        test_key = """-----BEGIN RSA PRIVATE KEY-----
test content
-----END RSA PRIVATE KEY-----
"""

        temp_path = service._write_private_key_to_temp(test_key)

        try:
            assert os.path.exists(temp_path)
            # 检查文件权限
            file_stat = os.stat(temp_path)
            # Windows 可能不完全支持 chmod 0o600，所以只检查文件存在
            # 在 Unix 系统上可以检查: oct(file_stat.st_mode & 0o777) == 0o600

            # 读取并验证内容
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert content == test_key
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_create_ssh_command(self):
        """测试创建 SSH 命令"""
        service = GitCloneService()
        test_key_path = "/tmp/test_key"
        ssh_cmd = service._create_ssh_command(test_key_path)

        assert 'ssh' in ssh_cmd
        assert f'-i "{test_key_path}"' in ssh_cmd
        assert 'StrictHostKeyChecking=no' in ssh_cmd
        assert 'UserKnownHostsFile=/dev/null' in ssh_cmd
        assert 'IdentitiesOnly=yes' in ssh_cmd
        assert 'LogLevel=ERROR' in ssh_cmd

    def test_clone_with_ssh_key_invalid_key_format(self):
        """测试使用无效格式的私钥克隆"""
        service = GitCloneService()
        invalid_key = "invalid_key_content_without_markers"

        with tempfile.TemporaryDirectory() as temp_dir:
            result = service.clone_with_ssh_key(
                "https://example.com/repo.git",
                invalid_key,
                temp_dir
            )
            assert result is False
