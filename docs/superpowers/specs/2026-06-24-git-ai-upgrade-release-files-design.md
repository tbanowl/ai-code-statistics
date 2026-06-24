# git-ai upgrade 内部发布文件管理设计

日期：2026-06-24

## 背景

`git-ai` 客户端已有 `git-ai upgrade` 命令。当前升级流程会访问 `api_base_url` 下的发布接口：

- `GET /worker/releases`：读取各通道当前版本和 `SHA256SUMS` 文件自身的 SHA-256。
- `GET /worker/releases/{channel}/download/SHA256SUMS`：下载校验清单。
- `GET /worker/releases/{channel}/download/install.ps1`：Windows 安装脚本。

客户端会先校验 `SHA256SUMS`，再用 `SHA256SUMS` 校验安装脚本，然后运行安装脚本完成升级。当前 `git-ai-code-metrics` 后端已经注册 `releases_bp`，但 `api/routes/git_ai_worker.py` 的 releases 只从 `config.yaml` 返回静态 `version/checksum`，没有真实的发布文件上传、数据库存储、管理页面和下载能力。

本系统是内部系统，发布构建只能在本地机器完成。因此不能采用 GitHub Actions 同步发布物，也不能只做后端接口。发布人员需要在管理页面上传本地构建出来的 `git-ai` 可执行文件和安装脚本，后端把脚本与二进制文件保存到数据库中，再由 `git-ai upgrade` 下载使用。

## 目标

1. 增加 Git-AI 发布管理页面，支持在前端上传本地构建产物。
2. 后端提供 release 上传、列表、详情、删除或停用、通道元数据和文件下载接口。
3. 安装脚本和可执行文件内容保存到数据库，不保存到文件系统或对象存储。
4. `GET /worker/releases` 保持现有 `git-ai upgrade` 兼容响应格式。
5. `git-ai upgrade` 可以从内部平台下载并校验后端生成的 `SHA256SUMS`、安装脚本和后续脚本需要的二进制文件。
6. 管理员能看到每个版本的文件清单、大小、SHA-256、上传时间和当前生效通道。

## 非目标

1. 不使用 GitHub Actions 上传或同步发布物。
2. 不使用 GitHub Release、外部 CDN、对象存储或文件系统作为发布物主存储。
3. 不在第一版中实现自动本地构建；构建仍由发布人员在本地完成。
4. 不设计复杂审批流；第一版由有权限的管理用户上传，并在确认后手动激活到指定通道。
5. 不改变 metrics、CAS、OAuth、authorship notes 等已有 worker API 的行为。

## 设计方案

采用“本地构建 + 管理页面上传 + 数据库存储 + 客户端兼容下载”的方案。

发布人员先在本地机器构建 `git-ai` 可执行文件，并准备对应安装脚本。然后登录内部管理系统，在 Git-AI 发布管理页选择通道和版本号，上传这些文件。后端校验文件名、大小和必需文件，计算每个文件的 SHA-256，把文件内容作为数据库二进制字段保存，并自动生成 `SHA256SUMS` artifact。上传成功后版本先进入 `inactive` 状态，管理员在页面确认文件清单、大小和校验值后，再手动激活到目标通道。

`git-ai upgrade` 仍调用现有 `/worker/releases` 和 `/worker/releases/{channel}/download/{filename}`。后端从数据库读取当前通道对应的 release 和 artifact，下载接口把数据库中的 BLOB 作为响应体返回。安装脚本如果需要下载平台二进制，也通过同一类下载接口获取，例如：

- `/worker/releases/latest/download/git-ai-windows-x64.exe`

这个方案符合内部系统约束，发布流程可由人手动控制，所有发布物集中在数据库中备份和审计。主要代价是数据库会存储较大的二进制内容，需要配置单文件大小限制、请求体大小限制和合理的下载流式响应。

## 后端设计

### 模块边界

新增 `ReleaseService`，负责发布业务逻辑：校验上传参数、读取文件内容、计算 SHA-256、生成 `SHA256SUMS`、调用数据库、构造下载响应所需元数据。

