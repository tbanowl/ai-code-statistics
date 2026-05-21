# 仓库地址归一化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 所有写入数据库的 repo_url / repo_path 统一归一化为 `host/path` 格式，并提供还原函数用于 git clone 等场景。

**Architecture:** 新建 `core/utils/repo_url.py` 提供两个纯函数 `normalize_repo_url()` 和 `restore_repo_url()`。在 6 个写入入口调用归一化，在 2 个 git 操作入口调用还原。

**Tech Stack:** Python 3.10+, SQLAlchemy, pytest

**Design Spec:** `docs/superpowers/specs/2026-05-21-repo-url-normalization-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `core/utils/repo_url.py` | 归一化 + 还原两个纯函数 |
| Create | `tests/unit/test_utils/test_repo_url.py` | 新函数单元测试 |
| Modify | `core/services/metrics_service.py` | 入口 1: Committed/AgentUsage repo_url 归一化 |
| Modify | `core/scheduler/tasks/metrics_event_processor_task.py` | 入口 2: 事件处理 repo_path 归一化 |
| Modify | `core/services/codeup_payload_normalizer.py` | 入口 3: Webhook payload repo_url 归一化 |
| Modify | `core/services/notes_service.py` | 入口 4: Notes 服务 repo_url 归一化 |
| Modify | `core/database/stats_db.py` | 入口 5: 替换 `_normalize_repo_path` 为 `normalize_repo_url` |
| Modify | `core/scheduler/tasks/daily_aggregation_task.py` | 入口 6: 聚合任务 repo_path 归一化 |
| Modify | `core/services/codeup_git_service.py` | 还原点 1: `_repo_url_for_auth` 还原后再做 SSH 转换 |
| Modify | `core/services/git_clone_service.py` | 还原点 2: `clone_with_ssh_key` 还原后再克隆 |

---

### Task 1: 实现归一化与还原函数 + 单元测试

**Files:**
- Create: `core/utils/repo_url.py`
- Create: `tests/unit/test_utils/test_repo_url.py`

- [ ] **Step 1: 创建归一化函数文件**

创建 `core/utils/repo_url.py`：

```python
"""仓库地址归一化与还原工具函数。"""

from __future__ import annotations

_UNKNOWN = "未知仓库"


