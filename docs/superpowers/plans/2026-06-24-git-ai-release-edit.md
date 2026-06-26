# Git-AI Release Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Git-AI 发布管理增加修改能力，支持 active/inactive 发布修改元数据和完整替换发布文件。

**Architecture:** 采用同一发布记录原子更新。服务层复用创建发布的字段校验和 artifact 构造逻辑；数据库层在单事务内更新 release、可选删除旧 artifacts、写入新 artifacts，并刷新 `sha256sums_checksum`。前端复用上传弹窗表单，新增编辑模式、active 风险提示和 `PUT /worker/releases/admin/{release_id}` 调用。

**Tech Stack:** Python 3.10+、Flask、SQLAlchemy、pytest、Vue 3、TypeScript、Element Plus、pure-table。

**Execution note:** 本仓库当前规则要求只有用户明确要求时才执行 `git commit`。本计划不包含自动提交步骤；执行者完成每个任务后只运行验证并汇报变更。

---

## File Structure

- Modify: `core/database/release_db.py`
  - 增加 `update_release()`。
  - 增加 active 改 channel 时目标 channel 冲突检测。
  - 保持 create/list/detail/delete 现有行为。
- Modify: `core/services/release_service.py`
  - 抽出字段归一化和 artifact 构造辅助方法。
  - 增加 `update_release()`，支持 metadata-only 和 full artifact replacement。
- Modify: `api/routes/git_ai_worker.py`
  - 增加 `PUT /worker/releases/admin/<release_id>`。
  - 复用 `ReleaseValidationError` 返回 400，release 不存在返回 404。
- Modify: `frontend/src/api/gitAiRelease.ts`
  - 增加 `updateGitAiRelease()`。
- Modify: `frontend/src/views/git-ai-release/index.vue`
  - 增加编辑模式、修改按钮、编辑弹窗预填、当前 artifact 展示、active 风险提示和保存逻辑。
- Modify: `tests/unit/test_database/test_release_db.py`
  - 增加数据库更新行为测试。
- Modify: `tests/unit/test_services/test_release_service.py`
  - 增加服务层更新和校验测试。
- Modify: `tests/integration/test_git_ai_releases_api.py`
  - 增加 PUT API 集成测试。

---

### Task 1: Database Update API

**Files:**
- Modify: `tests/unit/test_database/test_release_db.py`
- Modify: `core/database/release_db.py`

- [ ] **Step 1: Add failing tests for metadata-only update**

Append to `tests/unit/test_database/test_release_db.py`:

```python
def test_update_release_changes_metadata_only(sqlite_release_db):
    db = sqlite_release_db
    release = db.create_release(
        tag="v1.0.0",
        version="1.0.0",
        channel="latest",
        sha256sums_checksum="a" * 64,
        artifacts=[
            {
                "filename": "install.ps1",
                "artifact_type": "installer",
                "platform": "windows-x64",
                "sha256": "b" * 64,
                "size_bytes": 2,
                "content_type": "text/plain",
                "content_blob": b"ps",
            }
        ],
        description="old",
        created_by="tester",
    )

    updated = db.update_release(
        release["id"],
        tag="v1.0.1",
        version="1.0.1",
        channel="next",
        description="new",
    )

    assert updated["tag"] == "v1.0.1"
    assert updated["version"] == "1.0.1"
    assert updated["channel"] == "next"
    assert updated["description"] == "new"
    assert updated["sha256sums_checksum"] == "a" * 64
    artifacts = db.list_artifacts(release["id"], include_content=True)
    assert len(artifacts) == 1
    assert artifacts[0]["filename"] == "install.ps1"
    assert artifacts[0]["content_blob"] == b"ps"


def test_update_release_returns_none_for_missing_release(sqlite_release_db):
    assert sqlite_release_db.update_release(
        "missing",
        tag="v1.0.1",
        version="1.0.1",
        channel="latest",
        description=None,
    ) is None
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/unit/test_database/test_release_db.py::test_update_release_changes_metadata_only tests/unit/test_database/test_release_db.py::test_update_release_returns_none_for_missing_release -v
```

Expected: FAIL with `AttributeError: 'ReleaseDatabase' object has no attribute 'update_release'`.

- [ ] **Step 3: Implement metadata-only update**

Add imports and method in `core/database/release_db.py`:

```python
from sqlalchemy import and_
```

