# Authorship Notes Strong Incremental Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement strong incremental synchronization for `authorship_notes` using server-side `change_seq` watermarks and stable `sha256(note_content)` hashes, without relying on `note_blob_oid` for consistency.

**Architecture:** The Python service becomes the source of truth for note change metadata: every content-changing write computes `content_hash` and advances a database-backed `change_seq`. The Rust client consumes paginated summary items from `/worker/authorship_notes/list`, compares stable content hashes against local Git Notes, fetches only missing or changed notes through `/batch`, and advances a local sync watermark only after successful application.

**Tech Stack:** Python 3.10+, Flask, SQLAlchemy 2.0, SQLite tests, MySQL DDL, Rust 2024, serde, Git CLI-backed notes operations.

---

## File Structure

### Python service

- Modify: `core/database/models.py`
  - Add `content_hash`, `change_seq`, and a small `AuthorshipNotesSeq` counter model for database-backed sequence allocation.
  - Add `(repo_url, change_seq)` index.
- Modify: `core/database/authorship_notes_db.py`
  - Add SHA-256 hash helper and transaction-local sequence allocation.
  - Update single and batch upserts to be idempotent by content hash.
  - Add paginated summary listing while preserving old `commit_shas` behavior.
- Modify: `core/services/notes_service.py`
  - Pass new `since_change_seq` and `limit` parameters through to the database layer.
- Modify: `api/routes/authorship_notes.py`
  - Read `since_change_seq` and `limit` from `/list` payload.
  - Return old `commit_shas` plus new `items`, `next_change_seq`, `has_more` fields.
- Modify: `sql/metrics_schema_mysql.sql`
  - Add DDL for `content_hash`, `change_seq`, `authorship_notes_seq`, and `idx_authorship_notes_repo_change_seq`.
- Modify: `tests/unit/test_models/test_notes.py`
  - Assert new columns and index exist.
- Modify: `tests/unit/test_services/test_notes_rest_service.py`
  - Cover hash generation, idempotent writes, sequence advancement, and paginated summaries.
- Modify: `tests/integration/test_notes_rest_api.py`
  - Cover REST shape and backward compatibility.

### Rust client

- Modify: `git-ai/src/api/types.rs`
  - Add summary item fields to list response.
  - Add `since_change_seq` and `limit` to list request.
  - Add optional hash/seq fields to batch response items.
  - Add `unchanged` to push response data.
- Modify: `git-ai/src/git/sync_authorship.rs`
  - Add local sync state load/save helpers.
  - Add SHA-256 helper for local note content.
  - Update REST fetch to page through summary items and batch-get only missing/changed notes.
  - Update REST push to avoid using `note_blob_oid` for consistency checks.

---

## Task 1: Python model and SQL schema metadata

**Files:**
- Modify: `core/database/models.py:410-433`
- Modify: `sql/metrics_schema_mysql.sql:217-231`
- Test: `tests/unit/test_models/test_notes.py`

- [ ] **Step 1: Write failing model tests for new columns and indexes**

Add these assertions to `tests/unit/test_models/test_notes.py`:

```python
def test_authorship_notes_model_columns():
    """Test AuthorshipNotes has all required columns"""
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
        "content_hash",
        "change_seq",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(columns), (
        f"Missing columns: {expected_columns - columns}"
    )


def test_authorship_notes_indexes():
    """Test AuthorshipNotes has required indexes"""
    indexes = {i.name for i in getattr(AuthorshipNotes.__table__, "indexes", set())}

    assert "idx_authorship_notes_repo_url" in indexes, "Missing repo_url index"
    assert "idx_authorship_notes_repo_commit" in indexes, "Missing repo_commit index"
    assert (
        "idx_authorship_notes_repo_change_seq" in indexes
    ), "Missing repo_change_seq index"
```

- [ ] **Step 2: Run model tests to verify they fail**

Run:

```bash
pytest tests/unit/test_models/test_notes.py -v
```

Expected: FAIL because `content_hash`, `change_seq`, and `idx_authorship_notes_repo_change_seq` do not exist.

- [ ] **Step 3: Add ORM fields and sequence model**

Update the `AuthorshipNotes` model in `core/database/models.py` to include the new index and fields:

```python
class AuthorshipNotes(ModelBase):
    """作者注释表 - 用于 REST Notes Store API"""

    __tablename__ = "authorship_notes"

    __table_args__ = (
        UniqueConstraint("repo_url", "commit_sha"),
        Index("idx_authorship_notes_repo_url", "repo_url"),
        Index("idx_authorship_notes_repo_commit", "repo_url", "commit_sha"),
        Index("idx_authorship_notes_repo_change_seq", "repo_url", "change_seq"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(String(40), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    note_blob_oid: Mapped[str] = mapped_column(String(40), nullable=True)
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    author_email: Mapped[str] = mapped_column(Text, nullable=False)
    note_content: Mapped[str] = mapped_column(Text, nullable=False)
    commit_time: Mapped[int] = mapped_column(BigInteger, nullable=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    change_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts
    )
```