def normalize_repo_url(raw: str | None) -> str:
    """将任意 Git URL 归一化为 host/path 格式。

    规则（按顺序）：
    1. None / 空白 → "未知仓库"
    2. 去除协议前缀：https://, http://, ssh://, git://, file://
    3. 去除 git@ 前缀，将第一个 : 替换为 /（处理 git@host:path 格式）
    4. 去除末尾 .git（仅当以 .git 结尾时）
    5. 去除首尾空白和斜杠
    """
    value = (raw or "").strip()
    if not value:
        return _UNKNOWN

    # 去除协议前缀
    for prefix in ("https://", "http://", "ssh://", "git://", "file://"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break

    # 去除 git@ 前缀，将第一个 : 替换为 /
    if value.startswith("git@"):
        value = value[4:]
        colon_pos = value.find(":")
        if colon_pos != -1:
            value = value[:colon_pos] + "/" + value[colon_pos + 1:]

    # 去除末尾 .git
    if value.endswith(".git"):
        value = value[:-4]

    # 去除首尾斜杠
    value = value.strip("/")

    return value or _UNKNOWN


def restore_repo_url(normalized: str, protocol: str = "ssh") -> str:
    """将归一化地址还原为完整 Git URL。

    Args:
        normalized: 归一化后的地址（如 codeup.aliyun.com/org/repo）
        protocol: 目标协议 - "ssh"（默认）, "https", "http", "git"

    Returns:
        完整 Git URL
    """
    if not normalized or normalized == _UNKNOWN:
        return normalized or ""

    if protocol == "ssh":
        return f"ssh://git@{normalized}.git"
    elif protocol == "https":
        return f"https://{normalized}.git"
    elif protocol == "http":
        return f"http://{normalized}.git"
    elif protocol == "git":
        return f"git://{normalized}.git"
    else:
        return f"ssh://git@{normalized}.git"
```

- [ ] **Step 2: 创建单元测试文件**

创建 `tests/unit/test_utils/test_repo_url.py`：

```python
"""repo_url 工具函数单元测试"""

import pytest
from core.utils.repo_url import normalize_repo_url, restore_repo_url


class TestNormalizeRepoUrl:
    """normalize_repo_url 测试"""

    def test_https_url(self):
        assert normalize_repo_url("https://codeup.aliyun.com/org/repo.git") == "codeup.aliyun.com/org/repo"

    def test_http_url(self):
        assert normalize_repo_url("http://codeup.aliyun.com/org/repo.git") == "codeup.aliyun.com/org/repo"

    def test_ssh_url(self):
        assert normalize_repo_url("ssh://git@codeup.aliyun.com/org/repo.git") == "codeup.aliyun.com/org/repo"

    def test_git_at_url(self):
        assert normalize_repo_url("git@codeup.aliyun.com:org/repo.git") == "codeup.aliyun.com/org/repo"

    def test_git_protocol_url(self):
        assert normalize_repo_url("git://codeup.aliyun.com/org/repo.git") == "codeup.aliyun.com/org/repo"

    def test_url_with_port(self):
        assert normalize_repo_url("http://devops.cxmt.com:8022/group/project.git") == "devops.cxmt.com:8022/group/project"

    def test_ssh_url_with_port(self):
        assert normalize_repo_url("ssh://git@devops.cxmt.com:8022/group/project.git") == "devops.cxmt.com:8022/group/project"

    def test_already_normalized(self):
        assert normalize_repo_url("org/repo") == "org/repo"

    def test_none_input(self):
        assert normalize_repo_url(None) == "未知仓库"

    def test_empty_string(self):
        assert normalize_repo_url("") == "未知仓库"

    def test_whitespace_only(self):
        assert normalize_repo_url("   ") == "未知仓库"

    def test_trailing_slash(self):
        assert normalize_repo_url("https://codeup.aliyun.com/org/repo.git/") == "codeup.aliyun.com/org/repo"

    def test_no_git_suffix(self):
        assert normalize_repo_url("https://codeup.aliyun.com/org/repo") == "codeup.aliyun.com/org/repo"

    def test_file_protocol(self):
        assert normalize_repo_url("file:///local/path/repo.git") == "local/path/repo"

    def test_url_with_spaces(self):
        assert normalize_repo_url("  https://codeup.aliyun.com/org/repo.git  ") == "codeup.aliyun.com/org/repo"

    def test_host_only_no_path(self):
        assert normalize_repo_url("https://codeup.aliyun.com") == "codeup.aliyun.com"


class TestRestoreRepoUrl:
    """restore_repo_url 测试"""

    def test_ssh(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo", "ssh") == "ssh://git@codeup.aliyun.com/org/repo.git"

    def test_https(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo", "https") == "https://codeup.aliyun.com/org/repo.git"

    def test_http(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo", "http") == "http://codeup.aliyun.com/org/repo.git"

    def test_git(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo", "git") == "git://codeup.aliyun.com/org/repo.git"

    def test_default_protocol_is_ssh(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo") == "ssh://git@codeup.aliyun.com/org/repo.git"

    def test_with_port(self):
        assert restore_repo_url("devops.cxmt.com:8022/group/project", "ssh") == "ssh://git@devops.cxmt.com:8022/group/project.git"

    def test_unknown_repo(self):
        assert restore_repo_url("未知仓库", "ssh") == "未知仓库"

    def test_empty_string(self):
        assert restore_repo_url("", "ssh") == ""

    def test_unknown_protocol_fallback_ssh(self):
        assert restore_repo_url("codeup.aliyun.com/org/repo", "unknown") == "ssh://git@codeup.aliyun.com/org/repo.git"


class TestRoundTrip:
    """往返测试：restore(normalize(x)) 应还原为可用 URL"""

    @pytest.mark.parametrize("raw_url,protocol", [
        ("https://codeup.aliyun.com/org/repo.git", "https"),
        ("http://codeup.aliyun.com/org/repo.git", "http"),
        ("ssh://git@codeup.aliyun.com/org/repo.git", "ssh"),
        ("git@codeup.aliyun.com:org/repo.git", "ssh"),
        ("http://devops.cxmt.com:8022/group/project.git", "http"),
    ])
    def test_round_trip(self, raw_url, protocol):
        normalized = normalize_repo_url(raw_url)
        restored = restore_repo_url(normalized, protocol)
        # 还原后的 URL 应以正确协议开头
        assert restored.startswith(f"{protocol}://")
        assert restored.endswith(".git")
```

- [ ] **Step 3: 运行测试验证通过**

Run: `cd /Users/neptune/deepDark/banz/dk/git-ai-code-metrics && python -m pytest tests/unit/test_utils/test_repo_url.py -v`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add core/utils/repo_url.py tests/unit/test_utils/test_repo_url.py
git commit -m "feat: add normalize_repo_url and restore_repo_url utility functions"
```

---

### Task 2: 修改 metrics_service.py（入口 1）

**Files:**
- Modify: `core/services/metrics_service.py`

- [ ] **Step 1: 添加 import**

在 `core/services/metrics_service.py` 文件顶部添加：

```python
from core.utils.repo_url import normalize_repo_url
```

- [ ] **Step 2: 归一化 Committed 事件的 repo_url（约 L81）**

将：
```python
                repo_url= self._get_string(attrs, "1"),
```
改为：
```python
                repo_url= normalize_repo_url(self._get_string(attrs, "1")),
```

- [ ] **Step 3: 归一化 AgentUsage 事件的 repo_url（约 L102）**

将：
```python
                repo_url = self._get_string(attrs, "1"),
```
改为：
```python
                repo_url = normalize_repo_url(self._get_string(attrs, "1")),
```

- [ ] **Step 4: 运行 metrics 相关测试**

Run: `python -m pytest tests/ -k "metrics" -v --ignore=tests/integration`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add core/services/metrics_service.py
git commit -m "feat: normalize repo_url in metrics service (Committed + AgentUsage)"
```

---

### Task 3: 修改 metrics_event_processor_task.py（入口 2）

**Files:**
- Modify: `core/scheduler/tasks/metrics_event_processor_task.py`

- [ ] **Step 1: 添加 import**

在文件顶部（约 L5 附近）添加：

```python
from core.utils.repo_url import normalize_repo_url
```

- [ ] **Step 2: 归一化 repo_path（约 L44）**

将：
```python
            repo_path = attrs.get("1") or ""
```
改为：
```python
            repo_path = normalize_repo_url(attrs.get("1"))
```

- [ ] **Step 3: 运行事件处理器测试**

Run: `python -m pytest tests/test_metrics_event_processor_task.py tests/unit/test_scheduler/test_stats_task.py -v`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add core/scheduler/tasks/metrics_event_processor_task.py
git commit -m "feat: normalize repo_path in metrics event processor task"
```

---

### Task 4: 修改 codeup_payload_normalizer.py（入口 3）

**Files:**
- Modify: `core/services/codeup_payload_normalizer.py`

- [ ] **Step 1: 添加 import**

在文件顶部添加：

```python
from core.utils.repo_url import normalize_repo_url
```

- [ ] **Step 2: 归一化 normalizer 输出的 repo_url（约 L51）**

将 `normalize` 方法中构造 `NormalizedCodeupMergeEvent` 的 `repo_url` 参数从：

```python
            repo_url=self._first_string(
                repository.get("git_http_url"),
                repository.get("http_url"),
                repository.get("url"),
                project_repository.get("git_http_url"),
                project_repository.get("http_url"),
                project_repository.get("url"),
                project.get("git_http_url"),
                project.get("git_ssh_url"),
            ),
```
改为：
```python
            repo_url=normalize_repo_url(self._first_string(
                repository.get("git_http_url"),
                repository.get("http_url"),
                repository.get("url"),
                project_repository.get("git_http_url"),
                project_repository.get("http_url"),
                project_repository.get("url"),
                project.get("git_http_url"),
                project.get("git_ssh_url"),
            )),
```

- [ ] **Step 3: 更新 test_codeup_payload_normalizer.py 中的断言**

打开 `tests/unit/test_services/test_codeup_payload_normalizer.py`。

**`test_normalize_extracts_repo_url_from_repository`（约 L27）：** 断言值从 `"https://codeup.aliyun.com/org/repo.git"` 改为 `"codeup.aliyun.com/org/repo"`：

```python
assert event.repo_url == "codeup.aliyun.com/org/repo"
```

**`test_normalize_extracts_repo_url_from_project_repository`（约 L54）：** 断言值从 `"https://codeup.aliyun.com/org/legacy.git"` 改为 `"codeup.aliyun.com/org/legacy"`：

```python
assert event.repo_url == "codeup.aliyun.com/org/legacy"
```

**`test_missing_repo_url_is_recorded_without_guessing`（约 L70）：** 此测试断言 `repo_url is None`，`normalize_repo_url(None)` 返回 `"未知仓库"` 而非 `None`。需将断言改为：

```python
assert event.repo_url == "未知仓库"
```

- [ ] **Step 4: 更新 test_codeup_merge_event_classifier.py 中的测试数据**

打开 `tests/unit/test_services/test_codeup_merge_event_classifier.py`。

在 `_event` 辅助函数中（约 L7），`repo_url` 的默认值为完整 URL。将测试数据改为归一化后的格式：

将：
```python
    "repo_url": "https://codeup.aliyun.com/org/repo.git",
```
改为：
```python
    "repo_url": "codeup.aliyun.com/org/repo",
```

同时检查 `test_classify_returns_invalid_when_repo_url_is_none`（约 L45），此测试传入 `repo_url=None`。由于 normalizer 现在会归一化 None 为 `"未知仓库"`，classifier 的 `_event` 辅助函数直接构造 `NormalizedCodeupMergeEvent`，因此仍可直接传 `None`，无需修改此测试。

- [ ] **Step 5: 更新 test_codeup_webhook_service.py 中的断言**

打开 `tests/unit/test_services/test_codeup_webhook_service.py`。

**`test_enqueue_merge_event_creates_task`（约 L77）：** 断言值从完整 URL 改为归一化格式：

```python
assert task.repo_url == "codeup.aliyun.com/org/repo"
```

**`test_enqueue_normalizes_payload`（约 L99）：** 同上：

```python
assert normalized["repo_url"] == "codeup.aliyun.com/org/repo"
```

**`test_missing_repo_url_raises_invalid_payload`（约 L128）：** 此测试验证缺少 repo_url 时抛异常。由于 normalizer 现在将 `None` 归一化为 `"未知仓库"` 而非 `None`，需修改测试 payload 使 `repository` 和 `project` 都不包含任何 URL 字段，然后验证 classifier 能识别为 invalid（无 repo_url 不再是 None，而是 `"未知仓库"`，classifier 的 `if not event.repo_url` 检查将失败）。

需要检查 `codeup_merge_event_classifier.py` 中的逻辑是否依赖 `repo_url is None` 还是 `repo_url == "未知仓库"` 做判断。打开 `core/services/codeup_merge_event_classifier.py` 确认：

如果 classifier 检查 `if not event.repo_url`，则 `"未知仓库"` 为 truthy 值，不会触发。需修改 classifier 逻辑：

打开 `core/services/codeup_merge_event_classifier.py`，约 L25：

将：
```python
if not event.repo_url or not event.merge_request_id:
```
改为：
```python
if not event.repo_url or event.repo_url == "未知仓库" or not event.merge_request_id:
```

然后更新 `test_missing_repo_url_raises_invalid_payload` 测试：payload 中 repository 和 project 保持空字典，断言仍然抛 `InvalidCodeupPayload`。

- [ ] **Step 6: 更新 test_codeup_webhook_api.py 中的测试数据**

打开 `tests/integration/test_codeup_webhook_api.py`。

检查约 L35 的 `git_http_url` 值。Webhook API 的入口是接收原始 payload（含完整 URL），normalizer 内部会归一化。测试 payload 中的原始 URL 不需要改，但断言中验证 `repo_url` 存储值的地方需要改为归一化格式。

- [ ] **Step 7: 运行 codeup 相关全部测试**

Run: `python -m pytest tests/unit/test_services/test_codeup_payload_normalizer.py tests/unit/test_services/test_codeup_webhook_service.py tests/unit/test_services/test_codeup_merge_event_classifier.py tests/unit/test_services/test_codeup_note_provider.py tests/unit/test_services/test_codeup_merge_authorship_service.py tests/unit/test_database/test_codeup_merge_authorship_db.py tests/integration/test_codeup_webhook_api.py -v`
Expected: 全部 PASS

- [ ] **Step 8: Commit**

```bash
git add core/services/codeup_payload_normalizer.py core/services/codeup_merge_event_classifier.py tests/unit/test_services/test_codeup_payload_normalizer.py tests/unit/test_services/test_codeup_webhook_service.py tests/unit/test_services/test_codeup_merge_event_classifier.py tests/integration/test_codeup_webhook_api.py
git commit -m "feat: normalize repo_url in codeup payload normalizer + update tests"
```

---

### Task 5: 修改 notes_service.py（入口 4）

**Files:**
- Modify: `core/services/notes_service.py`

- [ ] **Step 1: 添加 import**

在文件顶部添加：

```python
from core.utils.repo_url import normalize_repo_url
```

- [ ] **Step 2: 在每个公开方法入口处归一化 repo_url**

在以下 6 个方法中，在方法体开头添加归一化调用：

**`create_or_update_note`（约 L19）：** 在方法体开头添加：
```python
        repo_url = normalize_repo_url(repo_url)
```

**`get_note`（约 L45）：** 在方法体开头添加：
```python
        repo_url = normalize_repo_url(repo_url)
```

**`batch_get_notes`（约 L49）：** 在方法体开头添加：
```python
        repo_url = normalize_repo_url(repo_url)
```

**`batch_push_notes`（约 L53）：** 在方法体开头添加：
```python
        repo_url = normalize_repo_url(repo_url)
```

**`list_notes`（约 L57）：** 在方法体开头添加：
```python
        repo_url = normalize_repo_url(repo_url)
```

**`search_notes`（约 L71）：** 在方法体开头添加：
```python
        repo_url = normalize_repo_url(repo_url)
```

- [ ] **Step 3: 更新 test_notes_rest_service.py 中的测试数据**

打开 `tests/unit/test_services/test_notes_rest_service.py`。

此文件中所有测试使用 `"https://github.com/test/repo.git"` 作为 repo_url。归一化后该值会变为 `"github.com/test/repo"`。

由于归一化在 `notes_service.py` 入口处完成，测试通过 mock 的数据库层收到的将是归一化后的值。需要更新所有断言中检查 `repo_url` 参数的地方。

搜索并替换文件中所有断言里的 repo_url 值。关键位置：

- 凡是断言 `call_args` 或 `call_kwargs` 中 `repo_url == "https://github.com/test/repo.git"` 的地方，改为 `repo_url == "github.com/test/repo"`
- mock 调用中的 `repo_url` 参数同理

- [ ] **Step 4: 更新 test_notes_rest_api.py 集成测试**

打开 `tests/integration/test_notes_rest_api.py`。

此文件中 API 端到端测试使用 `"https://github.com/test/repo.git"` 作为请求 payload 中的 `repo_url`。由于归一化在 service 层完成，请求 payload 中的原始 URL 仍然可以发送，数据库中存储的是归一化后的值。

检查是否有断言验证数据库中的 `repo_url` 值。如有，更新为归一化格式 `"github.com/test/repo"`。

如果测试是验证响应中返回 repo_url（从数据库读取），也需要更新断言。

- [ ] **Step 5: 更新 test_codeup_note_provider.py**

打开 `tests/unit/test_services/test_codeup_note_provider.py`。

约 L38 `repo_url = "https://codeup.aliyun.com/org/repo.git"` — 这是传给 mock 数据库的值。由于 `CodeupNoteProvider` 调用 `database.batch_get_notes(repo_url, ...)` 之前 repo_url 已经在 normalizer 中归一化了（Task 4），所以此处传入的 repo_url 应该已经是归一化后的值。

将测试中的 repo_url 改为归一化格式：
```python
repo_url = "codeup.aliyun.com/org/repo"
```

- [ ] **Step 6: 运行 Notes 相关全部测试**

Run: `python -m pytest tests/unit/test_services/test_notes_rest_service.py tests/unit/test_services/test_codeup_note_provider.py tests/unit/test_models/test_notes.py tests/integration/test_notes_rest_api.py -v`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add core/services/notes_service.py tests/unit/test_services/test_notes_rest_service.py tests/unit/test_services/test_codeup_note_provider.py tests/integration/test_notes_rest_api.py
git commit -m "feat: normalize repo_url in notes service + update tests"
```

---

### Task 6: 修改 stats_db.py（入口 5）

**Files:**
- Modify: `core/database/stats_db.py`

- [ ] **Step 1: 添加 import**

在文件顶部添加：

```python
from core.utils.repo_url import normalize_repo_url
```

- [ ] **Step 2: 修改 `get_or_create_repository` 方法（约 L487-511）**

将：
```python
    def get_or_create_repository(self, repo_path: str) -> str:
        self.consolidate_unknown_repositories()
        normalized_path = self._normalize_repo_path(repo_path)
        extracted_name = self._extract_repo_name(normalized_path)
```
改为：
```python
    def get_or_create_repository(self, repo_path: str) -> str:
        self.consolidate_unknown_repositories()
        normalized_path = normalize_repo_url(repo_path)
        extracted_name = self._extract_repo_name(normalized_path)
```

注意：调用方 `metrics_event_processor_task.py` 已在 Task 3 中归一化，此处双重归一化不会产生副作用（已归一化的值再次归一化结果不变）。

- [ ] **Step 3: 删除 `_normalize_repo_path` 静态方法（约 L268-271）**

删除整个方法：
```python
    @staticmethod
    def _normalize_repo_path(repo_path: Optional[str]) -> str:
        value = (repo_path or "").strip()
        return value or "未知仓库"
```

确认文件中没有其他地方调用 `_normalize_repo_path`（除 `get_or_create_repository` 外）。如有，也一并替换。

- [ ] **Step 4: 运行 stats_db 相关测试**

Run: `python -m pytest tests/unit/test_database/test_sqlite.py tests/unit/test_database/test_blame_stats_db.py tests/integration/test_dimensions_db.py tests/integration/test_dimensions_api.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add core/database/stats_db.py
git commit -m "feat: replace _normalize_repo_path with normalize_repo_url in stats_db"
```

---

### Task 7: 修改 daily_aggregation_task.py（入口 6）

**Files:**
- Modify: `core/scheduler/tasks/daily_aggregation_task.py`

- [ ] **Step 1: 添加 import**

在文件顶部添加：

```python
from core.utils.repo_url import normalize_repo_url
```

- [ ] **Step 2: 归一化 committed_events 中的 repo_path（约 L107）**

将：
```python
            repo_path = event.get("repo_url", "")
```
改为：
```python
            repo_path = normalize_repo_url(event.get("repo_url"))
```

- [ ] **Step 3: 归一化 checkpoint_events 中的 repo_path（约 L134）**

将：
```python
            repo_path = event.get("repo_url", "")
```
改为：
```python
            repo_path = normalize_repo_url(event.get("repo_url"))
```

- [ ] **Step 4: 运行聚合任务相关测试**

Run: `python -m pytest tests/ -k "aggregation or daily" -v`
Expected: PASS（可能无匹配测试，确认无报错即可）

- [ ] **Step 5: Commit**

```bash
git add core/scheduler/tasks/daily_aggregation_task.py
git commit -m "feat: normalize repo_path in daily aggregation task"
```

---

### Task 8: 修改 codeup_git_service.py（还原点 1）

**Files:**
- Modify: `core/services/codeup_git_service.py`

- [ ] **Step 1: 添加 import**

在文件顶部添加：

```python
from core.utils.repo_url import restore_repo_url
```

- [ ] **Step 2: 修改 `_repo_url_for_auth` 方法（约 L209-217）**

此方法当前接收 `repo_url` 并判断如果是 https 且有 private_key 就转为 ssh URL。归一化后 `repo_url` 是 `host/path` 格式（不含协议），需要先还原。

将：
```python
    def _repo_url_for_auth(self, repo_url: str, private_key: str | None) -> str:
        if private_key is None or not repo_url.startswith(("http://", "https://")):
            return repo_url
        ssh_url = repo_url.replace("https://", "ssh://git@", 1).replace(
            "http://", "ssh://git@", 1
        )
        if not ssh_url.endswith(".git"):
            ssh_url += ".git"
        return ssh_url
```
改为：
```python
    def _repo_url_for_auth(self, repo_url: str, private_key: str | None) -> str:
        if private_key is None:
            return restore_repo_url(repo_url, "https")
        return restore_repo_url(repo_url, "ssh")
```

说明：归一化后的 `repo_url` 不再以 `http://` 或 `https://` 开头，原有逻辑的判断条件不再适用。新逻辑：有 private_key 时还原为 SSH URL，否则还原为 HTTPS URL。

- [ ] **Step 3: 更新 test_codeup_git_service.py**

打开 `tests/unit/test_services/test_codeup_git_service.py`。

约 L92 `repo_url="https://codeup.aliyun.com/org/repo.git"` — 此处测试传入归一化前的 URL。需改为归一化格式：

将测试中所有传给 `ensure_repo` / `_repo_url_for_auth` 的 `repo_url="https://codeup.aliyun.com/org/repo.git"` 改为 `repo_url="codeup.aliyun.com/org/repo"`。

约 L137-161 的 SSH URL 测试：当前断言 `clone_call[0] == ["git", "clone", ssh_repo_url, ...]`，其中 `ssh_repo_url = "ssh://git@codeup.aliyun.com/org/repo.git"`。由于 `_repo_url_for_auth` 现在通过 `restore_repo_url` 还原，断言值不变，但输入需要改为归一化格式。

- [ ] **Step 4: 运行 git service 测试**

Run: `python -m pytest tests/unit/test_services/test_codeup_git_service.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add core/services/codeup_git_service.py tests/unit/test_services/test_codeup_git_service.py
git commit -m "feat: use restore_repo_url in codeup git service"
```

---

### Task 9: 修改 git_clone_service.py（还原点 2）

**Files:**
- Modify: `core/services/git_clone_service.py`

- [ ] **Step 1: 添加 import**

在文件顶部添加：

```python
from core.utils.repo_url import restore_repo_url
```

- [ ] **Step 2: 修改 `clone_with_ssh_key` 方法中的 URL 还原逻辑（约 L57-63）**

将：
```python
            # 将 http/https 地址改为 ssh
            if repo_url.startswith('http'):
                repo_url = repo_url.replace('https://', 'ssh://git@')
                repo_url = repo_url.replace('http://', 'ssh://git@')
                repo_url = repo_url.replace('devops.cxmt.com', 'devops.cxmt.com:8022')
                if not repo_url.endswith('.git'):
                    repo_url += '.git'
```
改为：
```python
            # 将归一化地址还原为 SSH URL
            repo_url = restore_repo_url(repo_url, "ssh")
```

注意：原代码中有 `devops.cxmt.com` → `devops.cxmt.com:8022` 的特殊处理。这是一个硬编码的域名替换，归一化后 `devops.cxmt.com:8022/group/project` 已保留端口号，`restore_repo_url` 还原后会正确生成 `ssh://git@devops.cxmt.com:8022/group/project.git`。但原代码对无端口的 `devops.cxmt.com` 也会添加 `:8022`，这个特殊逻辑在新方案中不再保留。如果需要保留此行为，需在 `restore_repo_url` 之外额外处理。

**重要决策点：** 如果 `devops.cxmt.com` 的仓库确实都需 `:8022` 端口，则应在归一化前确保原始 URL 包含端口号（数据源侧保证），或在 `git_clone_service.py` 中 `restore_repo_url` 之后添加端口替换逻辑。实现时请确认。

- [ ] **Step 3: 更新 test_git_clone_service.py**

打开 `tests/unit/test_services/test_git_clone_service.py`。

测试中传入的 `repo_url` 需改为归一化格式。还原后的 clone URL 仍应为 `ssh://git@...` 格式，断言不变。

- [ ] **Step 4: 运行 git clone service 测试**

Run: `python -m pytest tests/unit/test_services/test_git_clone_service.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add core/services/git_clone_service.py tests/unit/test_services/test_git_clone_service.py
git commit -m "feat: use restore_repo_url in git clone service"
```

---

### Task 10: 全量回归测试

**Files:**
- 无新增/修改，纯运行测试

- [ ] **Step 1: 运行全量单元测试**

Run: `python -m pytest tests/unit/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 2: 运行全量集成测试**

Run: `python -m pytest tests/integration/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 3: 运行全量测试**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 4: 修复所有回归失败（如有）**

逐个排查并修复失败的测试。常见原因：
- 测试中硬编码了完整 URL 作为断言值
- Mock 对象的 `repo_url` 参数需要更新为归一化格式
- 测试 payload 中的原始 URL 仍然用完整格式发送（这是正确的），但断言数据库中存储值的测试需要用归一化格式

---

### Task 11: 更新 data_uid.py 中的 UID 生成（可选，视回归测试结果）

**Files:**
- Modify: `core/utils/data_uid.py`（如果回归测试发现 UID 变化导致 upsert 冲突）

**说明：** `data_uid.py` 中的 `gen_checkpoint_uid` 和 `gen_agent_usage_uid` 将 `repo_url` 参与哈希计算。归一化后 `repo_url` 值变化会导致 UID 不同。如果 `upsert_committed_event` 等方法依赖 UID 做去重，新旧数据的 UID 将不同，可能产生重复记录。

如果回归测试中 `test_data_uid.py` 中有测试断言特定 UID 值，需更新测试数据。由于 UID 是哈希值，修改 `repo_url` 输入自然会得到不同的哈希值——这是预期行为，只需更新测试中的期望值。

- [ ] **Step 1: 检查 test_data_uid.py 是否失败**

Run: `python -m pytest tests/unit/test_utils/test_data_uid.py -v`

- [ ] **Step 2: 如失败，更新测试中的期望 UID 值**

运行测试获取新的期望值，更新断言。

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_utils/test_data_uid.py
git commit -m "test: update data_uid expected values after repo_url normalization"
```
