# Codeup Merge Webhook Refactor Design

## 背景

当前系统已经支持 `POST /webhook/codeup/merge`，并把 merged 类事件转换为异步的 Codeup merge authorship 任务。现有实现可以完成入队和后续归因，但它把多个职责揉在一起了：

1. webhook 层同时承担事件判断、字段提取和任务创建；
2. worker 层同时承担仓库准备、merge 事实判定、note 读取、归因合并和状态写回；
3. 任务模型只保存原始 payload 和少量抽取字段，缺少可观察、可追踪的事件语义；
4. authorship 处理还没有按 `git-ai standard v3.0.0` 的 merge 语义分类型处理。

本次重构的目标是把这些职责拆清楚，并把“Webhook payload 只是输入信号，仓库状态才是 merge 事实来源”这条原则落实到代码里。

## 目标

- 将 Codeup payload 归一化、事件分类、仓库 merge 类型判定、authorship 策略拆成独立组件。
- 兼容 Codeup 新旧 webhook payload 字段差异。
- 让 webhook 只负责入参校验、归一化结果判断和任务入队，不直接决定归因事实。
- 让 merge 类型由仓库 commit DAG、parent 关系和 commit 内容判定，而不是由 payload 猜测。
- 让 authorship 处理符合 `git-ai standard v3.0.0` 中对 standard merge、squash、rebase 和保守归因的要求。
- 对 fast-forward 采用保守策略：不为不存在的新 merge commit 发明归因。
- 保持现有的异步任务、失败重试、幂等更新能力。

## 非目标

- 不在本次重构中实现 Codeup webhook 鉴权。
- 不把 Codeup 的 user / author / assignee / reviewer 字段纳入 AI authorship 决策。
- 不把 notes 写回 Codeup 仓库。
- 不新增前端页面或管理界面。
- 不改变现有任务调度框架。

## 当前行为约束

- webhook 路由位于 `api/routes/codeup_webhook.py`，返回统一的 `{success, data|error}` 结构。
- `CodeupWebhookService.enqueue_merge_event()` 目前负责判断 merged、提取 repo / MR / branch / commit 信息并创建任务。
- `CodeupMergeAuthorshipDatabase.create_or_update_task()` 以 `(repo_url, merge_request_id, merge_commit_sha)` 为幂等键。
- `CodeupMergeAuthorshipService.process_next_task()` 负责领取任务、准备仓库、读取 notes、合并归因并写回结果。
- `MergeAuthorshipCalculator` 负责 note 的解析、合并和序列化，当前采用 target priority + source 补充策略。

这些约束在重构后仍应保持，除非设计中明确说明变化。

## 推荐架构

```text
POST /webhook/codeup/merge
  └─> CodeupWebhookService
        ├─> CodeupPayloadNormalizer
        ├─> CodeupMergeEventClassifier
        └─> CodeupMergeAuthorshipDatabase

Scheduler Worker
  └─> CodeupMergeAuthorshipService
        ├─> CodeupGitService
        ├─> CodeupDatabaseNoteProvider
        ├─> RepositoryMergeResolver
        ├─> MergeAuthorshipPolicy
        └─> NotesRestService
```

### 分层原则

- **Route 层**：只做 HTTP 处理和响应包装。
- **Webhook Service 层**：只做 payload 归一化、事件分类和任务入队。
- **Database 层**：只做任务持久化、幂等更新和状态流转。
- **Worker Orchestration 层**：只做任务领取、仓库准备、策略编排和状态回写。
- **Resolver / Policy 层**：只负责 merge 类型判定和归因决策。

## 组件设计

### 1. CodeupPayloadNormalizer

文件：`core/services/codeup_payload_normalizer.py`

职责：把原始 Codeup payload 转成稳定的内部事件对象 `NormalizedCodeupMergeEvent`。

建议字段：

| 字段 | 说明 |
|---|---|
| `repo_url` | 可 clone/fetch 的仓库 URL |
| `project_id` | Codeup project 标识 |
| `merge_request_id` | 稳定的 MR 标识 |
| `source_branch` | 源分支 |
| `target_branch` | 目标分支 |
| `merge_commit_sha` | payload 中可见的 merge 结果 commit |
| `source_commit_shas` | payload 中可见的源提交列表 |
| `event_action` | 归一化后的 action/state |
| `payload_version_hint` | `new` / `legacy` / `unknown` |
| `is_update_by_push` | Codeup 新版 push update 标识 |
| `raw_payload` | 原始 payload |

归一化优先级：

- MR 标识：`biz_id` → `local_id` → `iid` → `id` → 顶层字段；
- repo URL：`repository` → `project.repository` → `project.git_http_url` → `project.git_ssh_url`；
- source commits：`commits[].id` → `commits[].sha`；
- event action：`object_attributes.action` → `object_attributes.state` → 顶层 `action`。

### 2. CodeupMergeEventClassifier

文件：`core/services/codeup_merge_event_classifier.py`

职责：判断归一化后的事件是否应该入队，并给出清晰分类。

分类建议：

- `merge_candidate`
- `push_update`
- `mr_update`
- `invalid`
- `unknown`

分类原则：

- 缺少 repo 或 MR 标识时，返回 `invalid`，HTTP 400；
- `is_update_by_push=True` 时返回 `push_update`，不入队；
- 非 merge completion 的事件返回 `mr_update` 或 `unknown`，不入队；
- 只有 `merge_candidate` 才创建任务。

### 3. CodeupMergeAuthorshipTask 模型与数据库

文件：

- `core/database/models.py`
- `core/database/codeup_merge_authorship_db.py`
- `sql/metrics_schema_mysql.sql`

建议新增字段：

