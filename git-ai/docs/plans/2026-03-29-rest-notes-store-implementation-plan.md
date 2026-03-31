# REST 注释存储实现计划

> **对于 Claude：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。

**目标：** 添加一个可配置的 REST 支持的注释同步模式（`notes_store=rest`），以便当远程不支持 `refs/notes/ai` 时，git-ai 可以同步作者注释。

**架构：** 保持本地 git-notes 读/写不变（`src/git/refs.rs`）。仅在 `src/git/sync_authorship.rs` 中分支：`notes_store=git` 时使用当前 git 路径，`notes_store=rest` 时使用 REST API 路径。重用现有的 `ApiClient`/`ApiContext` 约定和现有的远程解析模式。

**技术栈：** Rust 2024，通过现有 API 客户端抽象使用 minreq，serde/serde_json，git CLI 包装器，Flask + SQLAlchemy（服务端在单独仓库中）。

---

## 守则

- 不要更改本地注释原语（`note_blob_oids_for_commits`、`notes_add_batch`、`show_authorship_note`），测试除外。
- 不要更改 hook 调度连接；仅更改现有函数背后的同步行为。
- 保留当前的 `NotesExistence` 语义（`NotFound` 表示远程没有注释，而非通用的 HTTP 失败）。
- 在 REST 调用之前对仓库 URL 进行规范化。

---

### 任务 1：添加 notes_store 配置接口

**文件：**
- 修改：`src/config.rs`
- 修改：`src/commands/config.rs`
- 测试：`src/config.rs` 测试

**步骤 1：编写失败的测试**

```rust
#[test]
fn test_notes_store_default_is_git() {
    let cfg = create_test_config(vec![], vec![]);
    assert_eq!(cfg.notes_store(), "git");
}
```

添加无效值回退和测试补丁覆盖的测试。

**步骤 2：运行测试（先失败）**

运行：`cargo test --package git-ai --lib test_notes_store_default_is_git -- --nocapture`
预期：实现前失败。

**步骤 3：最小实现**

- 将 `notes_store: String` 添加到 `Config`
- 将 `notes_store: Option<String>` 添加到 `FileConfig`
- 将 `notes_store: Option<String>` 添加到 `ConfigPatch`
- 在 `build_config()` 中，实现优先级：`GIT_AI_NOTES_STORE` > 文件配置 > 默认 `"git"`
- 仅验证 `git|rest`，对无效值发出警告/回退
- 添加 getter：`pub fn notes_store(&self) -> &str`
- 在 `apply_test_config_patch` 中，支持补丁 `notes_store`
- 在 `src/commands/config.rs` 中，在 help/show/get/set/unset 流程中暴露 `notes_store`

**步骤 4：重新运行测试**

运行：`cargo test --package git-ai --lib test_notes_store_default_is_git -- --nocapture`
预期：通过。

**步骤 5：提交**

```bash
git add src/config.rs src/commands/config.rs
git commit -m "feat(config): add notes_store backend selector"
```

---

### 任务 2：添加 REST 注释 API 载荷类型

**文件：**
- 修改：`src/api/types.rs`
- 测试：`src/api/types.rs` 测试

**步骤 1：编写失败的测试**

```rust
#[test]
fn test_notes_list_response_has_commit_shas() {
    let body = r#"{"ok":true,"data":{"commit_shas":["abc123","def456"]}}"#;
    let parsed: NotesListResponse = serde_json::from_str(body).unwrap();
    assert_eq!(parsed.data.commit_shas[0], "abc123");
    assert_eq!(parsed.data.commit_shas[1], "def456");
}
```

添加 notes_list 空列表和格式错误的 JSON 测试。

**步骤 2：运行测试（先失败）**

运行：`cargo test --package git-ai --lib test_notes_list_response_has_commit_shas -- --nocapture`
预期：失败。

**步骤 3：最小实现**

- 添加用于 list/batch/push 的请求/响应结构
- 重用现有的 `ApiErrorResponse` 用于非 200 处理路径

**步骤 4：重新运行测试**

运行：`cargo test --package git-ai --lib test_notes_list_response_has_commit_shas -- --nocapture`
预期：通过。

**步骤 5：提交**

```bash
git add src/api/types.rs
git commit -m "feat(api): add notes REST request and response types"
```

---

### 任务 3：实现注释 API 客户端模块

**文件：**
- 创建：`src/api/notes_api.rs`
- 修改：`src/api/mod.rs`
- 测试：`src/api/notes_api.rs` 测试

**步骤 1：编写失败的测试**

添加成功解析和非 200 错误解析回退的测试。

**步骤 2：运行测试（先失败）**

运行：`cargo test --package git-ai --lib notes_api -- --nocapture`
预期：失败。

**步骤 3：最小实现**

- 为 `impl ApiClient` 添加方法：
  - `notes_list`
  - `notes_batch_get`
  - `notes_push`
- 使用现有风格：`self.context().post_json(...)`，状态匹配，正文解析，`ApiErrorResponse` 回退
- 使用客户端构造模式：`ApiClient::new(ApiContext::new(None))`

**步骤 4：重新运行测试**

运行：`cargo test --package git-ai --lib notes_api -- --nocapture`
预期：通过。

**步骤 5：提交**

```bash
git add src/api/notes_api.rs src/api/mod.rs src/api/types.rs
git commit -m "feat(api): implement notes REST client methods"
```

---

### 任务 4：REST 分支前的回归安全网（必须在 REST 分支前运行）

