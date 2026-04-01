# Git Blame 统计逻辑修正实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修正 Git Blame 统计逻辑，使其符合 git-ai 的 authorship/3.0.0 格式标准

**Architecture:** 修改 BlameStatsService 解析 Git Note 的逻辑，正确处理文本+JSON 混合格式，实现批量查询优化和行号范围匹配

**Tech Stack:** Python 3.x, subprocess, json, typing

---

## Task 1: 实现 Git Note 解析核心方法

**Files:**
- Modify: `core/services/blame_stats_service.py`
- Test: `tests/services/test_blame_stats_service.py`

**Step 1: 编写 _parse_line_ranges 测试**

```python
# tests/services/test_blame_stats_service.py
import pytest
from core.services.blame_stats_service import BlameStatsService

def test_parse_line_ranges_single():
    """测试单行解析"""
    service = BlameStatsService(None, None, None)
    assert service._parse_line_ranges("16") == [(16, 16)]

def test_parse_line_ranges_range():
    """测试范围解析"""
    service = BlameStatsService(None, None, None)
    assert service._parse_line_ranges("6-8") == [(6, 8)]

def test_parse_line_ranges_multiple():
    """测试多个范围"""
    service = BlameStatsService(None, None, None)
    result = service._parse_line_ranges("6-8,10-12,16")
    assert result == [(6, 8), (10, 12), (16, 16)]
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/services/test_blame_stats_service.py::test_parse_line_ranges_single -v
```

预期: FAIL - AttributeError: 'BlameStatsService' object has no attribute '_parse_line_ranges'

**Step 3: 实现 _parse_line_ranges 方法**

```python
# core/services/blame_stats_service.py
from typing import List, Tuple

def _parse_line_ranges(self, ranges_str: str) -> List[Tuple[int, int]]:
    """解析行范围字符串
    
    Args:
        ranges_str: "6-8,10-12,16,21"
        
    Returns:
        [(6,8), (10,12), (16,16), (21,21)]
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
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/services/test_blame_stats_service.py -v
```

预期: PASS - 3 passed

**Step 5: 提交**

```bash
git add tests/services/test_blame_stats_service.py core/services/blame_stats_service.py
git commit -m "feat: add line ranges parser for git note format"
```

---

## Task 2: 实现 Git Note 内容解析

**Files:**
- Modify: `core/services/blame_stats_service.py`
- Test: `tests/services/test_blame_stats_service.py`

**Step 1: 编写 _parse_git_note_content 测试**

```python
# tests/services/test_blame_stats_service.py

def test_parse_git_note_content_basic():
    """测试基本 Git Note 解析"""
    service = BlameStatsService(None, None, None)
    note_content = """src/main.py
  a1b2c3d 6-8,10
---
{"prompts": {"a1b2c3d": {"agent_id": {"tool": "claude"}}}}"""
    
    attestations, prompts = service._parse_git_note_content(note_content)
    
    assert "src/main.py" in attestations
    assert "a1b2c3d" in attestations["src/main.py"]
    assert attestations["src/main.py"]["a1b2c3d"] == [(6, 8), (10, 10)]
    assert prompts["a1b2c3d"]["agent_id"]["tool"] == "claude"

def test_parse_git_note_content_multiple_files():
    """测试多文件 Git Note 解析"""
    service = BlameStatsService(None, None, None)
    note_content = """src/main.py
  a1b2c3d 1-5
src/utils.py
  e4f5g6h 10,15-20
---
{"prompts": {"a1b2c3d": {"agent_id": {"tool": "claude"}}, "e4f5g6h": {"agent_id": {"tool": "cursor"}}}}"""
    
    attestations, prompts = service._parse_git_note_content(note_content)
    
    assert len(attestations) == 2
    assert "src/main.py" in attestations
    assert "src/utils.py" in attestations
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/services/test_blame_stats_service.py::test_parse_git_note_content_basic -v
```

预期: FAIL - AttributeError

**Step 3: 实现 _parse_git_note_content 方法**

