"""测试 data_uid 模块的单元测试"""

import hashlib
from core.database.models import (
    MetricsEventsCheckpoint,
    MetricsEventsAgentUsage,
    MetricsEventsInstallHooks,
    MetricsEventsCommitted,
)
from core.utils.data_uid import (
    gen_commited_uid,
    gen_checkpoint_uid,
    gen_install_hooks_uid,
    gen_agent_usage_uid,
    check_append,
    hash_data,
)


class TestCheckAppend:
    """测试 check_append 辅助函数"""

    def test_check_append_with_none(self):
        """测试传入 None 值时不拼接"""
        result = check_append(None, "base")
        assert result == "base"

    def test_check_append_with_string(self):
        """测试传入字符串值时正确拼接"""
        result = check_append("value", "base")
        assert result == "base,value"

    def test_check_append_with_non_string(self):
        """测试传入非字符串值时转换为字符串拼接"""
        result = check_append(123, "base")
        # 修复后的行为: 所有值都转换为字符串并拼接
        assert result == "base,123"
    
    def test_check_append_with_concat_comma(self):
        result = check_append("123", "")
        assert result == "123"
        
    def test_check_append_with_concat_blank(self):
        result = check_append("    ", "233")
        assert result == "233"


class TestHashData:
    """测试 hash_data 函数"""

    def test_hash_data_default_sha1(self):
        """测试默认使用 sha1 算法"""
        data = "test data"
        result = hash_data(data)
        # 验证 sha1 哈希长度为 40
        assert len(result) == 40
        # 验证是合法的十六进制字符串
        assert all(c in "0123456789abcdef" for c in result)
        # 验证与标准 sha1 一致
        expected = hashlib.sha1(data.encode('utf-8')).hexdigest()
        assert result == expected

    def test_hash_data_with_md5(self):
        """测试指定 md5 算法"""
        data = "test data"
        result = hash_data(data, algorithm='md5')
        # md5 哈希长度为 32
        assert len(result) == 32
        # 验证与标准 md5 一致
        expected = hashlib.md5(data.encode('utf-8')).hexdigest()
        assert result == expected

    def test_hash_data_with_sha256(self):
        """测试指定 sha256 算法"""
        data = "test data"
        result = hash_data(data, algorithm='sha256')
        # sha256 哈希长度为 64
        assert len(result) == 64
        # 验证与标准 sha256 一致
        expected = hashlib.sha256(data.encode('utf-8')).hexdigest()
        assert result == expected

    def test_hash_data_empty_string(self):
        """测试空字符串的哈希"""
        result = hash_data("")
        assert len(result) == 40

    def test_hash_data_unicode(self):
        """测试 Unicode 字符串的哈希"""
        data = "测试数据 🚀"
        result = hash_data(data)
        assert len(result) == 40


class TestGenCommittedUid:
    """测试 gen_commited_uid 函数"""

    def test_gen_commited_uid_with_full_data(self):
        """测试包含所有字段的 committed 数据"""
        data = MetricsEventsCommitted(
            raw_id="test-raw-1",
            timestamp=1710000000000,
            commit_sha="abc123",
            base_commit_sha="def456",
        )
        result = gen_commited_uid(data)
        # 返回的是拼接后的字符串,不是哈希值
        assert result is not None
        assert "abc123" in result
        assert "def456" in result

    def test_gen_commited_uid_with_partial_data(self):
        """测试只包含部分字段的 committed 数据"""
        data = MetricsEventsCommitted(
            raw_id="test-raw-2",
            timestamp=1710000000000,
            commit_sha="abc123",
        )
        result = gen_commited_uid(data)
        assert result is not None
        assert "abc123" in result


class TestGenCheckpointUid:
    """测试 gen_checkpoint_uid 函数"""

    def test_gen_checkpoint_uid_with_full_data(self):
        """测试包含所有字段的 checkpoint 数据"""
        data = MetricsEventsCheckpoint(
            raw_id="test-raw-1",
            timestamp=1710000000000,
            checkpoint_ts=1710000005000,
            kind="edit",
            file_path="src/main.py",
            lines_added=10,
            lines_deleted=2,
            lines_added_sloc=8,
            lines_deleted_sloc=1,
            repo_url="https://github.com/test/repo",
            author="alice",
            commit_sha="abc123",
            base_commit_sha="def456",
            branch="main",
            tool="claude",
            model="claude-3-5",
            prompt_id="prompt-123",
        )
        result = gen_checkpoint_uid(data)
        assert result is not None
        assert len(result) == 40  # sha1 长度

    def test_gen_checkpoint_uid_with_partial_data(self):
        """测试只包含部分字段的 checkpoint 数据"""
        data = MetricsEventsCheckpoint(
            raw_id="test-raw-2",
            timestamp=1710000000000,
            file_path="src/main.py",
        )
        result = gen_checkpoint_uid(data)
        assert result is not None
        assert len(result) == 40

    def test_gen_checkpoint_uid_consistency(self):
        """测试相同数据生成的 UID 一致"""
        data = MetricsEventsCheckpoint(
            raw_id="test-raw-3",
            timestamp=1710000000000,
            file_path="src/main.py",
            kind="edit",
        )
        uid1 = gen_checkpoint_uid(data)
        uid2 = gen_checkpoint_uid(data)
        assert uid1 == uid2

    def test_gen_checkpoint_uid_different_fields(self):
        """测试不同字段值生成不同 UID"""
        data1 = MetricsEventsCheckpoint(
            raw_id="test-raw-4",
            timestamp=1710000000000,
            file_path="src/main.py",
            kind="edit",
        )
        data2 = MetricsEventsCheckpoint(
            raw_id="test-raw-5",
            timestamp=1710000000000,
            file_path="src/main.py",
            kind="create",
        )
        uid1 = gen_checkpoint_uid(data1)
        uid2 = gen_checkpoint_uid(data2)
        assert uid1 != uid2