Inside `ReleaseDatabase`:

```python
    def update_release(
        self,
        release_id: str,
        *,
        tag: str,
        version: str,
        channel: str,
        description: str | None,
        sha256sums_checksum: str | None = None,
        artifacts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            release = (
                session.query(GitAiRelease)
                .filter(GitAiRelease.id == release_id)
                .first()
            )
            if release is None:
                return None

            if release.status == "active" and channel != release.channel:
                active_target = (
                    session.query(GitAiRelease)
                    .filter(
                        GitAiRelease.channel == channel,
                        GitAiRelease.status == "active",
                        GitAiRelease.id != release_id,
                    )
                    .first()
                )
                if active_target is not None:
                    raise ValueError("target channel already has an active release")

            release.tag = tag
            release.version = version
            release.channel = channel
            release.description = description
            release.updated_at = now_ts()

            if artifacts is not None:
                session.query(GitAiReleaseArtifact).filter(
                    GitAiReleaseArtifact.release_id == release_id
                ).delete(synchronize_session=False)
                for artifact in artifacts:
                    session.add(GitAiReleaseArtifact(release_id=release.id, **artifact))
                if sha256sums_checksum is not None:
                    release.sha256sums_checksum = sha256sums_checksum

            try:
                session.flush()
            except IntegrityError as exc:
                raise ValueError("release update conflicts with existing release") from exc
            return self._release_dict(release)
```

Remove `from sqlalchemy import and_` if unused after implementation.

- [ ] **Step 4: Run database tests**

Run:

```bash
pytest tests/unit/test_database/test_release_db.py -v
```

Expected: PASS.

- [ ] **Step 5: Add artifact replacement tests**

Append to `tests/unit/test_database/test_release_db.py`:

```python
def test_update_release_replaces_artifacts(sqlite_release_db):
    db = sqlite_release_db
    release = db.create_release(
        tag="v1.0.0",
        version="1.0.0",
        channel="latest",
        sha256sums_checksum="a" * 64,
        artifacts=[
            {
                "filename": "install.ps1",
                "artifact_type": "installer",
                "platform": "windows-x64",
                "sha256": "b" * 64,
                "size_bytes": 2,
                "content_type": "text/plain",
                "content_blob": b"old",
            }
        ],
        description=None,
        created_by="tester",
    )

    updated = db.update_release(
        release["id"],
        tag="v1.0.0",
        version="1.0.0",
        channel="latest",
        description=None,
        sha256sums_checksum="c" * 64,
        artifacts=[
            {
                "filename": "install.ps1",
                "artifact_type": "installer",
                "platform": "windows-x64",
                "sha256": "d" * 64,
                "size_bytes": 3,
                "content_type": "text/plain",
                "content_blob": b"new",
            },
            {
                "filename": "SHA256SUMS",
                "artifact_type": "checksums",
                "platform": None,
                "sha256": "c" * 64,
                "size_bytes": 64,
                "content_type": "text/plain; charset=utf-8",
                "content_blob": b"checksums",
            },
        ],
    )

    assert updated["sha256sums_checksum"] == "c" * 64
    artifacts = db.list_artifacts(release["id"], include_content=True)
    assert [artifact["filename"] for artifact in artifacts] == ["SHA256SUMS", "install.ps1"]
    assert next(a for a in artifacts if a["filename"] == "install.ps1")["content_blob"] == b"new"
```

- [ ] **Step 6: Run replacement test**

Run:

```bash
pytest tests/unit/test_database/test_release_db.py::test_update_release_replaces_artifacts -v
```

Expected: PASS.

---

### Task 2: Release Service Update Logic

**Files:**
- Modify: `tests/unit/test_services/test_release_service.py`
- Modify: `core/services/release_service.py`

- [ ] **Step 1: Extend fake database**

Modify `FakeReleaseDatabase` in `tests/unit/test_services/test_release_service.py`:

```python
class FakeReleaseDatabase:
    def __init__(self):
        self.created = None
        self.updated = None
        self.active_release = None
        self.artifacts = []

    def create_release(self, **kwargs):
        self.created = kwargs
        return {"id": "rel1", **{k: v for k, v in kwargs.items() if k != "artifacts"}}

    def update_release(self, release_id, **kwargs):
        self.updated = {"release_id": release_id, **kwargs}
        if release_id == "missing":
            return None
        return {"id": release_id, **{k: v for k, v in kwargs.items() if k != "artifacts"}}

    def get_active_release(self, channel):
        return self.active_release if channel == "latest" else None

    def list_artifacts(self, release_id):
        if self.active_release and release_id == self.active_release["id"]:
            return self.artifacts
        return []
```