Add a small sequence table model near `AuthorshipNotes`:

```python
class AuthorshipNotesSeq(ModelBase):
    """单调递增序列表，用于 authorship_notes.change_seq。"""

    __tablename__ = "authorship_notes_seq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
```

- [ ] **Step 4: Update MySQL DDL**

Update `sql/metrics_schema_mysql.sql` `authorship_notes` definition:

```sql
CREATE TABLE IF NOT EXISTS authorship_notes (
    id VARCHAR(20) PRIMARY KEY COMMENT '主键，使用 XID',
    repo_url VARCHAR(200) NOT NULL COMMENT '仓库 URL',
    branch VARCHAR(100) NOT NULL COMMENT '分支名称',
    commit_sha VARCHAR(40) NOT NULL COMMENT '提交 SHA',
    commit_time BIGINT NOT NULL DEFAULT 0 COMMENT '提交时间戳（秒）',
    note_blob_oid VARCHAR(40) COMMENT 'Note Blob OID',
    author_name VARCHAR(100) NOT NULL COMMENT '作者名称',
    author_email VARCHAR(100) NOT NULL COMMENT '作者邮箱',
    note_content TEXT NOT NULL COMMENT '注释内容',
    content_hash VARCHAR(71) NOT NULL COMMENT 'note_content 的 SHA-256 摘要',
    change_seq BIGINT NOT NULL COMMENT '服务端单调递增变更序号',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    UNIQUE KEY uk_authorship_notes_repo_commit (repo_url, commit_sha),
    INDEX idx_authorship_notes_repo_url (repo_url),
    INDEX idx_authorship_notes_repo_commit (repo_url, commit_sha),
    INDEX idx_authorship_notes_repo_change_seq (repo_url, change_seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='作者注释表';

CREATE TABLE IF NOT EXISTS authorship_notes_seq (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '全局 authorship_notes change_seq',
    created_at BIGINT NOT NULL COMMENT '创建时间戳（毫秒）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Authorship Notes 变更序列表';
```

- [ ] **Step 5: Run model tests to verify they pass**

Run:

```bash
pytest tests/unit/test_models/test_notes.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/database/models.py sql/metrics_schema_mysql.sql tests/unit/test_models/test_notes.py
git commit -m "feat: add authorship notes change metadata schema"
```

---

## Task 2: Python database write semantics and summary list

**Files:**
- Modify: `core/database/authorship_notes_db.py`
- Modify: `core/services/notes_service.py`
- Test: `tests/unit/test_services/test_notes_rest_service.py`

- [ ] **Step 1: Write failing service tests for hash, idempotency, and summary listing**

Append these tests to `tests/unit/test_services/test_notes_rest_service.py`:

```python
import hashlib


def expected_note_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_create_note_generates_content_hash_and_change_seq(service):
    note = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha-hash-1",
        original_commit_sha=None,
        content="stable content",
        author_name="Test User",
        author_email="test@example.com",
    )

    assert note.content_hash == expected_note_hash("stable content")
    assert note.change_seq > 0


def test_same_content_update_is_unchanged_and_keeps_change_seq(service):
    first = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha-idempotent",
        original_commit_sha=None,
        content="same content",
        author_name="Test User",
        author_email="test@example.com",
    )
    first_seq = first.change_seq

    second = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="develop",
        commit_sha="sha-idempotent",
        original_commit_sha="different-blob",
        content="same content",
        author_name="Other User",
        author_email="other@example.com",
    )

    assert second.change_seq == first_seq
    assert second.content_hash == expected_note_hash("same content")


def test_changed_content_advances_change_seq(service):
    first = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha-change",
        original_commit_sha=None,
        content="old content",
        author_name="Test User",
        author_email="test@example.com",
    )

    second = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="sha-change",
        original_commit_sha=None,
        content="new content",
        author_name="Test User",
        author_email="test@example.com",
    )

    assert second.change_seq > first.change_seq
    assert second.content_hash == expected_note_hash("new content")
    assert second.note_content == "new content"


def test_batch_push_reports_unchanged(service):
    service.batch_push_notes(
        repo_url="https://github.com/test/repo.git",
        notes_data=[
            {
                "branch": "main",
                "commit_sha": "sha-same",
                "original_commit_sha": None,
                "author_name": "User1",
                "author_email": "user1@test.com",
                "content": "same content",
            }
        ],
    )

    result = service.batch_push_notes(
        repo_url="https://github.com/test/repo.git",
        notes_data=[
            {
                "branch": "main",
                "commit_sha": "sha-same",
                "original_commit_sha": "different-blob",
                "author_name": "User1",
                "author_email": "user1@test.com",
                "content": "same content",
            }
        ],
    )

    assert result == {"created": 0, "updated": 0, "unchanged": 1}


def test_list_notes_summary_paginates_by_change_seq(service):
    for idx, sha in enumerate(["sha1", "sha2", "sha3"], start=1):
        service.create_or_update_note(
            repo_url="https://github.com/test/repo.git",
            branch="main",
            commit_sha=sha,
            original_commit_sha=None,
            content=f"content {idx}",
            author_name="Test",
            author_email="test@test.com",
        )

    first_page = service.list_notes(
        repo_url="https://github.com/test/repo.git",
        since_change_seq=0,
        limit=2,
    )

    assert first_page["commit_shas"] == ["sha1", "sha2"]
    assert [item["commit_sha"] for item in first_page["items"]] == ["sha1", "sha2"]
    assert first_page["items"][0]["content_hash"] == expected_note_hash("content 1")
    assert first_page["has_more"] is True
    assert first_page["next_change_seq"] == first_page["items"][-1]["change_seq"]

    second_page = service.list_notes(
        repo_url="https://github.com/test/repo.git",
        since_change_seq=first_page["next_change_seq"],
        limit=2,
    )

    assert second_page["commit_shas"] == ["sha3"]
    assert second_page["has_more"] is False
```

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```bash
pytest tests/unit/test_services/test_notes_rest_service.py -v
```

