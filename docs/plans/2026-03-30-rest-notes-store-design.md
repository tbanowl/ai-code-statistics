# REST Notes Store API 设计文档

**日期**: 2026-03-30
**版本**: 2.0
**状态**: 已批准

---

## 1. 概述

### 1.1 问题

某些 git 远程托管平台（如阿里云 Codeup）不支持 `git notes` 的推送/拉取。这阻止了 git-ai 通过标准的 `git push/fetch refs/notes/ai` 机制在不同克隆之间同步作者注释。

### 1.2 解决方案

添加一个可配置的 REST API 后端来实现远程注释同步。本地 git 注释操作保持不变——仅在配置时，将远程同步通道（push/fetch）替换为 REST API 调用。

### 1.3 路由前缀

使用 `/worker/notes` 作为 API 路由前缀（遵循项目规范）。

---

## 2. 服务端（Python + Flask + SQLAlchemy）

### 2.1 技术栈

- **语言**: Python 3.10+
- **框架**: Flask
- **ORM**: SQLAlchemy
- **数据库**: SQLite（初始），PostgreSQL/MySQL（未来）
- **ID 生成**: XID（时间有序的全局唯一 ID）
- **部署**: 集成到 git-ai-code-metrics 服务中

### 2.2 数据模型

```sql
CREATE TABLE authorship_notes (
    id                  VARCHAR(20) PRIMARY KEY,       -- xid
    repo_url            TEXT NOT NULL,                  -- 仓库远程 URL
    branch              TEXT NOT NULL,                  -- 分支名称
    commit_sha          TEXT NOT NULL,                  -- 当前提交 SHA（40 字符）
    original_commit_sha TEXT,                           -- rebase/cherry-pick 之前的原始提交 SHA
    author_name         TEXT NOT NULL,                  -- 提交者名称
    author_email        TEXT NOT NULL,                  -- 提交者邮箱
    note_content        TEXT NOT NULL,                  -- AuthorshipLog 原始内容
    created_at          BIGINT NOT NULL,                -- unix 时间戳（毫秒）
    updated_at          BIGINT NOT NULL,                -- unix 时间戳（毫秒）
    UNIQUE(repo_url, commit_sha)
);

CREATE INDEX idx_authorship_notes_repo_url ON authorship_notes(repo_url);
CREATE INDEX idx_authorship_notes_repo_commit ON authorship_notes(repo_url, commit_sha);
```

### 2.3 SQLAlchemy 模型

```python
from sqlalchemy import String, BigInteger, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

class AuthorshipNotes(Base):
    """作者注释表"""

    __tablename__ = "authorship_notes"

    __table_args__ = (
        UniqueConstraint("repo_url", "commit_sha"),
        Index("idx_authorship_notes_repo_url", "repo_url"),
        Index("idx_authorship_notes_repo_commit", "repo_url", "commit_sha"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(Text, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    original_commit_sha: Mapped[str] = mapped_column(String(40), nullable=True)
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    author_email: Mapped[str] = mapped_column(Text, nullable=False)
    note_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )
```

---

## 3. REST API 端点

### 3.1 端点列表

| 方法 | 端点 | 描述 |
|------|------|------|
| PUT | `/worker/notes` | 创建或更新单个注释 |
| POST | `/worker/notes/get` | 获取单个注释 |
| POST | `/worker/notes/batch` | 批量获取注释 |
| POST | `/worker/notes/push` | 批量推送（创建/更新）注释 |
| POST | `/worker/notes/list` | 列出仓库中所有有注释的提交 SHA |
| POST | `/worker/notes/search` | 搜索注释内容 |

### 3.2 认证

所有端点都需要通过现有机制进行身份验证：
- `Authorization: Bearer {token}` (OAuth)
- 或 `X-API-Key: {key}` + `X-Author-Identity: {name <email>}`

### 3.3 错误响应格式

所有错误遵循统一格式：

```json
{
  "ok": false,
  "error": "<human-readable message>"
}
```

HTTP 状态码：
- 400: 错误请求
- 401: 未授权
- 404: 未找到
- 500: 服务器错误

