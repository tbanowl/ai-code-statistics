# Git Notes Sync Service 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于 Flask 的 Notes 同步服务，作为远程 Git notes 的替代方案，支持通过 HTTP API 存储和同步 notes 数据。

**架构:** 集成到现有 git-ai-code-metrics Flask 服务中，使用 SQLite 存储，提供 `/worker/notes` API 端点。服务器端通过 SQL 直接操作数据库，客户端通过 HTTP 请求同步 notes 数据。

**Tech Stack:** Python, Flask, SQLite, SQLAlchemy, dataclasses

---

## Task 1: 创建数据库 Schema 文件

**Files:**
- Create: `sql/notes_schema_sqlite.sql`

**Step 1: 创建数据库 Schema 文件**

```sql
-- Notes Sync Service 数据库表结构

-- 仓库表
CREATE TABLE IF NOT EXISTS git_repositories (
    id TEXT PRIMARY KEY NOT NULL,
    remote_url TEXT PRIMARY KEY NOT NULL,
    created_at TEXT NOT NULL,
    last_active_at TEXT
);

-- 分支表
CREATE TABLE IF NOT EXISTS git_branches (
    id TEXT PRIMARY KEY NOT NULL,
    remote_url TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    PRIMARY KEY (remote_url, branch_name)
);

-- Notes 表
CREATE TABLE IF NOT EXISTS git_notes (
    id TEXT PRIMARY KEY NOT NULL,
    remote_url TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    base_commit_sha TEXT NOT NULL,
    content TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    author_name TEXT NOT NULL,
    author_email TEXT NOT NULL,
    PRIMARY KEY (remote_url, branch_name, commit_sha)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_git_notes_updated_at ON git_notes(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_git_notes_commit_prefix ON git_notes(commit_sha(8));
CREATE INDEX IF NOT EXISTS idx_git_notes_base_commit ON git_notes(base_commit_sha(8));
CREATE INDEX IF NOT EXISTS idx_git_notes_author ON git_notes(author_email);
```

**Step 2: 初始化数据库**

```bash
cd Q:/w/prj/git-ai-code-metrics
sqlite3 data/ai_stats.db < sql/notes_schema_sqlite.sql
```

Expected: 无错误，表创建成功

**Step 3: 验证表创建**

```bash
sqlite3 data/ai_stats.db ".tables" | grep git_
```

Expected: 输出 `git_notes git_branches git_repositories`

**Step 4: Commit**

```bash
git add sql/notes_schema_sqlite.sql
git commit -m "feat: add notes sync service database schema"
```

---

## Task 2: 创建数据模型

**Files:**
- Create: `core/models/notes.py`

**Step 1: 写数据模型测试**

```bash
cd Q:/w/prj/git-ai-code-metrics
mkdir -p tests/unit
cat > tests/unit/test_notes_models.py << 'EOF'
import unittest
from core.models.notes import NoteModel, UpdateNoteRequest, GetNoteRequest

class TestNoteModels(unittest.TestCase):
    def test_note_model_creation(self):
        note = NoteModel(
            id="abc123def456abc12345",
            remote_url="https://github.com/user/repo.git",
            branch_name="main",
            commit_sha="abc123def456...",
            base_commit_sha="def456abc123...",
            content="notes content",
            version=1,
            updated_at="2026-03-27T10:00:00Z",
            author_name="John Doe",
            author_email="john@example.com"
        )
        self.assertEqual(note.remote_url, "https://github.com/user/repo.git")
        self.assertEqual(note.version, 1)

    def test_update_note_request_validation(self):
        req = UpdateNoteRequest(
            repo_url="https://github.com/user/repo.git",
            branch_name="main",
            commit_sha="abc123...",
            base_commit_sha="def456...",
            content="new content",
            author_name="John Doe",
            author_email="john@example.com"
        )
        self.assertEqual(req.repo_url, "https://github.com/user/repo.git")

if __name__ == '__main__':
    unittest.main()
EOF
```

**Step 2: 运行测试（预期失败）**

```bash
python -m pytest tests/unit/test_notes_models.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'core.models.notes'"

**Step 3: 实现数据模型**

```python
# core/models/notes.py
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import Optional, List

@dataclass_json
@dataclass
class NoteModel:
    """Notes 数据模型"""
    id: str
    remote_url: str
    branch_name: str
    commit_sha: str
    base_commit_sha: str
    content: str
    version: int
    updated_at: str
    author_name: str
    author_email: str