Expected: FAIL because `content_hash`, `change_seq`, `unchanged`, and summary-shaped `list_notes` do not exist yet.

- [ ] **Step 3: Implement hash and sequence helpers in database layer**

In `core/database/authorship_notes_db.py`, update imports:

```python
import hashlib
from typing import Any, Dict, List, Optional
from sqlalchemy import select

from .base import session_scope, BaseDatabase
from .models import AuthorshipNotes, AuthorshipNotesSeq, gen_xid
```

Add helpers near the top of the file:

```python
DEFAULT_LIST_LIMIT = 1000
MAX_LIST_LIMIT = 5000


def compute_note_content_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def normalize_list_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIST_LIMIT
    if limit <= 0:
        return DEFAULT_LIST_LIMIT
    return min(limit, MAX_LIST_LIMIT)
```

Add a private method to `AuthorshipNotesDatabase`:

```python
    def _next_change_seq(self, session) -> int:
        seq = AuthorshipNotesSeq()
        session.add(seq)
        session.flush()
        return seq.id
```

- [ ] **Step 4: Update single-note upsert semantics**

Replace the body of `create_or_update_note` with:

```python
        content_hash = compute_note_content_hash(content)

        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha == commit_sha,
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                if result.content_hash != content_hash:
                    result.branch = branch
                    setattr(result, "note_blob_oid", note_blob_oid)
                    result.note_content = content
                    result.content_hash = content_hash
                    result.change_seq = self._next_change_seq(session)
                    result.author_name = author_name
                    result.author_email = author_email
            else:
                note = AuthorshipNotes(
                    id=gen_xid(),
                    repo_url=repo_url,
                    branch=branch,
                    commit_sha=commit_sha,
                    note_blob_oid=note_blob_oid,
                    note_content=content,
                    content_hash=content_hash,
                    change_seq=self._next_change_seq(session),
                    author_name=author_name,
                    author_email=author_email,
                )
                session.add(note)

            session.flush()
            return session.execute(stmt).scalar_one()
```

- [ ] **Step 5: Update batch get response metadata**

Change the `notes` list in `batch_get_notes` to include hash and sequence:

```python
            notes = [
                {
                    "commit_sha": note.commit_sha,
                    "content": note.note_content,
                    "content_hash": note.content_hash,
                    "change_seq": note.change_seq,
                }
                for note in results
            ]
```

- [ ] **Step 6: Update batch push semantics**

Rewrite `batch_push_notes` so it tracks unchanged rows:

```python
    def batch_push_notes(self, repo_url: str, notes_data: List[Dict]) -> Dict[str, int]:
        created = 0
        updated = 0
        unchanged = 0

        with session_scope(self.engine) as session:
            for note_data in notes_data:
                commit_sha = note_data["commit_sha"]
                content = note_data["content"]
                content_hash = compute_note_content_hash(content)

                stmt = select(AuthorshipNotes).where(
                    AuthorshipNotes.repo_url == repo_url,
                    AuthorshipNotes.commit_sha == commit_sha,
                )
                note = session.execute(stmt).scalar_one_or_none()

                if note is None:
                    note = AuthorshipNotes(
                        id=gen_xid(),
                        repo_url=repo_url,
                        branch=note_data["branch"],
                        commit_sha=commit_sha,
                        note_blob_oid=note_data.get(
                            "original_commit_sha", note_data.get("note_blob_oid")
                        ),
                        note_content=content,
                        content_hash=content_hash,
                        change_seq=self._next_change_seq(session),
                        author_name=note_data["author_name"],
                        author_email=note_data["author_email"],
                        commit_time=note_data.get("commit_time"),
                    )
                    session.add(note)
                    created += 1
                    continue

                if note.content_hash == content_hash:
                    unchanged += 1
                    continue

                note.branch = note_data["branch"]
                setattr(
                    note,
                    "note_blob_oid",
                    note_data.get("original_commit_sha", note_data.get("note_blob_oid")),
                )
                note.note_content = content
                note.content_hash = content_hash
                note.change_seq = self._next_change_seq(session)
                note.author_name = note_data["author_name"]
                note.author_email = note_data["author_email"]
                note.commit_time = note_data.get("commit_time", 0)
                updated += 1

        return {"created": created, "updated": updated, "unchanged": unchanged}
```

