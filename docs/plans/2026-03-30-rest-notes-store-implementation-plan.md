# REST Notes Store Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a REST API backend for Git-AI authorship notes synchronization for platforms that don't support git notes push/fetch.

**Architecture:** Flask REST API with SQLAlchemy ORM, using XID for ID generation. The API provides CRUD operations for notes stored in database table `authorship_notes`, routed at `/worker/notes` prefix.

**Tech Stack:** Python 3.10+, Flask, SQLAlchemy, SQLite, xid library

---

## Task 1: Add SQLAlchemy Model for AuthorshipNotes

**Files:**
- Modify: `core/database/models.py`
- Test: `tests/unit/test_models/test_notes.py`

**Background:** SQLAlchemy 2.0 uses `MappedColumn` and type annotations. The project uses a `ModelBase` class that extends SQLAlchemy's `Base`. We add `UniqueConstraint` import for the database constraint.

**Step 1: Write the failing test**

Create `tests/unit/test_models/test_notes.py`:
```python
"""
Tests for AuthorshipNotes model
"""

import pytest
from core.database.models import AuthorshipNotes


def test_authorship_notes_model_columns():
    """Test AuthorshipNotes has all required columns"""
    # Get the table columns
    columns = {c.name for c in AuthorshipNotes.__table__.columns}

    expected_columns = {
        'id', 'repo_url', 'branch', 'commit_sha', 'original_commit_sha',
        'author_name', 'author_email', 'note_content', 'created_at', 'updated_at'
    }

    assert expected_columns.issubset(columns), f"Missing columns: {expected_columns - columns}"


def test_authorship_notes_unique_constraint():
    """Test AuthorshipNotes has unique constraint on repo_url + commit_sha"""
    constraints = AuthorshipNotes.__table_args__

    # Check for UniqueConstraint
    unique constraints = [c for c in constraints if hasattr(c, 'type') and c.type == 'unique']

    assert len(unique_constraints) > 0, "UniqueConstraint not found"


def test_authorship_notes_indexes():
    """Test AuthorshipNotes has required indexes"""
    indexes = {i.name for i in AuthorshipNotes.__table__.indexes}

    assert 'idx_authorship_notes_repo_url' in indexes, "Missing repo_url index"
    assert 'idx_authorship_notes_repo_commit' in indexes, "Missing repo_commit index"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_models/test_notes.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'core.database.models.AuthorshipNotes'` or similar

**Step 3: Write minimal implementation**

In `core/database/models.py`, first add `UniqueConstraint` to imports at line 11:
```python
from sqlalchemy import String, BigInteger, Integer, Text, ForeignKey, JSON, Numeric, Index, UniqueConstraint
```

Then at the end of the file (after `TelemetryEnvelope` class), add:
```python
# ============================================================================
# REST Notes Store 表
# ============================================================================


class AuthorshipNotes(ModelBase):
    """作者注释表 - 用于 REST Notes Store API"""

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

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_models/test_notes.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/database/models.py tests/unit/test_models/test_notes.py
git commit -m "feat: add AuthorshipNotes SQLAlchemy model"
```

---

## Task 2: Create SQL Schema for authorship_notes Table

**Files:**
- Create: `sql/authorship_notes_schema_sqlite.sql`

**Background:** This SQL creates the table structure that can be used to initialize SQLite databases. The project stores SQL schema files in `sql/` directory.

**Step 1: Create the SQL file**

Create `sql/authorship_notes_schema_sqlite.sql`:
```sql
-- ============================================================================
-- Authorship Notes 数据库表结构
-- 版本: 1.0
-- 日期: 2026-03-30
-- 用于 REST Notes Store API
-- ============================================================================

CREATE TABLE IF NOT EXISTS authorship_notes (
    -- 主键，使用 XID (20字符字符串)
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库远程 URL
    repo_url TEXT NOT NULL,
    -- 分支名称
    branch TEXT NOT NULL,
    -- 当前提交 SHA（40 字符）
    commit_sha VARCHAR(40) NOT NULL,
    -- rebase/cherry-pick 之前的原始提交 SHA
    original_commit_sha VARCHAR(40),
    -- 提交者名称
    author_name TEXT NOT NULL,
    -- 提交者邮箱
    author_email TEXT NOT NULL,
    -- AuthorshipLog 原始内容
    note_content TEXT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 唯一约束：同一仓库同一提交只能有一条记录
    UNIQUE(repo_url, commit_sha)
);

-- 索引：按仓库 URL 查询
CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_url ON authorship_notes(repo_url);
-- 索引：按仓库 URL 和提交 SHA 联合查询
CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_commit ON authorship_notes(repo_url, commit_sha);
```