@dataclass_json
@dataclass
class UpdateNoteRequest:
    """更新 notes 请求"""
    repo_url: str
    branch_name: str
    commit_sha: str
    base_commit_sha: str
    content: str
    author_name: str
    author_email: str

@dataclass_json
@dataclass
class GetNoteRequest:
    """获取 notes 请求"""
    repo_url: str
    branch_name: str
    commit_sha: str

@dataclass_json
@dataclass
class GetNotesBatchRequest:
    """批量获取 notes 请求"""
    repo_url: str
    branch_name: str
    commit_shas: List[str]

@dataclass_json
@dataclass
class DeleteNoteRequest:
    """删除 notes 请求"""
    repo_url: str
    branch_name: str
    commit_sha: str

@dataclass_json
@dataclass
class SyncInfoRequest:
    """同步信息请求"""
    repo_url: str
    branch_name: str

@dataclass_json
@dataclass
class SyncInfo:
    """同步信息"""
    total_notes: int
    latest_updated_at: str
    checksum: Optional[str]
```

**Step 4: 运行测试通过**

```bash
python -m pytest tests/unit/test_notes_models.py -v
```

Expected: PASS (所有测试通过)

**Step 5: Commit**

```bash
git add core/models/notes.py tests/unit/test_notes_models.py
git commit -m "feat: add notes data models"
```

---

## Task 3: 创建 NotesService 层

**Files:**
- Create: `core/services/notes_service.py`

**Step 1: 写 NotesService 测试**

```bash
cat > tests/unit/test_notes_service.py << 'EOF'
import unittest
import os
import tempfile
import sqlite3
from core.services.notes_service import NotesService
from core.models.notes import UpdateNoteRequest

class TestNotesService(unittest.TestCase):
    def setUp(self):
        # 创建临时数据库
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.service = NotesService(f"sqlite:///{self.db_path}")

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_update_note(self):
        req = UpdateNoteRequest(
            repo_url="https://github.com/test/repo.git",
            branch_name="main",
            commit_sha="abc123",
            base_commit_sha="def456",
            content="test notes",
            author_name="Test User",
            author_email="test@example.com"
        )
        note = self.service.update_note(
            req.repo_url,
            req.branch_name,
            req.commit_sha,
            req.base_commit_sha,
            req.content,
            req.author_name,
            req.author_email
        )
        self.assertEqual(note.commit_sha, "abc123")
        self.assertEqual(note.version, 1)

    def test_get_note(self):
        # 先创建一条记录
        req = UpdateNoteRequest(
            repo_url="https://github.com/test/repo.git",
            branch_name="main",
            commit_sha="abc123",
            base_commit_sha="def456",
            content="test notes",
            author_name="Test User",
            author_email="test@example.com"
        )
        self.service.update_note(
            req.repo_url,
            req.branch_name,
            req.commit_sha,
            req.base_commit_sha,
            req.content,
            req.author_name,
            req.author_email
        )

        # 获取记录
        note = self.service.get_note(req.repo_url, req.branch_name, req.commit_sha)
        self.assertIsNotNone(note)
        self.assertEqual(note.content, "test notes")

if __name__ == '__main__':
    unittest.main()
EOF
```

**Step 2: 运行测试（预期失败）**

```bash
python -m pytest tests/unit/test_notes_service.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'core.services.notes_service'"

**Step 3: 实现 NotesService**