| 字段 | 说明 |
|---|---|
| `event_kind` | classifier 输出 |
| `payload_version_hint` | payload 版本提示 |
| `normalized_payload` | 归一化事件 JSON |
| `merge_type` | resolver 输出的真实 merge 类型 |
| `skipped_reason` | skipped / unknown 原因 |

建议保持现有幂等键：

```text
(repo_url, merge_request_id, merge_commit_sha)
```

状态建议保留并扩展为：

```text
pending -> processing -> success
                    \-> failed
pending -> skipped
```

数据库适配器建议新增：

- `create_or_update_task(..., event_kind, payload_version_hint, normalized_payload, skipped_reason)`
- `mark_skipped(task_id, reason, merge_type=None)`
- `update_merge_type(task_id, merge_type)`

### 4. RepositoryMergeResolver

文件：`core/services/repository_merge_resolver.py`

职责：在本地仓库准备完成后，基于 Git 状态判断真实 merge 类型。

输出类型：

- `standard_merge`
- `squash_merge`
- `rebase_merge`
- `fast_forward`
- `unknown`

判定原则：

- `standard_merge`：merge commit 存在且 parent 数量大于 1；
- `squash_merge`：单个结果 commit 对应多个 source commits；
- `rebase_merge`：线性提交重写，SHA 变化但内容对应原 source commits；
- `fast_forward`：没有新的 merge commit；
- `unknown`：commit graph 或 source 信息不足以稳定判断。

resolver 只消费仓库状态和 Git 查询结果，不读取 Codeup payload 原始字段。

### 5. MergeAuthorshipPolicy

文件：`core/services/merge_authorship_policy.py`

职责：根据 `RepositoryMergeResolution` 决定如何合并、写入或跳过 authorship notes。

策略原则：

#### standard merge

- 保留源 commits 现有 notes；
- merge commit 只记录冲突解决或新增归因；
- 不把 source commits 的归因无条件复制到 merge commit；
- 若无可写入的新归因，可返回空写入结果。

#### squash merge

- 读取 source commits 的 notes；
- 将 attribution 迁移到 squash commit 的最终文件内容；
- 保留所有 prompt records；
- 允许 target priority，但不得丢失已知有效 attribution。

#### rebase merge

- 迁移原 commit 的 notes 到重写后的 commit；
- 按新 commit 内容重算 line attribution；
- 更新 `base_commit_sha` 相关信息；
- 不保留旧 SHA 作为最终归因落点。

#### fast-forward

- 不创建新的 merge note；
- 不改写已有 source commit notes；
- 返回 skipped 或空写入结果。

#### unknown

- 不猜测归因；
- 不写入新的 authorship 结果；
- 记录原因并跳过。

### 6. CodeupMergeAuthorshipService

文件：`core/services/codeup_merge_authorship_service.py`

重构后职责：

- 从数据库领取任务；
- 准备仓库；
- 推导 source commit 列表；
- 调用 `RepositoryMergeResolver`；
- 调用 `MergeAuthorshipPolicy`；
- 将结果写回 notes 服务；
- 标记任务 success / failed / skipped。

不再承担：

- Codeup payload 兼容；
- merge 类型规则判断；
- authorship 细节策略选择。

## 数据流

### Webhook 入站

```text
raw payload
  -> normalizer
  -> classifier
  -> skipped response 或 create/update task
```

### Worker 处理

```text
pending task
  -> claim processing
  -> ensure repo
  -> resolve merge type
  -> load notes
  -> apply policy
  -> upsert notes
  -> mark success / failed / skipped
```

## 错误处理

### HTTP 层

- 空 body 或非 JSON：400；
- 缺少关键标识：400；
- 非 merge candidate：200 + `skipped: true`；
- 处理异常：500。

### 任务层

- 重复成功任务：返回已有 task；
- 重复 pending / failed 任务：更新 normalized payload 并保持可处理；
- processing 任务：不抢占；
- 超过最大尝试次数：维持 failed。

### Resolver 层

- fetch 失败：failed，可重试；
- merge commit 缺失：按上下文判为 fast-forward 或 unknown；
- commit graph 不足以分类：unknown，不写归因；
- source commits 不完整：优先使用仓库推导，仍不足则失败。

### Policy 层

- standard merge 没有新归因时可以空写入；
- squash / rebase 需要足够信息才能写入；
- fast-forward / unknown 一律保守跳过，不生成猜测式归因。

## 测试策略

### 单元测试

- normalizer：新旧 payload 兼容、repo URL 兜底、MR id 兜底、source commits 提取；
- classifier：merge candidate、push update、mr update、invalid、unknown；
- database：新增字段写入、skip 状态、merge_type 更新、幂等语义；
- resolver：standard / squash / rebase / fast-forward / unknown；
- policy：不同 merge type 的 note 写入行为；
- webhook service：只在 merge candidate 时创建任务，其他事件跳过；
- worker service：按 merge type 编排数据库状态和 notes 写回。

### 集成测试

- `POST /webhook/codeup/merge` 对 merged payload 返回 `success=True` 且生成 task；
- 非 merge 事件返回 `success=True, skipped=True`；
- 缺少关键字段返回 400；
- worker 执行后可正确更新任务状态。

## 迁移与兼容性

- 保留现有任务幂等键和调度方式，避免影响现有 pending/failed 重试逻辑。
- 新增字段全部可空，确保旧任务记录仍可读取。
- 现有 `MergeAuthorshipCalculator` 可以继续作为 note 归并基础，不强制重写其全部行为。

## 结论

本次重构采用“事件归一化 + 事件分类 + 仓库语义解析 + authorship policy”的分层方案。这样可以把 Codeup webhook 的输入兼容性、worker 的仓库事实判断和 authorship 的策略执行拆开，降低耦合，同时让实现更贴近 `git-ai standard v3.0.0` 的保守归因原则。
