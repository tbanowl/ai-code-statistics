# 仓库地址归一化设计

## 背景

项目中同一仓库以多种 URL 格式入库（https、ssh、git@ 等），导致：

1. `stats_repositories` 出现重复条目（同一仓库多条记录）
2. 跨表 `repo_url` 查询无法匹配（事件表写的是 https 格式，Notes 表写的是 ssh 格式）
3. 维度聚合数据分散，统计结果不准确

### 当前现状

`stats_db._normalize_repo_path()` 仅做 `.strip()` + 空值替换为 `"未知仓库"`，不做 URL 标准化。

## 目标

1. 所有写入数据库的 `repo_url` / `repo_path` 统一归一化为 `host/path` 格式
2. 需要原始 URL 时（git clone 等），通过还原函数动态生成
3. 不新增数据库字段
4. 迁移脚本作为后续独立任务

## 归一化格式

去除协议前缀、`git@` 用户名、`.git` 后缀，保留端口号，结果为 `host/path` 格式。

| 输入 | 输出 |
|------|------|
| `https://codeup.aliyun.com/org/repo.git` | `codeup.aliyun.com/org/repo` |
| `http://codeup.aliyun.com/org/repo.git` | `codeup.aliyun.com/org/repo` |
| `git@codeup.aliyun.com:org/repo.git` | `codeup.aliyun.com/org/repo` |
| `ssh://git@codeup.aliyun.com/org/repo.git` | `codeup.aliyun.com/org/repo` |
| `http://devops.cxmt.com:8022/group/project.git` | `devops.cxmt.com:8022/group/project` |
| `org/repo`（已归一化） | `org/repo`（不变） |
| `""` / `None` | `未知仓库` |

## 还原格式

根据指定协议将归一化地址还原为完整 Git URL。

| normalized | protocol | 输出 |
|------------|----------|------|
| `codeup.aliyun.com/org/repo` | `ssh` | `ssh://git@codeup.aliyun.com/org/repo.git` |
| `codeup.aliyun.com/org/repo` | `https` | `https://codeup.aliyun.com/org/repo.git` |
| `devops.cxmt.com:8022/group/project` | `ssh` | `ssh://git@devops.cxmt.com:8022/group/project.git` |
| `未知仓库` | 任意 | 原样返回 |

## 实现方案

### 方案：集中式归一化函数

新建 `core/utils/repo_url.py`，包含两个纯函数：

```python
def normalize_repo_url(raw: str | None) -> str:
    """将任意 Git URL 归一化为 host/path 格式。"""

def restore_repo_url(normalized: str, protocol: str = "ssh") -> str:
    """将归一化地址还原为完整 Git URL。"""
```

### normalize_repo_url 规则（按顺序）

1. `None` / 空白字符串 → `"未知仓库"`
2. 去除协议前缀：`https://`、`http://`、`ssh://`、`git://`、`file://`
3. 去除 `git@` 前缀，将第一个 `:` 替换为 `/`（处理 `git@host:path` 格式）
4. 去除末尾 `.git`（仅当以 `.git` 结尾时）
5. 去除首尾空白和斜杠

### restore_repo_url 规则

1. `未知仓库` → 原样返回
2. `ssh` → `ssh://git@{host}/{path}.git`
3. `https` → `https://{host}/{path}.git`
4. `http` → `http://{host}/{path}.git`
5. `git` → `git://{host}/{path}.git`

### 写入入口修改点（6 处）

| # | 文件 | 位置 | 改动 |
|---|------|------|------|
| 1 | `core/services/metrics_service.py` | L81, L102（Committed/AgentUsage 的 `repo_url` 赋值） | `normalize_repo_url(...)` 包裹 |
| 2 | `core/scheduler/tasks/metrics_event_processor_task.py` | L44（`repo_path = attrs.get("1")`） | 归一化后再传给 `get_or_create_repository` |
| 3 | `core/services/codeup_payload_normalizer.py` | L51（`repo_url = self._first_string(...)`） | 在构造 `NormalizedCodeupMergeEvent` 前归一化 |
| 4 | `core/services/notes_service.py` | 所有公开方法的 `repo_url` 入参 | 入口处归一化后传给数据库层 |
| 5 | `core/database/stats_db.py` | L489 `get_or_create_repository()` | 替换 `_normalize_repo_path` 为 `normalize_repo_url`，删除旧方法 |
| 6 | `core/scheduler/tasks/daily_aggregation_task.py` | L107, L134（`repo_path = event.get("repo_url")`） | 归一化后使用 |