- [ ] **Step 7: Update list_notes return shape**

Replace `list_notes` with:

```python
    def list_notes(
        self,
        repo_url: str,
        since_commit_time: int | None = None,
        since_change_seq: int | None = None,
        limit: int | None = None,
    ) -> Dict[str, Any]:
        page_limit = normalize_list_limit(limit)

        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(AuthorshipNotes.repo_url == repo_url)

            if since_change_seq is not None:
                stmt = stmt.where(AuthorshipNotes.change_seq > since_change_seq)
                stmt = stmt.order_by(AuthorshipNotes.change_seq)
            else:
                if since_commit_time is not None:
                    stmt = stmt.where(AuthorshipNotes.commit_time >= since_commit_time)
                stmt = stmt.order_by(AuthorshipNotes.commit_sha)

            rows = list(session.execute(stmt.limit(page_limit + 1)).scalars().all())

        has_more = len(rows) > page_limit
        page_rows = rows[:page_limit]
        items = [
            {
                "commit_sha": note.commit_sha,
                "content_hash": note.content_hash,
                "change_seq": note.change_seq,
                "updated_at": note.updated_at,
            }
            for note in page_rows
        ]
        next_change_seq = items[-1]["change_seq"] if items else since_change_seq or 0

        return {
            "commit_shas": [note.commit_sha for note in page_rows],
            "items": items,
            "next_change_seq": next_change_seq,
            "has_more": has_more,
        }
```

- [ ] **Step 8: Update service pass-through**

Change `NotesRestService.list_notes` in `core/services/notes_service.py`:

```python
    def list_notes(
        self,
        repo_url: str,
        since_commit_time: int | None = None,
        since_change_seq: int | None = None,
        limit: int | None = None,
    ):
        return self.database.list_notes(
            repo_url=repo_url,
            since_commit_time=since_commit_time,
            since_change_seq=since_change_seq,
            limit=limit,
        )
```

- [ ] **Step 9: Update old service test expectations for list shape and unchanged key**

Update `test_batch_push_notes` expected result:

```python
    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["unchanged"] == 0
```

Update `test_batch_push_with_updates` expected result:

```python
    assert result["created"] == 1
    assert result["updated"] == 1
    assert result["unchanged"] == 0
```

Update `test_list_notes` expected shape:

```python
    result = service.list_notes(repo_url="https://github.com/test/repo.git")

    assert len(result["commit_shas"]) == 3
    assert set(result["commit_shas"]) == {"sha1", "sha2", "sha3"}
    assert len(result["items"]) == 3
    assert result["has_more"] is False
```

- [ ] **Step 10: Run service tests to verify they pass**

Run:

```bash
pytest tests/unit/test_services/test_notes_rest_service.py -v
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add core/database/authorship_notes_db.py core/services/notes_service.py tests/unit/test_services/test_notes_rest_service.py
git commit -m "feat: add authorship notes change summaries"
```

---

## Task 3: Python REST API compatibility and pagination

**Files:**
- Modify: `api/routes/authorship_notes.py:252-284`
- Test: `tests/integration/test_notes_rest_api.py`

- [ ] **Step 1: Write failing integration tests for list summaries and unchanged push**

Add tests to `TestListNotes` in `tests/integration/test_notes_rest_api.py`:

```python
    def test_list_notes_returns_incremental_summary_fields(self, client):
        for sha, content in [("sha1", "content one"), ("sha2", "content two")]:
            client.put('/worker/notes',
                json={
                    "repo_url": "https://github.com/test/repo.git",
                    "branch": "main",
                    "commit_sha": sha,
                    "original_commit_sha": None,
                    "author_name": "Test",
                    "author_email": "test@test.com",
                    "content": content,
                },
                headers={'X-API-Key': 'test-key'}
            )

        response = client.post('/worker/notes/list',
            json={"repo_url": "https://github.com/test/repo.git", "since_change_seq": 0, "limit": 1},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert len(data['data']['commit_shas']) == 1
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['commit_sha'] == 'sha1'
        assert data['data']['items'][0]['content_hash'].startswith('sha256:')
        assert data['data']['items'][0]['change_seq'] > 0
        assert data['data']['next_change_seq'] == data['data']['items'][0]['change_seq']
        assert data['data']['has_more'] is True

    def test_batch_get_returns_hash_and_change_seq(self, client):
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "sha1",
                "original_commit_sha": None,
                "author_name": "Test",
                "author_email": "test@test.com",
                "content": "content one",
            },
            headers={'X-API-Key': 'test-key'}
        )

        response = client.post('/worker/notes/batch',
            json={"repo_url": "https://github.com/test/repo.git", "commit_shas": ["sha1"]},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        note = data['data']['notes'][0]
        assert note['commit_sha'] == 'sha1'
        assert note['content_hash'].startswith('sha256:')
        assert note['change_seq'] > 0
```