**文件：**
- 测试：`tests/integration/internal_machine_commands.rs`
- 测试：`tests/integration/notes_sync_regression.rs`

**步骤 1：添加失败的回归断言**

- 默认模式（`notes_store` 未设置）保持当前 git 行为
- 现有的内部机器命令保留预期的 JSON 语义

**步骤 2：运行定向测试**

运行：`cargo test --package git-ai --test integration test_fetch_and_push_authorship_notes_internal_commands_json -- --nocapture`
运行：`cargo test --package git-ai --test notes_sync_regression -- --nocapture`
预期：断言对齐后通过；如需要修复测试假设。

**步骤 3：提交**

```bash
git add tests/integration/internal_machine_commands.rs tests/integration/notes_sync_regression.rs
git commit -m "test(sync): lock existing git-notes behavior before REST mode"
```

---

### 任务 5：在 sync_authorship 中实现 REST 分支

**文件：**
- 修改：`src/git/sync_authorship.rs`
- 修改：`src/api/notes_api.rs`（如果需要辅助方法）

**步骤 1：编写失败的集成测试**

为以下场景创建失败的测试：
- 空的远程列表 => `NotesExistence::NotFound`
- 远程注释存在 => fetch 返回 `Found`
- 更改的远程/本地注释标识导致更新写入

**步骤 2：最小实现**

- 在 `fetch_authorship_notes` 和 `push_authorship_notes` 中，对 `Config::get().notes_store() == "rest"` 分支
- 从现有的远程名称或 URL 流程解析远程 URL
- 在 REST 调用之前通过 `crate::repo_url::normalize_repo_url` 规范化 URL
- `rest_fetch_notes`：
  1. 调用 list 获取远程 commit_shas
  2. 如果为空 -> `NotFound`
  3. 通过 commit_sha 对比远程/本地
  4. 获取缺失的内容
  5. 通过 `notes_add_batch` 写入
  6. 返回 `Found`
- `rest_push_notes`：
  1. 枚举本地注释（`git notes --ref=ai list` 模式）
  2. 调用 list 获取远程 commit_shas
  3. 通过 commit_sha 对比找出仅本地的注释
  4. 仅推送已更改/缺失的注释

**步骤 3：运行定向测试**

运行：`cargo test --package git-ai --test integration rest_notes_sync -- --nocapture`
预期：通过。

**步骤 4：提交**

```bash
git add src/git/sync_authorship.rs src/api/notes_api.rs
git commit -m "feat(sync): add REST notes fetch/push backend path"
```

---

### 任务 6：添加 REST 集成测试框架和错误契约

**文件：**
- 创建：`tests/integration/rest_test_server.rs`
- 创建：`tests/integration/rest_notes_sync.rs`
- 创建：`tests/integration/rest_notes_errors.rs`
- 修改：`tests/integration/main.rs`

**步骤 1：编写失败的测试**

- 200 空列表 => `NotFound`
- 端点返回 HTTP 404 => 硬错误
- 认证/网络失败 => 硬错误

**步骤 2：实现测试辅助/服务器**

- 添加基于 stdlib `TcpListener` 的轻量级模拟服务器
- 按测试用例路由响应
- 确保测试设置 `GIT_AI_API_BASE_URL` 到模拟服务器

**步骤 3：运行聚焦集成测试**

运行：`cargo test --package git-ai --test integration rest_notes_sync -- --nocapture`
运行：`cargo test --package git-ai --test integration rest_notes_errors -- --nocapture`
预期：通过。

**步骤 4：提交**

```bash
git add tests/integration/rest_test_server.rs tests/integration/rest_notes_sync.rs tests/integration/rest_notes_errors.rs tests/integration/main.rs
git commit -m "test(sync): add REST notes integration and error-contract tests"
```

---

### 任务 7：完整验证门槛

**步骤 1：聚焦测试**

运行：
- `cargo test --package git-ai --test integration test_fetch_and_push_authorship_notes_internal_commands_json -- --nocapture`
- `cargo test --package git-ai --test integration rest_notes_sync -- --nocapture`
- `cargo test --package git-ai --test integration rest_notes_errors -- --nocapture`
- `cargo test --package git-ai --test notes_sync_regression -- --nocapture`

**步骤 2：质量检查**

运行：
- `cargo fmt -- --check`
- `cargo clippy`
- `cargo build`

**步骤 3：完整测试套件**

运行：`cargo test -- --test-threads=8`

**步骤 4：提交**

```bash
git add -A
git commit -m "chore: pass fmt clippy build and tests for REST notes store"
```

---

## 服务端交接说明（单独仓库）

- 键为 `(repo_url_normalized, commit_sha)`。
- 在服务器上插入或查询之前规范化仓库 URL。
- 对于插入更新，使用方言感知路径（`on_conflict_do_update` 可用时；用于 Oracle 迁移的回退方法）。
- 使用现有的 bearer/api-key 约定进行认证。

---

## 完成定义

- `notes_store` 完全在运行时配置 + CLI config 命令 + 测试补丁中可用。
- REST 模式仅更改远程同步通道；本地注释存储保持 git-notes。
- 默认模式保持当前 git 行为，无回归。
- 所有测试和质量门槛通过。

---

计划完成并保存到 `docs/plans/2026-03-29-rest-notes-store-implementation-plan.md`。两个执行选项：

**1. 子代理驱动（本次会话）** - 我为每个任务分派新的子代理，在任务之间审查，快速迭代

**2. 并行会话（单独）** - 用 executing-plans 打开新会话，带检查点的批量执行

选择哪种方法？