```python
# core/services/notes_service.py
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text
from core.database.base import session_scope
from core.models.notes import NoteModel, SyncInfo

class NotesService:
    def __init__(self, db_url=None):
        """初始化 NotesService

        Args:
            db_url: 数据库 URL，默认从环境变量读取
        """
        if db_url is None:
            import os
            db_url = os.environ.get("DB_URL", "sqlite:///data/ai_stats.db")

        self.engine = create_engine(db_url)
        self._init_tables()

    def _init_tables(self):
        """初始化数据库表"""
        with session_scope(self.engine) as session:
            # 执行 SQL 初始化
            import os
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sql_path = os.path.join(BASE_DIR, "sql", "notes_schema_sqlite.sql")
            if os.path.exists(sql_path):
                with open(sql_path, 'r') as f:
                    sql = f.read()
                session.execute(text(sql))

    def _generate_xid(self) -> str:
        """生成 20 字符 xid"""
        return str(uuid.uuid4()).replace('-', '')[:20]

    def update_note(self, repo_url: str, branch_name: str, commit_sha: str,
                   base_commit_sha: str, content: str, author_name: str,
                   author_email: str) -> NoteModel:
        """创建或更新 notes（最后写入胜出）"""
        now = datetime.utcnow().isoformat() + 'Z'

        with session_scope(self.engine) as session:
            # 检查 notes 是否存在
            result = session.execute(text("""
                SELECT id, version FROM git_notes
                WHERE remote_url = :url AND branch_name = :branch AND commit_sha = :sha
            """), {"url": repo_url, "branch": branch_name, "sha": commit_sha}).fetchone()

            if result:
                # 更新现有记录
                note_id, version = result
                version += 1
                session.execute(text("""
                    UPDATE git_notes
                    SET base_commit_sha = :base_sha, content = :content,
                        version = :version, updated_at = :updated_at,
                        author_name = :author_name, author_email = :author_email
                    WHERE id = :id
                """), {
                    "base_sha": base_commit_sha, "content": content,
                    "version": version, "updated_at": now,
                    "author_name": author_name, "author_email": author_email,
                    "id": note_id
                })
            else:
                # 创建新记录
                note_id = self._generate_xid()
                version = 1

                # 确保仓库存在
                session.execute(text("""
                    INSERT OR IGNORE INTO git_repositories (id, remote_url, created_at)
                    VALUES (:id, :url, :created_at)
                """), {"id": self._generate_xid(), "url": repo_url, "created_at": now})

                # 确保分支存在
                session.execute(text("""
                    INSERT OR IGNORE INTO git_branches (id, remote_url, branch_name)
                    VALUES (:id, :url, :branch)
                """), {"id": self._generate_xid(), "url": repo_url, "branch": branch_name})

                # 创建 notes
                session.execute(text("""
                    INSERT INTO git_notes (id, remote_url, branch_name, commit_sha,
                        base_commit_sha, content, version, updated_at,
                        author_name, author_email)
                    VALUES (:id, :url, :branch, :sha, :base_sha, :content,
                        :version, :updated_at, :author_name, :author_email)
                """), {
                    "id": note_id, "url": repo_url, "branch": branch_name,
                    "sha": commit_sha, "base_sha": base_commit_sha, "content": content,
                    "version": version, "updated_at": now,
                    "author_name": author_name, "author_email": author_email
                })

            return NoteModel(
                id=note_id,
                remote_url=repo_url,
                branch_name=branch_name,
                commit_sha=commit_sha,
                base_commit_sha=base_commit_sha,
                content=content,
                version=version,
                updated_at=now,
                author_name=author_name,
                author_email=author_email
            )

    def get_note(self, repo_url: str, branch_name: str, commit_sha: str) -> NoteModel:
        """获取单个 notes"""
        with session_scope(self.engine) as session:
            result = session.execute(text("""
                SELECT id, remote_url, branch_name, commit_sha, base_commit_sha,
                    content, version, updated_at, author_name, author_email
                FROM git_notes
                WHERE remote_url = :url AND branch_name = :branch AND commit_sha = :sha
            """), {"url": repo_url, "branch": branch_name, "sha": commit_sha}).fetchone()

            if result:
                return NoteModel(
                    id=result[0],
                    remote_url=result[1],
                    branch_name=result[2],
                    commit_sha=result[3],
                    base_commit_sha=result[4],
                    content=result[5],
                    version=result[6],
                    updated_at=result[7],
                    author_name=result[8],
                    author_email=result[9]
                )
            return None

    def get_notes_batch(self, repo_url: str, branch_name: str, commit_shas: list) -> dict:
        """批量获取 notes

        Returns:
            dict: {"notes": [NoteModel], "missing": [str]}
        """
        notes = []
        missing = []

        with session_scope(self.engine) as session:
            placeholders = ','.join([':' + str(i) for i in range(len(commit_shas))])
            params = {f"{i}": sha for i, sha in enumerate(commit_shas)}
            params["url"] = repo_url
            params["branch"] = branch_name

            results = session.execute(text(f"""
                SELECT id, remote_url, branch_name, commit_sha, base_commit_sha,
                    content, version, updated_at, author_name, author_email
                FROM git_notes
                WHERE remote_url = :url AND branch_name = :branch
                    AND commit_sha IN ({placeholders})
            """), params).fetchall()

            found_shas = set()
            for result in results:
                found_shas.add(result[3])
                notes.append(NoteModel(
                    id=result[0],
                    remote_url=result[1],
                    branch_name=result[2],
                    commit_sha=result[3],
                    base_commit_sha=result[4],
                    content=result[5],
                    version=result[6],
                    updated_at=result[7],
                    author_name=result[8],
                    author_email=result[9]
                ))

            missing = [sha for sha in commit_shas if sha not in found_shas]

        return {
            "notes": notes,
            "missing": missing
        }

    def delete_note(self, repo_url: str, branch_name: str, commit_sha: str) -> bool:
        """删除 notes"""
        with session_scope(self.engine) as session:
            result = session.execute(text("""
                DELETE FROM git_notes
                WHERE remote_url = :url AND branch_name = :branch AND commit_sha = :sha
            """), {"url": repo_url, "branch": branch_name, "sha": commit_sha})
            return result.rowcount > 0

    def get_sync_info(self, repo_url: str, branch_name: str) -> SyncInfo:
        """获取同步信息"""
        with session_scope(self.engine) as session:
            result = session.execute(text("""
                SELECT COUNT(*), MAX(updated_at)
                FROM git_notes
                WHERE remote_url = :url AND branch_name = :branch
            """), {"url": repo_url, "branch": branch_name}).fetchone()

            total = result[0] or 0
            latest = result[1]

            return SyncInfo(
                total_notes=total,
                latest_updated_at=latest or "",
                checksum=None
            )
```