Add this test to `TestBatchPushNotes`:

```python
    def test_batch_push_reports_unchanged_for_same_content(self, client):
        payload = {
            "repo_url": "https://github.com/test/repo.git",
            "notes": [
                {
                    "branch": "main",
                    "commit_sha": "sha1",
                    "original_commit_sha": None,
                    "author_name": "User1",
                    "author_email": "user1@test.com",
                    "content": "content1",
                }
            ]
        }

        client.post('/worker/notes/push', json=payload, headers={'X-API-Key': 'test-key'})
        response = client.post('/worker/notes/push', json=payload, headers={'X-API-Key': 'test-key'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data'] == {"created": 0, "updated": 0, "unchanged": 1}
```

- [ ] **Step 2: Run integration tests to verify they fail**

Run:

```bash
pytest tests/integration/test_notes_rest_api.py -v
```

Expected: FAIL until route passes `since_change_seq` and returns new shape.

- [ ] **Step 3: Update `/list` route**

In `api/routes/authorship_notes.py`, replace the list route body after validation with:

```python
        since_commit_time = payload.get("since_commit_time")
        since_change_seq = payload.get("since_change_seq")
        limit = payload.get("limit")
        result = get_notes_service().list_notes(
            repo_url=payload["repo_url"],
            since_commit_time=since_commit_time,
            since_change_seq=since_change_seq,
            limit=limit,
        )

        return ok_response(result)
```

- [ ] **Step 4: Update old integration test expectations for push unchanged key if necessary**

In `test_batch_push_notes`, keep existing assertions and add:

```python
        assert data['data']['unchanged'] == 0
```

In `test_batch_push_with_updates`, add:

```python
        assert data['data']['unchanged'] == 0
```

Existing list tests that check `data['data']['commit_shas']` must continue to pass.

- [ ] **Step 5: Run integration tests to verify they pass**

Run:

```bash
pytest tests/integration/test_notes_rest_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/routes/authorship_notes.py tests/integration/test_notes_rest_api.py
git commit -m "feat: expose authorship notes incremental summaries"
```

---

## Task 4: Rust API types for incremental summaries

**Files:**
- Modify: `git-ai/src/api/types.rs`

- [ ] **Step 1: Add failing serde tests for new response shapes**

Add these tests inside `#[cfg(test)] mod tests` in `git-ai/src/api/types.rs`:

```rust
    #[test]
    fn parses_authorship_notes_list_summary_fields() {
        let json = r#"
        {
          "ok": true,
          "data": {
            "commit_shas": ["sha1"],
            "items": [
              {
                "commit_sha": "sha1",
                "content_hash": "sha256:abc",
                "change_seq": 42,
                "updated_at": 1000
              }
            ],
            "next_change_seq": 42,
            "has_more": false
          }
        }
        "#;

        let parsed: AuthorshipNotesListResponse = serde_json::from_str(json).unwrap();
        assert_eq!(parsed.data.commit_shas, vec!["sha1"]);
        assert_eq!(parsed.data.items.len(), 1);
        assert_eq!(parsed.data.items[0].content_hash, "sha256:abc");
        assert_eq!(parsed.data.items[0].change_seq, 42);
        assert_eq!(parsed.data.next_change_seq, 42);
        assert!(!parsed.data.has_more);
    }

    #[test]
    fn serializes_authorship_notes_list_request_with_change_seq_and_limit() {
        let request = AuthorshipNotesListRequest {
            repo_url: "https://github.com/test/repo.git".to_string(),
            since_commit_time: None,
            since_change_seq: Some(10),
            limit: Some(500),
        };

        let value = serde_json::to_value(request).unwrap();
        assert_eq!(value["repo_url"], "https://github.com/test/repo.git");
        assert_eq!(value["since_change_seq"], 10);
        assert_eq!(value["limit"], 500);
        assert!(value.get("since_commit_time").is_none());
    }

    #[test]
    fn parses_batch_notes_with_optional_hash_metadata() {
        let json = r#"
        {
          "ok": true,
          "data": {
            "notes": [
              {
                "commit_sha": "sha1",
                "content": "content one",
                "content_hash": "sha256:def",
                "change_seq": 12
              }
            ],
            "missing": []
          }
        }
        "#;

        let parsed: AuthorshipBatchResponse = serde_json::from_str(json).unwrap();
        assert_eq!(parsed.data.notes[0].content_hash.as_deref(), Some("sha256:def"));
        assert_eq!(parsed.data.notes[0].change_seq, Some(12));
    }
```

- [ ] **Step 2: Run Rust type tests to verify they fail**

Run:

```bash
cd git-ai && task test CARGO_TEST_ARGS="--lib api::types"
```

Expected: FAIL because fields are not defined.

- [ ] **Step 3: Update Rust request and response structs**