class TestGenInstallHooksUid:
    """测试 gen_install_hooks_uid 函数"""

    def test_gen_install_hooks_uid_with_full_data(self):
        """测试包含所有字段的 install hooks 数据"""
        data = MetricsEventsInstallHooks(
            raw_id="test-raw-1",
            timestamp=1710000000000,
            tool_id="pre-commit",
            status="success",
            message="hooks installed successfully",
        )
        result = gen_install_hooks_uid(data)
        assert result is not None
        assert len(result) == 40  # sha1 长度

    def test_gen_install_hooks_uid_with_partial_data(self):
        """测试只包含部分字段的 install hooks 数据"""
        data = MetricsEventsInstallHooks(
            raw_id="test-raw-2",
            timestamp=1710000000000,
            tool_id="pre-commit",
        )
        result = gen_install_hooks_uid(data)
        assert result is not None
        assert len(result) == 40

    def test_gen_install_hooks_uid_consistency(self):
        """测试相同数据生成的 UID 一致"""
        data = MetricsEventsInstallHooks(
            raw_id="test-raw-3",
            timestamp=1710000000000,
            tool_id="pre-commit",
            status="success",
        )
        uid1 = gen_install_hooks_uid(data)
        uid2 = gen_install_hooks_uid(data)
        assert uid1 == uid2

    def test_gen_install_hooks_uid_different_timestamps(self):
        """测试不同时间戳生成不同 UID"""
        data1 = MetricsEventsInstallHooks(
            raw_id="test-raw-4",
            timestamp=1710000000000,
            tool_id="pre-commit",
        )
        data2 = MetricsEventsInstallHooks(
            raw_id="test-raw-5",
            timestamp=1710000001000,
            tool_id="pre-commit",
        )
        uid1 = gen_install_hooks_uid(data1)
        uid2 = gen_install_hooks_uid(data2)
        assert uid1 != uid2


class TestGenAgentUsageUid:
    """测试 gen_agent_usage_uid 函数"""

    def test_gen_agent_usage_uid_with_full_data(self):
        """测试包含所有字段的 agent usage 数据"""
        data = MetricsEventsAgentUsage(
            raw_id="test-raw-1",
            timestamp=1710000000000,
            repo_url="https://github.com/test/repo",
            author="alice",
            commit_sha="abc123",
            base_commit_sha="def456",
            branch="main",
            tool="claude",
            model="claude-3-5",
            prompt_id="prompt-123",
        )
        result = gen_agent_usage_uid(data)
        assert result is not None
        assert len(result) == 40  # sha1 长度

    def test_gen_agent_usage_uid_with_partial_data(self):
        """测试只包含部分字段的 agent usage 数据"""
        data = MetricsEventsAgentUsage(
            raw_id="test-raw-2",
            timestamp=1710000000000,
        )
        result = gen_agent_usage_uid(data)
        assert result is not None
        assert len(result) == 40

    def test_gen_agent_usage_uid_consistency(self):
        """测试相同数据生成的 UID 一致"""
        data = MetricsEventsAgentUsage(
            raw_id="test-raw-3",
            timestamp=1710000000000,
            tool="claude",
        )
        uid1 = gen_agent_usage_uid(data)
        uid2 = gen_agent_usage_uid(data)
        assert uid1 == uid2

    def test_gen_agent_usage_uid_different_models(self):
        """测试不同模型生成不同 UID"""
        data1 = MetricsEventsAgentUsage(
            raw_id="test-raw-4",
            timestamp=1710000000000,
            model="claude-3-5",
        )
        data2 = MetricsEventsAgentUsage(
            raw_id="test-raw-5",
            timestamp=1710000000000,
            model="claude-3-opus",
        )
        uid1 = gen_agent_usage_uid(data1)
        uid2 = gen_agent_usage_uid(data2)
        assert uid1 != uid2