```python
# core/services/blame_stats_service.py
import json
from typing import Dict, Tuple

def _parse_git_note_content(self, note_content: str) -> Tuple[Dict, Dict]:
    """解析 Git Note 的 AuthorshipLog 格式
    
    Returns:
        (file_attestations, prompts_metadata)
    """
    lines = note_content.split('\n')
    
    # 找到分隔符
    try:
        divider_index = lines.index('---')
    except ValueError:
        raise ValueError("Invalid AuthorshipLog: missing '---'")
    
    # 解析上半部分：文件归因
    file_attestations = {}
    current_file = None
    
    for line in lines[:divider_index]:
        if not line.strip():
            continue
        
        if not line.startswith('  '):
            # 文件路径行
            current_file = line.strip().strip('"')
            file_attestations[current_file] = {}
        else:
            # 归因行
            parts = line.strip().split(' ', 1)
            if len(parts) == 2:
                prompt_hash = parts[0]
                ranges = self._parse_line_ranges(parts[1])
                file_attestations[current_file][prompt_hash] = ranges
    
    # 解析下半部分：JSON
    json_content = '\n'.join(lines[divider_index + 1:])
    metadata = json.loads(json_content)
    
    return file_attestations, metadata.get('prompts', {})
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/services/test_blame_stats_service.py::test_parse_git_note_content -v
```

预期: PASS

**Step 5: 提交**

```bash
git add tests/services/test_blame_stats_service.py core/services/blame_stats_service.py
git commit -m "feat: add git note content parser for authorship/3.0.0"
```

---

## Task 3: 实现 AI 行判断逻辑

**Files:**
- Modify: `core/services/blame_stats_service.py`
- Test: `tests/services/test_blame_stats_service.py`

**Step 1: 编写 _is_ai_line 测试**

```python
# tests/services/test_blame_stats_service.py

def test_is_ai_line_match():
    """测试 AI 行匹配"""
    service = BlameStatsService(None, None, None)
    
    notes_cache = {
        "abc123": (
            {"src/main.py": {"a1b2c3d": [(6, 8), (10, 12)]}},
            {"a1b2c3d": {"agent_id": {"tool": "claude"}}}
        )
    }
    
    is_ai, author = service._is_ai_line(7, "src/main.py", "abc123", notes_cache)
    assert is_ai is True
    assert author == "claude"

def test_is_ai_line_no_match():
    """测试非 AI 行"""
    service = BlameStatsService(None, None, None)
    
    notes_cache = {
        "abc123": (
            {"src/main.py": {"a1b2c3d": [(6, 8)]}},
            {"a1b2c3d": {"agent_id": {"tool": "claude"}}}
        )
    }
    
    is_ai, author = service._is_ai_line(15, "src/main.py", "abc123", notes_cache)
    assert is_ai is False
    assert author is None
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/services/test_blame_stats_service.py::test_is_ai_line -v
```

预期: FAIL

**Step 3: 实现 _is_ai_line 方法**

```python
# core/services/blame_stats_service.py
from typing import Optional

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
    
    for prompt_hash, ranges in attestations[file_path].items():
        for start, end in ranges:
            if start <= line_num <= end:
                prompt_info = prompts.get(prompt_hash, {})
                agent_id = prompt_info.get('agent_id', {})
                ai_author = agent_id.get('tool', 'unknown')
                return True, ai_author
    
    return False, None
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/services/test_blame_stats_service.py::test_is_ai_line -v
```

预期: PASS

**Step 5: 提交**

```bash
git add tests/services/test_blame_stats_service.py core/services/blame_stats_service.py
git commit -m "feat: add AI line detection logic"
```

---

## Task 4: 实现 git blame 解析

**Files:**
- Modify: `core/services/blame_stats_service.py`
- Test: `tests/services/test_blame_stats_service.py`

**Step 1: 编写 _parse_blame_porcelain 测试**

```python
def test_parse_blame_porcelain():
    service = BlameStatsService(None, None, None)
    blame_output = """abc123 1 1 1
author Alice
	line content"""
    result = service._parse_blame_porcelain(blame_output)
    assert result[1]['commit'] == 'abc123'
    assert result[1]['author'] == 'Alice'
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/services/test_blame_stats_service.py::test_parse_blame_porcelain -v
```

**Step 3: 实现 _parse_blame_porcelain**

```python
def _parse_blame_porcelain(self, blame_output: str) -> Dict[int, Dict]:
    lines = blame_output.split('\n')
    result = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        parts = line.split()
        if len(parts) >= 3:
            commit_sha = parts[0]
            final_line = int(parts[2])
            author = None
            i += 1
            while i < len(lines) and not lines[i].startswith('\t'):
                if lines[i].startswith('author '):
                    author = lines[i][7:]
                i += 1
            if i < len(lines) and lines[i].startswith('\t'):
                i += 1
            result[final_line] = {"commit": commit_sha, "author": author or "Unknown"}
        else:
            i += 1
    return result
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/services/test_blame_stats_service.py::test_parse_blame_porcelain -v
```