In `git-ai/src/api/types.rs`, update the list request:

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuthorshipNotesListRequest {
    pub repo_url: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub since_commit_time: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub since_change_seq: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub limit: Option<usize>,
}
```

Add summary item and update data:

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuthorshipNotesListItem {
    pub commit_sha: String,
    pub content_hash: String,
    pub change_seq: i64,
    pub updated_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuthorshipNotesListData {
    pub commit_shas: Vec<String>,
    #[serde(default)]
    pub items: Vec<AuthorshipNotesListItem>,
    #[serde(default)]
    pub next_change_seq: i64,
    #[serde(default)]
    pub has_more: bool,
    pub note_blob_oids: Option<Vec<String>>,
}
```

Update batch item:

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuthorshipNotesBatchItem {
    pub commit_sha: String,
    pub content: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub note_blob_oid: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub content_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub change_seq: Option<i64>,
}
```

Update push data:

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuthorshipNotesPushData {
    pub created: usize,
    pub updated: usize,
    #[serde(default)]
    pub unchanged: usize,
}
```

- [ ] **Step 4: Update existing list request constructors**

Find every `AuthorshipNotesListRequest` construction and add the new fields:

```rust
AuthorshipNotesListRequest {
    repo_url: repo_url.to_string(),
    since_commit_time: None,
    since_change_seq: None,
    limit: None,
}
```

- [ ] **Step 5: Run Rust type tests to verify they pass**

Run:

```bash
cd git-ai && task test CARGO_TEST_ARGS="--lib api::types"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add git-ai/src/api/types.rs git-ai/src/git/sync_authorship.rs
git commit -m "feat: add authorship notes incremental API types"
```

---

## Task 5: Rust local sync state and hash helpers

**Files:**
- Modify: `git-ai/src/git/sync_authorship.rs`

- [ ] **Step 1: Add focused unit tests for hash and sync state path behavior**

Add tests inside `#[cfg(test)] mod tests` in `git-ai/src/git/sync_authorship.rs`:

```rust
    #[test]
    fn note_content_hash_is_stable_sha256() {
        assert_eq!(
            note_content_hash("stable content"),
            "sha256:ce382ddb3d232ecb903c37fe6bd4779a18c6d664a15d7ddee0e5ca7ea9406120"
        );
    }

    #[test]
    fn sync_state_round_trips_last_change_seq() {
        let tmp_repo = TmpRepo::new().expect("create tmp repo");
        let repo = tmp_repo.gitai_repo();
        let repo_url = "https://github.com/test/repo.git";

        assert_eq!(load_rest_notes_sync_state(repo, repo_url).unwrap(), 0);
        save_rest_notes_sync_state(repo, repo_url, 42).unwrap();
        assert_eq!(load_rest_notes_sync_state(repo, repo_url).unwrap(), 42);
    }
```

- [ ] **Step 2: Run sync_authorship tests to verify they fail**

Run:

```bash
cd git-ai && task test CARGO_TEST_ARGS="--lib git::sync_authorship"
```

Expected: FAIL because helper functions do not exist.

- [ ] **Step 3: Add helper structs and functions**

At the top of `git-ai/src/git/sync_authorship.rs`, add imports:

```rust
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::PathBuf;
```

Add helper code near `list_local_authorship_notes_with_blob_oid`:

```rust
const REST_NOTES_SYNC_LIMIT: usize = 1000;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct RestNotesSyncState {
    repo_url: String,
    last_change_seq: i64,
}

fn note_content_hash(content: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(content.as_bytes());
    format!("sha256:{:x}", hasher.finalize())
}

fn rest_notes_sync_state_path(repository: &Repository, repo_url: &str) -> PathBuf {
    let mut hasher = Sha256::new();
    hasher.update(repo_url.as_bytes());
    let key = format!("{:x}", hasher.finalize());
    repository
        .common_dir()
        .join("ai")
        .join("rest_notes_sync_state")
        .join(format!("{key}.json"))
}

fn load_rest_notes_sync_state(repository: &Repository, repo_url: &str) -> Result<i64, GitAiError> {
    let path = rest_notes_sync_state_path(repository, repo_url);
    if !path.exists() {
        return Ok(0);
    }
    let contents = fs::read_to_string(path)?;
    let state: RestNotesSyncState = serde_json::from_str(&contents)?;
    Ok(state.last_change_seq)
}

fn save_rest_notes_sync_state(
    repository: &Repository,
    repo_url: &str,
    last_change_seq: i64,
) -> Result<(), GitAiError> {
    let path = rest_notes_sync_state_path(repository, repo_url);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let state = RestNotesSyncState {
        repo_url: repo_url.to_string(),
        last_change_seq,
    };
    fs::write(path, serde_json::to_vec_pretty(&state)?)?;
    Ok(())
}
```

`repository.common_dir()` is used instead of `repository.path().join(".git")` so the state file is written under the Git common directory for normal repos, bare repos, and linked worktrees.

- [ ] **Step 4: Run sync_authorship tests to verify they pass**

Run:

```bash
cd git-ai && task test CARGO_TEST_ARGS="--lib git::sync_authorship"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add git-ai/src/git/sync_authorship.rs
git commit -m "feat: persist REST notes sync watermark"
```

