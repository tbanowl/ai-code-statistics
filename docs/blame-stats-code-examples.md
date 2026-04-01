# Git Blame 统计代码实现示例

## 完整的 BlameStatsService 实现

```python
# core/services/blame_stats_service.py

import subprocess
import json
from typing import Dict, List, Tuple, Optional
from pathlib import Path

class BlameStatsService:
    """Blame 统计服务 - 符合 git-ai 逻辑"""
    
    def __init__(self, db, config, logger):
        self.db = db
        self.config = config
        self.logger = logger
    
    def analyze_file_blame(self, repo_path: str, file_path: str) -> Dict:
        """分析单个文件的 AI 代码归因
        
        核心逻辑：
        1. 执行 git blame 获取每行的 commit SHA
        2. 批量查询数据库获取 Git Notes
        3. 解析 AuthorshipLog 格式
        4. 逐行判断 AI 归属
        """
        # 1. 执行 git blame --line-porcelain
        blame_output = self._run_git_blame(repo_path, file_path)
        blame_data = self._parse_blame_porcelain(blame_output)
        
        if not blame_data:
            return {
                "total_lines": 0,
                "ai_lines": 0,
                "non_ai_lines": 0,
                "contributors": {}
            }
        
        # 2. 收集唯一的 commit SHA 并批量查询 Git Notes
        unique_commits = set(line['commit'] for line in blame_data.values())
        notes_dict = self.db.get_git_notes_batch(list(unique_commits))
        
        # 3. 解析所有 Git Notes
        notes_cache = {}
        for commit_sha, note_content in notes_dict.items():
            try:
                attestations, prompts = self._parse_git_note_content(note_content)
                notes_cache[commit_sha] = (attestations, prompts)
            except Exception as e:
                self.logger.warning(f"Failed to parse note for {commit_sha}: {e}")
                continue
        
        # 4. 逐行判断 AI 归属并统计
        stats = {
            "total_lines": len(blame_data),
            "ai_lines": 0,
            "non_ai_lines": 0,
            "contributors": {}
        }
        
        for line_num, line_info in blame_data.items():
            is_ai, ai_author = self._is_ai_line(
                line_num, file_path, line_info['commit'], notes_cache
            )
            
            if is_ai:
                stats['ai_lines'] += 1
                author = ai_author
            else:
                stats['non_ai_lines'] += 1
                author = line_info['author']
            
            # 按贡献者统计
            if author not in stats['contributors']:
                stats['contributors'][author] = {"ai": 0, "non_ai": 0}
            
            if is_ai:
                stats['contributors'][author]['ai'] += 1
            else:
                stats['contributors'][author]['non_ai'] += 1
        
        return stats
    
    def _run_git_blame(self, repo_path: str, file_path: str) -> str:
        """执行 git blame --line-porcelain"""
        result = subprocess.run(
            ['git', 'blame', '--line-porcelain', file_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    
    def _parse_blame_porcelain(self, blame_output: str) -> Dict[int, Dict]:
        """解析 git blame --line-porcelain 输出
        
        Returns:
            {line_num: {"commit": "abc123", "author": "Alice"}}
        """
        lines = blame_output.split('\n')
        result = {}
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # 第一行格式：<commit> <orig_line> <final_line> [<num_lines>]
            parts = line.split()
            if len(parts) >= 3:
                commit_sha = parts[0]
                final_line = int(parts[2])
                
                # 读取元数据
                author = None
                i += 1
                while i < len(lines) and not lines[i].startswith('\t'):
                    if lines[i].startswith('author '):
                        author = lines[i][7:]
                    i += 1
                
                # 跳过内容行
                if i < len(lines) and lines[i].startswith('\t'):
                    i += 1
                
                result[final_line] = {
                    "commit": commit_sha,
                    "author": author or "Unknown"
                }
            else:
                i += 1
        
        return result
    
    def _parse_git_note_content(self, note_content: str) -> Tuple[Dict, Dict]:
        """解析 Git Note 的 AuthorshipLog 格式
        
        Returns:
            (file_attestations, prompts_metadata)
            
        file_attestations = {
            "src/main.py": {
                "a1b2c3d": [(6, 8), (10, 12)],
                "e4f5g6h": [(16, 16), (21, 21)]
            }
        }
        
        prompts_metadata = {
            "a1b2c3d": {"agent_id": {"tool": "claude", ...}, ...}
        }
        """
        lines = note_content.split('\n')
        
        # 找到分隔符
        try:
            divider_index = lines.index('---')
        except ValueError:
            raise ValueError("Invalid AuthorshipLog format: missing '---' divider")
        
        # 解析上半部分：文件归因
        file_attestations = {}
        current_file = None
        
        for line in lines[:divider_index]:
            if not line.strip():
                continue
            
            if not line.startswith('  '):
                # 文件路径行（可能带引号）
                current_file = line.strip().strip('"')
                file_attestations[current_file] = {}
            else:
                # 归因行：  <hash> <ranges>
                parts = line.strip().split(' ', 1)
                if len(parts) != 2:
                    continue
                
                prompt_hash = parts[0]
                ranges_str = parts[1]
                ranges = self._parse_line_ranges(ranges_str)
                file_attestations[current_file][prompt_hash] = ranges
        
        # 解析下半部分：JSON metadata
        json_content = '\n'.join(lines[divider_index + 1:])
        metadata = json.loads(json_content)
        
        return file_attestations, metadata.get('prompts', {})
    
    def _parse_line_ranges(self, ranges_str: str) -> List[Tuple[int, int]]:
        """解析行范围字符串
        
        输入: "6-8,10-12,16,21,25"
        输出: [(6,8), (10,12), (16,16), (21,21), (25,25)]
        """
        ranges = []
        for part in ranges_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                ranges.append((start, end))
            else:
                line_num = int(part)
                ranges.append((line_num, line_num))
        return ranges
    
    def _is_ai_line(
        self, 
        line_num: int, 
        file_path: str, 
        commit_sha: str, 
        notes_cache: Dict
    ) -> Tuple[bool, Optional[str]]:
        """判断某行是否为 AI 生成
        
        Returns:
            (is_ai, ai_author)
        """
        if commit_sha not in notes_cache:
            return False, None
        
        attestations, prompts = notes_cache[commit_sha]
        
        if file_path not in attestations:
            return False, None
        
        # 检查行号是否在任何 prompt 的范围内
        for prompt_hash, ranges in attestations[file_path].items():
            for start, end in ranges:
                if start <= line_num <= end:
                    # 获取 AI 工具名称
                    prompt_info = prompts.get(prompt_hash, {})
                    agent_id = prompt_info.get('agent_id', {})
                    ai_author = agent_id.get('tool', 'unknown')
                    return True, ai_author
        
        return False, None
```