**Step 2: Commit**

```bash
git add sql/authorship_notes_schema_sqlite.sql
git commit -m "feat: add authorship_notes SQL schema"
```

---

## Task 3: Create NotesRestService Layer

**Files:**
- Create: `core/services/notes_rest_service.py`
- Test: `tests/unit/test_services/test_notes_rest_service.py`
- Modify: `core/services/__init__.py`

**Background:** The service layer contains business logic. This service provides CRUD operations for notes. It uses `session_scope` context manager for database sessions and `get_engine` for getting database connections. XID is used for generating IDs.

**Step 1: Write the failing test**

Create `tests/unit/test_services/test_notes_rest_service.py`:
```python
"""
Tests for NotesRestService
"""

import pytest
import tempfile
import os
from core.services.notes_rest_service import NotesRestService


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield f'sqlite:///{path}'
    os.unlink(path)


@pytest.fixture
def service(temp_db):
    """Create service instance with temp database"""
    return NotesRestService(db_url=temp_db)


def test_create_note(service):
    """Test creating a new note"""
    result = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="abc123def4567890123456789012345678901234",
        original_commit_sha=None,
        content="test content",
        author_name="Test User",
        author_email="test@example.com"
    )

    assert result.id is not None
    assert result.repo_url == "https://github.com/test/repo.git"
    assert result.branch == "main"
    assert result.commit_sha == "abc123def4567890123456789012345678901234"
    assert result.note_content == "test content"
    assert result.author_name == "Test User"
    assert result.author_email == "test@example.com"


def test_update_note(service):
    """Test updating an existing note"""
    # Create initial note
    service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="abc123def4567890123456789012345678901234",
        original_commit_sha=None,
        content="original content",
        author_name="Test User",
        author_email="test@example.com"
    )

    # Update the note
    result = service.create_or_update_note(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        commit_sha="abc123def4567890123456789012345678901234",
        original_commit_sha="original123",
        content="updated content",
        author_name="Updated User",
        author_email="updated@example.com"
    )

    assert result.note_content == "updated content"
    assert result.original_commit_sha == "original123"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_services/test_notes_rest_service.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'core.services.notes_rest_service'`

**Step 3: Write minimal implementation**

