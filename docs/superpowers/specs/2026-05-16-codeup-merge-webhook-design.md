# Codeup Merge Webhook AI 归属重算设计

## 背景

当前项目是 Flask + SQLAlchemy 后端，已经通过 `authorship_notes` 表存储 Git-AI authorship note 数据。现有 notes API 和服务层已经支持按 `(repo_url, commit_sha)` 对 note 进行新增或更新。仓库内的 `git-ai` Rust 子项目提供了可参考的 merge 归因逻辑，核心思想是分别构建目标分支和源分支的行级虚拟归属，再按“目标分支优先”的规则合并归属。

阿里 Codeup 仓库不支持 Git Notes。因此，本功能必须把数据库作为 authorship notes 的唯一来源和唯一落点。Codeup Git 仓库只用于读取 Git 对象，例如提交、父提交、diff、文件内容和类似 blame 的行映射信息。

## 目标

- 新增 Codeup merge webhook 接口，仅接收合并完成事件。
- Webhook 快速返回，通过持久化后台任务异步处理耗时重算。
- 对 Merge Request 相关的全部提交重新计算 AI 代码归属。
- 从 `authorship_notes` 表读取已有 authorship note 数据，而不是从 Git Notes 读取。
- 将重算后的 authorship notes 写回 `authorship_notes` 表。
- 保证处理幂等，避免 Codeup webhook 重试造成重复副作用。

## 非目标

- 不把 notes 推送回 Codeup。
- 不依赖 Codeup 仓库中的 `refs/notes/ai`。
- 第一版不增加 webhook 鉴权。
- 第一版不开发任务状态前端页面。

## 推荐架构

采用异步流水线：

1. `POST /webhook/codeup/merge` 接收 Codeup merge webhook payload。
2. 路由校验必填字段，并判断事件是否为合并完成。
3. 路由创建或更新一条持久化 merge authorship 重算任务，并立即返回任务 ID。
4. 调度器或后台任务领取 pending / 可重试任务。
5. Worker 将 Codeup 仓库 clone 或 fetch 到本地缓存目录。
6. Worker 推导 Merge Request 的提交范围，并重算全部相关提交的 authorship。
7. Worker 通过现有 authorship notes upsert 能力写入结果。
8. Worker 将任务标记为 `success` 或 `failed`，并记录处理结果。

该架构可以避免 webhook 超时，并为失败重试提供持久化基础。

## API 设计

### 接口

- 方法：`POST`
- 路径：`/webhook/codeup/merge`
- 鉴权：第一版不鉴权
- 响应风格：沿用现有 worker 风格 JSON，例如 `{"success": true, ...}`

### Payload 处理

接口接收 Codeup Merge Request webhook 原始 payload，并提取以下字段：

- 仓库 URL
- project id，如果 payload 中存在
- merge request id 或 iid
- 源分支
- 目标分支
- merge 状态
- merge commit SHA
- 源提交 SHA 列表，如果 payload 中存在

只有已合并事件会入队。非合并完成的 Merge Request 事件返回 HTTP 200，并带上 `skipped: true` 和类似 `not_merged` 的原因。缺少关键 merge 字段的 payload 返回 HTTP 400。

## 任务持久化模型

新增任务表：`codeup_merge_authorship_tasks`。

建议字段：

- `id`：主键
- `repo_url`：仓库 URL
- `project_id`：Codeup project id，可为空
- `merge_request_id`：Codeup merge request id 或 iid
- `source_branch`：源分支名
- `target_branch`：目标分支名
- `merge_commit_sha`：目标 merge commit 或 squash commit SHA
- `source_commit_shas`：JSON/Text 格式的源提交 SHA 数组，可为空，后续可推导
- `payload`：JSON/Text 格式的 webhook 原始 payload
- `status`：`pending`、`processing`、`success` 或 `failed`
- `attempts`：重试次数
- `last_error`：最近一次失败信息
- `result_summary`：JSON/Text 格式的结果摘要，例如 created / updated note 数量
- `created_at`：毫秒时间戳
- `updated_at`：毫秒时间戳

唯一键建议使用 `(repo_url, merge_request_id, merge_commit_sha)`。如果 Codeup 重复投递 webhook，且已有任务成功，则直接返回已有任务；如果已有任务仍是 pending 或 failed，则更新 payload 并保持可重试。

## 后台处理流程

Worker 通过原子状态更新领取任务：把符合条件的 `pending` 或 `failed` 任务切换为 `processing`，同时受 `max_attempts` 限制。这样可以避免多个 worker 并发处理同一个 merge。

处理步骤：

