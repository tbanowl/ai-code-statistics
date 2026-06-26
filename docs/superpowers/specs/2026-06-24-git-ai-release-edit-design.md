# Git-AI 发布管理修改功能设计

日期：2026-06-24

## 背景

现有 Git-AI 发布管理已经支持上传发布包、查看列表和详情、激活版本、删除未激活版本。发布记录由 `git_ai_releases` 保存元数据，由 `git_ai_release_artifacts` 保存安装脚本、二进制文件和服务端生成的 `SHA256SUMS`。客户端下载仍通过公开接口读取 active 发布：

- `GET /worker/releases/`
- `GET /worker/releases/{channel}/download/{filename}`

当前管理页只能新增发布包，不能修改已上传记录。发布人员如果填错 tag、version、channel、说明，或上传了错误文件，只能删除未激活记录后重新上传。用户明确要求发布管理添加修改功能，并要求同一个编辑入口同时支持元数据修改和文件替换，且 active 发布也允许直接修改。

## 目标

1. 在发布管理列表增加“修改”操作。
2. 支持修改 `tag`、`version`、`channel`、`description` 等发布元数据。
3. 支持重新上传发布文件，并由服务端重新生成 `SHA256SUMS`。
4. active 和 inactive 发布都允许直接修改。
5. 修改 active 发布后，`GET /worker/releases/` 和下载接口立即反映修改结果。
6. 后端更新必须在一个数据库事务内完成，避免元数据和 artifact 不一致。
7. 保持现有上传、激活、删除、详情和下载接口行为不破坏。

## 非目标

1. 不新增审批流、草稿流或发布回滚流。
2. 不引入发布历史快照表或 artifact 版本表。
3. 不改变客户端 upgrade 协议。
4. 不把发布文件迁移到文件系统、对象存储或外部 CDN。
5. 不放宽现有文件名、文件数量、大小、必需文件和 channel 校验规则。

## 方案比较

### 方案一：同一发布记录原子更新

编辑时直接更新当前 release 记录。若用户上传了新文件，服务端在同一事务中删除该 release 的旧 artifacts、写入新 artifacts、重新生成 `SHA256SUMS` 并更新 `sha256sums_checksum`。若用户未上传新文件，则只更新元数据。

优点是符合“修改”语义，前端交互简单，不增加额外记录。active 发布允许修改时，公开接口会自然读取更新后的同一条记录。缺点是没有内建历史快照，修改 active 文件会立刻影响客户端下载。

### 方案二：编辑时创建新发布记录

编辑入口保存时创建一条新 release，旧 release 保持不变；如果原记录是 active，再自动激活新记录。

优点是天然保留旧记录，回滚更容易。缺点是用户要求的是修改功能，但实际会产生新记录；同一 `(channel, tag)` 唯一约束需要额外处理；active 自动切换也更复杂。

### 方案三：只允许修改元数据

只提供元数据编辑，不允许替换文件。文件错误时仍需重新上传。

优点是风险最低。缺点是不满足用户已确认的“都要支持”。

## 推荐方案

采用方案一：同一发布记录原子更新。

这个方案最贴合当前需求和现有结构。由于用户明确要求 active 发布也允许直接修改，设计需要把风险显式交给管理端确认，并保证服务端事务一致性。后续如果需要审计或回滚，可以在此基础上新增历史快照，但第一版不引入额外复杂度。

## 后端设计

### 数据访问层

在 `core/database/release_db.py` 增加 `update_release()` 方法，负责同一事务内更新 release 元数据和可选 artifacts。

输入字段：

- `release_id`: 必填。
- `tag`: 必填，去除首尾空白后保存。
- `version`: 必填或由服务层默认成 tag。
- `channel`: 必填，必须是允许的 channel。
- `description`: 可为空。
- `sha256sums_checksum`: 仅当替换文件时传入。
- `artifacts`: 仅当替换文件时传入完整 artifact 列表，包含服务端生成的 `SHA256SUMS`。

行为：

1. 按 `release_id` 加载 release，不存在返回 `None`。
2. 更新 tag、version、channel、description、updated_at。
3. 如果传入 artifacts，先删除该 release 的旧 artifacts，再批量写入新 artifacts，并更新 `sha256sums_checksum`。
4. 如果 release 当前是 active 且 channel 被改动，目标 channel 不能已经存在其他 active release；否则拒绝更新，避免一次编辑隐式停用另一个通道的版本。
5. 捕获唯一约束冲突并向上抛出可识别错误，供 API 返回 400。