Create `core/services/notes_rest_service.py`:
```python
"""
REST Notes Store 服务

提供 Authorship Notes 数据的 CRUD 业务逻辑。
"""

import os
import xid
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from core.database.base import get_engine, session_scope
from core.database.models import AuthorshipNotes


class NotesRestService:
    """REST Notes Store 服务"""

    def __init__(self, db_url: str = None):
        """初始化 NotesRestService

        Args:
            db_url: 数据库 URL，默认从环境变量读取
        """
        if db_url is None:
            db_url = os.environ.get("DB_URL", "sqlite:///data/ai_stats.db")

        self.engine = get_engine(db_url)
        self._init_tables()

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'engine'):
            self.engine.dispose()

    def _init_tables(self):
        """初始化数据库表"""
        import os
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sql_path = os.path.join(BASE_DIR, "sql", "authorship_notes_schema_sqlite.sql")

        if os.path.exists(sql_path):
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql = f.read()
            with session_scope(self.engine) as session:
                try:
                    statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
                    for stmt in statements:
                        session.execute(text(stmt))
                except Exception as e:
                    if "already exists" not in str(e):
                        raise

    def _gen_xid(self) -> str:
        """生成 XID 字符串"""
        return xid.Xid().string()

    def create_or_update_note(self, repo_url: str, branch: str, commit_sha: str,
                              original_commit_sha: str, content: str,
                              author_name: str, author_email: str) -> AuthorshipNotes:
        """创建或更新单个 notes

        Args:
            repo_url: 仓库远程 URL
            branch: 分支名称
            commit_sha: 提交 SHA
            original_commit_sha: 原始提交 SHA（rebase/cherry-pick 前）
            content: notes 内容
            author_name: 作者名称
            author_email: 作者邮箱

        Returns:
            AuthorshipNotes: 创建或更新后的 notes
        """
        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha == commit_sha
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                result.branch = branch
                result.original_commit_sha = original_commit_sha
                result.note_content = content
                result.author_name = author_name
                result.author_email = author_email
            else:
                note = AuthorshipNotes(
                    id=self._gen_xid(),
                    repo_url=repo_url,
                    branch=branch,
                    commit_sha=commit_sha,
                    original_commit_sha=original_commit_sha,
                    note_content=content,
                    author_name=author_name,
                    author_email=author_email
                )
                session.add(note)

            session.flush()
            return session.execute(stmt).scalar_one()

    def get_note(self, repo_url: str, commit_sha: str) -> AuthorshipNotes:
        """获取单个 notes"""
        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha == commit_sha
            )
            return session.execute(stmt).scalar_one_or_none()

    def batch_get_notes(self, repo_url: str, commit_shas: list) -> dict:
        """批量获取 notes"""
        if not commit_shas:
            return {"notes": [], "missing": []}

        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.commit_sha.in_(commit_shas)
            )
            results = session.execute(stmt).scalars().all()

            found_shas = set(note.commit_sha for note in results)
            notes = [{"commit_sha": note.commit_sha, "content": note.note_content} for note in results]
            missing = [sha for sha in commit_shas if sha not in found_shas]

        return {"notes": notes, "missing": missing}

    def batch_push_notes(self, repo_url: str, notes_data: list) -> dict:
        """批量推送（创建/更新）notes"""
        created = 0
        updated = 0

        with session_scope(self.engine) as session:
            existing_stmt = select(AuthorshipNotes.commit_sha).where(
                AuthorshipNotes.repo_url == repo_url
            )
            existing_shas = set(session.execute(existing_stmt).scalars().all())

            for note_data in notes_data:
                commit_sha = note_data["commit_sha"]

                if commit_sha in existing_shas:
                    stmt = select(AuthorshipNotes).where(
                        AuthorshipNotes.repo_url == repo_url,
                        AuthorshipNotes.commit_sha == commit_sha
                    )
                    note = session.execute(stmt).scalar_one()
                    note.branch = note_data["branch"]
                    note.original_commit_sha = note_data.get("original_commit_sha")
                    note.note_content = note_data["content"]
                    note.author_name = note_data["author_name"]
                    note.author_email = note_data["author_email"]
                    updated += 1
                else:
                    note = AuthorshipNotes(
                        id=self._gen_xid(),
                        repo_url=repo_url,
                        branch=note_data["branch"],
                        commit_sha=commit_sha,
                        original_commit_sha=note_data.get("original_commit_sha"),
                        note_content=note_data["content"],
                        author_name=note_data["author_name"],
                        author_email=note_data["author_email"]
                    )
                    session.add(note)
                    existing_shas.add(commit_sha)
                    created += 1

        return {"created": created, "updated": updated}

    def list_notes(self, repo_url: str) -> list:
        """列出仓库中所有有注释的提交 SHA"""
        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes.commit_sha).where(
                AuthorshipNotes.repo_url == repo_url
            ).order_by(AuthorshipNotes.commit_sha)
            return session.execute(stmt).scalars().all()

    def search_notes(self, repo_url: str, pattern: str) -> list:
        """在注释内容中搜索"""
        with session_scope(self.engine) as session:
            stmt = select(AuthorshipNotes.commit_sha).where(
                AuthorshipNotes.repo_url == repo_url,
                AuthorshipNotes.note_content.like(f"%{pattern}%")
            )
            return session.execute(stmt).scalars().all()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_services/test_notes_rest_service.py -v`
Expected: PASS

**Step 5: Update __init__.py**

In `core/services/__init__.py`, add:
```python
"""Services 模块提供业务逻辑处理"""

from .notes_rest_service import NotesRestService

__all__ = ["NotesRestService"]

# Keep existing exports if any
```

**Step 6: Commit**

```bash
git add core/services/notes_rest_service.py tests/unit/test_services/test_notes_rest_service.py core/services/__init__.py
git commit -m "feat: add NotesRestService for notes CRUD operations"
```

---

## Task 4: Create REST API Blueprint

**Files:**
- Create: `api/routes/notes_rest.py`
- Test: `tests/integration/test_notes_rest_api.py`
- Modify: `api/routes/__init__.py`

**Background:** Flask uses blueprints for routing. All blueprints are registered in `app.py`. The API uses `@auth_required` decorator for authentication. Response format follows `{"ok": true, "data": {...}}` pattern.

**Step 1: Write the failing test**