**Step 4: 运行测试通过**

```bash
python -m pytest tests/unit/test_notes_service.py -v
```

Expected: PASS (所有测试通过)

**Step 5: Commit**

```bash
git add core/services/notes_service.py tests/unit/test_notes_service.py
git commit -m "feat: add notes service layer"
```

---

## Task 4: 创建 API 蓝图

**Files:**
- Create: `api/routes/notes.py`
- Create: `tests/integration/test_notes_api.py`

**Step 1: 写 API 测试**

```bash
mkdir -p tests/integration
cat > tests/integration/test_notes_api.py << 'EOF'
import unittest
import json
import os
import tempfile
from app import app

class TestNotesAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_health_endpoint(self):
        response = self.client.get('/worker/notes/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')

    def test_get_note_not_found(self):
        response = self.client.post('/worker/notes/get',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch_name": "main",
                "commit_sha": "nonexistent"
            },
            headers={'Authorization': 'Bearer test-key'}
        )
        self.assertEqual(response.status_code, 404)

    def test_update_note(self):
        response = self.client.put('/worker/notes/update',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch_name": "main",
                "commit_sha": "abc123",
                "base_commit_sha": "def456",
                "content": "test notes",
                "author_name": "Test User",
                "author_email": "test@example.com"
            },
            headers={'Authorization': 'Bearer test-key'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])

if __name__ == '__main__':
    unittest.main()
EOF
```

**Step 2: 运行测试（预期失败）**

```bash
python -m pytest tests/integration/test_notes_api.py -v
```

Expected: FAIL with "404 Not Found" (路由不存在)

**Step 3: 实现 API 蓝图**