新增 `ReleaseDatabase`，负责 SQLAlchemy 数据访问：创建 release、保存 artifact BLOB、查询当前通道、列出版本、读取 artifact 内容、停用或删除 release。

扩展 `api/routes/git_ai_worker.py` 中的 `releases_bp`，保持 worker 下载接口位置不变。route 层只处理 HTTP 参数、文件上传、鉴权和响应映射。

前端管理接口建议仍放在 `/worker/releases` 下，便于和客户端下载接口复用同一业务模块。下载接口公开给客户端使用；上传、删除、发布、停用等管理接口需要登录或 API key 权限。

### 配置

新增配置节：

```yaml
git_ai:
  releases:
    max_file_size_mb: 200
    max_files_per_release: 12
    allowed_channels:
      - latest
      - next
      - enterprise-latest
      - enterprise-next
```

不再配置 `storage_dir`，因为发布物内容保存在数据库中。

第一版采用默认限制：单文件最大 200MB，单个 release 最多 12 个 artifact。Windows 必需上传 2 个文件，后端再生成 1 个 `SHA256SUMS`，因此 12 个 artifact 足够覆盖第一版和后续 Linux/macOS 扩展。超过限制的上传请求直接返回 400，不写入数据库。

### 数据模型

新增 `git_ai_releases` 表：

- `id`: XID 主键。
- `tag`: 发布 tag，例如 `v1.2.3`。
- `version`: 客户端展示和比较用版本，默认等于 tag。
- `channel`: 发布通道，例如 `latest` 或 `next`。
- `status`: `active`、`inactive`。同一 channel 只能有一个 `active` release。
- `sha256sums_checksum`: `SHA256SUMS` 文件内容的 SHA-256，返回给 `GET /worker/releases`。
- `description`: 管理员填写的发布说明，可为空。
- `created_by`: 上传人，可为空。
- `published_at`: 发布时间毫秒时间戳。
- `created_at` / `updated_at`: 审计字段。

约束：同一 `(channel, tag)` 不重复。同一 `channel` 只能有一个 active release，这个约束可以在服务层事务中保证。

新增 `git_ai_release_artifacts` 表：

- `id`: XID 主键。
- `release_id`: 外键。
- `filename`: 文件名，例如 `SHA256SUMS`、`install.ps1`、`git-ai-windows-x64.exe`。
- `artifact_type`: `checksums`、`installer`、`binary`。
- `platform`: `linux-x64`、`macos-arm64`、`windows-x64` 等，可为空。
- `sha256`: 文件内容 SHA-256。
- `size_bytes`: 文件大小。
- `content_type`: 下载响应类型。
- `content_blob`: 二进制文件内容。
- `created_at`: 创建时间。

约束：同一 release 下 `filename` 唯一。

### 必需文件

第一版只支持 Windows。上传时至少要求：

- `install.ps1`
- `git-ai-windows-x64.exe`

后端根据这些上传文件自动生成 `SHA256SUMS`，并把生成结果作为 `checksums` 类型 artifact 存入数据库。Linux/WSL 和 macOS x64/arm64 作为第二阶段扩展。表结构中的 `platform` 字段保持通用，不阻止后续增加 `install.sh`、`git-ai-linux-x64`、`git-ai-macos-x64`、`git-ai-macos-arm64` 等 artifact，但第一版不把它们列为必需文件。

### API

#### GET /worker/releases

公开接口，供 `git-ai upgrade` 调用。返回兼容现有客户端结构：

```json
{
  "channels": {
    "latest": {"version": "v1.2.3", "checksum": "<sha256-of-SHA256SUMS>"},
    "next": {"version": "", "checksum": ""},
    "enterprise-latest": {"version": "", "checksum": ""},
    "enterprise-next": {"version": "", "checksum": ""}
  }
}
```

没有 active release 的通道返回空字符串。

#### GET /worker/releases/{channel}/download/{filename}

公开接口，根据 channel 找到 active release，再按 filename 读取 artifact。响应体来自数据库 `content_blob`。

响应头包含：

- `Content-Type`
- `Content-Length`
- `Content-Disposition`
- `ETag: "sha256:<hash>"`
- `X-Git-AI-SHA256: <hash>`

