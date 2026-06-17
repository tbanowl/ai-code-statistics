# Authorship Notes Rewrite API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the REST Authorship Notes rewrite API so rewritten commits can supersede prior active notes atomically and idempotently.

**Architecture:** Extend the existing Flask/SQLAlchemy REST Notes stack. The database layer owns atomic rewrite transactions, request hashing, active-note filtering, and rewrite edge persistence; the service layer normalizes repo URLs and forwards calls; the route layer handles request validation and error status mapping while preserving the `/worker/notes` compatibility prefix.

**Tech Stack:** Python 3, Flask, SQLAlchemy 2.0 ORM, SQLite test databases, MySQL DDL and migration SQL, Pytest.

---

## File Structure

- Modify: `core/database/models.py`
  - Add `status`, `superseded_by`, `superseded_at`, and `superseded_rewrite_id` to `AuthorshipNotes`.
  - Add `AuthorshipNoteRewrite` and `AuthorshipNoteRewriteMapping`.
  - Add indexes for active-note filtering and rewrite lookup.
- Modify: `core/database/authorship_notes_db.py`
  - Add active-note filter helper, deterministic rewrite request hash helper, rewrite exceptions, read filtering, and `rewrite_notes()`.
- Modify: `core/services/notes_service.py`
  - Add `include_superseded` passthroughs and `rewrite_notes()`.
- Modify: `api/routes/authorship_notes.py`
  - Add `include_superseded` parsing for read endpoints.
  - Add `POST /rewrite` on both notes prefixes.
- Modify: `core/database/stats_db.py`
  - Make `require_authorship_notes` checks count only active notes.
- Modify: `core/database/blame_stats_db.py`
  - Make note batch lookups count only active notes.
- Modify: `core/services/blame_stats_service.py`
  - Make direct note lookups count only active notes.
- Modify: `sql/metrics_schema_mysql.sql`
  - Add new columns and rewrite tables for new installs.
- Create: `sql/authorship_notes_rewrite_migration_mysql.sql`
  - Add the same schema changes for existing MySQL databases.
- Modify: `docs/swagger/api/notes-rest.yaml`
  - Document canonical and compatibility rewrite endpoints.
- Test: `tests/unit/test_models/test_notes.py`
- Test: `tests/unit/test_services/test_notes_rest_service.py`
- Test: `tests/integration/test_notes_rest_api.py`
- Test: `tests/unit/test_database/test_blame_stats_db.py`
- Test: `tests/integration/test_dimensions_db.py`

## Task 1: Schema And ORM Models

**Files:**
- Modify: `core/database/models.py`
- Modify: `sql/metrics_schema_mysql.sql`
- Create: `sql/authorship_notes_rewrite_migration_mysql.sql`
- Test: `tests/unit/test_models/test_notes.py`

- [ ] **Step 1: Write failing model tests**

Update `tests/unit/test_models/test_notes.py` imports:

```python
from core.database.models import (
    AuthorshipNoteRewrite,
    AuthorshipNoteRewriteMapping,
    AuthorshipNotes,
)
```

Replace `test_authorship_notes_model_columns()` with:

```python
def test_authorship_notes_model_columns():
    columns = {c.name for c in AuthorshipNotes.__table__.columns}

    expected_columns = {
        "id",
        "repo_url",
        "branch",
        "commit_sha",
        "note_blob_oid",
        "author_name",
        "author_email",
        "note_content",
        "commit_time",
        "commit_date",
        "content_hash",
        "change_seq",
        "status",
        "superseded_by",
        "superseded_at",
        "superseded_rewrite_id",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(columns), (
        f"Missing columns: {expected_columns - columns}"
    )
```

Replace `test_authorship_notes_indexes()` with:

```python
def test_authorship_notes_indexes():
    indexes = {i.name for i in getattr(AuthorshipNotes.__table__, "indexes", set())}

    assert "idx_authorship_notes_repo_url" in indexes
    assert "idx_authorship_notes_repo_commit" in indexes
    assert "idx_authorship_notes_repo_change_seq" in indexes
    assert "idx_authorship_notes_repo_status" in indexes
    assert "idx_authorship_notes_superseded_rewrite" in indexes
```

Add:

```python
def test_authorship_note_rewrite_model_columns():
    columns = {c.name for c in AuthorshipNoteRewrite.__table__.columns}

    expected_columns = {
        "id",
        "rewrite_id",
        "repo_url",
        "operation",
        "branch",
        "original_head",
        "new_head",
        "request_hash",
        "created_at",
    }

    assert expected_columns.issubset(columns), (
        f"Missing columns: {expected_columns - columns}"
    )


def test_authorship_note_rewrite_mapping_model_columns():
    columns = {c.name for c in AuthorshipNoteRewriteMapping.__table__.columns}

    expected_columns = {
        "id",
        "rewrite_id",
        "repo_url",
        "source_commit",
        "target_commit",
        "source_note_blob_oid",
        "target_note_blob_oid",
        "target_content_hash",
        "disposition",
        "created_at",
    }

    assert expected_columns.issubset(columns), (
        f"Missing columns: {expected_columns - columns}"
    )
```

- [ ] **Step 2: Run model tests and verify failure**

Run:

```bash
pytest tests/unit/test_models/test_notes.py -v
```

Expected: FAIL because the new model fields and rewrite models do not exist.

- [ ] **Step 3: Add ORM fields and models**

In `core/database/models.py`, replace the `AuthorshipNotes.__table_args__` tuple with:

```python
    __table_args__ = (
        UniqueConstraint("repo_url", "commit_sha"),
        Index("idx_authorship_notes_repo_url", "repo_url"),
        Index("idx_authorship_notes_repo_commit", "repo_url", "commit_sha"),
        Index("idx_authorship_notes_repo_change_seq", "repo_url", "change_seq"),
        Index("idx_authorship_notes_repo_status", "repo_url", "status"),
        Index(
            "idx_authorship_notes_superseded_rewrite",
            "repo_url",
            "superseded_rewrite_id",
        ),
    )
```

Add these fields after `change_seq`:

```python
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    superseded_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    superseded_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    superseded_rewrite_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

Add the rewrite models after `AuthorshipNotesSeq`:

```python
class AuthorshipNoteRewrite(ModelBase):
    """Authorship note rewrite request metadata."""

    __tablename__ = "authorship_note_rewrites"

    __table_args__ = (
        UniqueConstraint("rewrite_id"),
        Index("idx_authorship_note_rewrites_repo", "repo_url"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    rewrite_id: Mapped[str] = mapped_column(String(200), nullable=False)
    repo_url: Mapped[str] = mapped_column(String, nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    original_head: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_head: Mapped[str | None] = mapped_column(String(40), nullable=True)
    request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)


class AuthorshipNoteRewriteMapping(ModelBase):
    """Authorship note source-to-target rewrite edge."""

    __tablename__ = "authorship_note_rewrite_mappings"

    __table_args__ = (
        UniqueConstraint("repo_url", "source_commit", "target_commit", "rewrite_id"),
        Index(
            "idx_authorship_note_rewrite_source",
            "repo_url",
            "source_commit",
        ),
        Index(
            "idx_authorship_note_rewrite_target",
            "repo_url",
            "target_commit",
        ),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    rewrite_id: Mapped[str] = mapped_column(String(200), nullable=False)
    repo_url: Mapped[str] = mapped_column(String, nullable=False)
    source_commit: Mapped[str] = mapped_column(String(40), nullable=False)
    target_commit: Mapped[str] = mapped_column(String(40), nullable=False)
    source_note_blob_oid: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_note_blob_oid: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    disposition: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
```

- [ ] **Step 4: Update MySQL schema for new installs**

In `sql/metrics_schema_mysql.sql`, add columns to the `authorship_notes` table after `change_seq`:

```sql
    status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'Note 状态：active 或 superseded',
    superseded_by VARCHAR(40) NULL COMMENT '替代当前 note 的目标提交 SHA',
    superseded_at BIGINT NULL COMMENT '被 supersede 的服务器时间戳（毫秒）',
    superseded_rewrite_id VARCHAR(200) NULL COMMENT '执行 supersede 的 rewrite_id',
```

Add indexes to the same table:

```sql
    INDEX idx_authorship_notes_repo_status (repo_url, status),
    INDEX idx_authorship_notes_superseded_rewrite (repo_url, superseded_rewrite_id),
```

Add these tables after `authorship_notes_seq`:

```sql
CREATE TABLE IF NOT EXISTS authorship_note_rewrites (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    rewrite_id VARCHAR(200) NOT NULL COMMENT '客户端幂等 rewrite ID',
    repo_url VARCHAR(400) NOT NULL COMMENT '规范化仓库 URL',
    operation VARCHAR(50) NOT NULL COMMENT 'rewrite 类型',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    original_head VARCHAR(40) NULL COMMENT 'rewrite 前 HEAD',
    new_head VARCHAR(40) NULL COMMENT 'rewrite 后 HEAD',
    request_hash VARCHAR(71) NOT NULL COMMENT '规范化请求体 SHA-256',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    UNIQUE KEY uk_authorship_note_rewrites_rewrite_id (rewrite_id),
    INDEX idx_authorship_note_rewrites_repo (repo_url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Authorship Notes rewrite 请求表';

CREATE TABLE IF NOT EXISTS authorship_note_rewrite_mappings (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    rewrite_id VARCHAR(200) NOT NULL COMMENT '客户端幂等 rewrite ID',
    repo_url VARCHAR(400) NOT NULL COMMENT '规范化仓库 URL',
    source_commit VARCHAR(40) NOT NULL COMMENT '被替代的源提交 SHA',
    target_commit VARCHAR(40) NOT NULL COMMENT '替代后的目标提交 SHA',
    source_note_blob_oid VARCHAR(40) NULL COMMENT '源 note blob oid',
    target_note_blob_oid VARCHAR(40) NULL COMMENT '目标 note blob oid',
    target_content_hash VARCHAR(71) NOT NULL COMMENT '目标 note 内容 SHA-256',
    disposition VARCHAR(50) NOT NULL COMMENT 'rewrite 处置方式',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    UNIQUE KEY uk_authorship_note_rewrite_mapping (repo_url, source_commit, target_commit, rewrite_id),
    INDEX idx_authorship_note_rewrite_source (repo_url, source_commit),
    INDEX idx_authorship_note_rewrite_target (repo_url, target_commit)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Authorship Notes rewrite 映射表';
```

- [ ] **Step 5: Add MySQL migration for existing databases**

Create `sql/authorship_notes_rewrite_migration_mysql.sql`:

```sql
-- Authorship Notes rewrite API migration
--
-- 适用场景：已有 MySQL 数据库已经存在 authorship_notes 表，需要补齐
-- rewrite 状态字段、rewrite 请求表与 rewrite 映射表。
-- 新库建表请使用 metrics_schema_mysql.sql。

ALTER TABLE authorship_notes
    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'Note 状态：active 或 superseded' AFTER change_seq,
    ADD COLUMN superseded_by VARCHAR(40) NULL COMMENT '替代当前 note 的目标提交 SHA' AFTER status,
    ADD COLUMN superseded_at BIGINT NULL COMMENT '被 supersede 的服务器时间戳（毫秒）' AFTER superseded_by,
    ADD COLUMN superseded_rewrite_id VARCHAR(200) NULL COMMENT '执行 supersede 的 rewrite_id' AFTER superseded_at,
    ADD INDEX idx_authorship_notes_repo_status (repo_url, status),
    ADD INDEX idx_authorship_notes_superseded_rewrite (repo_url, superseded_rewrite_id);

CREATE TABLE IF NOT EXISTS authorship_note_rewrites (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    rewrite_id VARCHAR(200) NOT NULL COMMENT '客户端幂等 rewrite ID',
    repo_url VARCHAR(400) NOT NULL COMMENT '规范化仓库 URL',
    operation VARCHAR(50) NOT NULL COMMENT 'rewrite 类型',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    original_head VARCHAR(40) NULL COMMENT 'rewrite 前 HEAD',
    new_head VARCHAR(40) NULL COMMENT 'rewrite 后 HEAD',
    request_hash VARCHAR(71) NOT NULL COMMENT '规范化请求体 SHA-256',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    UNIQUE KEY uk_authorship_note_rewrites_rewrite_id (rewrite_id),
    INDEX idx_authorship_note_rewrites_repo (repo_url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Authorship Notes rewrite 请求表';

CREATE TABLE IF NOT EXISTS authorship_note_rewrite_mappings (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    rewrite_id VARCHAR(200) NOT NULL COMMENT '客户端幂等 rewrite ID',
    repo_url VARCHAR(400) NOT NULL COMMENT '规范化仓库 URL',
    source_commit VARCHAR(40) NOT NULL COMMENT '被替代的源提交 SHA',
    target_commit VARCHAR(40) NOT NULL COMMENT '替代后的目标提交 SHA',
    source_note_blob_oid VARCHAR(40) NULL COMMENT '源 note blob oid',
    target_note_blob_oid VARCHAR(40) NULL COMMENT '目标 note blob oid',
    target_content_hash VARCHAR(71) NOT NULL COMMENT '目标 note 内容 SHA-256',
    disposition VARCHAR(50) NOT NULL COMMENT 'rewrite 处置方式',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    UNIQUE KEY uk_authorship_note_rewrite_mapping (repo_url, source_commit, target_commit, rewrite_id),
    INDEX idx_authorship_note_rewrite_source (repo_url, source_commit),
    INDEX idx_authorship_note_rewrite_target (repo_url, target_commit)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Authorship Notes rewrite 映射表';
```

- [ ] **Step 6: Run model tests and verify pass**

Run:

```bash
pytest tests/unit/test_models/test_notes.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit schema changes**

```bash
git add core/database/models.py sql/metrics_schema_mysql.sql sql/authorship_notes_rewrite_migration_mysql.sql tests/unit/test_models/test_notes.py
git commit -m "feat: add authorship notes rewrite schema"
```

## Task 2: Active-Note Read Filtering

**Files:**
- Modify: `core/database/authorship_notes_db.py`
- Modify: `core/services/notes_service.py`
- Modify: `api/routes/authorship_notes.py`
- Test: `tests/unit/test_services/test_notes_rest_service.py`
- Test: `tests/integration/test_notes_rest_api.py`

- [ ] **Step 1: Write failing service tests for active-note filtering**

Append to `tests/unit/test_services/test_notes_rest_service.py`:

```python
from core.database.base import session_scope
from core.database.models import AuthorshipNotes


def mark_note_superseded(service, commit_sha: str):
    with session_scope(service.database.engine) as session:
        note = (
            session.query(AuthorshipNotes)
            .filter(AuthorshipNotes.commit_sha == commit_sha)
            .one()
        )
        note.status = "superseded"
        note.superseded_by = f"{commit_sha}-target"
        note.superseded_rewrite_id = f"rewrite-{commit_sha}"
        note.superseded_at = 1710000000000


def test_get_note_excludes_superseded_by_default(service):
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="source-sha",
        original_commit_sha=None,
        content="source content",
        author_name="Test User",
        author_email="test@example.com",
    )
    mark_note_superseded(service, "source-sha")

    assert service.get_note(
        repo_url="https://github.com/test/repo.git",
        commit_sha="source-sha",
    ) is None

    note = service.get_note(
        repo_url="https://github.com/test/repo.git",
        commit_sha="source-sha",
        include_superseded=True,
    )
    assert note is not None
    assert note.status == "superseded"


def test_batch_list_and_search_exclude_superseded_by_default(service):
    for sha in ["active-sha", "superseded-sha"]:
        service.create_or_update_note(
            repo_url="https://github.com/test/repo.git",
            branch="main",
            commit_sha=sha,
            original_commit_sha=None,
            content=f"shared search content {sha}",
            author_name="Test User",
            author_email="test@example.com",
        )
    mark_note_superseded(service, "superseded-sha")

    batch = service.batch_get_notes(
        repo_url="https://github.com/test/repo.git",
        commit_shas=["active-sha", "superseded-sha"],
    )
    assert {note["commit_sha"] for note in batch["notes"]} == {"active-sha"}
    assert "superseded-sha" in batch["missing"]

    batch_with_audit = service.batch_get_notes(
        repo_url="https://github.com/test/repo.git",
        commit_shas=["active-sha", "superseded-sha"],
        include_superseded=True,
    )
    assert {note["commit_sha"] for note in batch_with_audit["notes"]} == {
        "active-sha",
        "superseded-sha",
    }

    listed = service.list_notes(repo_url="https://github.com/test/repo.git")
    assert listed["commit_shas"] == ["active-sha"]

    listed_with_audit = service.list_notes(
        repo_url="https://github.com/test/repo.git",
        include_superseded=True,
    )
    assert set(listed_with_audit["commit_shas"]) == {"active-sha", "superseded-sha"}

    searched = service.search_notes(
        repo_url="https://github.com/test/repo.git",
        pattern="shared search content",
    )
    assert searched == ["active-sha"]

    searched_with_audit = service.search_notes(
        repo_url="https://github.com/test/repo.git",
        pattern="shared search content",
        include_superseded=True,
    )
    assert set(searched_with_audit) == {"active-sha", "superseded-sha"}
```

- [ ] **Step 2: Run service tests and verify failure**

Run:

```bash
pytest tests/unit/test_services/test_notes_rest_service.py -v
```

Expected: FAIL because read methods do not accept `include_superseded` and do not filter `status`.

- [ ] **Step 3: Add active-note helper and database read filters**

In `core/database/authorship_notes_db.py`, update imports:

```python
import hashlib
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, or_, select
```

Update model imports:

```python
from .models import (
    AuthorshipNoteRewrite,
    AuthorshipNoteRewriteMapping,
    AuthorshipNotes,
    AuthorshipNotesSeq,
    gen_xid,
    now_ts,
)
```

Add helper functions near `normalize_list_limit()`:

```python
def active_authorship_note_filter():
    return or_(AuthorshipNotes.status.is_(None), AuthorshipNotes.status == "active")


def apply_active_filter(stmt, include_superseded: bool):
    if include_superseded:
        return stmt
    return stmt.where(active_authorship_note_filter())
```

Update method signatures:

```python
    def get_note(
        self,
        repo_url: str,
        commit_sha: str,
        include_superseded: bool = False,
    ) -> Optional[AuthorshipNotes]:
```

```python
    def batch_get_notes(
        self,
        repo_url: str,
        commit_shas: List[str],
        include_superseded: bool = False,
    ) -> Dict[str, List]:
```

```python
    def list_notes(
        self,
        repo_url: str,
        since_commit_time: int | None = None,
        since_change_seq: int | None = None,
        limit: int | None = None,
        include_superseded: bool = False,
    ) -> Dict[str, Any]:
```

```python
    def search_notes(
        self,
        repo_url: str,
        pattern: str,
        include_superseded: bool = False,
    ) -> List[str]:
```

Apply `apply_active_filter(stmt, include_superseded)` after each base `select(AuthorshipNotes)` or `select(AuthorshipNotes.commit_sha)` in these methods.

Add `status` to batch and list response items:

```python
                    "status": note.status,
                    "superseded_by": note.superseded_by,
                    "superseded_rewrite_id": note.superseded_rewrite_id,
```

- [ ] **Step 4: Add service passthroughs**

Update `core/services/notes_service.py` signatures and calls:

```python
    def get_note(
        self,
        repo_url: str,
        commit_sha: str,
        include_superseded: bool = False,
    ):
        repo_url = normalize_repo_url(repo_url)
        return self.database.get_note(
            repo_url=repo_url,
            commit_sha=commit_sha,
            include_superseded=include_superseded,
        )
```

```python
    def batch_get_notes(
        self,
        repo_url: str,
        commit_shas: list,
        include_superseded: bool = False,
    ):
        repo_url = normalize_repo_url(repo_url)
        return self.database.batch_get_notes(
            repo_url=repo_url,
            commit_shas=commit_shas,
            include_superseded=include_superseded,
        )
```

```python
    def list_notes(
        self,
        repo_url: str,
        since_commit_time: int | None = None,
        since_change_seq: int | None = None,
        limit: int | None = None,
        include_superseded: bool = False,
    ):
        repo_url = normalize_repo_url(repo_url)
        return self.database.list_notes(
            repo_url=repo_url,
            since_commit_time=since_commit_time,
            since_change_seq=since_change_seq,
            limit=limit,
            include_superseded=include_superseded,
        )
```

```python
    def search_notes(
        self,
        repo_url: str,
        pattern: str,
        include_superseded: bool = False,
    ):
        repo_url = normalize_repo_url(repo_url)
        return self.database.search_notes(
            repo_url=repo_url,
            pattern=pattern,
            include_superseded=include_superseded,
        )
```

- [ ] **Step 5: Add route parsing**

In `api/routes/authorship_notes.py`, add:

```python
def optional_bool(payload, field):
    value = payload.get(field)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise ValueError(field)
```

Use it in `/get`, `/batch`, `/list`, and `/search`:

```python
include_superseded = optional_bool(payload, "include_superseded")
```

Pass `include_superseded=include_superseded` into service calls. In `/get`, include audit fields in the response:

```python
                "status": note.status,
                "superseded_by": note.superseded_by,
                "superseded_at": note.superseded_at,
                "superseded_rewrite_id": note.superseded_rewrite_id,
```

- [ ] **Step 6: Run read filtering tests and verify pass**

Run:

```bash
pytest tests/unit/test_services/test_notes_rest_service.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit read filtering changes**

```bash
git add core/database/authorship_notes_db.py core/services/notes_service.py api/routes/authorship_notes.py tests/unit/test_services/test_notes_rest_service.py
git commit -m "feat: filter superseded authorship notes"
```

## Task 3: Rewrite Database And Service Semantics

**Files:**
- Modify: `core/database/authorship_notes_db.py`
- Modify: `core/services/notes_service.py`
- Test: `tests/unit/test_services/test_notes_rest_service.py`

- [ ] **Step 1: Write failing service tests for rewrite semantics**

Append to `tests/unit/test_services/test_notes_rest_service.py`:

```python
import pytest
from core.database.authorship_notes_db import (
    RewriteIdConflictError,
    compute_rewrite_request_hash,
)


def rewrite_payload(content: str = "target content"):
    return {
        "repo_url": "https://github.com/test/repo.git",
        "rewrite_id": "rewrite-1",
        "operation": "rebase_conflict_manual_commit",
        "branch": "main",
        "original_head": "source-sha",
        "new_head": "target-sha",
        "mappings": [
            {
                "source_commit": "source-sha",
                "target_commit": "target-sha",
                "target_content": content,
                "author_name": "Target User",
                "author_email": "target@example.com",
                "disposition": "supersede_source",
            }
        ],
    }


def test_rewrite_request_hash_normalizes_repo_url():
    first = compute_rewrite_request_hash(
        repo_url="https://github.com/test/repo.git",
        rewrite_id="rewrite-1",
        operation="rebase_conflict_manual_commit",
        branch="main",
        original_head="source-sha",
        new_head="target-sha",
        mappings=rewrite_payload()["mappings"],
    )
    second = compute_rewrite_request_hash(
        repo_url="git@github.com:test/repo.git",
        rewrite_id="rewrite-1",
        operation="rebase_conflict_manual_commit",
        branch="main",
        original_head="source-sha",
        new_head="target-sha",
        mappings=rewrite_payload()["mappings"],
    )
    assert first == second
    assert first.startswith("sha256:")


def test_rewrite_creates_target_and_supersedes_source(service):
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="source-sha",
        original_commit_sha=None,
        content="source content",
        author_name="Source User",
        author_email="source@example.com",
    )

    result = service.rewrite_notes(**rewrite_payload())

    assert result == {
        "created": 1,
        "updated": 0,
        "superseded": 1,
        "unchanged": 0,
        "conflicts": [],
    }
    assert service.get_note(
        repo_url="https://github.com/test/repo.git",
        commit_sha="source-sha",
    ) is None
    source = service.get_note(
        repo_url="https://github.com/test/repo.git",
        commit_sha="source-sha",
        include_superseded=True,
    )
    target = service.get_note(
        repo_url="https://github.com/test/repo.git",
        commit_sha="target-sha",
    )
    assert source.status == "superseded"
    assert source.superseded_by == "target-sha"
    assert source.superseded_rewrite_id == "rewrite-1"
    assert target.note_content == "target content"
    assert target.status == "active"


def test_rewrite_replay_is_idempotent(service):
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="source-sha",
        original_commit_sha=None,
        content="source content",
        author_name="Source User",
        author_email="source@example.com",
    )

    first = service.rewrite_notes(**rewrite_payload())
    second = service.rewrite_notes(**rewrite_payload())

    assert first["created"] == 1
    assert first["superseded"] == 1
    assert second == {
        "created": 0,
        "updated": 0,
        "superseded": 0,
        "unchanged": 1,
        "conflicts": [],
    }


def test_rewrite_replay_repairs_target_content_drift(service):
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="source-sha",
        original_commit_sha=None,
        content="source content",
        author_name="Source User",
        author_email="source@example.com",
    )
    service.rewrite_notes(**rewrite_payload("target content"))
    service.batch_push_notes(
        repo_url="https://github.com/test/repo.git",
        notes_data=[
            {
                "branch": "main",
                "commit_sha": "target-sha",
                "original_commit_sha": None,
                "author_name": "Drift User",
                "author_email": "drift@example.com",
                "content": "drifted target content",
            }
        ],
    )

    result = service.rewrite_notes(**rewrite_payload("target content"))

    assert result == {
        "created": 0,
        "updated": 1,
        "superseded": 0,
        "unchanged": 0,
        "conflicts": [],
    }
    target = service.get_note(
        repo_url="https://github.com/test/repo.git",
        commit_sha="target-sha",
    )
    assert target.note_content == "target content"


def test_rewrite_same_id_different_request_raises_conflict(service):
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="source-sha",
        original_commit_sha=None,
        content="source content",
        author_name="Source User",
        author_email="source@example.com",
    )
    service.rewrite_notes(**rewrite_payload("target content"))

    changed = rewrite_payload("different target content")
    with pytest.raises(RewriteIdConflictError):
        service.rewrite_notes(**changed)


def test_rewrite_target_note_conflict_does_not_overwrite(service):
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="source-sha",
        original_commit_sha=None,
        content="source content",
        author_name="Source User",
        author_email="source@example.com",
    )
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="target-sha",
        original_commit_sha=None,
        content="remote target content",
        author_name="Remote User",
        author_email="remote@example.com",
    )

    result = service.rewrite_notes(**rewrite_payload("local target content"))

    assert result["created"] == 0
    assert result["superseded"] == 0
    assert result["conflicts"][0]["reason"] == "target_note_conflict"
    target = service.get_note(
        repo_url="https://github.com/test/repo.git",
        commit_sha="target-sha",
    )
    assert target.note_content == "remote target content"
```

- [ ] **Step 2: Run service tests and verify failure**

Run:

```bash
pytest tests/unit/test_services/test_notes_rest_service.py -v
```

Expected: FAIL because `rewrite_notes`, `RewriteIdConflictError`, and `compute_rewrite_request_hash` do not exist.

- [ ] **Step 3: Add rewrite helpers and exceptions**

In `core/database/authorship_notes_db.py`, add:

```python
ALLOWED_REWRITE_OPERATIONS = {
    "rebase_conflict_manual_commit",
    "rebase_complete",
    "cherry_pick_complete",
    "amend",
}
ALLOWED_REWRITE_DISPOSITIONS = {"supersede_source"}


class RewriteValidationError(ValueError):
    pass


class RewriteIdConflictError(ValueError):
    pass


def compute_rewrite_request_hash(
    *,
    repo_url: str,
    rewrite_id: str,
    operation: str,
    branch: str,
    original_head: str | None,
    new_head: str | None,
    mappings: list[dict],
) -> str:
    normalized = {
        "repo_url": normalize_repo_url(repo_url),
        "rewrite_id": rewrite_id,
        "operation": operation,
        "branch": branch,
        "original_head": original_head,
        "new_head": new_head,
        "mappings": mappings,
    }
    body = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Add database `rewrite_notes()`**

Add this method to `AuthorshipNotesDatabase`:

```python
    def rewrite_notes(
        self,
        *,
        repo_url: str,
        rewrite_id: str,
        operation: str,
        branch: str,
        original_head: str | None,
        new_head: str | None,
        mappings: list[dict],
    ) -> Dict[str, Any]:
        repo_url = normalize_repo_url(repo_url)
        self._validate_rewrite_request(
            repo_url=repo_url,
            rewrite_id=rewrite_id,
            operation=operation,
            branch=branch,
            mappings=mappings,
        )
        request_hash = compute_rewrite_request_hash(
            repo_url=repo_url,
            rewrite_id=rewrite_id,
            operation=operation,
            branch=branch,
            original_head=original_head,
            new_head=new_head,
            mappings=mappings,
        )

        result = {
            "created": 0,
            "updated": 0,
            "superseded": 0,
            "unchanged": 0,
            "conflicts": [],
        }

        with session_scope(self.engine) as session:
            existing = session.execute(
                select(AuthorshipNoteRewrite).where(
                    AuthorshipNoteRewrite.rewrite_id == rewrite_id
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise RewriteIdConflictError(
                        "rewrite_id already exists with different request content"
                    )
            else:
                rewrite = AuthorshipNoteRewrite(
                    id=gen_xid(),
                    rewrite_id=rewrite_id,
                    repo_url=repo_url,
                    operation=operation,
                    branch=branch,
                    original_head=original_head,
                    new_head=new_head,
                    request_hash=request_hash,
                )
                session.add(rewrite)
                session.flush()

            for mapping in mappings:
                self._apply_rewrite_mapping(
                    session=session,
                    repo_url=repo_url,
                    rewrite_id=rewrite_id,
                    branch=branch,
                    mapping=mapping,
                    result=result,
                )

        return result
```

Add validation and mapping helpers to the same class:

```python
    def _validate_rewrite_request(
        self,
        *,
        repo_url: str,
        rewrite_id: str,
        operation: str,
        branch: str,
        mappings: list[dict],
    ) -> None:
        if not repo_url:
            raise RewriteValidationError("缺少必需字段: repo_url")
        if not rewrite_id:
            raise RewriteValidationError("缺少必需字段: rewrite_id")
        if operation not in ALLOWED_REWRITE_OPERATIONS:
            raise RewriteValidationError(f"不支持的 rewrite operation: {operation}")
        if not branch:
            raise RewriteValidationError("缺少必需字段: branch")
        if not isinstance(mappings, list) or not mappings:
            raise RewriteValidationError("mappings 必须是非空数组")
        required_mapping_fields = {
            "source_commit",
            "target_commit",
            "target_content",
            "author_name",
            "author_email",
            "disposition",
        }
        for mapping in mappings:
            missing = required_mapping_fields - set(mapping)
            if missing:
                raise RewriteValidationError(
                    f"mapping 缺少必需字段: {', '.join(sorted(missing))}"
                )
            if mapping["disposition"] not in ALLOWED_REWRITE_DISPOSITIONS:
                raise RewriteValidationError(
                    f"不支持的 disposition: {mapping['disposition']}"
                )
            if mapping["source_commit"] == mapping["target_commit"]:
                raise RewriteValidationError("source_commit 不能等于 target_commit")

    def _apply_rewrite_mapping(
        self,
        *,
        session,
        repo_url: str,
        rewrite_id: str,
        branch: str,
        mapping: dict,
        result: dict,
    ) -> None:
        source_commit = mapping["source_commit"]
        target_commit = mapping["target_commit"]
        target_content = mapping["target_content"]
        target_hash = compute_note_content_hash(target_content)

        target_stmt = select(AuthorshipNotes).where(
            AuthorshipNotes.repo_url == repo_url,
            AuthorshipNotes.commit_sha == target_commit,
        )
        target = session.execute(target_stmt).scalar_one_or_none()

        mapping_exists = session.execute(
            select(AuthorshipNoteRewriteMapping).where(
                AuthorshipNoteRewriteMapping.repo_url == repo_url,
                AuthorshipNoteRewriteMapping.source_commit == source_commit,
                AuthorshipNoteRewriteMapping.target_commit == target_commit,
                AuthorshipNoteRewriteMapping.rewrite_id == rewrite_id,
            )
        ).scalar_one_or_none()

        if (
            target is not None
            and target.content_hash != target_hash
            and mapping_exists is None
        ):
            result["conflicts"].append(
                {
                    "source_commit": source_commit,
                    "target_commit": target_commit,
                    "reason": "target_note_conflict",
                    "remote_content_hash": target.content_hash,
                    "local_content_hash": target_hash,
                }
            )
            return

        if target is None:
            target = AuthorshipNotes(
                id=gen_xid(),
                repo_url=repo_url,
                branch=branch,
                commit_sha=target_commit,
                note_blob_oid=mapping.get("target_note_blob_oid"),
                note_content=target_content,
                content_hash=target_hash,
                change_seq=self._next_change_seq(session),
                author_name=mapping["author_name"],
                author_email=mapping["author_email"],
                commit_time=mapping.get("commit_time"),
                status="active",
            )
            session.add(target)
            result["created"] += 1
        elif target.content_hash == target_hash:
            result["unchanged"] += 1
        else:
            target.branch = branch
            target.note_blob_oid = mapping.get("target_note_blob_oid")
            target.note_content = target_content
            target.content_hash = target_hash
            target.change_seq = self._next_change_seq(session)
            target.author_name = mapping["author_name"]
            target.author_email = mapping["author_email"]
            target.commit_time = mapping.get("commit_time")
            target.status = "active"
            result["updated"] += 1

        source = session.execute(
            select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha == source_commit,
            )
        ).scalar_one_or_none()
        if source is None:
            result["conflicts"].append(
                {
                    "source_commit": source_commit,
                    "target_commit": target_commit,
                    "reason": "source_note_missing",
                }
            )
        elif source.status == "superseded":
            if (
                source.superseded_by == target_commit
                and source.superseded_rewrite_id == rewrite_id
            ):
                pass
            else:
                result["conflicts"].append(
                    {
                        "source_commit": source_commit,
                        "target_commit": target_commit,
                        "reason": "source_already_superseded",
                    }
                )
        else:
            source.status = "superseded"
            source.superseded_by = target_commit
            source.superseded_rewrite_id = rewrite_id
            source.superseded_at = now_ts()
            source.change_seq = self._next_change_seq(session)
            result["superseded"] += 1

        if mapping_exists is None:
            session.add(
                AuthorshipNoteRewriteMapping(
                    id=gen_xid(),
                    rewrite_id=rewrite_id,
                    repo_url=repo_url,
                    source_commit=source_commit,
                    target_commit=target_commit,
                    source_note_blob_oid=mapping.get("source_note_blob_oid"),
                    target_note_blob_oid=mapping.get("target_note_blob_oid"),
                    target_content_hash=target_hash,
                    disposition=mapping["disposition"],
                )
            )
```

- [ ] **Step 5: Add service method**

In `core/services/notes_service.py`, add:

```python
    def rewrite_notes(
        self,
        repo_url: str,
        rewrite_id: str,
        operation: str,
        branch: str,
        original_head: str | None,
        new_head: str | None,
        mappings: list[dict],
    ):
        repo_url = normalize_repo_url(repo_url)
        return self.database.rewrite_notes(
            repo_url=repo_url,
            rewrite_id=rewrite_id,
            operation=operation,
            branch=branch,
            original_head=original_head,
            new_head=new_head,
            mappings=mappings,
        )
```

- [ ] **Step 6: Run service tests and verify pass**

Run:

```bash
pytest tests/unit/test_services/test_notes_rest_service.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit rewrite database and service changes**

```bash
git add core/database/authorship_notes_db.py core/services/notes_service.py tests/unit/test_services/test_notes_rest_service.py
git commit -m "feat: add authorship notes rewrite service"
```

## Task 4: Rewrite REST Endpoint

**Files:**
- Modify: `api/routes/authorship_notes.py`
- Test: `tests/integration/test_notes_rest_api.py`

- [ ] **Step 1: Register both blueprints in the integration fixture**

In `tests/integration/test_notes_rest_api.py`, update the app fixture after creating the Flask app:

```python
    app.register_blueprint(authorship_notes.git_notes_rest_bp)
    app.register_blueprint(authorship_notes.authorship_notes_rest_bp)
```

- [ ] **Step 2: Add failing integration tests for rewrite**

Append:

```python
class TestRewriteNotes:
    def test_authorship_notes_rewrite_creates_target_and_supersedes_source(self, client):
        client.put('/worker/authorship_notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "source-sha",
                "original_commit_sha": None,
                "author_name": "Source User",
                "author_email": "source@example.com",
                "content": "source content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        response = client.post('/worker/authorship_notes/rewrite',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "rewrite_id": "rewrite-api-1",
                "operation": "rebase_conflict_manual_commit",
                "branch": "main",
                "original_head": "source-sha",
                "new_head": "target-sha",
                "mappings": [
                    {
                        "source_commit": "source-sha",
                        "target_commit": "target-sha",
                        "target_content": "target content",
                        "author_name": "Target User",
                        "author_email": "target@example.com",
                        "disposition": "supersede_source"
                    }
                ]
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['data']['created'] == 1
        assert data['data']['superseded'] == 1
        assert data['data']['conflicts'] == []

        source_default = client.post('/worker/authorship_notes/get',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_sha": "source-sha"
            },
            headers={'X-API-Key': 'test-key'}
        )
        assert source_default.status_code == 404

        source_audit = client.post('/worker/authorship_notes/get',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_sha": "source-sha",
                "include_superseded": True
            },
            headers={'X-API-Key': 'test-key'}
        )
        assert source_audit.status_code == 200
        assert json.loads(source_audit.data)['data']['status'] == "superseded"

    def test_notes_rewrite_alias_matches_canonical_endpoint(self, client):
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "alias-source",
                "original_commit_sha": None,
                "author_name": "Source User",
                "author_email": "source@example.com",
                "content": "source content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        response = client.post('/worker/notes/rewrite',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "rewrite_id": "rewrite-alias-1",
                "operation": "rebase_conflict_manual_commit",
                "branch": "main",
                "original_head": "alias-source",
                "new_head": "alias-target",
                "mappings": [
                    {
                        "source_commit": "alias-source",
                        "target_commit": "alias-target",
                        "target_content": "alias target content",
                        "author_name": "Target User",
                        "author_email": "target@example.com",
                        "disposition": "supersede_source"
                    }
                ]
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        assert json.loads(response.data)['data']['created'] == 1

    def test_rewrite_id_conflict_returns_409(self, client):
        payload = {
            "repo_url": "https://github.com/test/repo.git",
            "rewrite_id": "rewrite-conflict",
            "operation": "rebase_conflict_manual_commit",
            "branch": "main",
            "original_head": "source-one",
            "new_head": "target-one",
            "mappings": [
                {
                    "source_commit": "source-one",
                    "target_commit": "target-one",
                    "target_content": "target content",
                    "author_name": "Target User",
                    "author_email": "target@example.com",
                    "disposition": "supersede_source"
                }
            ]
        }
        client.post('/worker/notes/rewrite', json=payload, headers={'X-API-Key': 'test-key'})

        changed = dict(payload)
        changed["new_head"] = "target-two"
        changed["mappings"] = [
            {
                "source_commit": "source-one",
                "target_commit": "target-two",
                "target_content": "target content two",
                "author_name": "Target User",
                "author_email": "target@example.com",
                "disposition": "supersede_source"
            }
        ]
        response = client.post('/worker/notes/rewrite',
            json=changed,
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 409
        assert json.loads(response.data)['ok'] is False

    def test_rewrite_filters_source_from_default_reads(self, client):
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "filter-source",
                "original_commit_sha": None,
                "author_name": "Source User",
                "author_email": "source@example.com",
                "content": "shared rewrite content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        client.post('/worker/notes/rewrite',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "rewrite_id": "rewrite-filter",
                "operation": "rebase_conflict_manual_commit",
                "branch": "main",
                "original_head": "filter-source",
                "new_head": "filter-target",
                "mappings": [
                    {
                        "source_commit": "filter-source",
                        "target_commit": "filter-target",
                        "target_content": "shared rewrite content target",
                        "author_name": "Target User",
                        "author_email": "target@example.com",
                        "disposition": "supersede_source"
                    }
                ]
            },
            headers={'X-API-Key': 'test-key'}
        )

        default_get = client.post('/worker/notes/get',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_sha": "filter-source"
            },
            headers={'X-API-Key': 'test-key'}
        )
        assert default_get.status_code == 404

        audit_get = client.post('/worker/notes/get',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_sha": "filter-source",
                "include_superseded": True
            },
            headers={'X-API-Key': 'test-key'}
        )
        assert audit_get.status_code == 200
        assert json.loads(audit_get.data)['data']['status'] == "superseded"

        listed = client.post('/worker/notes/list',
            json={"repo_url": "https://github.com/test/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )
        assert json.loads(listed.data)['data']['commit_shas'] == ["filter-target"]

        batch = client.post('/worker/notes/batch',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_shas": ["filter-source", "filter-target"]
            },
            headers={'X-API-Key': 'test-key'}
        )
        batch_data = json.loads(batch.data)['data']
        assert {note["commit_sha"] for note in batch_data["notes"]} == {"filter-target"}
        assert "filter-source" in batch_data["missing"]

        searched = client.post('/worker/notes/search',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "pattern": "shared rewrite content"
            },
            headers={'X-API-Key': 'test-key'}
        )
        assert json.loads(searched.data)['data']['commit_shas'] == ["filter-target"]