- [ ] **Step 2: Add service update tests**

Append to `tests/unit/test_services/test_release_service.py`:

```python
def test_update_release_metadata_only_keeps_checksum():
    service, db = build_service()

    release = service.update_release(
        "rel1",
        tag=" v1.0.1 ",
        version="",
        channel="latest",
        description="new",
        files=[],
    )

    assert release["id"] == "rel1"
    assert db.updated["tag"] == "v1.0.1"
    assert db.updated["version"] == "v1.0.1"
    assert db.updated["channel"] == "latest"
    assert db.updated["description"] == "new"
    assert db.updated["artifacts"] is None
    assert db.updated["sha256sums_checksum"] is None


def test_update_release_with_files_regenerates_sha256sums():
    service, db = build_service()

    release = service.update_release(
        "rel1",
        tag="v1.0.1",
        version="1.0.1",
        channel="latest",
        description=None,
        files=[
            UploadFile("install.ps1", b"ps-new"),
            UploadFile("git-ai-windows-x64.exe", b"exe-new"),
        ],
    )

    assert release["id"] == "rel1"
    artifact_names = [artifact["filename"] for artifact in db.updated["artifacts"]]
    assert artifact_names == ["install.ps1", "git-ai-windows-x64.exe", "SHA256SUMS"]
    checksum_artifact = next(a for a in db.updated["artifacts"] if a["filename"] == "SHA256SUMS")
    assert db.updated["sha256sums_checksum"] == checksum_artifact["sha256"]
    assert b"install.ps1" in checksum_artifact["content_blob"]


def test_update_release_with_files_requires_windows_files():
    service, _ = build_service()

    with pytest.raises(ReleaseValidationError, match="git-ai-windows-x64.exe"):
        service.update_release(
            "rel1",
            tag="v1.0.1",
            version="1.0.1",
            channel="latest",
            description=None,
            files=[UploadFile("install.ps1", b"ps")],
        )


def test_update_release_rejects_uploaded_sha256sums():
    service, _ = build_service()

    with pytest.raises(ReleaseValidationError, match="SHA256SUMS"):
        service.update_release(
            "rel1",
            tag="v1.0.1",
            version="1.0.1",
            channel="latest",
            description=None,
            files=[UploadFile("SHA256SUMS", b"bad")],
        )
```

- [ ] **Step 3: Run service tests to verify failure**

Run:

```bash
pytest tests/unit/test_services/test_release_service.py::test_update_release_metadata_only_keeps_checksum -v
```

Expected: FAIL with `AttributeError: 'ReleaseService' object has no attribute 'update_release'`.

- [ ] **Step 4: Refactor release service helpers**

Modify `core/services/release_service.py` so `create_release()` uses helpers:

```python
    def create_release(
        self,
        *,
        tag: str,
        version: str | None,
        channel: str,
        description: str | None,
        created_by: str | None,
        files: list[Any],
    ) -> dict[str, Any]:
        tag, version, channel = self._normalize_release_fields(tag, version, channel)
        artifacts, sha256sums_checksum = self._build_artifacts(files)
        return self.database.create_release(
            tag=tag,
            version=version,
            channel=channel,
            sha256sums_checksum=sha256sums_checksum,
            artifacts=artifacts,
            description=description,
            created_by=created_by,
        )

    def update_release(
        self,
        release_id: str,
        *,
        tag: str,
        version: str | None,
        channel: str,
        description: str | None,
        files: list[Any],
    ) -> dict[str, Any] | None:
        tag, version, channel = self._normalize_release_fields(tag, version, channel)
        artifacts = None
        sha256sums_checksum = None
        if files:
            artifacts, sha256sums_checksum = self._build_artifacts(files)
        return self.database.update_release(
            release_id,
            tag=tag,
            version=version,
            channel=channel,
            description=description,
            sha256sums_checksum=sha256sums_checksum,
            artifacts=artifacts,
        )

    def _normalize_release_fields(
        self, tag: str, version: str | None, channel: str
    ) -> tuple[str, str, str]:
        tag = tag.strip()
        version = (version or tag).strip()
        channel = channel.strip()
        if not tag:
            raise ReleaseValidationError("tag is required")
        if channel not in self.allowed_channels:
            raise ReleaseValidationError(f"channel {channel} is not allowed")
        return tag, version, channel

    def _build_artifacts(self, files: list[Any]) -> tuple[list[dict[str, Any]], str]:
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
        return artifacts, checksums_artifact["sha256"]
```