```python
# api/routes/notes.py
from flask import Blueprint, request, jsonify
from core.middleware.auth_required import auth_required
from core.services.notes_service import NotesService
from core.models.notes import UpdateNoteRequest
from dataclasses import asdict

notes_bp = Blueprint('notes', __name__, url_prefix='/worker/notes')
notes_service = NotesService()

def success_response(data):
    """成功响应"""
    return jsonify({"success": True, "data": data})

def error_response(code, message, details=None):
    """错误响应"""
    return jsonify({
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {}
        }
    })

@notes_bp.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok'})

@notes_bp.route('/get', methods=['POST'])
@auth_required
def get_note():
    """获取单个 commit 的 notes"""
    try:
        payload = request.json
        note = notes_service.get_note(
            payload['repo_url'],
            payload['branch_name'],
            payload['commit_sha']
        )
        if note:
            return success_response(asdict(note))
        return error_response("NOT_FOUND", f"Note not found for commit {payload['commit_sha']}"), 404
    except KeyError as e:
        return error_response("INVALID_REQUEST", f"Missing required field: {e}"), 400
    except Exception as e:
        return error_response("SERVER_ERROR", str(e)), 500

@notes_bp.route('/batch', methods=['POST'])
@auth_required
def get_notes_batch():
    """批量获取 notes"""
    try:
        payload = request.json
        result = notes_service.get_notes_batch(
            payload['repo_url'],
            payload['branch_name'],
            payload['commit_shas']
        )
        # 转换 NoteModel 为 dict
        notes_data = [asdict(note) for note in result['notes']]
        return success_response({
            "notes": notes_data,
            "missing": result['missing']
        })
    except KeyError as e:
        return error_response("INVALID_REQUEST", f"Missing required field: {e}"), 400
    except Exception as e:
        return error_response("SERVER_ERROR", str(e)), 500

@notes_bp.route('/update', methods=['PUT'])
@auth_required
def put_note():
    """创建/更新 notes（最后写入胜出）"""
    try:
        payload = request.json
        note = notes_service.update_note(
            payload['repo_url'],
            payload['branch_name'],
            payload['commit_sha'],
            payload['base_commit_sha'],
            payload['content'],
            payload['author_name'],
            payload['author_email']
        )
        return success_response(asdict(note))
    except KeyError as e:
        return error_response("INVALID_REQUEST", f"Missing required field: {e}"), 400
    except Exception as e:
        return error_response("SERVER_ERROR", str(e)), 500

@notes_bp.route('/delete', methods=['DELETE'])
@auth_required
def delete_note():
    """删除 notes"""
    try:
        payload = request.json
        success = notes_service.delete_note(
            payload['repo_url'],
            payload['branch_name'],
            payload['commit_sha']
        )
        if success:
            return success_response({"deleted": True})
        return error_response("NOT_FOUND", "Note not found"), 404
    except KeyError as e:
        return error_response("INVALID_REQUEST", f"Missing required field: {e}"), 400
    except Exception as e:
        return error_response("SERVER_ERROR", str(e)), 500

@notes_bp.route('/sync/info', methods=['POST'])
@auth_required
def get_sync_info():
    """获取同步信息"""
    try:
        payload = request.json
        info = notes_service.get_sync_info(
            payload['repo_url'],
            payload['branch_name']
        )
        return success_response(asdict(info))
    except KeyError as e:
        return error_response("INVALID_REQUEST", f"Missing required field: {e}"), 400
    except Exception as e:
        return error_response("SERVER_ERROR", str(e)), 500
```

**Step 4: 注册蓝图到 app.py**

修改 `app.py`:

```python
# 在 app.py 顶部添加导入
from api.routes.notes import notes_bp

# 在注册蓝图部分添加
# 注册 Git-AI Worker 蓝图
app.register_blueprint(metrics_bp)
app.register_blueprint(cas_bp)
app.register_blueprint(oauth_bp)
app.register_blueprint(releases_bp)

# 注册 Notes Sync 蓝图 (新增)
app.register_blueprint(notes_bp)
```

**Step 5: 运行测试通过**

```bash
python -m pytest tests/integration/test_notes_api.py -v
```

Expected: PASS (所有测试通过)

**Step 6: Commit**

```bash
git add api/routes/notes.py app.py tests/integration/test_notes_api.py
git commit -m "feat: add notes API blueprint"
```

---

## Task 5: 添加配置

**Files:**
- Modify: `config.yaml`
- Modify: `.env.example`

**Step 1: 添加 config.yaml 配置**

```yaml
# 在 config.yaml 末尾添加

# Git-AI Notes 同步服务配置
git_ai:
  notes:
    enabled: true
    # API 认证密钥（可选）
    api_key: ${GIT_AI_NOTES_API_KEY:default-key}
    # 单次批量获取的最大 notes 数量
    max_batch_size: 100
    # notes 内容最大长度（字节）
    max_content_length: 1048576  # 1MB
```

**Step 2: 添加 .env.example 配置**

```bash
# 在 .env.example 末尾添加
# Notes 服务配置
GIT_AI_NOTES_API_KEY=your-secret-api-key
```

**Step 3: 验证配置加载**

```bash
python -c "from core.config.loader import load_config_by_path; import os; config = load_config_by_path('config.yaml'); print(config.get('git_ai', {}).get('notes', {}))"
```

Expected: 输出包含 `enabled`, `api_key`, `max_batch_size`, `max_content_length`

**Step 4: Commit**

```bash
git add config.yaml .env.example
git commit -m "feat: add notes service configuration"
```