```

- [ ] **Step 3: Run integration tests and verify failure**

Run:

```bash
pytest tests/integration/test_notes_rest_api.py -v
```

Expected: FAIL because `/rewrite` is not routed.

- [ ] **Step 4: Add route handler**

In `api/routes/authorship_notes.py`, update imports:

```python
from core.database.authorship_notes_db import (
    RewriteIdConflictError,
    RewriteValidationError,
)
```

Add the route before `list_notes()`:

```python
@git_notes_rest_bp.route("/rewrite", methods=["POST"])
@authorship_notes_rest_bp.route("/rewrite", methods=["POST"])
@auth_required
def rewrite_notes():
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return error_response("请求体不能为空", 400)

        required_fields = [
            "repo_url",
            "rewrite_id",
            "operation",
            "branch",
            "mappings",
        ]
        for field in required_fields:
            if field not in payload:
                return error_response(f"缺少必需字段: {field}", 400)

        result = get_notes_service().rewrite_notes(
            repo_url=payload["repo_url"],
            rewrite_id=payload["rewrite_id"],
            operation=payload["operation"],
            branch=payload["branch"],
            original_head=payload.get("original_head"),
            new_head=payload.get("new_head"),
            mappings=payload["mappings"],
        )
        return ok_response(result)

    except RewriteIdConflictError as exc:
        return error_response(str(exc), 409)
    except RewriteValidationError as exc:
        return error_response(str(exc), 400)
    except Exception as e:
        logger.error("rewrite authorship notes 错误", exc_info=e)
        return error_response("服务器错误", 500)