更新必须和删除/插入 artifacts 在一个事务里完成。这样不会出现 release 元数据已经更新但文件仍是旧版本，或文件已替换但 checksum 仍是旧值的状态。

### 服务层

在 `core/services/release_service.py` 增加 `update_release()` 方法。服务层复用现有创建发布的校验和 artifact 构造逻辑，避免上传和编辑规则分叉。

接口语义：

- 未上传新文件：只更新元数据，不改变现有 artifacts 和 `sha256sums_checksum`。
- 上传新文件：必须提供完整文件集合，不能只补丁式替换单个文件。
- 上传新文件时仍禁止上传 `SHA256SUMS`，由服务端生成。
- 上传新文件时仍要求 `install.ps1` 和 `git-ai-windows-x64.exe` 同时存在。
- 上传新文件时仍执行最大文件数量、最大文件大小、安全文件名和 channel 校验。

推荐新增内部辅助方法：

- `_normalize_release_fields(tag, version, channel)`：统一清理和校验 tag/version/channel。
- `_build_artifacts(files)`：读取上传文件、校验必需文件、生成 `SHA256SUMS`，返回 artifacts 和 checksum。

`create_release()` 和 `update_release()` 都调用这些辅助方法，减少重复实现。

### API

新增管理接口：

```text
PUT /worker/releases/admin/{release_id}
```

请求使用 `multipart/form-data`，方便同一接口同时提交文本字段和可选文件。

字段：

- `tag`: 必填。
- `version`: 可选，默认等于 tag。
- `channel`: 必填。
- `description`: 可选。
- `files`: 可选，多文件字段；存在时表示完整替换 artifact 集合。

响应：

```json
{
  "success": true,
  "release": {
    "id": "...",
    "tag": "v1.2.3",
    "version": "1.2.3",
    "channel": "latest",
    "status": "active",
    "sha256sums_checksum": "..."
  }
}
```

错误响应：

- 404：release 不存在。
- 400：校验失败、唯一约束冲突、active channel 冲突、文件集合不完整。
- 500：未预期异常。

修改 active 发布后，`GET /worker/releases/` 会立即返回新的 tag/version/checksum/platforms。下载接口会立即按新 artifacts 返回文件。

## 前端设计

### API 封装

在 `frontend/src/api/gitAiRelease.ts` 增加：

```ts
export const updateGitAiRelease = (id: string, data: FormData) =>
  http.request<R<{ release: GitAiReleaseItem }>>(
    "put",
    `/worker/releases/admin/${id}`,
    { data },
    { headers: { "Content-Type": "multipart/form-data" } }
  );
```

### 页面交互

在 `frontend/src/views/git-ai-release/index.vue` 的操作列增加“修改”按钮。编辑弹窗复用上传弹窗的大部分表单结构，但文案和行为区分为“上传”和“修改”。

编辑打开流程：

1. 点击“修改”。
2. 调用详情接口获取最新 release 和 artifacts。
3. 将 tag、version、channel、description 填入表单。
4. 显示当前 artifact 清单，提示“未重新选择文件时仅修改元数据”。
5. 若用户选择新文件，则按完整替换处理，并显示必需文件是否齐全。

保存流程：

1. 校验 tag/channel 必填。
2. 如果选择了新文件，校验必需文件齐全。
3. 构造 `FormData`，提交 `PUT /worker/releases/admin/{release_id}`。
4. 成功后关闭弹窗，刷新列表和 channel 卡片。

### Active 修改提示

由于 active 发布允许直接修改，编辑 active 记录时需要在弹窗顶部显示警告：

```text
当前发布已激活，保存后客户端升级接口会立即使用新的元数据和文件。
```

如果用户选择了新文件，保存按钮旁或确认弹窗中再次提示：

```text
将替换当前 active 发布文件，并重新生成 SHA256SUMS。确认保存？
```

这个提示不阻止操作，只让管理员明确知道影响范围。

## 数据流

### 仅修改元数据

1. 前端打开编辑弹窗并展示当前详情。
2. 用户修改 tag/version/channel/description，不选择文件。
3. 前端提交 `PUT /worker/releases/admin/{id}`。
4. 后端校验字段，事务内更新 release。
5. 前端刷新列表和 channel 卡片。
6. 如果 release 是 active，公开 channel 元数据立即变化；下载文件保持不变。

