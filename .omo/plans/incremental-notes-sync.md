# 增量拉取 Authorship Notes 设计文档

## 背景

当前 `rest_fetch_authorship_notes` 每次调用 `authorship_notes_list` 都返回该仓库全量 commit_shas。随着仓库提交数增长，list 响应体线性膨胀，即使大多数 notes 本地已有，每次 fetch 仍需传输全量数据。

## 目标

通过在 push 时记录 `commit_time`，并在 list 时传入游标，实现增量拉取，减少不必要的数据传输。

---

## 方案：commit_time 游标

### 核心思路

1. Push 时：每条 note 附带对应 commit 的 committer timestamp（`commit_time`），存入服务端数据库
2. Fetch 时：客户端从本地 git log 推导出游标（本地已有 notes 中最大的 commit_time），减去 24h buffer 后传给 list API
3. List API：只返回 `commit_time >= since_commit_time` 的 commit_shas

### 游标推导逻辑

```
since_commit_time = max(local noted commits' commit_time) - 86400s (24h buffer)
```

buffer 的作用：防止时钟漂移或同一秒内多个 commit 导致边界遗漏。

首次同步（本地无 notes）：`since_commit_time` 为 None，走全量拉取。

---

## 改动范围

### 客户端（Rust）

#### 1. `git-ai/src/git/refs.rs` — `get_commits_with_notes_from_list`

format string 加入 `%ct`（committer timestamp）：

```
before: "--pretty=format:%H%n%an%n%ae"
after:  "--pretty=format:%H%n%an%n%ae%n%ct"
```

解析逻辑：每个 commit 块从 3 行变为 4 行，多读一行存入 `commit_times: HashMap<String, i64>`。

`CommitAuthorship` 两个 variant 均增加字段：

```rust
pub enum CommitAuthorship {
    NoLog { sha: String, git_author: String, commit_time: i64 },
    Log   { sha: String, git_author: String, commit_time: i64, authorship_log: AuthorshipLog },
}
```

#### 2. `git-ai/src/api/types.rs`

`AuthorshipNotesPushItem` 增加字段：

```rust
pub commit_time: i64,  // committer timestamp (Unix seconds)
```

`AuthorshipNotesListRequest` 增加可选字段：

```rust
pub since_commit_time: Option<i64>,
```

#### 3. `git-ai/src/git/sync_authorship.rs` — `rest_push_notes`

从 `CommitAuthorship` 取 `commit_time`，填入 `AuthorshipNotesPushItem`。

#### 4. `git-ai/src/git/sync_authorship.rs` — `rest_fetch_authorship_notes`

fetch 前推导游标：

```rust
// 取本地所有 noted commits 的 commit_time，找最大值，减去 24h buffer
let since_commit_time = local_max_commit_time().map(|t| t - 86400);
```

将 `since_commit_time` 传入 `AuthorshipNotesListRequest`。

获取本地 commit_time 的方式：对 `list_local_authorship_notes_with_blob_oid` 返回的 commit_shas 执行一次 `git log --no-walk --pretty=format:%H%n%ct`，取最大值。

---

### 服务端（Python）

#### 1. `core/database/models.py` — `AuthorshipNotes`

增加列：

```python
commit_time: Mapped[int] = mapped_column(BigInteger, nullable=True, index=True)
```

加索引：`Index("idx_authorship_notes_repo_commit_time", "repo_url", "commit_time")`

#### 2. `core/database/authorship_notes_db.py`

`batch_push_notes`：存储 `commit_time`（字段可选，旧客户端不传时为 None）。

`list_notes`：增加 `since_commit_time: Optional[int] = None` 参数，有值时加 `WHERE commit_time >= since_commit_time` 过滤。

#### 3. `api/routes/authorship_notes.py` — `list_notes` route

从请求体读取 `since_commit_time`（可选），传给 service。

#### 4. DB Migration

新增列和索引（SQLite 用 `ALTER TABLE`，PostgreSQL 同）：

```sql
ALTER TABLE authorship_notes ADD COLUMN commit_time BIGINT;
CREATE INDEX idx_authorship_notes_repo_commit_time ON authorship_notes(repo_url, commit_time);
```

---

## 边界场景

| 场景 | 处理方式 |
|------|----------|
| 首次同步，本地无 notes | `since_commit_time = None`，全量拉取 |
| 旧客户端 push（无 commit_time） | `commit_time` 列为 NULL，list 过滤时 NULL 行不会被 `>= since` 匹配，旧数据不影响增量逻辑 |
| 旧服务端（不支持 since 参数） | 服务端忽略未知字段，退化为全量返回，客户端行为不变 |
| 给旧 commit 补录 note（commit_time 远小于游标） | 24h buffer 可覆盖正常延迟；极端补录场景（数月前的 commit）需手动触发全量同步（超出本文档范围） |

---

## 数据流对比

**改造前：**
```
list(repo_url) → 全量 N 个 sha
本地对比 → 找出 missing M 个
batch_get(M shas) → 拉取内容
```

**改造后：**
```
推导 since_commit_time（本地 max commit_time - 24h）
list(repo_url, since_commit_time) → 增量 K 个 sha（K << N）
本地对比 → 找出 missing M' 个（M' <= K）
batch_get(M' shas) → 拉取内容
```

---

## 文件改动汇总

| 文件 | 改动类型 |
|------|----------|
| `git-ai/src/git/refs.rs` | 修改 format string，扩展 CommitAuthorship |
| `git-ai/src/api/types.rs` | 增加字段 |
| `git-ai/src/git/sync_authorship.rs` | 推导游标，传参 |
| `core/database/models.py` | 增加列 |
| `core/database/authorship_notes_db.py` | 存储/过滤 commit_time |
| `api/routes/authorship_notes.py` | 读取 since_commit_time |
| `sql/` | migration SQL |