```

- [ ] **Step 5: Run integration tests and verify pass**

Run:

```bash
pytest tests/integration/test_notes_rest_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit route changes**

```bash
git add api/routes/authorship_notes.py tests/integration/test_notes_rest_api.py
git commit -m "feat: expose authorship notes rewrite API"
```

## Task 5: Active-Note Filtering In Stats And Blame Consumers

**Files:**
- Modify: `core/database/stats_db.py`
- Modify: `core/database/blame_stats_db.py`
- Modify: `core/services/blame_stats_service.py`
- Test: `tests/unit/test_database/test_blame_stats_db.py`
- Test: `tests/integration/test_dimensions_db.py`

- [ ] **Step 1: Add failing blame DB test**

In `tests/unit/test_database/test_blame_stats_db.py`, add a superseded note to `test_get_git_notes_batch_returns_matching_notes()`:

```python
            AuthorshipNotes(
                id="note-superseded",
                repo_url="github.com/test/repo",
                branch="main",
                commit_sha="superseded",
                note_blob_oid=None,
                author_name="Test",
                author_email="test@example.com",
                note_content="superseded content",
                content_hash="sha256:superseded",
                change_seq=3,
                status="superseded",
                superseded_by="replacement",
                superseded_rewrite_id="rewrite-1",
            ),
```