---

## 4. API 端点详细说明

### 4.1 PUT /worker/notes

创建或更新单个注释。

**请求:**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git",
  "branch": "main",
  "commit_sha": "abc123def456...",
  "original_commit_sha": null,
  "author_name": "John Doe",
  "author_email": "john@example.com",
  "content": "<authorship log content>"
}
```

**响应 (200):**
```json
{
  "ok": true,
  "data": { "id": "ctg3h1e..." }
}
```

---

### 4.2 POST /worker/notes/get

通过 repo_url + commit_sha 获取单个注释。

**请求:**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git",
  "commit_sha": "abc123def456..."
}
```

**响应 (200):**
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
    "created_at": 1711670400000,
    "updated_at": 1711670400000
  }
}
```

**响应 (404):**
```json
{
  "ok": false,
  "error": "note not found"
}
```

---

### 4.3 POST /worker/notes/batch

批量获取多个提交 SHA 的注释。

**请求:**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git",
  "commit_shas": ["abc123...", "def456...", "789ghi..."]
}
```

**响应 (200):**
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

---

### 4.4 POST /worker/notes/push

批量推送（创建/更新）注释。

**请求:**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git",
  "notes": [
    {
      "branch": "main",
      "commit_sha": "abc123...",
      "original_commit_sha": null,
      "author_name": "John Doe",
      "author_email": "john@example.com",
      "content": "<authorship log content>"
    }
  ]
}
```

**响应 (200):**
```json
{
  "ok": true,
  "data": { "created": 3, "updated": 1 }
}
```

---

### 4.5 POST /worker/notes/list

列出给定仓库中所有有注释的提交 SHA。

**请求:**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git"
}
```

**响应 (200):**
```json
{
  "ok": true,
  "data": {
    "commit_shas": ["abc123...", "def456...", ...]
  }
}
```

---

### 4.6 POST /worker/notes/search

在注释内容中进行全文搜索。

**请求:**
```json
{
  "repo_url": "https://codeup.aliyun.com/org/repo.git",
  "pattern": "cursor"
}
```

**响应 (200):**
```json
{
  "ok": true,
  "data": {
    "commit_shas": ["abc123...", "def456..."]
  }
}
```

---

## 5. 项目结构

```
git-ai-code-metrics/
├── api/
│   └── routes/
│       └── notes_rest.py          # Notes REST API 蓝图
├── core/
│   ├── database/
│   │   └── models.py              # 添加 AuthorshipNotes 模型
│   └── services/
│       └── notes_rest_service.py  # Notes 服务层
├── sql/
│   └── authorship_notes_schema_sqlite.sql  # 数据库表结构
└── app.py                         # 注册蓝图
```

---

## 6. 客户端集成（Rust）

### 6.1 配置

在 `config.rs` 中添加：

```rust
notes_store: Option<String>  // "git" (默认) | "rest"
```

环境变量：`GIT_AI_NOTES_STORE`

### 6.2 API 客户端封装

```rust
pub fn rest_fetch_notes(
    repo: &Repository,
    api: &ApiClient,
    repo_url: &str,
) -> Result<NotesExistence, GitAiError>

pub fn rest_push_notes(
    repo: &Repository,
    api: &ApiClient,
    repo_url: &str,
) -> Result<(), GitAiError>
```

**rest_fetch_notes 流程:**
1. 调用 `POST /worker/notes/list` 获取远程提交 SHA
2. 与本地注释对比
3. 缺失的 SHA 调用 `POST /worker/notes/batch`
4. 将获取的注释写入本地 git 注释

**rest_push_notes 流程:**
1. 列出本地有注释的提交
2. 调用 `POST /worker/notes/list` 获取远程提交 SHA
3. 对比找出仅本地的注释
4. 调用 `POST /worker/notes/push` 上传

---

## 7. 非目标

- 不更改本地 git 注释操作（add、show、search、merge）
- 不更改 hook 调度逻辑
- 不支持双重同步（同时使用 git + REST）
- REST 模式不支持离线队列/重试（未来可扩展）