#### GET /worker/releases/admin/list

管理接口，供前端列表使用。支持按 channel、status、keyword 查询，返回 release 摘要和 artifact 数量。

#### GET /worker/releases/admin/{release_id}

管理接口，返回 release 详情和 artifact 清单，但不返回 `content_blob`。

#### POST /worker/releases/admin/upload

管理接口，使用 `multipart/form-data` 上传本地构建产物。

字段：

- `tag`: 必填。
- `version`: 可选，默认等于 tag。
- `channel`: 必填。
- `description`: 可选。
- `files`: 多文件字段。

服务端行为：

1. 校验 channel 是否允许。
2. 校验每个文件 basename 安全，不允许路径穿越。
3. 校验数量和大小限制。
4. 读取文件内容到内存并计算 SHA-256。
5. 确认存在必需文件。
6. 按 `<sha256>  <filename>` 格式生成 `SHA256SUMS` 内容。
7. 计算生成的 `SHA256SUMS` 自身 SHA-256，作为 release 的 `sha256sums_checksum`。
8. 在事务中创建 release、写入上传 artifact BLOB 和生成的 `SHA256SUMS` artifact BLOB，新 release 默认保存为 `inactive`。

#### POST /worker/releases/admin/{release_id}/activate

管理接口，把某个已上传 release 设置为该 channel 的 active release。

激活时在同一数据库事务中把同 channel 旧 active release 置为 `inactive`，再把目标 release 置为 `active`。只有 `active` release 会出现在 `GET /worker/releases` 中，也只有 `active` release 会被 `/worker/releases/{channel}/download/{filename}` 下载接口选中。

#### DELETE /worker/releases/admin/{release_id}

管理接口，删除未 active 的 release。active release 不能直接删除，必须先切换通道。

## 前端设计

新增页面：`frontend/src/views/git-ai-release/index.vue`。

新增 API 封装：`frontend/src/api/gitAiRelease.ts`。

页面风格遵循现有 pure-admin 管理页模式，例如 `repo-manage/ssh-key/index.vue`：使用 `PureTableBar`、`pure-table`、`el-dialog`、`el-form`、`el-upload`、`el-tag`、`el-button` 和统一 `message()` 提示。

管理入口新增为“Git-AI 管理”一级菜单，下面放“发布管理”页面。这样发布功能不会混入系统用户、角色、菜单等平台治理页面，也方便后续继续扩展 Git-AI 客户端配置、版本历史和升级审计页面。

### 页面功能

1. 顶部卡片展示各通道当前版本：latest、next、enterprise-latest、enterprise-next。
2. release 列表展示 tag、channel、status、artifact 数量、总大小、SHA256SUMS checksum、上传时间、操作。
3. “上传发布包”按钮打开弹窗。
4. 上传弹窗包含：tag、version、channel、description、多文件上传控件。
5. 上传前在前端做基础校验：tag/channel 必填，至少选择 `install.ps1` 和 `git-ai-windows-x64.exe`；`SHA256SUMS` 由后端自动生成。
6. 上传成功后刷新列表和通道卡片；新上传版本显示为 `inactive`。
7. 详情弹窗展示 artifact 文件名、类型、平台、大小、SHA-256，并提供下载链接。
8. 支持把历史版本重新激活到对应 channel。

### 交互原则

这是内部发布管理页，视觉方向应偏“工业化、审计感、稳定”。不做炫技动画，重点是清晰展示风险信息：当前 active 版本、校验值、文件是否齐全、二进制大小。

## 客户端设计

`git-ai/src/commands/upgrade.rs` 主流程保持不变。第一版只做最小增强：

1. 下载 `SHA256SUMS`、`install.ps1` 时，如果后端返回 404，错误信息明确提示“当前通道没有上传该文件”。
2. 校验失败时继续阻止安装脚本执行。

安装脚本需要确认二进制下载来源。如果安装脚本仍从 GitHub Release 下载二进制，就不符合内部系统要求。因此第一版内部 Windows 安装脚本 `install.ps1` 应由本地构建时生成或手动维护，脚本里的二进制下载 URL 指向内部平台，例如：

