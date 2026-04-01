# Git Blame 统计逻辑修正总结

## 一、核心修正点

### 1. Git Note 格式理解 ✅

**原设计文档误解：**
- 假设数据结构为简单的 `{"file_path": {"session_id": [ranges]}}`

**实际 git-ai 格式：**
```
文件路径
  prompt_hash 行范围
---
JSON metadata
```

### 2. 统计流程修正 ✅

**关键步骤：**
1. `git blame --line-porcelain` → 获取每行的 commit SHA
2. 批量查询数据库 → 获取 Git Notes 内容
3. 解析 AuthorshipLog → 分离文本部分和 JSON 部分
4. 逐行匹配 → 检查行号是否在 prompt 的 line_ranges 中
5. 判断归属 → AI (agent_id.tool) 或 Human (git author)

### 3. 数据来源确认 ✅

- Git Notes 存储在数据库的 `git_notes` 表（原始内容）
- 不需要修改表结构
- 统计时从数据库读取并解析

## 二、需要修改的设计文档章节

### 第 4.3 节 - Blame 统计服务

**修改前：**
```python
def _parse_authorship_log(self, content: str) -> Dict:
    返回格式: {
        "file_path": {
            "session_id": [(line_start, line_end), ...],
        }
    }
```

**修改后：**
```python
def _parse_git_note_content(self, note_content: str) -> Tuple[Dict, Dict]:
    """解析 Git Note 的 AuthorshipLog 格式
    
    Returns:
        (file_attestations, prompts_metadata)
    """
    # 1. 按 '---' 分割
    # 2. 上半部分解析文件归因
    # 3. 下半部分解析 JSON metadata
```

### 第 10.2 节 - Git Blame 实现

**修改前：**
```
3. 查询 authorship_notes：根据 commit SHA + 文件路径 + 行号判断 AI 归属
```

**修改后：**
```
3. 批量查询 git_notes 表获取 Git Note 内容
4. 解析 AuthorshipLog 格式（文本 + JSON）
5. 对每一行：
   - 获取该行的 commit SHA
   - 在该 commit 的 AuthorshipLog 中查找当前文件
   - 检查行号是否在任何 prompt_hash 的 line_ranges 中
   - 匹配成功 → AI (使用 agent_id.tool)
   - 匹配失败 → Human (使用 git blame 的 author)
```

## 三、关键代码片段

### 解析 Git Note

```python
def _parse_git_note_content(self, note_content: str):
    lines = note_content.split('\n')
    divider_index = lines.index('---')
    
    # 上半部分：文件归因
    file_attestations = {}
    current_file = None
    for line in lines[:divider_index]:
        if not line.startswith('  '):
            current_file = line.strip().strip('"')
            file_attestations[current_file] = {}
        else:
            hash, ranges_str = line.strip().split(' ', 1)
            file_attestations[current_file][hash] = parse_ranges(ranges_str)
    
    # 下半部分：JSON
    metadata = json.loads('\n'.join(lines[divider_index + 1:]))
    return file_attestations, metadata['prompts']
```

### 判断 AI 归属

```python
def _is_ai_line(self, line_num, file_path, commit_sha, notes_cache):
    if commit_sha not in notes_cache:
        return False, None
    
    attestations, prompts = notes_cache[commit_sha]
    
    if file_path in attestations:
        for prompt_hash, ranges in attestations[file_path].items():
            for start, end in ranges:
                if start <= line_num <= end:
                    ai_author = prompts[prompt_hash]['agent_id']['tool']
                    return True, ai_author
    
    return False, None
```

## 四、性能优化要点

1. **批量查询 Git Notes** - 避免 N+1 查询
2. **缓存解析结果** - 同一 commit 只解析一次
3. **行号范围匹配** - 简单的数值比较，无需复杂算法

## 五、验证清单

- [ ] Git Note 格式解析正确（文本 + JSON）
- [ ] 行范围解析支持单行和范围（`16` 和 `6-8`）
- [ ] AI 作者使用 `agent_id.tool` 而非 `session_id`
- [ ] Human 作者使用 git blame 的 `author`
- [ ] 批量查询优化已实现
- [ ] 错误处理完善（解析失败、文件不存在等）