Update the assertion:

```python
    result = blame_stats_db.get_git_notes_batch(["abc123", "missing", "superseded"])
    assert result == {"abc123": "note-a"}
```

- [ ] **Step 2: Add failing dimensions DB test**

In `tests/integration/test_dimensions_db.py`, add a focused test near existing `require_authorship_notes` coverage:

```python
def test_query_committed_events_require_authorship_notes_ignores_superseded(setup_dbs):
    metrics_db, stats_db = setup_dbs

    raw_id = metrics_db.save_metrics_raw(
        version=1,
        event_count=1,
        payload_json="{}",
        received_at=1710000000000,
    )
    committed = MetricsEventsCommitted(
        raw_id=raw_id,
        timestamp=1710000001,
        commit_date=20260617,
        repo_url="github.com/test/repo",
        author="Test User <test@example.com>",
        commit_sha="superseded-sha",
        human_additions=0,
        git_diff_deleted_lines=0,
        git_diff_added_lines=1,
        ai_additions=[1, 1],
        ai_accepted=[1, 1],
        total_ai_additions=[1, 1],
    )
    committed.uid = gen_commited_uid(committed)
    metrics_db.upsert_committed_event(committed)

    with session_scope(stats_db.engine) as session:
        session.add(
            AuthorshipNotes(
                repo_url="github.com/test/repo",
                branch="main",
                commit_sha="superseded-sha",
                note_blob_oid=None,
                author_name="Test User",
                author_email="test@example.com",
                note_content="superseded note",
                content_hash="sha256:superseded",
                change_seq=1,
                status="superseded",
                superseded_by="replacement-sha",
                superseded_rewrite_id="rewrite-1",
            )
        )

    rows = stats_db.query_committed_events(
        1710000000,
        1710000010,
        require_authorship_notes=True,
    )

    assert rows == []
```

