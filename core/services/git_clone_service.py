"""Git Clone 服务（支持 SSH Key）"""
import os
import subprocess
import tempfile
import shutil
import fnmatch
from typing import Optional
from core.config.logging import Logger
from core.utils.repo_url import normalize_repo_url, restore_repo_url


class GitCloneService:
    """Git Clone 服务"""

    def __init__(self):
        """初始化 Git Clone 服务"""
        self.logger = Logger.get_logger('services.git_clone')

    def clone_with_ssh_key(
        self,
        repo_url: str,
        private_key: str,
        target_dir: str,
        depth: int = 1,
    ) -> bool:
        """
        使用指定 SSH Key 克隆仓库

        Args:
            repo_url: Git 仓库 URL
            private_key: SSH 私钥内容
            target_dir: 目标目录
            depth: 浅克隆深度，默认只克隆最新 1 层提交

        Returns:
            是否成功克隆
        """
        temp_key_file = None
        try:
            # 验证私钥格式
            if not self._validate_private_key_format(private_key):
                self.logger.error("SSH 私钥格式无效，必须包含标准的 BEGIN/END 标记")
                return False

            # 规范化私钥格式
            private_key = self._normalize_private_key(private_key)

            # 将私钥写入临时文件
            temp_key_file = self._write_private_key_to_temp(private_key)

            # 创建 SSH 配置
            ssh_command = self._create_ssh_command(temp_key_file)

            # 设置环境变量
            env = os.environ.copy()
            env['GIT_SSH_COMMAND'] = ssh_command

            # 将仓库地址转换为 SSH URL
            if repo_url.startswith('http://') or repo_url.startswith('https://'):
                # 遗留完整 URL：先归一化，再还原为 SSH
                normalized = normalize_repo_url(repo_url)
                # 遗留兼容：devops.cxmt.com 的 HTTP URL 无端口时注入 :8022
                if (normalized.startswith('devops.cxmt.com/')
                        and ':8022' not in normalized):
                    normalized = normalized.replace(
                        'devops.cxmt.com/', 'devops.cxmt.com:8022/', 1)
                repo_url = restore_repo_url(normalized, "ssh")
            elif not repo_url.startswith('ssh://') and not repo_url.startswith('git://'):
                # 无协议输入：可能是已归一化 host/path，也可能是 scp-style git@host:path.git。
                normalized = normalize_repo_url(repo_url)
                repo_url = restore_repo_url(normalized, "ssh")

            cmd = [
                'git',
                'clone',
                '--depth',
                str(depth),
                '--no-single-branch',
                repo_url,
                target_dir,
            ]

            self.logger.info(f"开始克隆仓库: {repo_url} (depth: {depth})")

            result = subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',  # 处理无法解码的字符
                timeout=300  # 5 分钟超时
            )

            if result.returncode != 0:
                self.logger.error(f"克隆失败: {result.stderr}\ncmd: {cmd}")
                return False

            self.logger.info(f"仓库克隆成功: {target_dir}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"克隆超时: {repo_url}")
            return False
        except Exception as e:
            self.logger.error(f"克隆过程中出错: {repo_url}", )
            return False
        finally:
            # 清理临时私钥文件
            if temp_key_file and os.path.exists(temp_key_file):
                os.unlink(temp_key_file)

    def _validate_private_key_format(self, private_key: str) -> bool:
        """
        验证私钥格式是否正确

        Args:
            private_key: 私钥内容

        Returns:
            格式是否有效
        """
        if not private_key or not private_key.strip():
            return False

        key_content = private_key.strip()
        # 检查是否包含标准的私钥头部
        has_header = any(header in key_content for header in [
            '-----BEGIN RSA PRIVATE KEY-----',
            '-----BEGIN OPENSSH PRIVATE KEY-----',
            '-----BEGIN EC PRIVATE KEY-----',
            '-----BEGIN DSA PRIVATE KEY-----',
            '-----BEGIN PRIVATE KEY-----',
            '-----BEGIN ED25519 PRIVATE KEY-----'
        ])
        # 检查是否包含标准的私钥尾部
        has_footer = any(footer in key_content for footer in [
            '-----END RSA PRIVATE KEY-----',
            '-----END OPENSSH PRIVATE KEY-----',
            '-----END EC PRIVATE KEY-----',
            '-----END DSA PRIVATE KEY-----',
            '-----END PRIVATE KEY-----',
            '-----END ED25519 PRIVATE KEY-----'
        ])

        return has_header and has_footer

    def _normalize_private_key(self, private_key: str) -> str:
        """
        规范化私钥格式，确保正确的换行符

        Args:
            private_key: 原始私钥内容

        Returns:
            规范化后的私钥
        """
        # 去除首尾空白
        key_content = private_key.strip()
        # 将 \\n 替换为实际换行符（处理从环境变量或配置文件读取的情况）
        key_content = key_content.replace('\\n', '\n')
        # 将 \r\n 替换为 \n
        key_content = key_content.replace('\r\n', '\n')

        # 确保头部前有换行（仅在需要时）
        if not key_content.startswith('\n'):
            key_content = '\n' + key_content

        # 确保尾部有换行
        if not key_content.endswith('\n'):
            key_content += '\n'

        return key_content[1:]  # 移除开头的换行符

    def _write_private_key_to_temp(self, private_key: str) -> str:
        """
        将私钥写入临时文件

        Args:
            private_key: 私钥内容

        Returns:
            临时文件路径
        """
        fd, temp_path = tempfile.mkstemp(prefix='ssh_key_')

        try:
            # 使用二进制模式写入私钥，避免编码问题
            with os.fdopen(fd, 'wb') as f:
                f.write(private_key.encode('utf-8'))

            # 设置文件权限为 600
            os.chmod(temp_path, 0o600)

            return temp_path
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    def _create_ssh_command(self, key_file_path: str) -> str:
        """
        创建 SSH 命令字符串

        Args:
            key_file_path: SSH 私钥文件路径

        Returns:
            SSH 命令字符串
        """
        return (
            f'ssh -i "{key_file_path}" '
            '-o StrictHostKeyChecking=no '
            '-o UserKnownHostsFile=/dev/null '
            '-o IdentitiesOnly=yes '
            '-o LogLevel=ERROR'
        )

    def get_current_commit_sha(self, repo_dir: str) -> Optional[str]:
        """
        获取仓库当前提交 SHA

        Args:
            repo_dir: 仓库目录

        Returns:
            提交 SHA 或 None
        """
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=100
            )

            if result.returncode == 0:
                return result.stdout.strip()

            return None
        except Exception as e:
            self.logger.error(f"获取提交 SHA 失败", e)
            return None

    def get_current_branch(self, repo_dir: str) -> Optional[str]:
        """
        获取仓库当前分支名称

        Args:
            repo_dir: 仓库目录

        Returns:
            分支名称或 None
        """
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=100
            )

            if result.returncode == 0:
                return result.stdout.strip()

            return None
        except Exception as e:
            self.logger.error(f"获取分支名称失败: {e}")
            return None

    def list_files(self, repo_dir: str, extensions: Optional[list] = None) -> list:
        """
        列出仓库中的文件

        Args:
            repo_dir: 仓库目录
            extensions: 文件扩展名过滤列表

        Returns:
            文件路径列表
        """
        try:
            # 获取所有已跟踪的文件
            result = subprocess.run(
                ['git', '-c', 'core.quotepath=false', 'ls-files'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300
            )

            if result.returncode != 0:
                self.logger.error(f"列出文件失败: {result.stderr}")
                return []

            files = result.stdout.split('\n')
            files = [f for f in files if f]  # 过滤空行

            # 使用相对路径
            files = [os.path.join(repo_dir, f) for f in files]

            # 按扩展名过滤
            if extensions:
                files = [
                    f for f in files
                    if any(f.endswith(ext) for ext in extensions)
                ]

            return files

        except Exception as e:
            self.logger.error(f"列出文件时出错: {e}")
            return []

    def list_branches(self, repo_dir: str) -> list:
        """
        列出仓库所有远程分支

        Args:
            repo_dir: 仓库目录

        Returns:
            分支名称列表（去除 origin/ 前缀）
        """
        try:
            result = subprocess.run(
                ['git', 'branch', '-r', '--format=%(refname:short)'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60
            )
            if result.returncode != 0:
                self.logger.error(f"列出分支失败: {result.stderr}")
                return []

            branches = result.stdout.strip().split('\n')
            branches = [b.strip() for b in branches if b.strip()]

            # 去除 origin/ 前缀（只移除前缀，不是替换所有出现）
            branches = [b.removeprefix('origin/') for b in branches if b.startswith('origin/')]

            # 过滤 HEAD
            branches = [b for b in branches if b != 'HEAD']

            return branches

        except Exception as e:
            self.logger.error(f"列出分支时出错", e)
            return []

    def checkout_branch(self, repo_dir: str, branch: str) -> bool:
        """
        切换到指定分支（支持浅克隆场景）

        Args:
            repo_dir: 仓库目录
            branch: 分支名称

        Returns:
            是否成功切换
        """
        try:
            # 先尝试直接切换（如果本地分支已存在）
            result = subprocess.run(
                ['git', 'checkout', branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60
            )

            if result.returncode == 0:
                self.logger.info(f"成功切换到分支: {branch}")
                return True

            # 如果失败，尝试从远程分支创建本地分支（浅克隆场景）
            self.logger.debug(f"直接切换失败，尝试从远程分支创建: {branch}")
            result = subprocess.run(
                ['git', 'checkout', '-b', branch, f'origin/{branch}'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30
            )

            if result.returncode != 0:
                self.logger.error(f"切换分支失败: {result.stderr}")
                return False

            self.logger.info(f"成功切换到分支: {branch}")
            return True

        except Exception as e:
            self.logger.error(f"切换分支时出错", e)
            return False

    def match_branches(
        self,
        all_branches: list,
        branch_configs: list
    ) -> list:
        """
        根据配置匹配分支

        Args:
            all_branches: 所有分支列表
            branch_configs: 分支配置列表

        Returns:
            匹配的分支列表（已排序）
        """
        matched = set()

        for config in branch_configs:
            # 输入验证：检查必需的键是否存在
            if 'branch_pattern' not in config:
                self.logger.warning(f"分支配置缺少 'branch_pattern' 键，跳过: {config}")
                continue
            if 'pattern_type' not in config:
                self.logger.warning(f"分支配置缺少 'pattern_type' 键，跳过: {config}")
                continue

            pattern = config['branch_pattern']
            pattern_type = config['pattern_type']

            if pattern_type == 'special':
                if pattern == 'all':
                    # 返回所有分支（已排序）
                    return sorted(all_branches)
            elif pattern_type == 'exact':
                # 精确匹配
                if pattern in all_branches:
                    matched.add(pattern)
            elif pattern_type == 'wildcard':
                # 通配符匹配
                for branch in all_branches:
                    if fnmatch.fnmatch(branch, pattern):
                        matched.add(branch)
            else:
                # 未知的 pattern_type
                self.logger.warning(f"未知的 pattern_type: {pattern_type}，跳过配置: {config}")

        return sorted(list(matched))

    def cleanup_temp_dir(self, temp_dir: str) -> None:
        """
        清理临时目录

        Args:
            temp_dir: 临时目录路径
        """
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                self.logger.info(f"清理临时目录: {temp_dir}")
            except Exception as e:
                self.logger.error(f"清理临时目录失败: {e}")
