# Git Blame 统计实现细节

## 核心方法实现

### 1. Git 操作辅助方法

```python
# core/services/blame_stats_service.py (续)

def _get_head_commit(self, repo_path: str) -> str:
    """获取当前 HEAD commit SHA"""
    result = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()

def _get_current_branch(self, repo_path: str) -> str:
    """获取当前分支名"""
    result = subprocess.run(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()

def _get_tracked_files(self, repo_path: str) -> List[str]:
    """获取所有被 Git 跟踪的文件
    
    排除：
    - 二进制文件
    - .git 目录
    - 根据配置过滤的文件类型
    """
    result = subprocess.run(
        ['git', 'ls-files'],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    )
    
    all_files = result.stdout.strip().split('\n')
    
    # 应用文件过滤
    if self.config.get('blame_stats.file_filter.enabled'):
        mode = self.config.get('blame_stats.file_filter.mode', 'all')
        
        if mode == 'code_only':
            # 只统计代码文件
            code_extensions = {
                '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go',
                '.rs', '.cpp', '.c', '.h', '.hpp', '.cs', '.rb',
                '.php', '.swift', '.kt', '.scala', '.sh', '.sql'
            }
            return [f for f in all_files if any(f.endswith(ext) for ext in code_extensions)]
        
        elif mode == 'custom':
            # 自定义扩展名
            extensions = self.config.get('blame_stats.file_filter.extensions', [])
            return [f for f in all_files if any(f.endswith(ext) for ext in extensions)]
    
    return all_files
```

### 2. 保存统计结果

```python
def _save_stats(
    self,
    repo_id: str,
    stat_date: int,
    commit_sha: str,
    branch: str,
    repo_total: Dict,
    file_stats_list: List[Dict],
    contributor_stats: Dict
):
    """保存统计结果到数据库"""
    
    # 1. 保存仓库级统计
    ai_ratio = (repo_total['ai_lines'] / repo_total['total_lines'] * 100) if repo_total['total_lines'] > 0 else 0
    
    self.db.save_repo_blame_stats(
        repo_id=repo_id,
        stat_date=stat_date,
        commit_sha=commit_sha,
        branch=branch,
        total_lines=repo_total['total_lines'],
        ai_lines=repo_total['ai_lines'],
        non_ai_lines=repo_total['non_ai_lines'],
        ai_ratio=round(ai_ratio, 2),
        total_files=len(file_stats_list)
    )
    
    # 2. 保存文件级统计
    for file_stat in file_stats_list:
        file_ai_ratio = (file_stat['ai_lines'] / file_stat['total_lines'] * 100) if file_stat['total_lines'] > 0 else 0
        
        self.db.save_file_blame_stats(
            repo_id=repo_id,
            stat_date=stat_date,
            file_path=file_stat['file_path'],
            commit_sha=commit_sha,
            total_lines=file_stat['total_lines'],
            ai_lines=file_stat['ai_lines'],
            non_ai_lines=file_stat['non_ai_lines'],
            ai_ratio=round(file_ai_ratio, 2)
        )
        
        # 3. 保存文件贡献者统计
        for contributor, stats in file_stat['contributors'].items():
            contributor_id = self.db.get_or_create_contributor(
                name=contributor,
                email=None  # blame 输出中可以获取 email
            )
            
            self.db.save_file_contributor_stats(
                repo_id=repo_id,
                stat_date=stat_date,
                file_path=file_stat['file_path'],
                contributor_id=contributor_id,
                contributor_name=contributor,
                ai_lines=stats['ai'],
                non_ai_lines=stats['non_ai'],
                total_lines=stats['ai'] + stats['non_ai']
            )
    
    # 4. 保存仓库贡献者统计
    for contributor, stats in contributor_stats.items():
        contributor_id = self.db.get_or_create_contributor(
            name=contributor,
            email=None
        )
        
        self.db.save_repo_contributor_stats(
            repo_id=repo_id,
            stat_date=stat_date,
            contributor_id=contributor_id,
            contributor_name=contributor,
            ai_lines=stats['ai'],
            non_ai_lines=stats['non_ai'],
            total_lines=stats['ai'] + stats['non_ai']
        )
```

## 关键优化点

### 1. 批量查询 Git Notes

```python
# 错误做法：逐个查询
for line_num, line_info in blame_data.items():
    note = self.db.get_git_note(line_info['commit'])  # N 次查询

# 正确做法：批量查询
unique_commits = set(line['commit'] for line in blame_data.values())
notes_cache = self.db.get_git_notes_batch(unique_commits)  # 1 次查询
```

### 2. 缓存解析结果

```python
# 同一个 commit 的 Git Note 只解析一次
notes_cache = {}
for commit_sha in unique_commits:
    note_content = notes_dict.get(commit_sha)
    if note_content:
        attestations, prompts = self._parse_git_note_content(note_content)
        notes_cache[commit_sha] = (attestations, prompts)
```

### 3. 行号范围匹配优化

```python
def _line_in_ranges(self, line_num: int, ranges: List[Tuple[int, int]]) -> bool:
    """检查行号是否在范围内（优化版）"""
    for start, end in ranges:
        if start <= line_num <= end:
            return True
    return False
```