---

## Task 6: 完整端到端测试

**Files:**
- None (使用 curl 手动测试)

**Step 1: 启动服务**

```bash
cd Q:/w/prj/git-ai-code-metrics
python app.py
```

Expected: 服务启动，显示 "启动服务器..." 和访问地址

**Step 2: 测试健康检查**

```bash
curl http://localhost:8888/worker/notes/health
```

Expected: `{"status": "ok"}`

**Step 3: 测试创建 notes**

```bash
curl -X PUT http://localhost:8888/worker/notes/update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{
    "repo_url": "https://github.com/test/example.git",
    "branch_name": "main",
    "commit_sha": "abc123def456abc123def456abc123def456abc1",
    "base_commit_sha": "def456abc123def456abc123def456abc123def456d",
    "content": "src/main.rs\n  hash1 1-10\n...\n---\n{}",
    "author_name": "Test User",
    "author_email": "test@example.com"
  }'
```

Expected: 返回 `{"success": true, "data": {...}}`

**Step 4: 测试获取 notes**

```bash
curl -X POST http://localhost:8888/worker/notes/get \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{
    "repo_url": "https://github.com/test/example.git",
    "branch_name": "main",
    "commit_sha": "abc123def456abc123def456abc123def456abc1"
  }'
```

Expected: 返回刚才创建的 notes 数据

**Step 5: 测试批量获取

```bash
curl -X POST http://localhost:8888/worker/notes/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{
    "repo_url": "https://github.com/test/example.git",
    "branch_name": "main",
    "commit_shas": ["abc123def456abc123def456abc123def456abc1", "nonexistent"]
  }'
```

Expected: 返回找到的 notes 和 missing 列表

**Step 6: 测试删除 notes**

```bash
curl -X DELETE http://localhost:8888/worker/notes/delete \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{
    "repo_url": "https://github.com/test/example.git",
    "branch_name": "main",
    "commit_sha": "abc123def456abc123def456abc123def456abc1"
  }'
```

Expected: 返回 `{"success": true, "data": {"deleted": true}}`

---

## Task 7: 更新文档

**Files:**
- Modify: `CLAUDE.md`

**Step 1: 添加文档到 CLAUDE.md**

在 CLAUDE.md 的核心架构部分添加：

```markdown
## Notes 同步服务 (/worker/notes)

当远程 Git 服务器不支持 refs/notes/* 的推送时，作为备用方案同步 notes 数据。

### 环境
- 数据库 URL: `DB_URL`
- API 密钥: `GIT_AI_NOTES_API_KEY`

### API 端点
- `GET /worker/notes/health` - 健康检查
- `POST /worker/notes/get` - 获取单个 notes
- `POST /worker/notes/batch` - 批量获取 notes
- `PUT /worker/notes/update` - 创建/更新 notes
- `DELETE /worker/notes/delete` - 删除 notes
- `POST /worker/notes/sync/info` - 获取同步信息
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add notes sync service documentation"
```

---

## Task 8: 最终验证和清理

**Step 1: 运行所有测试**

```bash
cd Q:/w/prj/git-ai-code-metrics
python -m pytest tests/ -v
```

Expected: 所有测试通过

**Step 2: 检查代码风格（可选）**

```bash
python -m flake8 api/routes/notes.py core/services/notes_service.py core/models/notes.py
```

Expected: 无警告或错误

**Step 3: 最终提交**

```bash
git push origin main
```

---

## 实现说明

### 关键设计决策

1. **数据库设计**: 使用三个表（git_repositories, git_branches, git_notes）通过 remote_url 和 branch_name 关联，避免外键约束
2. **ID 生成**: 使用 20 字符 xid（UUID 去掉横线后截取）
3. **冲突处理**: 采用最后写入胜出策略，version 字段记录更新次数
4. **认证**: 复用现有的 @auth_required 装饰器

### 扩展点

1. **数据压缩**: 未来可在 NoteModel 中添加 content_compressed 字段
2. **缓存**: 可添加 Redis 缓存层减少数据库查询
3. **多数据库支持**: 通过 Database 抽象层支持 PostgreSQL/MySQL
4. **批量优化**: NotesService.get_notes_batch 可使用参数化查询优化

### 参考技能

- @superpowers:test-driven-development - 测试驱动开发
- @superpowers:systematic-debugging - 系统化调试
