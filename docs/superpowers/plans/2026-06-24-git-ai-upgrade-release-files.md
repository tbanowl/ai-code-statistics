# Git-AI Upgrade Release Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现内部 Git-AI 发布管理能力：管理员在前端上传本地构建的安装脚本和可执行文件，后端保存到数据库，`git-ai upgrade` 从内部平台下载并校验升级文件。

**Architecture:** 后端新增 release 数据模型、数据库访问层和服务层，`api/routes/git_ai_worker.py` 继续承载公开 upgrade 接口并新增管理接口。前端新增 “Git-AI 管理 > 发布管理” 页面，使用 Element Plus 上传本地 release 文件。客户端只做最小错误提示增强，升级主流程保持兼容。

**Tech Stack:** Flask, SQLAlchemy 2.0, MySQL/SQLite, Vue 3, Element Plus, TypeScript, Rust 2024, `task test`, `pnpm build`.

---

## File Structure

**Backend**

- Modify: `core/database/models.py` — 增加 `GitAiRelease` 和 `GitAiReleaseArtifact` ORM 模型。
- Create: `core/database/release_db.py` — release 专用数据访问层。
- Modify: `core/database/__init__.py` — 导出 `ReleaseDatabase`。
- Create: `core/services/release_service.py` — 上传校验、SHA-256 计算、`SHA256SUMS` 生成、release 激活和下载元数据。
- Modify: `api/routes/git_ai_worker.py` — 扩展 `releases_bp` 的公开下载接口和管理接口。
- Modify: `config.yaml` — 增加 `git_ai.releases` 配置。
- Create: `tests/unit/test_database/test_release_db.py` — 数据层测试。
- Create: `tests/unit/test_services/test_release_service.py` — 服务层测试。
- Create: `tests/integration/test_git_ai_releases_api.py` — Flask API 集成测试。
- Modify or create: `docs/swagger/api/releases.yaml` — 更新 Release API 文档。

**Frontend**

- Create: `frontend/src/api/gitAiRelease.ts` — release 管理 API 封装。
- Create: `frontend/src/views/git-ai-release/index.vue` — 发布管理页面。
- Create or modify: `frontend/src/router/modules/git-ai.ts` — 新增 “Git-AI 管理 > 发布管理” 菜单路由。

**Client**

- Modify: `git-ai/src/commands/upgrade.rs` — 增强下载 404 和 artifact 缺失错误提示。

---

### Task 1: Backend ORM Models

**Files:**
- Modify: `core/database/models.py`
- Test: `tests/unit/test_database/test_release_db.py`

- [ ] **Step 1: Add failing model smoke test**

Create `tests/unit/test_database/test_release_db.py` with a temp SQLite fixture patterned after `tests/integration/test_notes_rest_api.py`:

```python
import os
import tempfile

import core.config.loader as loader
import core.database.base as database_base
from sqlalchemy import create_engine

from core.database.base import Base, session_scope


def test_release_models_can_persist_blob_artifact():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    temp_db_url = f"sqlite:///{path}"
    previous_config_data = loader.config_data
    previous_global_engine = database_base.global_engine
    engine = create_engine(temp_db_url, echo=False)
    loader.config_data = {"database": {"url": temp_db_url, "echo": False}}
    database_base.global_engine = engine
    try:
        Base.metadata.create_all(engine)
        from core.database.models import GitAiRelease, GitAiReleaseArtifact

        with session_scope(engine) as session:
            release = GitAiRelease(
                tag="v1.2.3",
                version="v1.2.3",
                channel="latest",
                status="inactive",
                sha256sums_checksum="abc123",
            )
            session.add(release)
            session.flush()
            session.add(
                GitAiReleaseArtifact(
                    release_id=release.id,
                    filename="install.ps1",
                    artifact_type="installer",
                    platform="windows-x64",
                    sha256="def456",
                    size_bytes=8,
                    content_type="text/plain",
                    content_blob=b"Write-Ok",
                )
            )

        with session_scope(engine) as session:
            artifact = session.query(GitAiReleaseArtifact).filter_by(filename="install.ps1").one()
            assert artifact.content_blob == b"Write-Ok"
    finally:
        engine.dispose()
        loader.config_data = previous_config_data
        database_base.global_engine = previous_global_engine
        os.unlink(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_database/test_release_db.py::test_release_models_can_persist_blob_artifact -v`