- [ ] **Step 5: Run service tests**

Run:

```bash
pytest tests/unit/test_services/test_release_service.py -v
```

Expected: PASS.

---

### Task 3: Release Update API

**Files:**
- Modify: `tests/integration/test_git_ai_releases_api.py`
- Modify: `api/routes/git_ai_worker.py`

- [ ] **Step 1: Add API integration tests**

Append to `tests/integration/test_git_ai_releases_api.py`:

```python
def _upload_release(client, tag="v1.0.0", version="1.0.0"):
    response = client.post(
        "/worker/releases/admin/upload",
        data={
            "tag": tag,
            "version": version,
            "channel": "latest",
            "files": [
                _bytes_file(b"ps", "install.ps1"),
                _bytes_file(b"exe", "git-ai-windows-x64.exe"),
            ],
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    return response.get_json()["release"]["id"]


def test_update_active_release_metadata_updates_channel_response(client):
    release_id = _upload_release(client)
    active = client.post(
        f"/worker/releases/admin/{release_id}/activate",
        headers={"X-API-Key": "test-key"},
    )
    assert active.status_code == 200

    response = client.put(
        f"/worker/releases/admin/{release_id}",
        data={"tag": "v1.0.1", "version": "1.0.1", "channel": "latest", "description": "edited"},
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    channels = client.get("/worker/releases/").get_json()["channels"]
    assert channels["latest"]["tag"] == "v1.0.1"
    assert channels["latest"]["version"] == "1.0.1"


def test_update_active_release_files_updates_download(client):
    release_id = _upload_release(client)
    active = client.post(
        f"/worker/releases/admin/{release_id}/activate",
        headers={"X-API-Key": "test-key"},
    )
    assert active.status_code == 200

    response = client.put(
        f"/worker/releases/admin/{release_id}",
        data={
            "tag": "v1.0.0",
            "version": "1.0.0",
            "channel": "latest",
            "files": [
                _bytes_file(b"ps-new", "install.ps1"),
                _bytes_file(b"exe-new", "git-ai-windows-x64.exe"),
            ],
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    download = client.get("/worker/releases/latest/download/install.ps1")
    assert download.status_code == 200
    assert download.data == b"ps-new"
    assert client.get("/worker/releases/").get_json()["channels"]["latest"]["checksum"] != ""


def test_update_missing_release_returns_404(client):
    response = client.put(
        "/worker/releases/admin/missing",
        data={"tag": "v1.0.1", "version": "1.0.1", "channel": "latest"},
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 404


def test_update_release_files_requires_required_files(client):
    release_id = _upload_release(client)
    response = client.put(
        f"/worker/releases/admin/{release_id}",
        data={
            "tag": "v1.0.0",
            "version": "1.0.0",
            "channel": "latest",
            "files": [_bytes_file(b"ps", "install.ps1")],
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 400
    assert "git-ai-windows-x64.exe" in response.get_json()["error"]
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```bash
pytest tests/integration/test_git_ai_releases_api.py::test_update_active_release_metadata_updates_channel_response -v
```

Expected: FAIL with status 405 or 404 because PUT route does not exist.

- [ ] **Step 3: Implement PUT route**

Add in `api/routes/git_ai_worker.py` before the DELETE route:

```python
@releases_bp.route('/admin/<release_id>', methods=['PUT'])
def update_admin_release(release_id):
    from core.services.release_service import ReleaseValidationError

    try:
        release = _release_service().update_release(
            release_id,
            tag=request.form.get('tag', ''),
            version=request.form.get('version'),
            channel=request.form.get('channel', ''),
            description=request.form.get('description'),
            files=request.files.getlist('files'),
        )
        if release is None:
            return jsonify({'success': False, 'error': 'Release not found'}), 404
        return jsonify({'success': True, 'release': release, 'data': {'release': release}}), 200
    except ReleaseValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Release admin update error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 4: Run API integration tests**

Run:

