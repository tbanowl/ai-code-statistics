"""Git Clone 服务（支持 SSH Key）"""
import os
import subprocess
import tempfile
import shutil
from typing import Optional
from core.config.logging import Logger


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
        # 使用 30 天作为默认值，平衡了数据完整性和克隆速度
        # 对于大多数统计场景，30 天的历史记录足够进行有意义的分析
        shallow_since: str = '30 days ago'
    ) -> bool:
        """
        使用指定 SSH Key 克隆仓库

        Args:
            repo_url: Git 仓库 URL
            private_key: SSH 私钥内容
            target_dir: 目标目录
            shallow_since: 浅克隆起始日期，支持以下格式：
                - 相对日期（推荐）: '30 days ago', '1 month ago', '2 weeks ago'
                - 绝对日期: '2026-03-20', '2026-01-01'
                默认为 '30 days ago'，自动适应时间推移

        Returns:
            是否成功克隆
        """
        temp_key_file = None
        try:
            # 将私钥写入临时文件
            temp_key_file = self._write_private_key_to_temp(private_key)

            # 创建 SSH 配置
            ssh_command = self._create_ssh_command(temp_key_file)

            # 设置环境变量
            env = os.environ.copy()
            env['GIT_SSH_COMMAND'] = ssh_command

            # 使用 shallow-since 替代 depth
            cmd = ['git', 'clone', '--shallow-since', shallow_since, repo_url, target_dir]

            self.logger.info(f"开始克隆仓库: {repo_url} (shallow-since: {shallow_since})")

            result = subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300  # 5 分钟超时
            )

            if result.returncode != 0:
                self.logger.error(f"克隆失败: {result.stderr}")
                return False

            self.logger.info(f"仓库克隆成功: {target_dir}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error("克隆超时")
            return False
        except Exception as e:
            self.logger.error(f"克隆过程中出错: {e}")
            return False
        finally:
            # 清理临时私钥文件
            if temp_key_file and os.path.exists(temp_key_file):
                os.unlink(temp_key_file)

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
            with os.fdopen(fd, 'w') as f:
                f.write(private_key)

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
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout.strip()

            return None
        except Exception as e:
            self.logger.error(f"获取提交 SHA 失败: {e}")
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
                timeout=10
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
                ['git', 'ls-files'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=30
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
                timeout=10
            )

            if result.returncode != 0:
                self.logger.error(f"列出分支失败: {result.stderr}")
                return []

            branches = result.stdout.strip().split('\n')
            branches = [b.strip() for b in branches if b.strip()]

            # 去除 origin/ 前缀
            branches = [b.replace('origin/', '') for b in branches if b.startswith('origin/')]

            # 过滤 HEAD
            branches = [b for b in branches if b != 'HEAD']

            return branches

        except Exception as e:
            self.logger.error(f"列出分支时出错: {e}")
            return []

    def checkout_branch(self, repo_dir: str, branch: str) -> bool:
        """
        切换到指定分支

        Args:
            repo_dir: 仓库目录
            branch: 分支名称

        Returns:
            是否成功切换
        """
        try:
            result = subprocess.run(
                ['git', 'checkout', branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                self.logger.error(f"切换分支失败: {result.stderr}")
                return False

            self.logger.info(f"成功切换到分支: {branch}")
            return True

        except Exception as e:
            self.logger.error(f"切换分支时出错: {e}")
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
            匹配的分支列表
        """
        import fnmatch

        matched = set()

        for config in branch_configs:
            pattern = config['branch_pattern']
            pattern_type = config['pattern_type']

            if pattern_type == 'special':
                if pattern == 'all':
                    # 返回所有分支
                    return all_branches
            elif pattern_type == 'exact':
                # 精确匹配
                if pattern in all_branches:
                    matched.add(pattern)
            elif pattern_type == 'wildcard':
                # 通配符匹配
                for branch in all_branches:
                    if fnmatch.fnmatch(branch, pattern):
                        matched.add(branch)

        return list(matched)

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