Create `tests/integration/test_notes_rest_api.py`:
```python
"""
Integration tests for Notes REST API
"""

import pytest
import json
from flask import Flask


@pytest.fixture
def app():
    """Create test app"""
    from api.routes.notes_rest import notes_rest_bp
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(notes_rest_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


def test_create_or_update_note(client):
    """Test PUT /worker/notes"""
    response = client.put('/worker/notes',
        json={
            "repo_url": "https://github.com/test/repo.git",
            "branch": "main",
            "commit_sha": "abc123def4567890123456789012345678901234",
            "original_commit_sha": None,
            "author_name": "Test User",
            "author_email": "test@example.com",
            "content": "test content"
        },
        headers={'X-API-Key': 'test-key'}
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True
    assert 'id' in data['data']


def test_get_note(client, app):
    """Test POST /worker/notes/get"""
    # First create a note
    client.put('/worker/notes',
        json={
            "repo_url": "https://github.com/test/repo.git",
            "branch": "main",
            "commit_sha": "abc123def4567890123456789012345678901234",
            "original_commit_sha": None,
            "author_name": "Test User",
            "author_email": "test@example.com",
            "content": "test content"
        },
        headers={'X-API-Key': 'test-key'}
    )

    # Then get it
    response = client.post('/worker/notes/get',
        json={
            "repo_url": "https://github.com/test/repo.git",
            "commit_sha": "abc123def4567890123456789012345678901234"
        },
        headers={'X-API-Key': 'test-key'}
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True
    assert data['data']['content'] == "test content"


def test_validate_required_fields(client):
    """Test validation of required fields"""
    response = client.put('/worker/notes',
        json={"repo_url": "https://github.com/test/repo.git"},  # Missing required fields
        headers={'X-API-Key': 'test-key'}
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['ok'] is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_notes_rest_api.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'api.routes.notes_rest'`

**Step 3: Write minimal implementation**

Create `api/routes/notes_rest.py`:
```python
"""
REST Notes Store API 路由

提供 Authorship Notes 的 REST API 端点。
路由前缀: /worker/notes
"""

from flask import Blueprint, request, jsonify
from core.middleware.auth import auth_required
from core.services.notes_rest_service import NotesRestService

notes_rest_bp = Blueprint('notes_rest', __name__, url_prefix='/worker/notes')
notes_service = NotesRestService()


def ok_response(data):
    """成功响应"""
    return jsonify({"ok": True, "data": data})


def error_response(message, status_code=400):
    """错误响应"""
    return jsonify({"ok": False, "error": message}), status_code


@notes_rest_bp.route('', methods=['PUT'])
@auth_required
def create_or_update_note():
    """创建或更新单个注释 (PUT /worker/notes)"""
    try:
        payload = request.json
        if not payload:
            return error_response("请求体不能为空", 400)

        required_fields = ['repo_url', 'branch', 'commit_sha', 'author_name', 'author_email', 'content']
        for field in required_fields:
            if field not in payload:
                return error_response(f"缺少必需字段: {field}", 400)

        note = notes_service.create_or_update_note(
            repo_url=payload['repo_url'],
            branch=payload['branch'],
            commit_sha=payload['commit_sha'],
            original_commit_sha=payload.get('original_commit_sha'),
            content=payload['content'],
            author_name=payload['author_name'],
            author_email=payload['author_email']
        )

        return ok_response({"id": note.id})

    except Exception as e:
        return error_response(f"服务器错误: {str(e)}", 500)


@notes_rest_bp.route('/get', methods=['POST'])
@auth_required
def get_note():
    """获取单个注释 (POST /worker/notes/get)"""
    try:
        payload = request.json
        if not payload:
            return error_response("请求体不能为空", 400)

        if 'repo_url' not in payload or 'commit_sha' not in payload:
            return error_response("缺少必需字段: repo_url 和 commit_sha", 400)

        note = notes_service.get_note(
            repo_url=payload['repo_url'],
            commit_sha=payload['commit_sha']
        )

        if not note:
            return error_response("note not found", 404)

        return ok_response({
            "id": note.id,
            "commit_sha": note.commit_sha,
            "branch": note.branch,
            "author_name": note.author_name,
            "author_email": note.author_email,
            "content": note.note_content,
            "created_at": note.created_at,
            "updated_at": note.updated_at
        })

    except Exception as e:
        return error_response(f"服务器错误: {str(e)}", 500)


@notes_rest_bp.route('/batch', methods=['POST'])
@auth_required
def batch_get_notes():
    """批量获取注释 (POST /worker/notes/batch)"""
    try:
        payload = request.json
        if not payload:
            return error_response("请求体不能为空", 400)

        if 'repo_url' not in payload or 'commit_shas' not in payload:
            return error_response("缺少必需字段: repo_url 和 commit_shas", 400)

        result = notes_service.batch_get_notes(
            repo_url=payload['repo_url'],
            commit_shas=payload['commit_shas']
        )

        return ok_response(result)

    except Exception as e:
        return error_response(f"服务器错误: {str(e)}", 500)


@notes_rest_bp.route('/push', methods=['POST'])
@auth_required
def batch_push_notes():
    """批量推送（创建/更新）注释 (POST /worker/notes/push)"""
    try:
        payload = request.json
        if not payload:
            return error_response("请求体不能为空", 400)

        if 'repo_url' not in payload or 'notes' not in payload:
            return error_response("缺少必需字段: repo_url 和 notes", 400)

        result = notes_service.batch_push_notes(
            repo_url=payload['repo_url'],
            notes_data=payload['notes']
        )

        return ok_response(result)

    except Exception as e:
        return error_response(f"服务器错误: {str(e)}", 500)


@notes_rest_bp.route('/list', methods=['POST'])
@auth_required
def list_notes():
    """列出仓库中所有有注释的提交 SHA (POST /worker/notes/list)"""
    try:
        payload = request.json
        if not payload:
            return error_response("请求体不能为空", 400)

        if 'repo_url' not in payload:
            return error_response("缺少必需字段: repo_url", 400)

        commit_shas = notes_service.list_notes(repo_url=payload['repo_url'])

        return ok_response({"commit_shas": commit_shas})

    except Exception as e:
        return error_response(f"服务器错误: {str(e)}", 500)


@notes_rest_bp.route('/search', methods=['POST'])
@auth_required
def search_notes():
    """在注释内容中搜索 (POST /worker/notes/search)"""
    try:
        payload = request.json
        if not payload:
            return error_response("请求体不能为空", 400)

        if 'repo_url' not in payload or 'pattern' not in payload:
            return error_response("缺少必需字段: repo_url 和 pattern", 400)

        commit_shas = notes_service.search_notes(
            repo_url=payload['repo_url'],
            pattern=payload['pattern']
        )

        return ok_response({"commit_shas": commit_shas})

    except Exception as e:
        return error_response(f"服务器错误: {str(e)}", 500)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_notes_rest_api.py -v`