Expected: FAIL with import error for `GitAiRelease`.

- [ ] **Step 3: Add ORM models**

In `core/database/models.py`, add imports and model classes near other Git-AI collection models:

```python
from sqlalchemy import LargeBinary
```

```python
class GitAiRelease(ModelBase):
    """Git-AI 客户端发布版本。"""

    __tablename__ = "git_ai_releases"
    __table_args__ = (
        UniqueConstraint("channel", "tag"),
        Index("idx_git_ai_releases_channel_status", "channel", "status"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    tag: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="inactive")
    sha256sums_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=True)
    published_at: Mapped[int] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts, onupdate=now_ts)


class GitAiReleaseArtifact(ModelBase):
    """Git-AI 发布文件，内容保存到数据库。"""

    __tablename__ = "git_ai_release_artifacts"
    __table_args__ = (
        UniqueConstraint("release_id", "filename"),
        Index("idx_git_ai_release_artifacts_release", "release_id"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    release_id: Mapped[str] = mapped_column(String(20), ForeignKey("git_ai_releases.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(30), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_blob: Mapped[bytes] = mapped_column(LargeBinary(length=(2**32) - 1), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
```

- [ ] **Step 4: Run model test**

Run: `pytest tests/unit/test_database/test_release_db.py::test_release_models_can_persist_blob_artifact -v`

Expected: PASS.

---

### Task 2: Release Database Layer

**Files:**
- Create: `core/database/release_db.py`
- Modify: `core/database/__init__.py`
- Test: `tests/unit/test_database/test_release_db.py`

- [ ] **Step 1: Add failing database behavior tests**

Extend `tests/unit/test_database/test_release_db.py` with:

```python
def test_activate_release_deactivates_previous_release(sqlite_release_db):
    db = sqlite_release_db
    first = db.create_release(
        tag="v1.0.0",
        version="v1.0.0",
        channel="latest",
        sha256sums_checksum="a" * 64,
        artifacts=[],
        description=None,
        created_by="tester",
    )
    second = db.create_release(
        tag="v1.0.1",
        version="v1.0.1",
        channel="latest",
        sha256sums_checksum="b" * 64,
        artifacts=[],
        description=None,
        created_by="tester",
    )

    db.activate_release(first["id"])
    db.activate_release(second["id"])

    assert db.get_release(first["id"])["status"] == "inactive"
    assert db.get_release(second["id"])["status"] == "active"
    assert db.get_active_release("latest")["tag"] == "v1.0.1"


def test_get_artifact_returns_content(sqlite_release_db):
    db = sqlite_release_db
    release = db.create_release(
        tag="v1.0.0",
        version="v1.0.0",
        channel="latest",
        sha256sums_checksum="a" * 64,
        artifacts=[{
            "filename": "install.ps1",
            "artifact_type": "installer",
            "platform": "windows-x64",
            "sha256": "b" * 64,
            "size_bytes": 8,
            "content_type": "text/plain",
            "content_blob": b"Write-Ok",
        }],
        description=None,
        created_by="tester",
    )

    artifact = db.get_artifact(release["id"], "install.ps1")
    assert artifact["content_blob"] == b"Write-Ok"
```

Add a `sqlite_release_db` fixture that sets `loader.config_data`, `database_base.global_engine`, creates tables, imports `ReleaseDatabase`, yields it, and restores state.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/test_database/test_release_db.py -v`

Expected: FAIL because `core.database.release_db` does not exist.

- [ ] **Step 3: Implement `ReleaseDatabase`**

Create `core/database/release_db.py`:

```python
from typing import Any

