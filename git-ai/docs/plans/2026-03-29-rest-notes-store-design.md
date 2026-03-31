# REST 注释存储设计

## 问题

某些 git 远程托管平台（如阿里云 Codeup）不支持 `git notes` 的推送/拉取。这阻止了 git-ai 通过标准的 `git push/fetch refs/notes/ai` 机制在不同克隆之间同步作者注释。

## 解决方案

添加一个可配置的 REST API 后端来实现远程注释同步。本地 git 注释操作保持不变——仅在配置时，将远程同步通道（push/fetch）替换为 REST API 调用。

## 架构

```
                          notes_store: "git" (默认)
                         ┌──────────────────────────────┐
                         │  git fetch/push refs/notes/ai │
                         └──────────────────────────────┘
                        /
sync_authorship.rs ────<
                        \
                         ┌──────────────────────────────┐
                         │  REST API (api_base_url)      │
                         └──────────────────────────────┘
                          notes_store: "rest"
```

**核心原则：** 本地 git 注释读/写（add、show、search、merge）完全不受影响。只有 `sync_authorship.rs` 中的 `fetch_authorship_notes()` 和 `push_authorship_notes()` 增加 REST 代码路径。

---

## 服务端（Python + Flask + SQLAlchemy）

### 技术栈

- **语言：** Python 3.10+
- **框架：** Flask
- **ORM：** SQLAlchemy
- **数据库：** SQLite（初始），Oracle（未来迁移）
- **ID 生成：** xid（时间有序的全局唯一 ID）
- **部署：** SaaS（托管）或自托管（私有部署）

### 数据模型

```sql
CREATE TABLE authorship_notes (
    id                  TEXT PRIMARY KEY,       -- xid
    repo_url            TEXT NOT NULL,          -- 仓库远程 URL
    branch              TEXT NOT NULL,          -- 分支名称
    commit_sha          TEXT NOT NULL,          -- 当前提交 SHA（40 字符）
    note_blob_oid       TEXT NOT NULL,          -- note_blob_oid
    author_name         TEXT NOT NULL,          -- 提交者名称
    author_email        TEXT NOT NULL,          -- 提交者邮箱
    note_content        TEXT NOT NULL,          -- AuthorshipLog 原始内容
    created_at          INTEGER NOT NULL,       -- unix 时间戳
    updated_at          INTEGER NOT NULL,       -- unix 时间戳
    UNIQUE(repo_url, commit_sha)
);

CREATE INDEX idx_authorship_notes_repo_url ON authorship_notes(repo_url);
CREATE INDEX idx_authorship_notes_repo_commit ON authorship_notes(repo_url, commit_sha);
```

### REST API 端点

所有端点都需要通过现有机制进行身份验证：
- `Authorization: Bearer {token}` (OAuth)
- 或 `X-API-Key: {key}` + `X-Author-Identity: {name <email>}`

#### PUT /worker/notes

创建或更新单个注释。

**请求：**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git",
  "branch": "main",
  "commit_sha": "abc123def456...",
  "note_blob_oid": "abdfadsfadfa...",
  "author_name": "John Doe",
  "author_email": "john@example.com",
  "content": "<authorship log content>"
}
```

**响应 (200)：**
```json
{
  "ok": true,
  "data": { "id": "ctg3h1e..." }
}
```

#### POST /worker/notes/get

通过 repo_url + commit_sha 获取单个注释。

**请求：**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git",
  "commit_sha": "abc123def456..."
}
```

**响应 (200)：**
```json
{
  "ok": true,
  "data": {
    "id": "ctg3h1e...",
    "commit_sha": "abc123def456...",
    "branch": "main",
    "author_name": "John Doe",
    "author_email": "john@example.com",
    "content": "<authorship log content>",
    "created_at": 1711670400,
    "updated_at": 1711670400
  }
}
```

**响应 (404)：**
```json
{
  "ok": false,
  "error": "note not found"
}
```

#### POST /worker/notes/batch

批量获取多个提交 SHA 的注释。

**请求：**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git",
  "commit_shas": ["abc123...", "def456...", "789ghi..."]
}
```

**响应 (200)：**
```json
{
  "ok": true,
  "data": {
    "notes": [
      {
        "commit_sha": "abc123...",
        "content": "<authorship log content>"
      },
      {
        "commit_sha": "def456...",
        "content": "<authorship log content>"
      }
    ],
    "missing": ["789ghi..."]
  }
}
```

#### POST /worker/notes/push

批量推送（创建/更新）注释。

**请求：**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git",
  "notes": [
    {
      "branch": "main",
      "commit_sha": "abc123...",
      "note_blob_oid": "abc3434",
      "author_name": "John Doe",
      "author_email": "john@example.com",
      "content": "<authorship log content>"
    }
  ]
}
```