### 修改元数据并替换文件

1. 前端打开编辑弹窗并展示当前详情。
2. 用户修改字段并选择完整文件集合。
3. 前端提交 `PUT /worker/releases/admin/{id}`。
4. 后端校验字段和文件，生成新的 artifact 列表和 `SHA256SUMS`。
5. 后端事务内更新 release、删除旧 artifacts、写入新 artifacts、更新 `sha256sums_checksum`。
6. 前端刷新列表、详情和 channel 卡片。
7. 如果 release 是 active，公开 channel checksum 和下载文件立即变化。

## 错误处理

1. release 不存在：返回 404，前端提示“发布记录不存在或已删除”。
2. tag 为空：返回 400，前端提示“Tag 不能为空”。
3. channel 不允许：返回 400，前端提示后端错误信息。
4. `(channel, tag)` 已存在：返回 400，前端提示“同通道 Tag 已存在”。
5. active channel 冲突：返回 400，前端提示“该通道已有激活发布，请先切换或修改目标通道”。
6. 替换文件时缺少必需文件：返回 400，前端提示缺少的文件名。
7. 上传 `SHA256SUMS`：返回 400，前端提示该文件由服务端生成。
8. 单文件过大或文件数量超限：返回 400，前端提示限制信息。
9. 未预期异常：返回 500，前端提示“修改发布失败”。

## 测试设计

### 数据库单元测试

在 `tests/unit/test_database/test_release_db.py` 增加：

1. `test_update_release_changes_metadata_only`：更新 tag/version/channel/description，不改变 artifacts。
2. `test_update_release_replaces_artifacts`：传入新 artifacts 后旧 artifacts 被删除，新 checksum 被保存。
3. `test_update_release_returns_none_for_missing_release`：不存在返回 `None`。
4. `test_update_release_rejects_duplicate_channel_tag`：同 channel 下重复 tag 触发约束错误。

### 服务单元测试

在 `tests/unit/test_services/test_release_service.py` 增加：

1. `test_update_release_metadata_only_keeps_checksum`。
2. `test_update_release_with_files_regenerates_sha256sums`。
3. `test_update_release_with_files_requires_windows_files`。
4. `test_update_release_rejects_uploaded_sha256sums`。

### API 集成测试

在 `tests/integration/test_git_ai_releases_api.py` 增加：

1. 上传并激活 release 后，PUT 修改 version，`GET /worker/releases/` 返回新 version。
2. 上传并激活 release 后，PUT 替换文件，下载接口返回新文件内容，checksum 更新。
3. PUT 不存在 release 返回 404。
4. PUT 替换文件缺少必需文件返回 400。

### 前端验证

1. 列表中 inactive 和 active 记录都显示“修改”。
2. 编辑 inactive 元数据成功后列表刷新。
3. 编辑 active 元数据成功后顶部 channel 卡片刷新。
4. 编辑 active 并替换文件时出现影响提示。
5. 替换文件后详情中的 SHA-256 和大小变为新值。

## 实施顺序

1. 后端数据库层新增 `update_release()` 和单元测试。
2. 服务层抽出 artifact 构造逻辑并新增 `update_release()`。
3. API 层新增 `PUT /worker/releases/admin/{release_id}` 和集成测试。
4. 前端 API 增加 `updateGitAiRelease()`。
5. 发布管理页增加编辑状态、编辑弹窗、active 修改提示和保存逻辑。
6. 运行后端相关测试和前端类型检查。

## 验收标准

1. 管理员可以从发布管理列表打开修改弹窗。
2. 不选择文件时，保存只修改元数据。
3. 选择新文件时，保存完整替换 artifacts 并重新生成 `SHA256SUMS`。
4. active 发布可直接修改，修改后公开 channel 元数据和下载文件立即生效。
5. 替换文件仍必须包含 `install.ps1` 和 `git-ai-windows-x64.exe`。
6. 上传 `SHA256SUMS`、非法文件名、文件超限、重复 `(channel, tag)` 都被拒绝。
7. 现有上传、激活、删除、详情、下载流程保持可用。

## 风险与约束

active 发布允许直接替换文件会让客户端下载内容立即变化。如果管理员误操作，客户端可能下载到错误文件。第一版通过弹窗警告和服务端事务一致性降低风险，但不提供历史回滚。后续如需更强审计，应新增 release revision 或操作日志，而不是继续扩展当前修改接口。
