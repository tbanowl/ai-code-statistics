# 设计文档修正建议

## 审查结论

✅ **数据来源正确** - Git Notes 从数据库获取（因 Codeup 限制）
✅ **表结构无需修改** - 保持高性能
❌ **统计逻辑需要修正** - 与 git-ai 实际实现不符

## 关键修正点

### 1. Git Note 格式理解

**实际格式（authorship/3.0.0）：**
```
src/main.py
  a1b2c3d 6-8,10-12
  e4f5g6h 16,21
---
{"prompts": {"a1b2c3d": {"agent_id": {"tool": "claude"}}}}
```

### 2. 统计逻辑修正

**核心流程：**
```
git blame → 获取每行 commit SHA
↓
批量查询数据库 → 获取 Git Notes
↓
解析 AuthorshipLog → 文本部分 + JSON 部分
↓
逐行匹配 → 检查行号是否在 line_ranges 中
↓
判断归属 → AI (agent_id.tool) 或 Human (author)
```

### 3. 需要修改的代码

**第 4.3 节方法签名：**
```python
# 修改前
def _parse_authorship_log(self, content: str) -> Dict

# 修改后
def _parse_git_note_content(self, note_content: str) -> Tuple[Dict, Dict]
```

**第 10.2 节步骤 3-4：**
```
3. 批量查询 git_notes 表获取内容
4. 解析 AuthorshipLog（按 '---' 分割）
5. 逐行匹配 line_ranges
```

## 完整实现参考

详见：
- `docs/blame-stats-code-examples.md` - 完整代码
- `docs/blame-stats-corrected-logic.md` - 详细流程
- `docs/blame-stats-summary.md` - 修正总结