Expected: PASS

**Step 5: Update routes __init__.py**

In `api/routes/__init__.py`, add to imports:
```python
from .notes_rest import notes_rest_bp

# Add to __all__ list
```

Update the `__all__` list to include `notes_rest_bp`.

**Step 6: Commit**

```bash
git add api/routes/notes_rest.py tests/integration/test_notes_rest_api.py api/routes/__init__.py
git commit -m "feat: add Notes REST API blueprint with 6 endpoints"
```

---

## Task 5: Register Blueprint in Application

**Files:**
- Modify: `app.py`

**Background:** Flask app registers all blueprints in `app.py`. Need to import the blueprint and call `app.register_blueprint()`.

**Step 1: Add import**

In `app.py`, after the other route imports (around line 14), add:
```python
from api.routes.notes_rest import notes_rest_bp
```

**Step 2: Register blueprint**

After the other `app.register_blueprint()` calls (around line 54), add:
```python
# 注册 REST Notes Store 蓝图
app.register_blueprint(notes_rest_bp)
```

**Step 3: Test manually**

Run: `python app.py` (in a separate terminal)
Run: `curl -X PUT http://localhost:8888/worker/notes -H "Content-Type: application/json" -H "X-API-Key: test-key" -d '{"repo_url":"https://test.com/repo.git","branch":"main","commit_sha":"abc123","author_name":"Test","author_email":"test@test.com","content":"test"}'`
Expected: `{"ok": true, "data": {"id": "..."}}`

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: register notes_rest blueprint in Flask app"
```

---

## Task 6: Update Main Database Schema

**Files:**
- Modify: `sql/metrics_schema_sqlite.sql`

**Background:** The main schema file should include the `authorship_notes` table for complete database initialization.

**Step 1: Add authorship_notes table to main schema**

In `sql/metrics_schema_sqlite.sql`, at the end of the file, add:
```sql
-- ============================================================================
-- REST Notes Store 表
-- ============================================================================

-- authorship_notes (作者注释表 - 用于 REST Notes Store API)
CREATE TABLE IF NOT EXISTS authorship_notes (
    -- 主键，使用 XID (20字符字符串)
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库远程 URL
    repo_url TEXT NOT NULL,
    -- 分支名称
    branch TEXT NOT NULL,
    -- 当前提交 SHA（40 字符）
    commit_sha VARCHAR(40) NOT NULL,
    -- rebase/cherry-pick 之前的原始提交 SHA
    original_commit_sha VARCHAR(40),
    -- 提交者名称
    author_name TEXT NOT NULL,
    -- 提交者邮箱
    author_email TEXT NOT NULL,
    -- AuthorshipLog 原始内容
    note_content TEXT NOT NULL,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    -- 唯一约束：同一仓库同一提交只能有一条记录
    UNIQUE(repo_url, commit_sha)
);

