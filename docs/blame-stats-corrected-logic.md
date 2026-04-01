# Git Blame 统计逻辑修正方案

## 一、核心问题总结

原设计文档的主要问题：
1. ❌ 假设数据结构为 `{"file_path": {"session_id": [ranges]}}`
2. ✅ 实际结构为 Git Note 文本格式 + JSON metadata
3. ❌ 缺少 Git Note 解析逻辑
4. ✅ 需要正确解析 `authorship/3.0.0` 格式

## 二、修正后的完整流程

### 流程图

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 克隆仓库到临时目录                                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 获取所有被跟踪的文件列表                                    │
│    git ls-files                                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 对每个文件执行 git blame --line-porcelain                  │
│    获取每行的 commit SHA 和作者信息                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 收集所有唯一的 commit SHA                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 批量查询数据库获取 Git Notes                               │
│    SELECT commit_sha, note_content FROM git_notes           │
│    WHERE commit_sha IN (...)                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. 解析每个 Git Note 的 AuthorshipLog                        │
│    - 上半部分：文件路径 + prompt_hash + 行范围                │
│    - 分隔符：---                                              │
│    - 下半部分：JSON metadata (prompts 详情)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. 对每个文件的每一行判断 AI 归属                             │
│    - 获取该行的 commit SHA                                    │
│    - 在该 commit 的 AuthorshipLog 中查找当前文件             │
│    - 检查行号是否在任何 prompt_hash 的 line_ranges 中        │
│    - 如果在 → AI (使用 agent_id.tool 作为作者)               │
│    - 如果不在 → Human (使用 git blame 的 author)             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. 聚合统计结果                                               │
│    - 文件级：total_lines, ai_lines, non_ai_lines            │
│    - 仓库级：汇总所有文件                                     │
│    - 贡献者级：按 contributor 分组统计                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. 保存到数据库                                               │
│    - stats_blame_repo                                        │
│    - stats_blame_file                                        │
│    - stats_blame_repo_contributor                            │
│    - stats_blame_file_contributor                            │
└─────────────────────────────────────────────────────────────┘
```

## 三、Git Note 格式详解

### 示例 Git Note 内容

```
src/commands/blame.rs
  a1b2c3d 6-8,10-12
  e4f5g6h 16,21,25
src/main.rs
  a1b2c3d 1-5
---
{
  "schema_version": "authorship/3.0.0",
  "git_ai_version": "0.1.4",
  "base_commit_sha": "f4a8b2c...",
  "prompts": {
    "a1b2c3d": {
      "agent_id": {
        "tool": "claude",
        "id": "session-123",
        "model": "claude-sonnet-4-5"
      },
      "human_author": "Alice <alice@example.com>",
      "total_additions": 15,
      "total_deletions": 2,
      "accepted_lines": 13,
      "messages_url": "https://..."
    },
    "e4f5g6h": {
      "agent_id": {
        "tool": "cursor",
        "id": "session-456",
        "model": "gpt-4"
      },
      "human_author": "Bob <bob@example.com>",
      "total_additions": 8,
      "total_deletions": 0,
      "accepted_lines": 8,
      "messages_url": "https://..."
    }
  }
}
```

### 格式说明

1. **上半部分（文件归因）**
   - 文件路径（可能带引号，如果包含空格）
   - 缩进 2 个空格 + prompt_hash + 空格 + 行范围
   - 行范围格式：`6-8,10-12,16,21,25`
     - 单行：`16`
     - 范围：`6-8` (包含 6, 7, 8)
     - 多个用逗号分隔

2. **分隔符**
   - 固定为 `---`

3. **下半部分（JSON metadata）**
   - `schema_version`: 固定为 `"authorship/3.0.0"`
   - `prompts`: 字典，key 为 prompt_hash
   - 每个 prompt 包含：
     - `agent_id.tool`: AI 工具名称（"claude", "cursor", "copilot" 等）
     - `agent_id.model`: 模型名称
     - `human_author`: 人类作者（指派任务的人）

## 四、关键实现要点

### 1. 行范围解析

```python
def parse_line_ranges(ranges_str: str) -> List[Tuple[int, int]]:
    """解析行范围字符串
    
    输入: "6-8,10-12,16,21,25"
    输出: [(6,8), (10,12), (16,16), (21,21), (25,25)]
    """
    ranges = []
    for part in ranges_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            ranges.append((start, end))
        else:
            line_num = int(part)
            ranges.append((line_num, line_num))
    return ranges
```

### 2. 行号匹配

```python
def is_ai_line(line_num: int, file_path: str, commit_sha: str, notes_cache: Dict) -> Tuple[bool, Optional[str]]:
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
                ai_author = prompts[prompt_hash]['agent_id']['tool']
                return True, ai_author
    
    return False, None
```

### 3. 贡献者识别

```python
# AI 代码的贡献者
ai_author = prompt_info['agent_id']['tool']  # "claude", "cursor" 等

# 人类代码的贡献者
human_author = blame_line_info['author']  # Git blame 的 author
```