from .base import BaseDatabase, session_scope, now_ts
from .models import GitAiRelease, GitAiReleaseArtifact


class ReleaseDatabase(BaseDatabase):
    def create_release(self, *, tag: str, version: str, channel: str, sha256sums_checksum: str, artifacts: list[dict[str, Any]], description: str | None, created_by: str | None) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            release = GitAiRelease(
                tag=tag,
                version=version,
                channel=channel,
                status="inactive",
                sha256sums_checksum=sha256sums_checksum,
                description=description,
                created_by=created_by,
                published_at=None,
            )
            session.add(release)
            session.flush()
            for artifact in artifacts:
                session.add(GitAiReleaseArtifact(release_id=release.id, **artifact))
            session.flush()
            return release.to_dict()

    def activate_release(self, release_id: str) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            release = session.query(GitAiRelease).filter(GitAiRelease.id == release_id).first()
            if release is None:
                return None
            session.query(GitAiRelease).filter(
                GitAiRelease.channel == release.channel,
                GitAiRelease.status == "active",
            ).update({"status": "inactive"})
            release.status = "active"
            release.published_at = now_ts()
            session.flush()
            return release.to_dict()

    def get_release(self, release_id: str) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            release = session.query(GitAiRelease).filter(GitAiRelease.id == release_id).first()
            return release.to_dict() if release else None

    def get_active_release(self, channel: str) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            release = session.query(GitAiRelease).filter(
                GitAiRelease.channel == channel,
                GitAiRelease.status == "active",
            ).first()
            return release.to_dict() if release else None

    def list_releases(self, channel: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        with session_scope(self.engine) as session:
            query = session.query(GitAiRelease)
            if channel:
                query = query.filter(GitAiRelease.channel == channel)
            if status:
                query = query.filter(GitAiRelease.status == status)
            return [row.to_dict() for row in query.order_by(GitAiRelease.created_at.desc()).all()]

    def list_artifacts(self, release_id: str, include_content: bool = False) -> list[dict[str, Any]]:
        with session_scope(self.engine) as session:
            rows = session.query(GitAiReleaseArtifact).filter(GitAiReleaseArtifact.release_id == release_id).all()
            result = []
            for row in rows:
                data = row.to_dict()
                if not include_content:
                    data.pop("content_blob", None)
                result.append(data)
            return result

    def get_artifact(self, release_id: str, filename: str) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            row = session.query(GitAiReleaseArtifact).filter(
                GitAiReleaseArtifact.release_id == release_id,
                GitAiReleaseArtifact.filename == filename,
            ).first()
            return row.to_dict() if row else None
```

Update `core/database/__init__.py` to import and export `ReleaseDatabase`.

- [ ] **Step 4: Run database tests**

Run: `pytest tests/unit/test_database/test_release_db.py -v`

Expected: PASS.

---

### Task 3: Release Service Validation and SHA256SUMS Generation

**Files:**
- Create: `core/services/release_service.py`
- Test: `tests/unit/test_services/test_release_service.py`

- [ ] **Step 1: Add failing service tests**

Create `tests/unit/test_services/test_release_service.py`:

```python
from dataclasses import dataclass

import pytest

from core.services.release_service import ReleaseService, ReleaseValidationError


@dataclass
class UploadFile:
    filename: str
    data: bytes
    content_type: str = "application/octet-stream"

    def read(self):
        return self.data


class FakeReleaseDatabase:
    def __init__(self):
        self.created = None

    def create_release(self, **kwargs):
        self.created = kwargs
        return {"id": "rel1", **{k: v for k, v in kwargs.items() if k != "artifacts"}}


def build_service():
    db = FakeReleaseDatabase()
    service = ReleaseService(database=db, config={"max_file_size_mb": 200, "max_files_per_release": 12, "allowed_channels": ["latest", "next"]})
    return service, db


def test_create_release_generates_sha256sums_artifact():
    service, db = build_service()
    release = service.create_release(
        tag="v1.0.0",
        version="v1.0.0",
        channel="latest",
        description="test",
        created_by="tester",
        files=[
            UploadFile("install.ps1", b"ps"),
            UploadFile("git-ai-windows-x64.exe", b"exe"),
        ],
    )
    artifact_names = [a["filename"] for a in db.created["artifacts"]]
    assert release["id"] == "rel1"
    assert "SHA256SUMS" in artifact_names
    checksums = next(a for a in db.created["artifacts"] if a["filename"] == "SHA256SUMS")
    assert b"install.ps1" in checksums["content_blob"]
    assert db.created["sha256sums_checksum"] == checksums["sha256"]


def test_create_release_rejects_missing_windows_binary():
    service, _ = build_service()
    with pytest.raises(ReleaseValidationError, match="git-ai-windows-x64.exe"):
        service.create_release(
            tag="v1.0.0",
            version="v1.0.0",
            channel="latest",
            description=None,
            created_by=None,
            files=[
                UploadFile("install.ps1", b"ps"),
            ],
        )


def test_create_release_rejects_uploaded_sha256sums():
    service, _ = build_service()
    with pytest.raises(ReleaseValidationError, match="SHA256SUMS"):
        service.create_release(
            tag="v1.0.0",
            version="v1.0.0",
            channel="latest",
            description=None,
            created_by=None,
            files=[UploadFile("SHA256SUMS", b"bad")],
        )
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/test_services/test_release_service.py -v`

Expected: FAIL because `core.services.release_service` does not exist.

- [ ] **Step 3: Implement `ReleaseService`**

Create `core/services/release_service.py` with:

```python
import hashlib
import mimetypes
from pathlib import PurePath
from typing import Any

from core.config import load_config
from core.config.logging import Logger
from core.database.release_db import ReleaseDatabase


REQUIRED_FILES = {"install.ps1", "git-ai-windows-x64.exe"}
DEFAULT_CHANNELS = ["latest", "next", "enterprise-latest", "enterprise-next"]


class ReleaseValidationError(ValueError):
    pass


class ReleaseService:
    def __init__(self, database: ReleaseDatabase | None = None, config: dict[str, Any] | None = None):
        self.logger = Logger.get_logger("services.release")
        releases_config = config if config is not None else load_config().get("git_ai", {}).get("releases", {})
        self.database = database or ReleaseDatabase()
        self.max_file_size = int(releases_config.get("max_file_size_mb", 200)) * 1024 * 1024
        self.max_files = int(releases_config.get("max_files_per_release", 12))
        self.allowed_channels = releases_config.get("allowed_channels", DEFAULT_CHANNELS)

    def create_release(self, *, tag: str, version: str | None, channel: str, description: str | None, created_by: str | None, files: list[Any]) -> dict[str, Any]:
        tag = tag.strip()
        version = (version or tag).strip()
        channel = channel.strip()
        if not tag:
            raise ReleaseValidationError("tag is required")
        if channel not in self.allowed_channels:
            raise ReleaseValidationError(f"channel {channel} is not allowed")
        if len(files) > self.max_files:
            raise ReleaseValidationError(f"too many files, maximum {self.max_files}")

        artifacts = [self._read_upload_file(file) for file in files]
        names = {artifact["filename"] for artifact in artifacts}
        if "SHA256SUMS" in names:
            raise ReleaseValidationError("SHA256SUMS is generated by server")
        missing = sorted(REQUIRED_FILES - names)
        if missing:
            raise ReleaseValidationError(f"missing required files: {', '.join(missing)}")
        checksums_artifact = self._build_sha256sums_artifact(artifacts)
        artifacts.append(checksums_artifact)

        return self.database.create_release(
            tag=tag,
            version=version,
            channel=channel,
            sha256sums_checksum=checksums_artifact["sha256"],
            artifacts=artifacts,
            description=description,
            created_by=created_by,
        )

    def _read_upload_file(self, file: Any) -> dict[str, Any]:
        filename = self._safe_filename(file.filename)
        content = file.read()
        if len(content) > self.max_file_size:
            raise ReleaseValidationError(f"{filename} exceeds max file size")
        sha256 = hashlib.sha256(content).hexdigest()
        return {
            "filename": filename,
            "artifact_type": self._artifact_type(filename),
            "platform": self._platform(filename),
            "sha256": sha256,
            "size_bytes": len(content),
            "content_type": file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            "content_blob": content,
        }

    def _build_sha256sums_artifact(self, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        lines = [f'{artifact["sha256"]}  {artifact["filename"]}' for artifact in sorted(artifacts, key=lambda item: item["filename"])]
        content = ("\n".join(lines) + "\n").encode("utf-8")
        sha256 = hashlib.sha256(content).hexdigest()
        return {
            "filename": "SHA256SUMS",
            "artifact_type": "checksums",
            "platform": None,
            "sha256": sha256,
            "size_bytes": len(content),
            "content_type": "text/plain; charset=utf-8",
            "content_blob": content,
        }

    def _safe_filename(self, filename: str) -> str:
        name = PurePath(filename).name
        if not name or name != filename or "/" in filename or "\\" in filename:
            raise ReleaseValidationError(f"invalid filename: {filename}")
        return name

    def _artifact_type(self, filename: str) -> str:
        if filename.endswith(".sh") or filename.endswith(".ps1"):
            return "installer"
        return "binary"

    def _platform(self, filename: str) -> str | None:
        mapping = {
            "install.ps1": "windows-x64",
            "git-ai-windows-x64.exe": "windows-x64",
        }
        return mapping.get(filename)
```

- [ ] **Step 4: Run service tests**

Run: `pytest tests/unit/test_services/test_release_service.py -v`

Expected: PASS.

---

### Task 4: Release API Routes

**Files:**
- Modify: `api/routes/git_ai_worker.py`
- Test: `tests/integration/test_git_ai_releases_api.py`

- [ ] **Step 1: Add failing API integration tests**

Create `tests/integration/test_git_ai_releases_api.py` using the temp SQLite fixture style from `test_notes_rest_api.py`. Tests:

```python
def test_upload_activate_and_download_release_files(client):
    response = client.post(
        "/worker/releases/admin/upload",
        data={
            "tag": "v1.0.0",
            "version": "v1.0.0",
            "channel": "latest",
            "files": [
                (_bytes_file(b"ps", "install.ps1")),
                (_bytes_file(b"exe", "git-ai-windows-x64.exe")),
            ],
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    release_id = response.get_json()["release"]["id"]

    active = client.post(f"/worker/releases/admin/{release_id}/activate", headers={"X-API-Key": "test-key"})
    assert active.status_code == 200

    channels = client.get("/worker/releases/").get_json()["channels"]
    assert channels["latest"]["version"] == "v1.0.0"

    download = client.get("/worker/releases/latest/download/install.ps1")
    assert download.status_code == 200
    assert download.data == b"ps"


def test_admin_list_does_not_include_content_blob(client):
    response = client.get("/worker/releases/admin/list", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert "content_blob" not in response.get_data(as_text=True)
```

Define `_bytes_file` with `io.BytesIO` and create a Flask app that registers `releases_bp`.

- [ ] **Step 2: Run API tests to verify failure**

Run: `pytest tests/integration/test_git_ai_releases_api.py -v`

Expected: FAIL because routes do not exist.

- [ ] **Step 3: Implement routes in `api/routes/git_ai_worker.py`**

Add imports:

```python
from flask import send_file
from io import BytesIO
```

Add route helpers and endpoints under Releases API:

```python
def _release_service():
    from core.services.release_service import ReleaseService
    return ReleaseService()


def _admin_authorized():
    from core.config import load_config
    api_key = request.headers.get("X-API-Key")
    configured = load_config().get("git_ai", {}).get("api_key")
    return bool(api_key and configured and api_key == configured)


def _require_admin():
    if not _admin_authorized():
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return None
```

Replace `get_releases()` to read database active releases while preserving empty channel defaults. Add:

```python
@releases_bp.route('/<channel>/download/<path:filename>', methods=['GET'])
def download_release_artifact(channel, filename):
    service = _release_service()
    artifact = service.get_active_artifact(channel, filename)
    if artifact is None:
        return jsonify({'error': 'Release artifact not found'}), 404
    response = send_file(
        BytesIO(artifact['content_blob']),
        mimetype=artifact['content_type'],
        as_attachment=True,
        download_name=artifact['filename'],
    )
    response.headers['ETag'] = f'"sha256:{artifact["sha256"]}"'
    response.headers['X-Git-AI-SHA256'] = artifact['sha256']
    return response
```

Add admin routes for list, detail, upload, activate. Use `ReleaseService.create_release()`, `ReleaseDatabase.activate_release()`, `list_releases()`, and `list_artifacts()`.

- [ ] **Step 4: Add service query methods**

In `ReleaseService`, add:

```python
def list_channel_metadata(self) -> dict[str, dict[str, str]]:
    channels = {channel: {"version": "", "checksum": ""} for channel in DEFAULT_CHANNELS}
    for channel in channels:
        release = self.database.get_active_release(channel)
        if release:
            channels[channel] = {"version": release["version"], "checksum": release["sha256sums_checksum"]}
    return channels

def get_active_artifact(self, channel: str, filename: str) -> dict[str, Any] | None:
    release = self.database.get_active_release(channel)
    if not release:
        return None
    return self.database.get_artifact(release["id"], filename)
```

- [ ] **Step 5: Run API tests**

Run: `pytest tests/integration/test_git_ai_releases_api.py -v`

Expected: PASS.

---

### Task 5: Frontend API and Page

**Files:**
- Create: `frontend/src/api/gitAiRelease.ts`
- Create: `frontend/src/views/git-ai-release/index.vue`
- Create: `frontend/src/router/modules/git-ai.ts`

- [ ] **Step 1: Add API wrapper**

Create `frontend/src/api/gitAiRelease.ts`:

```ts
import { http } from "@/utils/http";

type R<T> = { success: boolean; data?: T; error?: string };

export type GitAiReleaseItem = {
  id: string;
  tag: string;
  version: string;
  channel: string;
  status: "active" | "inactive";
  sha256sums_checksum: string;
  created_at: number;
  published_at?: number | null;
};

export type GitAiReleaseArtifact = {
  id: string;
  filename: string;
  artifact_type: string;
  platform?: string | null;
  sha256: string;
  size_bytes: number;
  content_type: string;
};

export const getGitAiReleaseChannels = () =>
  http.request<{ channels: Record<string, { version: string; checksum: string }> }>("get", "/worker/releases/");

export const getGitAiReleaseList = (params?: { channel?: string; status?: string }) =>
  http.request<R<{ releases: GitAiReleaseItem[] }>>("get", "/worker/releases/admin/list", { params });

export const getGitAiReleaseDetail = (id: string) =>
  http.request<R<{ release: GitAiReleaseItem; artifacts: GitAiReleaseArtifact[] }>>("get", `/worker/releases/admin/${id}`);

export const uploadGitAiRelease = (data: FormData) =>
  http.request<R<{ release: GitAiReleaseItem }>>("post", "/worker/releases/admin/upload", { data });

export const activateGitAiRelease = (id: string) =>
  http.request<R<{ release: GitAiReleaseItem }>>("post", `/worker/releases/admin/${id}/activate`);
```

- [ ] **Step 2: Build frontend to catch API type errors**

Run: `cd frontend && pnpm build`

Expected: PASS or unrelated existing build failure. If it fails on the new API file, fix types before continuing.

- [ ] **Step 3: Add page route**

Create `frontend/src/router/modules/git-ai.ts`:

```ts
import { system } from "@/router/enums";

const Layout = () => import("@/layout/index.vue");

export default {
  path: "/git-ai",
  name: "GitAiManage",
  component: Layout,
  redirect: "/git-ai/releases",
  meta: {
    icon: "ri:git-branch-line",
    title: "Git-AI 管理",
    rank: system + 10
  },
  children: [
    {
      path: "/git-ai/releases",
      name: "GitAiReleaseManage",
      component: () => import("@/views/git-ai-release/index.vue"),
      meta: { title: "发布管理" }
    }
  ]
} satisfies RouteConfigsTable;
```

- [ ] **Step 4: Add release management page**

Create `frontend/src/views/git-ai-release/index.vue` using `repo-manage/ssh-key/index.vue` style: channel cards, `PureTableBar`, upload dialog, detail dialog. Required upload filenames: `install.ps1`, `git-ai-windows-x64.exe`.

Use `el-upload` with `:auto-upload="false"`, build `FormData`, append repeated `files`, call `uploadGitAiRelease(formData)`, then refresh list.

- [ ] **Step 5: Run frontend build**

Run: `cd frontend && pnpm build`

Expected: PASS.

---

### Task 6: Client Error Message Enhancement

**Files:**
- Modify: `git-ai/src/commands/upgrade.rs`

- [ ] **Step 1: Inspect existing upgrade tests**

Run: `rg -n "fetch_and_verify|download|SHA256SUMS|upgrade" git-ai/src/commands/upgrade.rs git-ai/tests tests`

Expected: identify current unit tests in `upgrade.rs`.

- [ ] **Step 2: Add targeted test for 404 messaging if practical**

In `git-ai/src/commands/upgrade.rs`, add or extend a unit test around the helper that handles HTTP status for artifact downloads. If there is no separable helper, extract status formatting first.

- [ ] **Step 3: Improve error strings**

Update download failures from generic HTTP messages to include channel and filename:

```rust
return Err(format!(
    "Release artifact '{}' is not available for channel '{}' (HTTP {})",
    script_name, channel, response.status_code
));
```

Apply the same pattern for `SHA256SUMS`.

- [ ] **Step 4: Run focused Rust tests**

Run: `cd git-ai && task test TEST_FILTER=upgrade`

Expected: PASS.

---

### Task 7: Verification

**Files:** all changed files.

- [ ] **Step 1: Run backend release tests**

Run: `pytest tests/unit/test_database/test_release_db.py tests/unit/test_services/test_release_service.py tests/integration/test_git_ai_releases_api.py -v`

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && pnpm build`

Expected: PASS.

- [ ] **Step 3: Run Rust upgrade tests**

Run: `cd git-ai && task test TEST_FILTER=upgrade`

Expected: PASS.

- [ ] **Step 4: Run diagnostics on changed source files**

Run LSP diagnostics for changed Python, Vue, TypeScript, and Rust files. Expected: no new diagnostics from changed files.

- [ ] **Step 5: Manual QA**

Start backend and frontend locally, open the Git-AI 发布管理 page, upload a test release with two small files named exactly:

- `install.ps1`
- `git-ai-windows-x64.exe`

Expected:

- Upload creates an inactive release.
- Detail view shows three artifacts including generated `SHA256SUMS`.
- Activating the release updates `/worker/releases`.
- Downloading `/worker/releases/latest/download/install.ps1` returns the uploaded bytes.

---

## Self-Review

**Spec coverage:** The plan covers DB BLOB storage, backend release upload/list/detail/activate/download APIs, frontend management page, generated `SHA256SUMS`, Windows-only required files, inactive-by-default activation, upload limits, and client download error messages.

**Placeholder scan:** No `TBD`, `TODO`, or “implement later” placeholders are intentionally left. Every implementation task names exact files and commands.

**Type consistency:** `GitAiRelease`, `GitAiReleaseArtifact`, `ReleaseDatabase`, and `ReleaseService` names are consistent across tasks. API paths match the design document: `/worker/releases`, `/worker/releases/{channel}/download/{filename}`, and `/worker/releases/admin/*`.