-- 索引：按仓库 URL 查询
CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_url ON authorship_notes(repo_url);
-- 索引：按仓库 URL 和提交 SHA 联合查询
CREATE INDEX IF NOT EXISTS idx_authorship_notes_repo_commit ON authorship_notes(repo_url, commit_sha);
```

**Step 2: Verify SQL syntax**

Run: `cat sql/metrics_schema_sqlite.sql | sqlite3 test.db`
Expected: No errors, tables created successfully

**Step 3: Commit**

```bash
git add sql/metrics_schema_sqlite.sql
git commit -m "feat: add authorship_notes table to main schema"
```

---

## Task 7: Create API Documentation

**Files:**
- Create: `docs/api/notes-rest.yaml`

**Background:** The project uses Swagger for API documentation stored as YAML files in `docs/api/` directory.

**Step 1: Create API documentation**

Create `docs/api/notes-rest.yaml`:
```yaml
openapi: 3.0.0
info:
  title: REST Notes Store API
  version: 2.0.0
  description: API for storing and retrieving authorship notes when git notes is not supported.

paths:
  /worker/notes:
    put:
      summary: Create or update a single note
      security:
        - bearerAuth: []
        - apiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - repo_url
                - branch
                - commit_sha
                - author_name
                - author_email
                - content
              properties:
                repo_url:
                  type: string
                  example: https://github.com/user/repo.git
                branch:
                  type: string
                  example: main
                commit_sha:
                  type: string
                  format: uuid
                  example: abc123def4567890123456789012345678901234
                original_commit_sha:
                  type: string
                  nullable: true
                author_name:
                  type: string
                  example: John Doe
                author_email:
                  type: string
                  format: email
                  example: john@example.com
                content:
                  type: string
                  description: Authorship log content
      responses:
        '200':
          description: Note created or updated
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok:
                    type: boolean
                  data:
                    type: object
                    properties:
                      id:
                        type: string

  /worker/notes/get:
    post:
      summary: Get a single note
      security:
        - bearerAuth: []
        - apiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - repo_url
                - commit_sha
              properties:
                repo_url:
                  type: string
                commit_sha:
                  type: string
      responses:
        '200':
          description: Note found
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok:
                    type: boolean
                  data:
                    $ref: '#/components/schemas/Note'
        '404':
          description: Note not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  /worker/notes/batch:
    post:
      summary: Batch get notes
      security:
        - bearerAuth: []
        - apiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - repo_url
                - commit_shas
              properties:
                repo_url:
                  type: string
                commit_shas:
                  type: array
                  items:
                    type: string
      responses:
        '200':
          description: Batch notes retrieved
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok:
                    type: boolean
                  data:
                    type: object
                    properties:
                      notes:
                        type: array
                        items:
                          type: object
                          properties:
                            commit_sha:
                              type: string
                            content:
                              type: string
                      missing:
                        type: array
                        items:
                          type: string

  /worker/notes/push:
    post:
      summary: Batch push (create/update) notes
      security:
        - bearerAuth: []
        - apiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - repo_url
                - notes
              properties:
                repo_url:
                  type: string
                notes:
                  type: array
                  items:
                    type: object
                    required:
                      - branch
                      - commit_sha
                      - author_name
                      - author_email
                      - content
                    properties:
                      branch:
                        type: string
                      commit_sha:
                        type: string
                      original_commit_sha:
                        type: string
                        nullable: true
                      author_name:
                        type: string
                      author_email:
                        type: string
                      content:
                        type: string
      responses:
        '200':
          description: Notes pushed
          content:
            application/json:
              schema:
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

  /worker/notes/list:
    post:
      summary: List all commit SHAs with notes for a repository
      security:
        - bearerAuth: []
        - apiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - repo_url
              properties:
                repo_url:
                  type: string
      responses:
        '200':
          description: List of commit SHAs
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok:
                    type: boolean
                  data:
                    type: object
                    properties:
                      commit_shas:
                        type: array
                        items:
                          type: string

  /worker/notes/search:
    post:
      summary: Search notes by content pattern
      security:
        - bearerAuth: []
        - apiKeyAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - repo_url
                - pattern
              properties:
                repo_url:
                  type: string
                pattern:
                  type: string
                  description: Search pattern (uses LIKE)
      responses:
        '200':
          description: Matching commit SHAs
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok:
                    type: boolean
                  data:
                    type: object
                    properties:
                      commit_shas:
                        type: array
                        items:
                          type: string

