# Git Blame 统计逻辑修正方案

> 基于 git-ai 实际实现的统计逻辑修正

## 一、审查结论

### ✅ 确认正确的部分

1. **数据来源** - Git Notes 从数据库 `git_notes` 表获取（因阿里云 Codeup 不支持推送自定义 refs）
2. **表结构** - 无需修改，直接存储原始 Git Note 内容以保持高性能
3. **整体架构** - SSH Key 管理、Git Clone 服务、定时任务设计合理

### ❌ 需要修正的核心问题

**统计逻辑与 git-ai 实际实现不符：**

1. **Git Note 格式理解错误**
   - 原设计假设：`{"file_path": {"session_id": [(start, end)]}}`
   - 实际格式：文本部分（文件归因）+ `---` 分隔符 + JSON 部分（metadata）

2. **统计流程缺少关键步骤**
   - 缺少 Git Note 的正确解析逻辑（文本格式解析）
   - 缺少行号范围匹配的详细实现
   - AI 作者识别错误（应使用 `agent_id.tool` 而非 `session_id`）

3. **数据结构理解偏差**
   - prompt_hash 是 7 位短哈希，不是 session_id
   - 行范围格式：`6-8,10-12,16,21` 而非数组

---

## 二、Git Note 格式详解

### 2.1 实际格式（authorship/3.0.0）

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

### 2.2 格式说明

**上半部分（文件归因）：**
- 文件路径（可能带引号，如果包含空格）
- 缩进 2 个空格 + prompt_hash（7 位）+ 空格 + 行范围
- 行范围格式：
  - 单行：`16`
  - 范围：`6-8` (包含 6, 7, 8)
  - 多个用逗号分隔：`6-8,10-12,16,21,25`

**分隔符：**
- 固定为 `---`

**下半部分（JSON metadata）：**
- `schema_version`: 固定为 `"authorship/3.0.0"`
- `prompts`: 字典，key 为 prompt_hash
- 每个 prompt 包含：
  - `agent_id.tool`: AI 工具名称（"claude", "cursor", "copilot" 等）
  - `agent_id.model`: 模型名称
  - `human_author`: 人类作者（指派任务的人）

---

## 三、修正后的统计流程

### 3.1 完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 克隆仓库到临时目录                                          │
│    git clone --depth 1 <repo_url>                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 获取所有被跟踪的文件列表                                    │
│    git ls-files                                              │
│    应用文件过滤（code_only / all / custom）                   │
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
│    unique_commits = set(line['commit'] for line in blame)   │
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
│    - 按 '---' 分割                                            │
│    - 上半部分：解析文件路径 + prompt_hash + 行范围            │
│    - 下半部分：解析 JSON metadata                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. 对每个文件的每一行判断 AI 归属                             │
│    for line_num, line_info in blame_data:                   │
│      commit = line_info['commit']                           │
│      if commit in notes_cache:                              │
│        attestations, prompts = notes_cache[commit]          │
│        if file_path in attestations:                        │
│          for prompt_hash, ranges in attestations[file]:     │
│            if line_num in ranges:                           │
│              → AI (agent_id.tool)                           │
│        else:                                                 │
│          → Human (git blame author)                         │
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

### 3.2 关键步骤说明

**步骤 3：git blame --line-porcelain**
- 输出格式：每行包含 commit SHA、原始行号、当前行号、作者等信息
- 需要解析获取：`commit_sha` 和 `author`

**步骤 6：解析 AuthorshipLog**
- 按 `---` 分割上下两部分
- 上半部分：逐行解析，识别文件路径和归因条目
- 下半部分：JSON.parse() 获取 prompts metadata

**步骤 7：行号匹配**
- 检查 `start <= line_num <= end`
- 支持单行（16,16）和范围（6,8）

---

## 四、核心代码实现

### 4.1 BlameStatsService 主方法

```python
# core/services/blame_stats_service.py

import subprocess
import json
from typing import Dict, List, Tuple, Optional

class BlameStatsService:
    """Blame 统计服务 - 符合 git-ai 逻辑"""
    
    def __init__(self, db, config, logger):
        self.db = db
        self.config = config
        self.logger = logger
    
    def analyze_file_blame(self, repo_path: str, file_path: str) -> Dict:
        """分析单个文件的 AI 代码归因
        
        Returns:
            {
                "total_lines": 100,
                "ai_lines": 45,
                "non_ai_lines": 55,
                "contributors": {
                    "Alice": {"ai": 0, "non_ai": 30},
                    "claude": {"ai": 45, "non_ai": 0}
                }
    }
    """
```

### 5.2 第 10.2 节 - Git Blame 实现

**修改前：**
```
1. 命令：git blame --line-porcelain <file>
2. 解析输出：获取每行的 commit SHA、作者信息
3. 查询 authorship_notes：根据 commit SHA + 文件路径 + 行号判断 AI 归属
4. 缓存优化：批量查询 notes，避免逐个查询
```

**修改后：**
```
1. 命令：git blame --line-porcelain <file>
2. 解析输出：获取每行的 commit SHA、作者信息
3. 批量查询 git_notes 表：获取所有唯一 commit 的 Git Note 内容
4. 解析 AuthorshipLog 格式：
   - 按 '---' 分割文本部分和 JSON 部分
   - 文本部分：解析文件路径 + prompt_hash + 行范围
   - JSON 部分：解析 prompts metadata
5. 逐行判断 AI 归属：
   - 获取该行的 commit SHA
   - 在该 commit 的 AuthorshipLog 中查找当前文件
   - 检查行号是否在任何 prompt_hash 的 line_ranges 中
   - 匹配成功 → AI (使用 agent_id.tool 作为作者)
   - 匹配失败 → Human (使用 git blame 的 author)
6. 缓存优化：同一 commit 的 Git Note 只解析一次
```