```bash
pytest tests/integration/test_git_ai_releases_api.py -v
```

Expected: PASS.

---

### Task 4: Frontend API Wrapper

**Files:**
- Modify: `frontend/src/api/gitAiRelease.ts`

- [ ] **Step 1: Add update API**

Add after `uploadGitAiRelease` in `frontend/src/api/gitAiRelease.ts`:

```ts
export const updateGitAiRelease = (id: string, data: FormData) =>
  http.request<R<{ release: GitAiReleaseItem }>>(
    "put",
    `/worker/releases/admin/${id}`,
    { data },
    { headers: { "Content-Type": "multipart/form-data" } }
  );
```

- [ ] **Step 2: Run TypeScript diagnostics**

Run:

```bash
cd frontend && pnpm exec vue-tsc --noEmit
```

Expected: PASS, or only pre-existing unrelated errors. Record any unrelated errors in the final implementation summary.

---

### Task 5: Frontend Edit Dialog

**Files:**
- Modify: `frontend/src/views/git-ai-release/index.vue`

- [ ] **Step 1: Update imports and icons**

Modify imports in `frontend/src/views/git-ai-release/index.vue`:

```ts
import EditPen from "~icons/ep/edit-pen";
```

Add `updateGitAiRelease` to the API import list.

- [ ] **Step 2: Add edit state**

Add near upload/detail refs:

```ts
const dialogMode = ref<"create" | "edit">("create");
const editingRelease = ref<GitAiReleaseItem | null>(null);
const currentArtifacts = ref<GitAiReleaseArtifact[]>([]);

const dialogTitle = computed(() =>
  dialogMode.value === "edit" ? "修改 Git-AI 发布包" : "上传 Git-AI Windows 发布包"
);

const hasSelectedReplacementFiles = computed(() => uploadFiles.value.length > 0);
```

- [ ] **Step 3: Split open create and open edit behavior**

Replace `openUpload` with:

```ts
const resetReleaseForm = () => {
  uploadForm.value = { tag: "", version: "", channel: "latest", description: "" };
  uploadFiles.value = [];
  currentArtifacts.value = [];
  editingRelease.value = null;
};

const openUpload = () => {
  dialogMode.value = "create";
  resetReleaseForm();
  uploadVisible.value = true;
};

const openEdit = async (row: GitAiReleaseItem) => {
  dialogMode.value = "edit";
  resetReleaseForm();
  uploadVisible.value = true;
  uploadLoading.value = true;
  try {
    const result = await getGitAiReleaseDetail(row.id);
    const release = result.release || result.data?.release || row;
    editingRelease.value = release;
    uploadForm.value = {
      tag: release.tag,
      version: release.version,
      channel: release.channel,
      description: release.description || ""
    };
    currentArtifacts.value = result.artifacts || result.data?.artifacts || [];
  } catch {
    message("获取发布详情失败", { type: "error" });
    uploadVisible.value = false;
  } finally {
    uploadLoading.value = false;
  }
};
```

- [ ] **Step 4: Update save handler**

Replace `handleUpload` with:

```ts
const handleSaveRelease = async () => {
  if (!uploadForm.value.tag.trim()) {
    message("Tag 不能为空", { type: "warning" });
    return;
  }
  const replacingFiles = dialogMode.value === "create" || hasSelectedReplacementFiles.value;
  if (replacingFiles && missingFiles.value.length > 0) {
    message(`缺少必需文件：${missingFiles.value.join("、")}`, { type: "warning" });
    return;
  }
  const formData = new FormData();
  formData.append("tag", uploadForm.value.tag.trim());
  formData.append("version", uploadForm.value.version.trim() || uploadForm.value.tag.trim());
  formData.append("channel", uploadForm.value.channel);
  formData.append("description", uploadForm.value.description.trim());
  uploadFiles.value.forEach(file => formData.append("files", file));

  uploadLoading.value = true;
  try {
    if (dialogMode.value === "edit" && editingRelease.value) {
      await updateGitAiRelease(editingRelease.value.id, formData);
      message("修改成功", { type: "success" });
    } else {
      await uploadGitAiRelease(formData);
      message("上传成功，发布包已进入待激活状态", { type: "success" });
    }
    uploadVisible.value = false;
    await onSearch();
  } catch {
    message(dialogMode.value === "edit" ? "修改发布失败" : "上传发布包失败", { type: "error" });
  } finally {
    uploadLoading.value = false;
  }
};
```