components:
  schemas:
    Note:
      type: object
      properties:
        id:
          type: string
        commit_sha:
          type: string
        branch:
          type: string
        author_name:
          type: string
        author_email:
          type: string
        content:
          type: string
        created_at:
          type: integer
          format: int64
        updated_at:
          type: integer
          format: int64

    Error:
      type: object
      properties:
        ok:
          type: boolean
          enum: [false]
        error:
          type: string

  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
```

**Step 2: Commit**

```bash
git add docs/api/notes-rest.yaml
git commit -m "docs: add OpenAPI spec for Notes REST API"
```

---

## Task 8: Add Comprehensive Integration Tests

**Files:**
- Create: `tests/integration/test_notes_rest_api_full.py`

**Background:** Add comprehensive tests for all endpoints to ensure the API works end-to-end.

**Step 1: Create full integration tests**

Create `tests/integration/test_notes_rest_api_full.py`:
```python
"""
Comprehensive integration tests for Notes REST API
"""

import pytest
import json
import tempfile
import os


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield f'sqlite:///{path}'
    os.unlink(path)


@pytest.fixture
def app(temp_db):
    """Create test app with temp database"""
    os.environ['DB_URL'] = temp_db

    from api.routes.notes_rest import notes_rest_bp
    from flask import Flask

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['DEBUG'] = True
    app.register_blueprint(notes_rest_bp)

    # Initialize database tables
    from core.services.notes_rest_service import NotesRestService
    service = NotesRestService()

    yield app
    service.close()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