- [ ] **Step 3: Run consumer tests and verify failure**

Run:

```bash
pytest tests/unit/test_database/test_blame_stats_db.py tests/integration/test_dimensions_db.py -v
```

Expected: FAIL because superseded notes still satisfy active-note joins.

- [ ] **Step 4: Apply active filters in consumers**

In `core/database/blame_stats_db.py`, import the helper:

```python
from core.database.authorship_notes_db import active_authorship_note_filter
```

Update `get_git_notes_batch()`:

```python
            notes = (
                session.query(AuthorshipNotes)
                .filter(AuthorshipNotes.commit_sha.in_(commit_shas))
                .filter(active_authorship_note_filter())
                .all()
            )
```

In `core/database/stats_db.py`, import the helper:

```python
from core.database.authorship_notes_db import active_authorship_note_filter
```

In every `require_authorship_notes` query, add the active filter. For the `matching_notes` query:

```python
                    matching_notes = (
                        session.query(AuthorshipNotes.repo_url, AuthorshipNotes.commit_sha)
                        .filter(AuthorshipNotes.repo_url.in_(note_repo_urls))
                        .filter(AuthorshipNotes.commit_sha.in_(note_commit_shas))
                        .filter(active_authorship_note_filter())
                        .all()
                    )
```

For the `exists()` clause:

```python
                note_exists = (
                    exists()
                    .where(AuthorshipNotes.repo_url == MetricsEventsCommitted.repo_url)
                    .where(AuthorshipNotes.commit_sha == MetricsEventsCommitted.commit_sha)
                    .where(active_authorship_note_filter())
                )
```

For the join query:

```python
                query = query.join(
                    AuthorshipNotes,
                    (MetricsEventsCommitted.repo_url == AuthorshipNotes.repo_url)
                    & (MetricsEventsCommitted.commit_sha == AuthorshipNotes.commit_sha),
                ).filter(active_authorship_note_filter())
```

In `core/services/blame_stats_service.py`, import and apply the same helper in `_preload_notes()` and `query_ai_lines_from_notes()`:

```python
from core.database.authorship_notes_db import active_authorship_note_filter
```

Add `.filter(active_authorship_note_filter())` to each query using `AuthorshipNotes`.

- [ ] **Step 5: Run consumer tests and verify pass**

Run:

```bash
pytest tests/unit/test_database/test_blame_stats_db.py tests/integration/test_dimensions_db.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit consumer filtering changes**

```bash
git add core/database/stats_db.py core/database/blame_stats_db.py core/services/blame_stats_service.py tests/unit/test_database/test_blame_stats_db.py tests/integration/test_dimensions_db.py
git commit -m "fix: ignore superseded notes in active metrics"
```

## Task 6: Swagger And API Reference

**Files:**
- Modify: `docs/swagger/api/notes-rest.yaml`
- Modify: `docs/git-ai-api-reference.md`

- [ ] **Step 1: Add rewrite paths to Swagger**

Add a path entry for `/worker/authorship_notes/rewrite` and `/worker/notes/rewrite` in `docs/swagger/api/notes-rest.yaml`:

```yaml
  /worker/authorship_notes/rewrite:
    post:
      summary: Rewrite authorship notes
      security:
        - bearerAuth: []
        - apiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RewriteNotesRequest'
      responses:
        '200':
          description: Rewrite processed
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RewriteNotesResponse'
        '400':
          description: Invalid rewrite request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
        '409':
          description: rewrite_id exists with different request content
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  /worker/notes/rewrite:
    post:
      summary: Rewrite authorship notes compatibility alias
      security:
        - bearerAuth: []
        - apiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RewriteNotesRequest'
      responses:
        '200':
          description: Rewrite processed
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RewriteNotesResponse'
        '400':
          description: Invalid rewrite request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
        '409':
          description: rewrite_id exists with different request content
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
```

Add schemas under `components.schemas`:

```yaml
    RewriteNotesRequest:
      type: object
      required:
        - repo_url
        - rewrite_id
        - operation
        - branch
        - mappings
      properties:
        repo_url:
          type: string
        rewrite_id:
          type: string
        operation:
          type: string
          enum:
            - rebase_conflict_manual_commit
            - rebase_complete
            - cherry_pick_complete
            - amend
        branch:
          type: string
        original_head:
          type: string
          nullable: true
        new_head:
          type: string
          nullable: true
        mappings:
          type: array
          items:
            $ref: '#/components/schemas/RewriteNotesMapping'

    RewriteNotesMapping:
      type: object
      required:
        - source_commit
        - target_commit
        - target_content
        - author_name
        - author_email
        - disposition
      properties:
        source_commit:
          type: string
        target_commit:
          type: string
        source_note_blob_oid:
          type: string
          nullable: true
        target_note_blob_oid:
          type: string
          nullable: true
        target_content:
          type: string
        commit_time:
          type: integer
          format: int64
        author_name:
          type: string
        author_email:
          type: string
        disposition:
          type: string
          enum:
            - supersede_source

    RewriteNotesResponse:
      type: object
      properties:
        ok:
          type: boolean
        data:
          type: object
          properties:
            created:
              type: integer
            updated:
              type: integer
            superseded:
              type: integer
            unchanged:
              type: integer
            conflicts:
              type: array
              items:
                $ref: '#/components/schemas/RewriteNotesConflict'

    RewriteNotesConflict:
      type: object
      properties:
        source_commit:
          type: string
        target_commit:
          type: string
        reason:
          type: string
        remote_content_hash:
          type: string
        local_content_hash:
          type: string