- [ ] **Step 5: Add operation button**

In operation slot, after “详情” button add:

```vue
<el-button link type="primary" :size="size" :icon="useRenderIcon(EditPen)" @click="openEdit(row)">
  修改
</el-button>
```

- [ ] **Step 6: Update dialog template**

Change dialog title and alert region:

```vue
<el-dialog v-model="uploadVisible" :title="dialogTitle" width="min(640px, 92vw)" destroy-on-close>
  <el-alert
    v-if="dialogMode === 'edit' && editingRelease?.status === 'active'"
    class="mb-4"
    type="warning"
    :closable="false"
    title="当前发布已激活，保存后客户端升级接口会立即使用新的元数据和文件。"
  />
  <el-alert
    class="mb-4"
    type="info"
    :closable="false"
    :title="dialogMode === 'edit' ? '未重新选择文件时仅修改元数据；选择文件后会完整替换发布文件并重新生成 SHA256SUMS。' : '第一版只支持 Windows，必须上传 install.ps1 和 git-ai-windows-x64.exe。SHA256SUMS 由服务端生成。'"
  />
```

After required-files block, show current artifacts in edit mode:

```vue
<div v-if="dialogMode === 'edit' && currentArtifacts.length" class="current-artifacts">
  <div class="current-artifacts-title">当前文件</div>
  <el-tag v-for="artifact in currentArtifacts" :key="artifact.id" effect="plain">
    {{ artifact.filename }} · {{ formatBytes(artifact.size_bytes) }}
  </el-tag>
</div>
```

Change footer save button:

```vue
<el-button type="primary" :loading="uploadLoading" @click="handleSaveRelease">
  {{ dialogMode === "edit" ? "保存" : "上传" }}
</el-button>
```

- [ ] **Step 7: Add styles**

Add to scoped style:

```scss
.current-artifacts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.current-artifacts-title {
  width: 100%;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
```

- [ ] **Step 8: Run frontend type check**

Run:

```bash
cd frontend && pnpm exec vue-tsc --noEmit
```

Expected: PASS, or only pre-existing unrelated errors.

---

### Task 6: Full Verification

**Files:**
- Verify only, no edits unless previous tasks caused failures.

- [ ] **Step 1: Run release backend tests**

Run:

```bash
pytest tests/unit/test_database/test_release_db.py tests/unit/test_services/test_release_service.py tests/integration/test_git_ai_releases_api.py -v
```

Expected: PASS.

- [ ] **Step 2: Run targeted frontend check**

Run:

```bash
cd frontend && pnpm exec vue-tsc --noEmit
```

Expected: PASS, or document unrelated pre-existing errors.

- [ ] **Step 3: Run LSP diagnostics on changed files**

Use diagnostics for:

- `core/database/release_db.py`
- `core/services/release_service.py`
- `api/routes/git_ai_worker.py`
- `frontend/src/api/gitAiRelease.ts`
- `frontend/src/views/git-ai-release/index.vue`

Expected: no new errors caused by this work.

- [ ] **Step 4: Manual QA path**

If local backend and frontend can run, verify this flow:

1. Open Git-AI 发布管理 page.
2. Upload a test release with `install.ps1` and `git-ai-windows-x64.exe`.
3. Activate it.
4. Click 修改 on the active row.
5. Change version only and save; confirm channel card version changes.
6. Click 修改 again, select replacement files, save; confirm detail SHA values and download content change.

Expected: active release edits are visible immediately in list, channel cards, detail dialog, and download endpoint.

---

## Self-Review

**Spec coverage:**

- 元数据修改：Task 1、Task 2、Task 3、Task 5 覆盖。
- 文件完整替换和重新生成 `SHA256SUMS`：Task 1、Task 2、Task 3、Task 5 覆盖。
- active 发布直接修改并立即影响公开接口：Task 3 和 Task 5 覆盖。
- 服务端事务一致性：Task 1 覆盖。
- 前端 active 风险提示：Task 5 覆盖。
- 验证：Task 6 覆盖。

**Completion-marker scan:** 本计划不包含未完成步骤或未定义实现细节。

**Type consistency:** 使用 `update_release()`、`updateGitAiRelease()`、`GitAiReleaseItem`、`GitAiReleaseArtifact` 命名，与现有代码和新增设计保持一致。