class TestCreateOrUpdateNote:
    """Tests for PUT /worker/notes"""

    def test_create_note_success(self, client):
        response = client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "abc123def4567890123456789012345678901234",
                "original_commit_sha": None,
                "author_name": "Test User",
                "author_email": "test@example.com",
                "content": "test content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert 'id' in data['data']
        assert len(data['data']['id']) == 20

    def test_update_note(self, client):
        # Create
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "abc123",
                "original_commit_sha": None,
                "author_name": "Test User",
                "author_email": "test@example.com",
                "content": "original content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        # Update
        response = client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "develop",
                "commit_sha": "abc123",
                "original_commit_sha": "xyz789",
                "author_name": "Updated User",
                "author_email": "updated@example.com",
                "content": "updated content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_missing_required_field(self, client):
        response = client.put('/worker/notes',
            json={"repo_url": "https://test.com/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert '缺少必需字段' in data['error']

    def test_empty_request_body(self, client):
        response = client.put('/worker/notes',
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 400


class TestGetNote:
    """Tests for POST /worker/notes/get"""

    def test_get_note_success(self, client):
        # Create first
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "abc123",
                "original_commit_sha": None,
                "author_name": "Test User",
                "author_email": "test@example.com",
                "content": "test content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        # Get
        response = client.post('/worker/notes/get',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_sha": "abc123"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['data']['content'] == "test content"
        assert data['data']['author_name'] == "Test User"

    def test_get_note_not_found(self, client):
        response = client.post('/worker/notes/get',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_sha": "nonexistent"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['ok'] is False
        assert data['error'] == "note not found"


class TestBatchGetNotes:
    """Tests for POST /worker/notes/batch"""

    def test_batch_get_notes(self, client):
        # Create notes
        for sha in ["sha1", "sha2", "sha3"]:
            client.put('/worker/notes',
                json={
                    "repo_url": "https://github.com/test/repo.git",
                    "branch": "main",
                    "commit_sha": sha,
                    "original_commit_sha": None,
                    "author_name": "Test",
                    "author_email": "test@test.com",
                    "content": f"content {sha}"
                },
                headers={'X-API-Key': 'test-key'}
            )

        # Batch get
        response = client.post('/worker/notes/batch',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_shas": ["sha1", "sha2", "nonexistent"]
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert len(data['data']['notes']) == 2
        assert "nonexistent" in data['data']['missing']

    def test_batch_get_empty_list(self, client):
        response = client.post('/worker/notes/batch',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_shas": []
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['notes'] == []
        assert data['data']['missing'] == []


class TestBatchPushNotes:
    """Tests for POST /worker/notes/push"""

    def test_batch_push_notes(self, client):
        response = client.post('/worker/notes/push',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "notes": [
                    {
                        "branch": "main",
                        "commit_sha": "sha1",
                        "original_commit_sha": None,
                        "author_name": "User1",
                        "author_email": "user1@test.com",
                        "content": "content1"
                    },
                    {
                        "branch": "main",
                        "commit_sha": "sha2",
                        "original_commit_sha": None,
                        "author_name": "User2",
                        "author_email": "user2@test.com",
                        "content": "content2"
                    }
                ]
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['data']['created'] == 2
        assert data['data']['updated'] == 0

    def test_batch_push_with_updates(self, client):
        # Create one note first
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "sha1",
                "original_commit_sha": None,
                "author_name": "User1",
                "author_email": "user1@test.com",
                "content": "old content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        # Batch push including the existing one and a new one
        response = client.post('/worker/notes/push',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "notes": [
                    {
                        "branch": "main",
                        "commit_sha": "sha1",
                        "original_commit_sha": None,
                        "author_name": "User1 Updated",
                        "author_email": "user1@test.com",
                        "content": "new content"
                    },
                    {
                        "branch": "main",
                        "commit_sha": "sha2",
                        "original_commit_sha": None,
                        "author_name": "User2",
                        "author_email": "user2@test.com",
                        "content": "content2"
                    }
                ]
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['created'] == 1
        assert data['data']['updated'] == 1


class TestListNotes:
    """Tests for POST /worker/notes/list"""

    def test_list_notes(self, client):
        # Create notes
        for sha in ["sha1", "sha2", "sha3"]:
            client.put('/worker/notes',
                json={
                    "repo_url": "https://github.com/test/repo.git",
                    "branch": "main",
                    "commit_sha": sha,
                    "original_commit_sha": None,
                    "author_name": "Test",
                    "author_email": "test@test.com",
                    "content": "content"
                },
                headers={'X-API-Key': 'test-key'}
            )

        response = client.post('/worker/notes/list',
            json={"repo_url": "https://github.com/test/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert len(data['data']['commit_shas']) == 3
        assert set(data['data']['commit_shas']) == {"sha1", "sha2", "sha3"}

    def test_list_notes_empty(self, client):
        response = client.post('/worker/notes/list',
            json={"repo_url": "https://github.com/empty/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['commit_shas'] == []


class TestSearchNotes:
    """Tests for POST /worker/notes/search"""

    def test_search_notes(self, client):
        # Create notes
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "sha1",
                "original_commit_sha": None,
                "author_name": "Test",
                "author_email": "test@test.com",
                "content": "cursor position"
            },
            headers={'X-API-Key': 'test-key'}
        )

        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "sha2",
                "original_commit_sha": None,
                "author_name": "Test",
                "author_email": "test@test.com",
                "content": "buffer size"
            },
            headers={'X-API-Key': 'test-key'}
        )

        response = client.post('/worker/notes/search',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "pattern": "cursor"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert "sha1" in data['data']['commit_shas']

    def test_search_notes_no_results(self, client):
        response = client.post('/worker/notes/search',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "pattern": "nonexistent"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['commit_shas'] == []
```

**Step 2: Run all tests**

Run: `pytest tests/integration/test_notes_rest_api_full.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/integration/test_notes_rest_api_full.py
git commit -m "test: add comprehensive integration tests for Notes API"
```

---

## Task 9: Verify All Tests Pass

**Step 1: Run all related tests**

```bash
pytest tests/unit/test_models/test_notes.py \
       tests/unit/test_services/test_notes_rest_service.py \
       tests/integration/test_notes_rest_api.py \
       tests/integration/test_notes_rest_api_full.py -v
```

Expected: All tests pass

**Step 2: Run full test suite**

```bash
pytest tests/ -k "not slow" --tb=short
```

Expected: Tests pass, no regressions

**Step 3: Verify API is accessible**

```bash
python app.py
```

In another terminal:
```bash
# Test health endpoint
curl http://localhost:8888/health

# Test create note
curl -X PUT http://localhost:8888/worker/notes \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "repo_url": "https://github.com/test/repo.git",
    "branch": "main",
    "commit_sha": "abc123def4567890123456789012345678901234",
    "author_name": "Test User",
    "author_email": "test@example.com",
    "content": "test note content"
  }'

# Test get note
curl -X POST http://localhost:8888/worker/notes/get \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{"repo_url": "https://github.com/test/repo.git", "commit_sha": "abc123def4567890123456789012345678901234"}'
```

---

## Summary

This implementation creates a complete REST API for Git-AI authorship notes storage with:

1. **Database Layer**: SQLAlchemy model `AuthorshipNotes` with proper indexes and constraints
2. **Schema**: SQL DDL for SQLite with XID primary keys and timestamp fields
3. **Service Layer**: `NotesRestService` providing CRUD operations
4. **API Layer**: Flask blueprint with 6 endpoints (PUT, GET, batch, push, list, search)
5. **Integration**: Blueprint registered in main app
6. **Testing**: Unit tests for models and services, integration tests for API
7. **Documentation**: OpenAPI 3.0 specification

All endpoints follow the project's error response format and use the existing `@auth_required` decorator.
