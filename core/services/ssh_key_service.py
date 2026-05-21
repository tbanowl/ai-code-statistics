"""SSH Key 管理服务"""

import os
import tempfile
from typing import Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from base64 import b64encode, b64decode
from core.config.logging import Logger
from core.database.base import BaseDatabase, session_scope
from core.database.models import StatsRepository, gen_xid


class SshKeyService:
    """SSH Key 管理服务"""

    def __init__(self):
        """
        初始化 SSH Key 服务

        Args:
            database: 数据库实例
        """
        self.logger = Logger.get_logger("services.ssh_key")
        self.database = BaseDatabase()

        # 获取加密密钥
        self.encryption_key = self._get_encryption_key()
        self.fernet = Fernet(self.encryption_key)

    def _get_encryption_key(self) -> bytes:
        """
        获取加密密钥

        优先从环境变量获取，如果没有则使用默认密钥
        """
        env_key = os.environ.get("SSH_KEY_ENCRYPTION_KEY")
        if env_key:
            # 确保值是 32 字节（URL 安全的 base64 编码）
            return env_key.encode()
        # 默认密钥（生产环境应该从配置文件获取）
        # 确保是 32 字节用于 Fernet
        return b"kGg7mK8Pj3hNqV9wR2tYs5xCz6vL8mK3jP9hNqV9wR2="

    def add_ssh_key(self, key_name: str, public_key: str, private_key: str) -> Dict:
        """
        添加 SSH Key（API 上传）

        Args:
            key_name: Key 名称
            public_key: 公钥内容
            private_key: 私钥内容

        Returns:
            创建的 SSH Key 对象字典
        """
        from core.database.models import StatsSshKey
        import time

        # 加密私钥
        private_key_encrypted = self._encrypt_private_key(private_key)

        key_id = gen_xid()
        now = int(time.time() * 1000)

        with session_scope(self.database.engine) as session:
            ssh_key = StatsSshKey(
                id=key_id,
                key_name=key_name,
                public_key=public_key,
                private_key_encrypted=private_key_encrypted,
                created_at=now,
                updated_at=now,
            )
            session.add(ssh_key)
            session.flush()

            return {
                "id": ssh_key.id,
                "key_name": ssh_key.key_name,
                "public_key": ssh_key.public_key,
                "created_at": ssh_key.created_at,
            }

    def _encrypt_private_key(self, private_key: str) -> str:
        """
        加密私钥

        Args:
            private_key: 明文私钥

        Returns:
            加密后的私钥（base64 编码）
        """
        # 将字符串转换为字节
        key_bytes = private_key.encode("utf-8")
        # 使用 Fernet 加密
        encrypted = self.fernet.encrypt(key_bytes)
        # 返回 base64 编码的字符串
        return b64encode(encrypted).decode("utf-8")

    def _decrypt_private_key(self, private_key_encrypted: str) -> str:
        """
        解密私钥

        Args:
            private_key_encrypted: 加密的私钥（base64 编码）

        Returns:
            明文私钥
        """
        # 将 base64 字符串转换为字节
        encrypted_bytes = b64decode(private_key_encrypted.encode("utf-8"))
        # 使用 Fernet 解密
        decrypted = self.fernet.decrypt(encrypted_bytes)
        # 返回字符串
        return decrypted.decode("utf-8")

    def get_ssh_key(self, key_id: str) -> Optional[Dict]:
        """
        获取 SSH Key（不包含私钥）

        Args:
            key_id: Key ID

        Returns:
            SSH Key 对象字典（不包含私钥）
        """
        from core.database.models import StatsSshKey

        with session_scope(self.database.engine) as session:
            ssh_key = (
                session.query(StatsSshKey).filter(StatsSshKey.id == key_id).first()
            )
            if not ssh_key:
                return None

            return {
                "id": ssh_key.id,
                "key_name": ssh_key.key_name,
                "public_key": ssh_key.public_key,
                "created_at": ssh_key.created_at,
            }

    def get_ssh_key_private(self, key_id: str) -> Optional[Dict]:
        """
        获取 SSH Key（包含解密的私钥）

        Args:
            key_id: Key ID

        Returns:
            SSH Key 对象字典（包含私钥）
        """
        from core.database.models import StatsSshKey

        with session_scope(self.database.engine) as session:
            ssh_key = (
                session.query(StatsSshKey).filter(StatsSshKey.id == key_id).first()
            )
            if not ssh_key:
                return None

            # 解密私钥
            private_key = self._decrypt_private_key(ssh_key.private_key_encrypted)

            return {
                "id": ssh_key.id,
                "key_name": ssh_key.key_name,
                "public_key": ssh_key.public_key,
                "private_key": private_key,
            }

    def list_ssh_keys(self) -> list:
        """
        列出所有 SSH Keys（不包含私钥）

        Returns:
            SSH Key 对象列表
        """
        from core.database.models import StatsSshKey

        with session_scope(self.database.engine) as session:
            ssh_keys = session.query(StatsSshKey).all()
            return [
                {
                    "id": key.id,
                    "key_name": key.key_name,
                    "public_key": key.public_key,
                    "created_at": key.created_at,
                }
                for key in ssh_keys
            ]

    def delete_ssh_key(self, key_id: str) -> bool:
        """
        删除 SSH Key

        Args:
            key_id: Key ID

        Returns:
            是否成功删除
        """
        from core.database.models import StatsSshKey

        with session_scope(self.database.engine) as session:
            ssh_key = (
                session.query(StatsSshKey).filter(StatsSshKey.id == key_id).first()
            )
            if not ssh_key:
                return False

            session.delete(ssh_key)
            return True

    def load_default_ssh_key_from_config(self) -> Optional[Dict[str, str]]:
        """
        从配置文件加载默认 SSH Key

        Returns:
            SSH Key 信息（包含解密后的私钥）或 None
        """
        from core.config import load_config

        config = load_config()
        blame_stats_config = config.get("blame_stats", {})

        key_name = blame_stats_config.get("default_ssh_key_name")
        public_key = blame_stats_config.get("default_ssh_key_public")
        private_key = blame_stats_config.get("default_ssh_key_private")

        if not key_name or not private_key:
            return None

        return {
            "key_name": key_name,
            "public_key": public_key,
            "private_key": private_key,
        }

    def get_ssh_key_for_repo_url(self, repo_url: Optional[str]) -> Optional[Dict]:
        """
        获取仓库的 SSH Key

        优先级：仓库配置的 Key > 配置文件默认 Key

        Args:
            repo_url: 仓库 URL

        Returns:
            SSH Key 信息（包含私钥）
        """
        # 优先使用仓库配置的 Key
        if repo_url:
            # 这里应该根据 repo_url 查找对应的 SSH Key ID
            repo = self._get_repo_for_repo_url(repo_url)
            if repo:
                key = self.get_ssh_key_private(repo.ssh_key_id)
                if key:
                    return key

        # 其次使用配置文件默认 Key
        default_key = self.load_default_ssh_key_from_config()
        return default_key


    def get_ssh_key_for_repo(self, repo_ssh_key_id: Optional[str]) -> Optional[Dict]:
        """
        获取仓库的 SSH Key

        优先级：仓库配置的 Key > 配置文件默认 Key

        Args:
            repo_ssh_key_id: 仓库配置的 SSH Key ID

        Returns:
            SSH Key 信息（包含私钥）
        """
        # 优先使用仓库配置的 Key
        if repo_ssh_key_id:
            key = self.get_ssh_key_private(repo_ssh_key_id)
            if key:
                return key

        # 其次使用配置文件默认 Key
        default_key = self.load_default_ssh_key_from_config()
        return default_key

    def write_private_key_to_temp_file(self, private_key: str) -> str:
        """
        将私钥写入临时文件并设置权限

        Args:
            private_key: 私钥内容

        Returns:
            临时文件路径
        """
        # 创建临时文件
        fd, temp_path = tempfile.mkstemp()

        try:
            # 写入私钥
            with os.fdopen(fd, "w") as f:
                f.write(private_key)

            # 设置文件权限为 600（仅所有者可读写）
            os.chmod(temp_path, 0o600)

            return temp_path
        except Exception as e:
            # 如果出错，删除临时文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    def _get_repo_for_repo_url(self, repo_url: str) -> Optional[StatsRepository]:
        """
        根据仓库 URL 获取对应的 SSH Key ID

        这里应该实现根据 repo_url 查找对应的 SSH Key ID 的逻辑
        可能需要一个新的数据库表来存储 repo_url 和 ssh_key_id 的映射关系

        Args:
            repo_url: 仓库 URL

        Returns:
            SSH Key ID 或 None
        """
        
        with session_scope(self.database.engine) as session:
            repo = (
                session.query(StatsRepository)
                .filter(StatsRepository.repo_path == repo_url)
                .filter(StatsRepository.repo_stats_flag == 1)
                .one()
            )

            return repo            