---

## Task 6: Rust incremental fetch using content hashes

**Files:**
- Modify: `git-ai/src/git/sync_authorship.rs:554-607`

- [ ] **Step 1: Add helper to read local note content hashes**

Add this helper near `list_local_authorship_notes_with_blob_oid`:

```rust
fn local_note_content_hashes_for_commits(
    repository: &Repository,
    commit_shas: &[String],
) -> HashMap<String, String> {
    let mut hashes = HashMap::new();
    for commit_sha in commit_shas {
        if let Some(content) = show_authorship_note(repository, commit_sha) {
            hashes.insert(commit_sha.clone(), note_content_hash(&content));
        }
    }
    hashes
}
```

- [ ] **Step 2: Replace REST fetch loop with paginated summary fetch**

Replace `rest_fetch_authorship_notes` with:

```rust
fn rest_fetch_authorship_notes(
    repository: &Repository,
    api: &ApiClient,
    repo_url: &str,
) -> Result<NotesExistence, GitAiError> {
    let starting_change_seq = load_rest_notes_sync_state(repository, repo_url)?;
    let mut since_change_seq = starting_change_seq;
    let mut latest_applied_change_seq = starting_change_seq;
    let mut saw_remote_notes = false;

    loop {
        let list_response =
            api.authorship_notes_list(&crate::api::types::AuthorshipNotesListRequest {
                repo_url: repo_url.to_string(),
                since_commit_time: None,
                since_change_seq: Some(since_change_seq),
                limit: Some(REST_NOTES_SYNC_LIMIT),
            })?;

        if list_response.data.items.is_empty() {
            if !saw_remote_notes {
                return Ok(NotesExistence::NotFound);
            }
            save_rest_notes_sync_state(repository, repo_url, latest_applied_change_seq)?;
            return Ok(NotesExistence::Found);
        }

        saw_remote_notes = true;
        let remote_commit_shas: Vec<String> = list_response
            .data
            .items
            .iter()
            .map(|item| item.commit_sha.clone())
            .collect();
        let local_hashes = local_note_content_hashes_for_commits(repository, &remote_commit_shas);

        let to_fetch: Vec<String> = list_response
            .data
            .items
            .iter()
            .filter(|item| {
                local_hashes
                    .get(&item.commit_sha)
                    .map(|hash| hash != &item.content_hash)
                    .unwrap_or(true)
            })
            .map(|item| item.commit_sha.clone())
            .collect();

        if !to_fetch.is_empty() {
            let batch_response: crate::api::AuthorshipBatchResponse =
                api.authorship_notes_batch_get(&crate::api::types::AuthorshipNotesBatchRequest {
                    repo_url: repo_url.to_string(),
                    commit_shas: to_fetch.clone(),
                })?;

            let requested: HashSet<String> = to_fetch.into_iter().collect();
            let entries: Vec<(String, String)> = batch_response
                .data
                .notes
                .into_iter()
                .filter(|note| requested.contains(&note.commit_sha))
                .map(|note| (note.commit_sha, note.content))
                .collect();

            if !entries.is_empty() {
                notes_add_batch(repository, &entries)?;
            }
        }

        latest_applied_change_seq = list_response.data.next_change_seq;
        since_change_seq = list_response.data.next_change_seq;

        if !list_response.data.has_more {
            save_rest_notes_sync_state(repository, repo_url, latest_applied_change_seq)?;
            return Ok(NotesExistence::Found);
        }
    }
}
```

- [ ] **Step 3: Preserve fallback for old servers**

If an old server returns `items: []` but non-empty `commit_shas`, keep the existing full-list behavior in a helper:

```rust
fn rest_fetch_authorship_notes_legacy_full_list(
    repository: &Repository,
    api: &ApiClient,
    repo_url: &str,
    remote_commit_shas: Vec<String>,
) -> Result<NotesExistence, GitAiError> {
    if remote_commit_shas.is_empty() {
        return Ok(NotesExistence::NotFound);
    }

    let local_note_blob_oids = note_blob_oids_for_commits(repository, &remote_commit_shas)?;
    let missing: Vec<String> = remote_commit_shas
        .iter()
        .filter(|commit_sha| !local_note_blob_oids.contains_key(*commit_sha))
        .cloned()
        .collect();

    if missing.is_empty() {
        return Ok(NotesExistence::Found);
    }

    let batch_response: crate::api::AuthorshipBatchResponse =
        api.authorship_notes_batch_get(&crate::api::types::AuthorshipNotesBatchRequest {
            repo_url: repo_url.to_string(),
            commit_shas: missing.clone(),
        })?;
    let missing_set: HashSet<String> = missing.into_iter().collect();
    let entries: Vec<(String, String)> = batch_response
        .data
        .notes
        .into_iter()
        .filter(|note| missing_set.contains(&note.commit_sha))
        .map(|note| (note.commit_sha, note.content))
        .collect();

    if !entries.is_empty() {
        notes_add_batch(repository, &entries)?;
    }

    Ok(NotesExistence::Found)
}
```