1. 将仓库 clone 或 fetch 到 `codeup_webhook.repo_cache_dir`。
2. fetch 目标分支、源分支、merge commit，以及已知的源提交。
3. 解析相关提交集合：
   - 优先使用 payload 中的 `source_commit_shas`。
   - 如果 payload 没有提供，则通过 merge-base 和 Git revision traversal 推导提交范围。
   - 始终包含 merge commit 本身。
4. 按 `repo_url + commit_sha` 从 `authorship_notes` 表加载已有 note 内容。
5. 对全部相关提交重新计算 authorship。
6. 通过现有数据库层批量 upsert note 记录。
7. 写入成功后，将任务标记为成功，并记录 created / updated 数量。

fetch 失败、merge commit 缺失、提交范围无法推导、关键 note 解析失败、数据库写入失败等情况会将任务标记为 `failed`，并写入 `last_error`。源提交缺少 note 不视为失败，按未知或人工归属处理。

## Authorship 重算设计

实现应复用 `git-ai` 的关键行为，但不能依赖 Git Notes：

- 构建目标侧和源侧内容的行级归属视图。
- 从数据库中的 authorship notes 读取 prompt 和 attribution 元数据。
- 合并目标侧和源侧归属；当同一个最终文件行同时存在目标侧和源侧归属时，目标侧归属优先。
- 保留已有 notes 中的 prompt 元数据。
- 当源提交存在 additions / deletions 等 totals 数据时进行累计，避免 merge 或 squash 后丢失 session 级统计。
- 输出保持现有 Git-AI authorship log 格式：文件 attestations，随后是 `---` 分隔符和 metadata JSON。

服务层应新增一个基于数据库的 note provider 抽象。该抽象按 `repo_url` 和 commit SHA 列表批量读取 note，并返回 `{commit_sha: note_content}`。Codeup 路径中不得使用 `git notes show`、`git notes fetch` 或 `git notes push`。

## Notes Upsert

复用现有 authorship notes 持久化方式：

- 按 `(repo_url, commit_sha)` upsert。
- 将重算后的 authorship log 文本存入 `note_content`。
- 可用时写入 branch、author、email、commit_time 和 note metadata。
- 优先使用批量 upsert，减少数据库往返。

本功能只更新数据库，不向本地 clone 写入 `refs/notes/ai`，也不向 Codeup 推送 notes。

## 配置项

新增 `codeup_webhook` 配置块：

```yaml
codeup_webhook:
  enabled: true
  repo_cache_dir: .cache/codeup_repos
  max_attempts: 3
  batch_size: 10
  clone_timeout_seconds: 300
  fetch_timeout_seconds: 120
```

Webhook secret 配置可在后续版本增加，但不属于第一版范围。

## 错误处理

- 缺少 webhook 必填字段：返回 HTTP 400。
- 非合并完成事件：返回 HTTP 200，并带 `skipped: true`。
- 重复的成功事件：返回 HTTP 200，并返回已有任务信息。
- 重复的 pending 或 failed 事件：更新任务 payload，并返回已有任务 ID。
- clone / fetch 失败：任务标记为 failed，并在 `max_attempts` 范围内允许重试。
- 源提交缺少 note：继续处理，按未知归属处理。
- merge commit 或提交范围无法解析：任务标记为 failed。
- 数据库 upsert 失败：任务标记为 failed。

## 测试策略

### API 测试

- merged payload 会创建 pending 任务。
- 非 merged payload 会被 skipped。
- 缺少必填字段返回 HTTP 400。
- 重复 payload 保持幂等。

### 数据库和服务测试

- 创建或更新 merge authorship task。
- 安全领取 pending 或 failed 任务。
- 标记 success 和 failed 状态。
- 按仓库和 commit SHA 从 `authorship_notes` 批量读取 authorship notes。

### 归因算法测试

- target 和 source 同时声明同一个最终行时，target 归属优先。
- source note 缺失时不导致处理失败。
- 生成的 note 内容可以被现有 blame 统计使用的 note parser 解析。
- prompt metadata 和 totals 在存在时会被保留。

### 集成测试

构造一个小型本地 Git 仓库，预置 `authorship_notes` 数据，模拟 Codeup merged payload，运行 worker，并验证全部相关提交的 notes 被 upsert，且 merge 归因符合预期。

## 已确认决策

- 触发范围：仅处理 Codeup 合并完成事件。
- 仓库访问：服务端 clone 或 fetch Codeup 仓库。
- 更新范围：Merge Request 全部相关提交，包括 merge commit。
- 安全策略：第一版不做 webhook 鉴权。
- Notes 来源和落点：仅使用 `authorship_notes` 表。