### 还原调用点（2 处）

| # | 文件 | 位置 | 改动 |
|---|------|------|------|
| 1 | `core/services/codeup_git_service.py` | `clone_or_fetch_repo()` / `_repo_url_for_auth()` | 接收归一化地址时，先用 `restore_repo_url()` 还原再操作 |
| 2 | `core/services/git_clone_service.py` | `clone_repo()` | 同上 |

## 测试计划

### 第一层：新函数单元测试

新建 `tests/unit/test_utils/test_repo_url.py`

覆盖场景：
- normalize：https / http / ssh / git@ / git:// / 带端口 / 已归一化 / 空值 / None / 末尾斜杠 / 末尾 .git
- restore：ssh / https / http / git 协议 / 带端口 / 未知仓库
- 往返：`restore(normalize(x))` 对各种格式可还原为可用 URL

### 第二层：受影响模块回归测试

以下现有测试文件需要确保归一化后全部通过，必要时更新测试数据中的 repo_url 值：

| 测试文件 | 涉及 repo_url 的关键测试 |
|----------|--------------------------|
| `tests/unit/test_services/test_codeup_payload_normalizer.py` | webhook payload 归一化后 repo_url 格式验证 |
| `tests/unit/test_services/test_codeup_webhook_service.py` | enqueue 时 repo_url 已归一化 |
| `tests/unit/test_services/test_notes_rest_service.py` | Notes CRUD 操作使用归一化地址 |
| `tests/unit/test_services/test_codeup_git_service.py` | clone 时还原为完整 URL |
| `tests/unit/test_services/test_git_clone_service.py` | clone 时还原为完整 URL |
| `tests/unit/test_services/test_codeup_merge_authorship_service.py` | merge 任务中 repo_url 归一化 |
| `tests/unit/test_services/test_codeup_note_provider.py` | Notes 查询使用归一化地址 |
| `tests/unit/test_services/test_codeup_merge_event_classifier.py` | 分类器输入含归一化地址 |
| `tests/unit/test_services/test_blame_stats_service.py` | blame 统计中 repo_url 使用 |
| `tests/unit/test_database/test_codeup_merge_authorship_db.py` | merge 任务 DB 操作 |
| `tests/unit/test_database/test_blame_stats_db.py` | blame stats DB 查询 |
| `tests/unit/test_database/test_sqlite.py` | `get_or_create_repository` 归一化验证 |
| `tests/unit/test_models/test_notes.py` | AuthorshipNotes 唯一约束 |
| `tests/unit/test_models/test_metrics.py` | MetricsEventsCommitted repo_url |
| `tests/unit/test_utils/test_data_uid.py` | UID 生成含 repo_url |
| `tests/unit/test_scheduler/test_stats_task.py` | stats 任务 repo_path |
| `tests/test_metrics_event_processor_task.py` | 事件处理 repo_path 归一化 |
| `tests/integration/test_notes_rest_api.py` | Notes REST API 端到端 |
| `tests/integration/test_dimensions_db.py` | 仓库维度数据库 |
| `tests/integration/test_dimensions_api.py` | 仓库维度 API |
| `tests/integration/test_codeup_webhook_api.py` | Codeup webhook 端到端 |

回归测试策略：
1. 先运行全量测试 `pytest` 记录当前通过状态
2. 实现归一化函数并通过新单元测试
3. 逐个修改写入入口
4. 每修改一个入口后运行相关测试文件
5. 全部修改完成后运行 `pytest` 确认无回归

## 后续任务（不在本实现范围）

- 历史数据迁移脚本：归一化已有 `repo_url`，合并 `stats_repositories` 中的重复条目
- 迁移脚本需处理唯一约束冲突（如 `authorship_notes` 的 `(repo_url, commit_sha)` 约束）