**Step 5: 提交**

```bash
git add tests/services/test_blame_stats_service.py core/services/blame_stats_service.py
git commit -m "feat: add git blame porcelain parser"
```

---

## Task 5: 实现数据库批量查询

**Files:**
- Modify: `core/database/blame_stats_db.py`
- Test: `tests/database/test_blame_stats_db.py`

**Step 1: 编写测试**

```python
def test_get_git_notes_batch_empty():
    db = BlameStatsDatabase(None)
    assert db.get_git_notes_batch([]) == {}
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/database/test_blame_stats_db.py -v
```

**Step 3: 实现方法**

```python
def get_git_notes_batch(self, commit_shas: List[str]) -> Dict[str, str]:
    if not commit_shas:
        return {}
    placeholders = ','.join(['?' for _ in commit_shas])
    query = f"SELECT commit_sha, note_content FROM git_notes WHERE commit_sha IN ({placeholders})"
    results = self.execute_query(query, commit_shas)
    return {row['commit_sha']: row['note_content'] for row in results}
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/database/test_blame_stats_db.py -v
```

**Step 5: 提交**

```bash
git add tests/database/test_blame_stats_db.py core/database/blame_stats_db.py
git commit -m "feat: add batch query for git notes"
```

---

## Task 6: 集成主方法 analyze_file_blame

**Files:**
- Modify: `core/services/blame_stats_service.py`
- Test: `tests/services/test_blame_stats_integration.py`

**Step 1: 编写集成测试**

```python
def test_analyze_file_blame_integration(mock_db, tmp_path):
    service = BlameStatsService(mock_db, None, None)
    # 准备测试数据
    mock_db.get_git_notes_batch.return_value = {
        'abc123': 'src/test.py\n  a1b2c3d 1-3\n---\n{"prompts": {"a1b2c3d": {"agent_id": {"tool": "claude"}}}}'
    }
    # 测试执行
    result = service.analyze_file_blame(str(tmp_path), 'src/test.py')
    assert 'total_lines' in result
    assert 'ai_lines' in result
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/services/test_blame_stats_integration.py -v
```

**Step 3: 实现主方法**

```python
def analyze_file_blame(self, repo_path: str, file_path: str) -> Dict:
    blame_output = self._run_git_blame(repo_path, file_path)
    blame_data = self._parse_blame_porcelain(blame_output)
    if not blame_data:
        return {"total_lines": 0, "ai_lines": 0, "non_ai_lines": 0, "contributors": {}}
    unique_commits = set(line['commit'] for line in blame_data.values())
    notes_dict = self.db.get_git_notes_batch(list(unique_commits))
    notes_cache = {}
    for commit_sha, note_content in notes_dict.items():
        try:
            attestations, prompts = self._parse_git_note_content(note_content)
            notes_cache[commit_sha] = (attestations, prompts)
        except Exception as e:
            self.logger.warning(f"Failed to parse note for {commit_sha}: {e}")
    stats = {"total_lines": len(blame_data), "ai_lines": 0, "non_ai_lines": 0, "contributors": {}}
    for line_num, line_info in blame_data.items():
        is_ai, ai_author = self._is_ai_line(line_num, file_path, line_info['commit'], notes_cache)
        author = ai_author if is_ai else line_info['author']
        if author not in stats['contributors']:
            stats['contributors'][author] = {"ai": 0, "non_ai": 0}
        if is_ai:
            stats['ai_lines'] += 1
            stats['contributors'][author]['ai'] += 1
        else:
            stats['non_ai_lines'] += 1
            stats['contributors'][author]['non_ai'] += 1
    return stats
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/services/test_blame_stats_integration.py -v
```

**Step 5: 提交**

```bash
git add tests/services/test_blame_stats_integration.py core/services/blame_stats_service.py
git commit -m "feat: integrate blame analysis with git note parsing"
```

---

## 执行选项

计划已保存到 `docs/plans/2026-03-31-git-blame-stats-correction.md`

**两种执行方式：**

1. **子代理驱动（当前会话）** - 每个任务派发新子代理，任务间审查，快速迭代
2. **并行会话（独立）** - 新会话使用 executing-plans，批量执行带检查点

选择哪种方式？