```text
{api_base_url}/worker/releases/{channel}/download/{binary_filename}
```

第一版可以约定：管理员上传的安装脚本已经写好内部下载 URL，平台不动态改写脚本内容。后端只自动生成 `SHA256SUMS`，不自动生成安装脚本。

## 安全与权限

1. 管理接口必须要求登录态或管理 API key。
2. 下载接口公开给 `git-ai upgrade`，否则未登录客户端无法自升级。
3. 文件名必须是 basename，拒绝 `/`、`\`、空文件名和控制字符。
4. 上传文件大小受 `max_file_size_mb` 限制。
5. 服务端计算 SHA-256，不信任前端传入值。
6. `SHA256SUMS` 由后端生成，不接受前端上传的同名文件覆盖。
7. active release 不能直接删除，避免正在升级的客户端下载失败。

## 错误处理

- 缺少 tag/channel/files：400。
- channel 不允许：400。
- 文件名非法：400。
- 文件过大或数量过多：400。
- 必需文件缺失：400。
- 上传文件中包含 `SHA256SUMS`：400，由后端统一生成。
- 未授权访问管理接口：401 或 403。
- 下载未发布 channel：404。
- 下载文件不存在：404。
- 数据库写入失败：500，并记录错误日志。

## 测试计划

### 后端单元测试

1. `ReleaseService` 成功创建 inactive release，并把 artifact 内容写入数据库。
2. 缺少安装脚本时失败。
3. 缺少 `git-ai-windows-x64.exe` 时失败。
4. 非法文件名失败。
5. 超过大小限制失败。
6. 上传文件中包含 `SHA256SUMS` 时失败。
7. 自动生成的 `SHA256SUMS` 内容包含所有上传 artifact 的 SHA-256。
8. 激活新 release 后，同 channel 旧 release 变为 inactive，`GET /worker/releases` 只返回新 active release。

### 后端集成测试

1. Flask test client 上传多文件后，`GET /worker/releases` 返回新 channel 元数据。
2. 下载 `SHA256SUMS` 和 Windows 安装脚本返回数据库中的原始 bytes。
3. 管理列表不返回 `content_blob`。
4. 未授权调用管理上传接口失败。

### 前端验证

1. 运行前端类型检查和构建。
2. 手动打开 Git-AI 发布管理页，验证上传弹窗、文件列表、详情弹窗和错误提示。
3. 上传一个小型测试 release，确认列表刷新并可点击下载。

### 客户端验证

1. 用测试服务返回 release 元数据和数据库下载接口内容，运行 `git-ai upgrade --force`。
2. 校验 `SHA256SUMS` mismatch 时不会运行安装脚本。

## 分阶段交付

第一阶段：后端数据库和 release API。

- 新增模型、数据库访问类、服务类。
- 扩展 `releases_bp` 的公开下载接口和管理接口。
- 添加后端单元与集成测试。

第二阶段：前端管理页面。

- 新增 API 封装。
- 新增 Git-AI 发布管理页面。
- 接入路由或系统菜单。
- 验证上传、列表、详情、下载。

第三阶段：客户端和脚本联调。

- 增强 `git-ai upgrade` 错误提示。
- 准备内部版安装脚本，确保二进制下载 URL 指向内部平台。
- 用真实上传 release 做端到端升级验证。

## 已确认设计点

当前设计点已全部确认，下一步可以进入实施计划编写。

## 验收标准

1. 管理员能在前端页面上传本地构建的安装脚本和可执行文件。
2. 上传后的脚本和可执行文件内容保存在数据库中。
3. 前端能展示 release 列表、当前 active 通道、artifact 清单、文件大小和 SHA-256。
4. `GET /worker/releases` 返回数据库中的 active release 元数据。
5. `GET /worker/releases/{channel}/download/{filename}` 返回数据库中的文件 bytes。
6. `git-ai upgrade` 可以通过内部平台完成升级文件下载和校验。
7. 测试覆盖后端成功、失败、下载和前端关键交互。