```

- [ ] **Step 2: Add API reference section**

In `docs/git-ai-api-reference.md`, add a REST Notes section with:

````markdown
# Authorship Notes Rewrite API

## Rewrite Notes

**接口**: `POST /worker/authorship_notes/rewrite`

兼容别名: `POST /worker/notes/rewrite`

普通新 note 仍使用 `/worker/authorship_notes/push`。当客户端执行 rebase、cherry-pick、amend 等历史改写并明确知道 source commit 被 target commit 替代时，必须调用 `/rewrite`，因为 `/push` 只能 upsert target note，不能把 source note 标记为 superseded。

**请求**:

```json
{
  "repo_url": "https://github.com/org/repo",
  "rewrite_id": "sha256:client-generated-id",
  "operation": "rebase_conflict_manual_commit",
  "branch": "main",
  "original_head": "B",
  "new_head": "D",
  "mappings": [
    {
      "source_commit": "B",
      "target_commit": "D",
      "target_content": "authorship note content",
      "author_name": "User",
      "author_email": "user@example.com",
      "disposition": "supersede_source"
    }
  ]
}
```

**响应**:

```json
{
  "ok": true,
  "data": {
    "created": 1,
    "updated": 0,
    "superseded": 1,
    "unchanged": 0,
    "conflicts": []
  }
}
```

同一个 `rewrite_id` 和同一个规范化请求体可以安全重放。相同 `rewrite_id` 携带不同请求体时返回 `409`。
````

- [ ] **Step 3: Run docs-related tests**

Run:

```bash
pytest tests/unit/test_swagger -v
```

Expected: PASS.

- [ ] **Step 4: Commit documentation changes**

```bash
git add docs/swagger/api/notes-rest.yaml docs/git-ai-api-reference.md
git commit -m "docs: document authorship notes rewrite API"
```

## Task 7: Final Verification

**Files:**
- Verify all files changed in Tasks 1-6.

- [ ] **Step 1: Run focused backend verification**

Run:

```bash
pytest tests/unit/test_models/test_notes.py tests/unit/test_services/test_notes_rest_service.py tests/integration/test_notes_rest_api.py tests/unit/test_database/test_blame_stats_db.py tests/integration/test_dimensions_db.py tests/unit/test_swagger -v
```

Expected: PASS.

- [ ] **Step 2: Inspect git status**

Run:

```bash
git status --short
```

Expected: only intentional files are modified or the working tree is clean after the task commits. The untracked source design file `docs/2026-06-17-rebase-conflict-manual-commit-authorship-design.md` may remain untracked and must not be included unless the user explicitly asks.

- [ ] **Step 3: Inspect commit history**

Run:

```bash
git log --oneline -6
```

Expected: recent commits include schema, service, route, consumer filtering, and docs commits from this plan.
