"""Git Blame 统计服务"""

import json
import os
import subprocess
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from core.config.logging import Logger


@dataclass
class BlameLineResult:
    """单行 blame 分析结果"""

    line_num: int
    commit_sha: str
    author: str
    is_ai: bool


@dataclass
class FileBlameResult:
    """文件 blame 分析结果"""

    file_path: str
    total_lines: int
    ai_lines: int
    non_ai_lines: int
    commit_sha: str
    # 按贡献者统计
    contributor_stats: Dict[
        str, Dict[str, int]
    ]  # {contributor_id: {ai: n, non_ai: m, total: t}}


@dataclass
class RepoBlameResult:
    """仓库 blame 分析结果"""

    stat_date: int
    commit_sha: str
    branch: str
    total_lines: int
    ai_lines: int
    non_ai_lines: int
    total_files: int
    files_results: List[FileBlameResult]
    # 按贡献者统计
    contributor_stats: Dict[str, Dict[str, int]]


class BlameStatsService:
    """Blame 统计服务"""

    # 默认代码文件扩展名
    CODE_EXTENSIONS = [
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".php",
        ".rb",
        ".swift",
        ".kt",
        ".scala",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".sql",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".xml",
        ".html",
        ".css",
        ".scss",
        ".less",
        ".vue",
        ".svelte",
        ".md",
        ".txt",
        ".rst",
        ".asciidoc",
    ]

    def __init__(self, database):
        """
        初始化 Blame 统计服务

        Args:
            database: 数据库实例
        """
        self.logger = Logger.get_logger("services.blame_stats")
        self.database = database

    def analyze_repository(
        self,
        repo_url: str,
        repo_dir: str,
        stat_date: int,
        file_filter: Optional[Dict] = None,
    ) -> Optional[RepoBlameResult]:
        """
        分析整个仓库

        Args:
            repo_url: 仓库 URL
            repo_dir: 仓库目录
            stat_date: 统计日期
            file_filter: 文件过滤配置

        Returns:
            仓库分析结果
        """
        try:
            # 获取当前提交 SHA 和分支
            from core.services.git_clone_service import GitCloneService

            git_service = GitCloneService()

            commit_sha = git_service.get_current_commit_sha(repo_dir)
            branch = git_service.get_current_branch(repo_dir)

            if not commit_sha or not branch:
                self.logger.error("无法获取当前提交 SHA 或分支名称")
                return None

            self.logger.info(f"开始统计仓库: {repo_url}")
            self.logger.info(f"当前提交: {commit_sha}, 分支: {branch}")

            # 获取文件列表
            files = self._filter_files(repo_dir, file_filter)
            self.logger.info(f"待统计文件数量: {len(files)}")

            # 统计每个文件
            total_lines = 0
            total_ai_lines = 0
            total_non_ai_lines = 0
            files_results = []
            contributor_stats = {}

            for idx, file_path in enumerate(files, 1):
                if idx % 100 == 0:
                    self.logger.info(f"处理进度: {idx}/{len(files)}")

                result = self.analyze_file_blame(
                    repo_url, file_path, repo_dir, commit_sha
                )

                if result:
                    total_lines += result.total_lines
                    total_ai_lines += result.ai_lines
                    total_non_ai_lines += result.non_ai_lines
                    files_results.append(result)

                    # 合并贡献者统计
                    for contrib_id, stats in result.contributor_stats.items():
                        if contrib_id not in contributor_stats:
                            contributor_stats[contrib_id] = {
                                "ai_lines": 0,
                                "non_ai_lines": 0,
                                "total_lines": 0,
                            }
                        contributor_stats[contrib_id]["ai_lines"] += stats["ai_lines"]
                        contributor_stats[contrib_id]["non_ai_lines"] += stats[
                            "non_ai_lines"
                        ]
                        contributor_stats[contrib_id]["total_lines"] += stats[
                            "total_lines"
                        ]

            ai_ratio = (total_ai_lines / total_lines * 100) if total_lines > 0 else 0.0

            self.logger.info(
                f"统计完成: 总行数 {total_lines}, AI 行数 {total_ai_lines}, 非 AI 行数 {total_non_ai_lines}"
            )

            return RepoBlameResult(
                stat_date=stat_date,
                commit_sha=commit_sha,
                branch=branch,
                total_lines=total_lines,
                ai_lines=total_ai_lines,
                non_ai_lines=total_non_ai_lines,
                total_files=len(files_results),
                files_results=files_results,
                contributor_stats=contributor_stats,
            )

        except Exception as e:
            self.logger.error(f"仓库统计失败: {e}")
            return None

    def _preload_notes(self, repo_url: str, commit_sha: str, files: List[str]) -> Dict:
        """
        预加载所有文件的 notes 数据

        Args:
            repo_url: 仓库 URL
            commit_sha: 提交 SHA
            files: 文件列表

        Returns:
            notes 缓存字典 {file_path: {line_num: is_ai}}
        """
        from core.database.models import AuthorshipNotes

        # 从 notes 表加载当前提交的 notes
        with self.database.session_scope() as session:
            notes_list = (
                session.query(AuthorshipNotes)
                .filter(
                    AuthorshipNotes.repo_url == repo_url,
                    AuthorshipNotes.commit_sha == commit_sha,
                )
                .all()
            )

            # 解析 notes 内容，构建缓存
            cache = {}
            for note in notes_list:
                note_data = self._parse_authorship_log(note.note_content)
                cache.update(note_data)

            return cache

    def _parse_authorship_log(self, content: str) -> Dict:
        """
        解析 AuthorshipLog 内容

        Args:
            content: AuthorshipLog 内容

        Returns:
            {file_path: {line_num: is_ai}} 字典
        """
        # AuthorshipLog 格式示例：
        # file_path,line_num,is_ai
        # example.py,123,true
        # example.py,124,false

        result = {}
        try:
            lines = content.strip().split("\n")
            for line in lines:
                if not line or line.startswith("#"):
                    continue

                parts = line.split(",")
                if len(parts) >= 3:
                    file_path = parts[0].strip()
                    line_num = int(parts[1].strip())
                    is_ai = parts[2].strip().lower() == "true"

                    if file_path not in result:
                        result[file_path] = {}
                    result[file_path][line_num] = is_ai

        except Exception as e:
            self.logger.error(f"解析 AuthorshipLog 失败: {e}")

        return result

    def _parse_line_ranges(self, ranges_str: str) -> List[Tuple[int, int]]:
        ranges = []
        for part in ranges_str.split(","):
            part = part.strip()
            if not part:
                continue

            if "-" in part:
                start, end = map(int, part.split("-", 1))
                ranges.append((start, end))
            else:
                line_num = int(part)
                ranges.append((line_num, line_num))

        return ranges

    def _parse_git_note_content(self, note_content: str) -> Tuple[Dict, Dict]:
        lines = note_content.split("\n")

        try:
            divider_index = lines.index("---")
        except ValueError as exc:
            raise ValueError("Invalid AuthorshipLog: missing '---'") from exc

        file_attestations = {}
        current_file = None

        for line in lines[:divider_index]:
            if not line.strip():
                continue

            if not line.startswith("  "):
                current_file = line.strip().strip('"')
                file_attestations[current_file] = {}
                continue

            if current_file is None:
                continue

            parts = line.strip().split(" ", 1)
            if len(parts) != 2:
                continue

            prompt_hash, range_text = parts
            file_attestations[current_file][prompt_hash] = self._parse_line_ranges(
                range_text
            )

        json_content = "\n".join(lines[divider_index + 1 :]).strip()
        metadata = json.loads(json_content) if json_content else {}

        return file_attestations, metadata.get("prompts", {})

    def _is_ai_line(
        self,
        line_num: int,
        file_path: str,
        commit_sha: str,
        notes_cache: Dict[str, Tuple[Dict, Dict]],
    ) -> Tuple[bool, Optional[str]]:
        note_data = notes_cache.get(commit_sha)
        if not note_data:
            return False, None

        attestations, prompts = note_data
        file_attestations = attestations.get(file_path)
        if not file_attestations:
            return False, None

        for prompt_hash, ranges in file_attestations.items():
            for start, end in ranges:
                if start <= line_num <= end:
                    prompt_info = prompts.get(prompt_hash, {})
                    agent_id = prompt_info.get("agent_id", {})
                    return True, agent_id.get("tool", "unknown")

        return False, None

    def _filter_files(
        self, repo_dir: str, file_filter: Optional[Dict] = None
    ) -> List[str]:
        """
        根据配置过滤文件

        Args:
            repo_dir: 仓库目录
            file_filter: 文件过滤配置

        Returns:
            文件路径列表
        """
        from core.services.git_clone_service import GitCloneService

        git_service = GitCloneService()
        all_files = git_service.list_files(repo_dir)

        if not file_filter:
            file_filter = {"enabled": False, "mode": "code_only", "extensions": []}

        if not file_filter.get("enabled", False):
            # 默认只统计代码文件
            return [f for f in all_files if self._is_code_file(f)]

        mode = file_filter.get("mode", "code_only")

        if mode == "all":
            return all_files
        elif mode == "code_only":
            return [f for f in all_files if self._is_code_file(f)]
        elif mode == "custom":
            custom_extensions = file_filter.get("extensions", [])
            return [
                f
                for f in all_files
                if any(f.endswith(ext) for ext in custom_extensions)
            ]
        else:
            return [f for f in all_files if self._is_code_file(f)]

    def _is_code_file(self, file_path: str) -> bool:
        """
        判断是否为代码文件

        Args:
            file_path: 文件路径

        Returns:
            是否为代码文件
        """
        return any(file_path.endswith(ext) for ext in self.CODE_EXTENSIONS)

    def analyze_file_blame(
        self,
        repo_url: str,
        file_path: str,
        repo_dir: str,
        commit_sha: str,
        notes_cache: Optional[Dict[str, Tuple[Dict, Dict]]] = None,
        rel_path: Optional[str] = None,
    ) -> Optional[FileBlameResult]:
        """
        分析单个文件

        Args:
            repo_url: 仓库 URL
            file_path: 文件绝对路径
            repo_dir: 仓库目录
            commit_sha: 提交 SHA
            notes_cache: notes 缓存 {line_num: is_ai}
            rel_path: 相对路径（可选）

        Returns:
            文件分析结果
        """
        try:
            if rel_path is None:
                rel_path = os.path.relpath(file_path, repo_dir)

            blame_output = self._run_git_blame(repo_dir, rel_path)
            blame_data = self._parse_blame_porcelain(blame_output)

            if not blame_data:
                return None

            if notes_cache is None:
                notes_cache = {}
                notes_dict = {}
                if self.database and hasattr(self.database, "get_git_notes_batch"):
                    unique_commits = list(
                        {line["commit"] for line in blame_data.values()}
                    )
                    notes_dict = self.database.get_git_notes_batch(unique_commits)

                for blamed_commit, note_content in notes_dict.items():
                    try:
                        notes_cache[blamed_commit] = self._parse_git_note_content(
                            note_content
                        )
                    except Exception as exc:
                        self.logger.warning(
                            f"Failed to parse note for {blamed_commit}: {exc}"
                        )

            total_lines = len(blame_data)
            ai_lines = 0
            non_ai_lines = 0
            contributor_stats = {}

            for line_num, line_info in blame_data.items():
                is_ai, ai_author = self._is_ai_line(
                    line_num, rel_path, line_info["commit"], notes_cache
                )
                author = ai_author if is_ai else line_info["author"]

                if is_ai:
                    ai_lines += 1
                else:
                    non_ai_lines += 1

                if author not in contributor_stats:
                    contributor_stats[author] = {
                        "ai_lines": 0,
                        "non_ai_lines": 0,
                        "total_lines": 0,
                    }

                if is_ai:
                    contributor_stats[author]["ai_lines"] += 1
                else:
                    contributor_stats[author]["non_ai_lines"] += 1
                contributor_stats[author]["total_lines"] += 1

            return FileBlameResult(
                file_path=rel_path,
                total_lines=total_lines,
                ai_lines=ai_lines,
                non_ai_lines=non_ai_lines,
                commit_sha=commit_sha,
                contributor_stats=contributor_stats,
            )

        except subprocess.TimeoutExpired:
            self.logger.warning(f"分析文件超时: {rel_path}")
            return None
        except Exception as e:
            self.logger.error(f"分析文件失败: {rel_path}, 错误: {e}")
            return None

    def _run_git_blame(self, repo_dir: str, rel_path: str) -> str:
        result = subprocess.run(
            ["git", "blame", "--line-porcelain", rel_path],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"执行 git blame 失败: {rel_path}")
        return result.stdout

    def _parse_blame_porcelain(self, blame_output: str) -> Dict[int, Dict[str, str]]:
        lines = blame_output.split("\n")
        result = {}
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            parts = line.split()
            if len(parts) >= 3 and re.fullmatch(r"[0-9a-f]{6,40}", parts[0]):
                commit_sha = parts[0]
                final_line = int(parts[2])
                author = "Unknown"
                i += 1

                while i < len(lines) and not lines[i].startswith("\t"):
                    if lines[i].startswith("author "):
                        author = lines[i][7:]
                    i += 1

                if i < len(lines) and lines[i].startswith("\t"):
                    i += 1

                result[final_line] = {"commit": commit_sha, "author": author}
                continue

            i += 1

        return result

    def _parse_blame_output(self, output: str) -> List[BlameLineResult]:
        """
        解析 git blame --line-porcelain 输出

        Args:
            output: git blame 输出内容

        Returns:
            行分析结果列表
        """
        results = []
        lines = output.split("\n")

        i = 0
        line_num = 1

        while i < len(lines):
            line = lines[i]

            # git blame --line-porcelain 输出格式：
            # 40-byte hex SHA <line count> <lineno> <lineno>
            # author <author name>
            # author-mail <email>
            # author-time <timestamp>
            # ...
            # tab followed by the actual line

            if "\t" in line:
                # 实际代码行（以 tab 开头）
                # 跳过这一行并准备处理下一个 blame 块
                i += 1
                line_num += 1
                continue

            # 解析 SHA（40 个十六进制字符）
            sha_match = re.match(r"^([0-9a-f]{40})", line)
            if sha_match:
                commit_sha = sha_match.group(1)

                # 查找 author 行
                author = "Unknown"
                j = i + 1
                while j < len(lines):
                    if lines[j].startswith("author "):
                        author = lines[j][7:]  # 去掉 'author ' 前缀
                        break
                    if "\t" in lines[j]:
                        break
                    j += 1

                results.append(
                    BlameLineResult(
                        line_num=line_num,
                        commit_sha=commit_sha,
                        author=author,
                        is_ai=False,  # 稍后根据 notes 判断
                    )
                )

            i += 1

        return results

    def query_ai_lines_from_notes(
        self, repo_url: str, commit_sha: str, file_path: str, line_nums: List[int]
    ) -> List[bool]:
        """
        从 notes 查询多行的 AI 归属

        Args:
            repo_url: 仓库 URL
            commit_sha: 提交 SHA
            file_path: 文件路径
            line_nums: 行号列表

        Returns:
            是否为 AI 代码的列表
        """
        from core.database.models import AuthorshipNotes

        with self.database.session_scope() as session:
            notes = (
                session.query(AuthorshipNotes)
                .filter(
                    AuthorshipNotes.repo_url == repo_url,
                    AuthorshipNotes.commit_sha == commit_sha,
                )
                .first()
            )

            if not notes:
                return [False] * len(line_nums)

            # 解析 notes 内容
            note_data = self._parse_authorship_log(notes.note_content)
            file_lines = note_data.get(file_path, {})

            return [file_lines.get(num, False) for num in line_nums]