**响应 (200)：**
```json
{
  "ok": true,
  "data": { "created": 3, "updated": 1 }
}
```

#### POST /worker/notes/list

列出给定仓库中所有有注释的提交 SHA。

**请求：**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git"
}
```

**响应 (200)：**
```json
{
  "ok": true,
  "data": {
    "commit_shas": ["abc123...", "def456...", ...]
  }
}
```

#### POST /worker/notes/search

在注释内容中进行全文搜索。

**请求：**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git",
  "pattern": "cursor"
}
```

**响应 (200)：**
```json
{
  "ok": true,
  "data": {
    "commit_shas": ["abc123...", "def456..."]
  }
}
```

### 错误响应格式

所有错误遵循：
```json
{
  "ok": false,
  "error": "<human-readable message>"
}
```

HTTP 状态码：400（错误请求）、401（未授权）、404（未找到）、500（服务器错误）。

---

## 客户端（Rust 更改）

### 配置变更

在 `config.rs` 中添加一个字段：

```rust
// Config 中的新字段
notes_store: Option<String>  // "git" (默认) | "rest"
```

环境变量覆盖：`GIT_AI_NOTES_STORE`

REST API URL 重用现有的 `api_base_url` 配置（默认：`https://usegitai.com`）。

### 新文件：src/api/notes_api.rs (~100 行)

封装 REST API 调用的两个公共函数：

```rust
/// 从 REST API 获取注释并写入本地 git 注释。
/// 如果获取到任何注释，返回 NotesExistence::Found。
pub fn rest_fetch_notes(
    repo: &Repository,
    api: &ApiClient,
    repo_url: &str,
) -> Result<NotesExistence, GitAiError>

/// 读取本地 git 注释并推送到 REST API。
pub fn rest_push_notes(
    repo: &Repository,
    api: &ApiClient,
    repo_url: &str,
) -> Result<(), GitAiError>
```

**rest_fetch_notes 流程：**
1. 调用 `POST /worker/notes/list` 获取远程提交 SHA
2. 与本地注释对比（使用 `refs::note_blob_oids_for_commits()`）
3. 对缺失的 SHA 调用 `POST /worker/notes/batch`
4. 通过 `refs::notes_add_batch` 将获取的注释写入本地 git 注释

**rest_push_notes 流程：**
1. 列出本地有注释的提交（使用 git log + refs::note_blob_oids_for_commits）
2. 调用 `POST /worker/notes/list` 获取远程提交 SHA
3. 对比找出仅本地的注释
4. 读取每条注释的内容（通过 `refs::show_authorship_note()`）
5. 从 git 提交元数据收集 branch、author_name、author_email
6. 调用 `POST /worker/notes/push` 上传

### 修改文件：src/git/sync_authorship.rs

在现有函数中添加 REST 分支：

```rust
pub fn fetch_authorship_notes(
    repository: &Repository,
    remote_name: &str,
) -> Result<NotesExistence, GitAiError> {
    let config = Config::get();
    if config.notes_store() == "rest" {
        let api = ApiClient::new();
        let repo_url = repository.remote_url(remote_name)?;
        return rest_fetch_notes(repository, &api, &repo_url);
    }
    // ... 现有的 git fetch 逻辑不变 ...
}

pub fn push_authorship_notes(
    repository: &Repository,
    remote_name: &str,
) -> Result<(), GitAiError> {
    let config = Config::get();
    if config.notes_store() == "rest" {
        let api = ApiClient::new();
        let repo_url = repository.remote_url(remote_name)?;
        return rest_push_notes(repository, &api, &repo_url);
    }
    // ... 现有的 git push 逻辑不变 ...
}
```

### 文件变更摘要

| 文件 | 变更 |
|------|------|
| `config.rs` | 添加 `notes_store` 字段 + getter + env 覆盖 |
| `sync_authorship.rs` | 在 fetch/push 函数顶部添加 REST 分支 |
| `api/notes_api.rs` | **新文件** — REST fetch/push 实现 |
| `api/mod.rs` | 添加 `pub mod notes_api;` |

客户端端总变更：~120 行新代码，~10 行修改。

## 认证

重用现有的 git-ai 认证机制：
- 通过 `Authorization: Bearer {token}` 的 OAuth 令牌
- 通过 `X-API-Key: {key}` + `X-Author-Identity: {name <email>}` 的 API 密钥

服务器根据与 git-ai 主 API 相同的认证后端验证令牌。

---

## 非目标

- 不更改本地 git 注释操作（add、show、search、merge）
- 不更改 hook 调度逻辑（push_hooks、fetch_hooks、clone_hooks）
- 不支持双重同步（同时使用 git + REST）
- REST 模式不支持离线队列/重试（可能稍后添加）