---

## 六、关键优化点

### 6.1 批量查询优化

```python
# ❌ 错误做法：逐个查询（N 次数据库查询）
for line_num, line_info in blame_data.items():
    note = self.db.get_git_note(line_info['commit'])

# ✅ 正确做法：批量查询（1 次数据库查询）
unique_commits = set(line['commit'] for line in blame_data.values())
notes_dict = self.db.get_git_notes_batch(unique_commits)
```

### 6.2 解析结果缓存

```python
# 同一个 commit 的 Git Note 只解析一次
notes_cache = {}
for commit_sha, note_content in notes_dict.items():
    attestations, prompts = self._parse_git_note_content(note_content)
    notes_cache[commit_sha] = (attestations, prompts)
```

### 6.3 行号范围匹配

```python
# 简单的数值比较，无需复杂算法
for start, end in ranges:
    if start <= line_num <= end:
        return True
```

---

## 七、验证清单

实现完成后，请验证以下要点：

- [ ] Git Note 格式解析正确（文本 + `---` + JSON）
- [ ] 行范围解析支持单行（`16`）和范围（`6-8`）
- [ ] 行范围解析支持多个范围（`6-8,10-12,16`）
- [ ] AI 作者使用 `agent_id.tool` 而非 `session_id`
- [ ] Human 作者使用 git blame 的 `author`
- [ ] 批量查询优化已实现（避免 N+1 查询）
- [ ] 解析结果缓存已实现（同一 commit 只解析一次）
- [ ] 错误处理完善（解析失败、文件不存在等）
- [ ] 文件路径带引号的情况正确处理
- [ ] 空行和格式异常的 Git Note 正确处理

---

## 八、测试建议

### 8.1 单元测试

```python
def test_parse_line_ranges():
    service = BlameStatsService(...)
    
    # 测试单行
    assert service._parse_line_ranges("16") == [(16, 16)]
    
    # 测试范围
    assert service._parse_line_ranges("6-8") == [(6, 8)]
    
    # 测试多个
    assert service._parse_line_ranges("6-8,10-12,16") == [(6, 8), (10, 12), (16, 16)]

def test_parse_git_note_content():
    service = BlameStatsService(...)
    note_content = """src/main.py
  a1b2c3d 6-8,10
---
{"prompts": {"a1b2c3d": {"agent_id": {"tool": "claude"}}}}"""
    
    attestations, prompts = service._parse_git_note_content(note_content)
    
    assert "src/main.py" in attestations
    assert "a1b2c3d" in attestations["src/main.py"]
    assert attestations["src/main.py"]["a1b2c3d"] == [(6, 8), (10, 10)]
    assert prompts["a1b2c3d"]["agent_id"]["tool"] == "claude"
```

### 8.2 集成测试

1. 准备测试仓库，包含 AI 生成的代码
2. 确保数据库中有对应的 Git Notes
3. 执行统计任务
4. 验证统计结果的准确性

---

## 九、总结

### 核心修正点

1. **Git Note 格式** - 文本部分 + `---` + JSON 部分
2. **行范围格式** - `6-8,10-12,16` 而非数组
3. **AI 作者识别** - `agent_id.tool` 而非 `session_id`
4. **统计流程** - 批量查询 → 解析 → 逐行匹配

### 实现要点

- 正确解析 AuthorshipLog 的两部分格式
- 批量查询和缓存优化
- 行号范围匹配逻辑
- 错误处理和边界情况

### 文档修改

- 第 4.3 节：方法签名和返回格式
- 第 10.2 节：统计步骤详细说明

---

**修正完成后，统计逻辑将与 git-ai 的 blame 命令完全一致。**


### 4.2 数据库查询方法

```python
# core/database/blame_stats_db.py

class BlameStatsDatabase(BaseDatabase):
    
    def get_git_notes_batch(self, commit_shas: List[str]) -> Dict[str, str]:
        """批量获取 Git Notes 内容
        
        Args:
            commit_shas: commit SHA 列表
            
        Returns:
            {commit_sha: note_content}
        """
        if not commit_shas:
            return {}
        
        placeholders = ','.join(['?' for _ in commit_shas])
        query = f"""
            SELECT commit_sha, note_content 
            FROM git_notes 
            WHERE commit_sha IN ({placeholders})
        """
        
        results = self.execute_query(query, commit_shas)
        return {row['commit_sha']: row['note_content'] for row in results}
```

---

## 五、设计文档需要修改的章节

### 5.1 第 4.3 节 - Blame 统计服务

**修改前：**
```python
def _parse_authorship_log(self, content: str) -> Dict:
    """解析 AuthorshipLog 内容
    
    返回格式: {
        "file_path": {
            "session_id": [(line_start, line_end), ...],
        }
    }
    """
```

**修改后：**
```python
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
        "a1b2c3d": {
            "agent_id": {"tool": "claude", "model": "..."},
            "human_author": "Alice <alice@example.com>"
        }
    }
    """
```

```