Then in the new fetch loop, after list response:

```rust
        if list_response.data.items.is_empty() && !list_response.data.commit_shas.is_empty() {
            return rest_fetch_authorship_notes_legacy_full_list(
                repository,
                api,
                repo_url,
                list_response.data.commit_shas,
            );
        }
```

- [ ] **Step 4: Run Rust sync tests**

Run:

```bash
cd git-ai && task test CARGO_TEST_ARGS="--lib git::sync_authorship"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add git-ai/src/git/sync_authorship.rs
git commit -m "feat: fetch authorship notes incrementally"
```

---

## Task 7: Rust push avoids blob oid consistency checks

**Files:**
- Modify: `git-ai/src/git/sync_authorship.rs:609-702`

- [ ] **Step 1: Update push logic to compare content hashes when summaries are available**

In `rest_push_notes`, replace remote full commit set lookup with summary lookup:

```rust
    let mut remote_hashes: HashMap<String, String> = HashMap::new();
    let mut since_change_seq = 0;
    loop {
        let response = api.authorship_notes_list(&crate::api::types::AuthorshipNotesListRequest {
            repo_url: repo_url.to_string(),
            since_commit_time: None,
            since_change_seq: Some(since_change_seq),
            limit: Some(REST_NOTES_SYNC_LIMIT),
        })?;

        if response.data.items.is_empty() && !response.data.commit_shas.is_empty() {
            for sha in response.data.commit_shas {
                remote_hashes.insert(sha, String::new());
            }
            break;
        }

        for item in response.data.items {
            remote_hashes.insert(item.commit_sha, item.content_hash);
        }

        if !response.data.has_more {
            break;
        }
        since_change_seq = response.data.next_change_seq;
    }
```

Then replace `local_notes_to_push` filtering with content hash comparison:

```rust
    let mut local_notes_to_push = Vec::new();
    for (sha, note_blob_oid) in local_notes {
        let Some(content) = show_authorship_note(repository, &sha) else {
            continue;
        };
        let local_hash = note_content_hash(&content);
        match remote_hashes.get(&sha) {
            Some(remote_hash) if remote_hash == &local_hash => {}
            _ => local_notes_to_push.push((sha, note_blob_oid, content)),
        }
    }
```

Update subsequent loops to use `(commit_sha, note_blob_oid, content)` and remove the second `show_authorship_note` call:

```rust
    let commits_to_push: Vec<String> = local_notes_to_push
        .iter()
        .map(|(sha, _, _)| sha.clone())
        .collect();
```

```rust
    for (commit_sha, note_blob_oid, content) in local_notes_to_push {
        let (git_author, commit_time) = commit_author_map
            .get(&commit_sha)
            .cloned()
            .unwrap_or_else(|| ("Unknown <unknown@example.com>".to_string(), 0));

        let (author_name, author_email) = parse_author_identity(&git_author);

        notes.push(crate::api::types::AuthorshipNotesPushItem {
            branch: branch.clone(),
            commit_sha,
            note_blob_oid,
            author_name,
            author_email,
            content,
            commit_time,
        });
    }
```

- [ ] **Step 2: Run Rust sync tests**

Run:

```bash
cd git-ai && task test CARGO_TEST_ARGS="--lib git::sync_authorship"
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add git-ai/src/git/sync_authorship.rs
git commit -m "feat: push authorship notes by content hash"
```

---

## Task 8: Full verification

**Files:**
- No code changes unless verification reveals defects.

- [ ] **Step 1: Run Python notes tests**

Run:

```bash
pytest tests/unit/test_models/test_notes.py tests/unit/test_services/test_notes_rest_service.py tests/integration/test_notes_rest_api.py -v
```

Expected: PASS.

- [ ] **Step 2: Run Rust targeted tests**

Run:

```bash
cd git-ai && task test CARGO_TEST_ARGS="--lib api::types git::sync_authorship"
```

Expected: PASS.

- [ ] **Step 3: Run Rust lint/format checks required by `git-ai/AGENTS.md`**

Run:

```bash
cd git-ai && task fmt && task lint
```

Expected: PASS.

- [ ] **Step 4: Run repository status check**

Run:

```bash
git status --short
```

Expected: Only intentional files changed. Do not include unrelated `D 1` unless the user explicitly asks to handle it.

- [ ] **Step 5: Commit final verification fixes if any**

If verification required changes, commit only those relevant files:

```bash
git add <relevant-files>
git commit -m "fix: stabilize authorship notes incremental sync"
```

---

## Self-Review Notes

- Spec coverage: schema metadata, content hash, `change_seq`, list pagination, batch metadata, push idempotency, fetch watermarking, no `note_blob_oid` consistency dependency, and verification are each covered by tasks above.
- Placeholder scan: this plan intentionally contains no placeholder markers or unspecified implementation steps.
- Type consistency: Python uses `content_hash`, `change_seq`, `since_change_seq`, `next_change_seq`, and `has_more`; Rust structs use the same JSON names through serde defaults.
