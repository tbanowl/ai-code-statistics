# Git-AI API 接口文档

## 认证与通用规则

### Headers

所有 API 请求默认包含以下通用 Headers：

| Header | 说明 | 示例 |
|--------|------|------|
| `User-Agent` | 客户端标识 | `git-ai/x.x.x` |
| `X-Distinct-ID` | 客户端唯一 ID | 自动生成的 UUID |
| `Authorization` | OAuth Bearer Token (可选) | `Bearer <token>` |
| `X-API-Key` | API Key (可选) | 从配置读取 |

### 请求超时

- 默认超时：30 秒
- 可通过 ApiContext.with_timeout() 配置

### 错误响应格式

所有 API 返回的通用错误格式：

```json
{
  "error": "错误描述",
  "details": {}  // 可选，额外错误详情
}
```

**HTTP 状态码**：
- `200` - 成功
- `400` - 请求参数错误
- `401` - 未授权
- `404` - 资源未找到 (CAS 读取时所有 hash 都不存在)
- `500` - 服务器内部错误

---

# OAuth API

## 安全要求

HTTPS 要求：
- **Release 构建**: 必须使用 HTTPS
- **Debug 构建**: 允许 HTTP 用于本地开发
- **环境变量 `GIT_AI_ALLOW_INSECURE=1`**: 允许 HTTP（不推荐用于生产）

## 获取设备授权码

**接口**: `POST /worker/oauth/device/code`

**请求**: 空体（JSON `{}`）

```json
{}
```

**响应**: DeviceAuthResponse (200)

```json
{
  "device_code": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "user_code": "WXYZ-1234",
  "verification_uri": "https://example.com/device",
  "verification_uri_complete": "https://example.com/device?code=WXYZ-1234",
  "expires_in": 900,
  "interval": 5
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| device_code | String | 设备授权码（用于轮询获取令牌） |
| user_code | String | 用户验证码（需用户在浏览器中输入） |
| verification_uri | String | 验证 URL |
| verification_uri_complete | String | 包含 user_code 的完整验证 URL（可选） |
| expires_in | u32 | device_code 过期时间（秒） |
| interval | u32 | 轮询间隔（秒） |

## 交换令牌

**接口**: `POST /worker/oauth/token`

支持三种授权类型（grant_type）：

### 1. 设备授权流程

**请求**:

```json
{
  "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
  "device_code": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "client_id": "git-ai-cli"
}
```

**响应**: TokenResponse (200)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
  "refresh_expires_in": 7776000
}
```

**错误**: OAuthError (400)

| error | 说明 |
|-------|------|
| authorization_pending | 用户尚未批准授权 |
| slow_down | 轮询太快，增加间隔（+5 秒） |
| access_denied | 用户拒绝了授权 |
| expired_token | device_code 已过期 |

### 2. 刷新令牌

**请求**:

```json
{
  "grant_type": "refresh_token",
  "refresh_token": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
  "client_id": "git-ai-cli"
}
```

**响应**: TokenResponse (200)

```json
{
  "access_token": "新令牌...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "新的刷新令牌...",
  "refresh_expires_in": 7776000
}
```

### 3. 安装 Nonce 交换

**请求**:

```json
{
  "grant_type": "install_nonce",
  "install_nonce": "安装页生成的 nonce",
  "client_id": "git-ai-cli"
}
```

**响应**: TokenResponse (200)

## OAuthError 错误格式

```json
{
  "error": "error_code",
  "error_description": "错误描述信息"
}
```

---

## 凭证存储

### StoredCredentials 结构

客户端本地存储的凭证格式：

```json
{
  "access_token": "短令牌（1小时过期）",
  "refresh_token": "长令牌（90天过期）",
  "access_token_expires_at": 1704067200,
  "refresh_token_expires_at": 1734172800
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| access_token | String | 访问令牌，有效期 1 小时 |
| refresh_token | String | 刷新令牌，有效期 90 天 |
| access_token_expires_at | i64 | 访问令牌过期时间（Unix 时间戳） |
| refresh_token_expires_at | i64 | 刷新令牌过期时间（Unix 时间戳） |

### 凭证存储位置

| 平台 | 位置 |
|------|------|
| macOS | Keychain |
| Windows | Credential Manager |
| Linux | Secret Service (libsecret) |
| Fallback | `~/.git-ai/internal/credentials` |

### 凭证状态管理

客户端会自动处理以下状态：

| 状态 | 说明 |
|------|------|
| LoggedOut | 无存储凭证 |
| LoggedIn | 凭证有效（access_token 未过期或有 5 分钟缓冲） |
| RefreshExpired | refresh_token 已过期，需要重新登录 |
| Error | 凭证加载或解析失败 |

### Access Token Payload (JWT)

客户端可直接从 access_token 解析用户身份（JWT Base64 URL 编码）：

```json
{
  "sub": "user_id",              // 用户 ID
  "email": "user@example.com",  // 用户邮箱
  "name": "User Name",           // 用户姓名
  "orgs": [                     // 用户所属组织列表
    {
      "org_id": "org123",
      "org_name": "Organization Name",
      "org_slug": "org-slug",
      "role": "owner"
    }
  ],
  "personal_org_id": "org456"    // 个人组织 ID
}
```

**注意**: 这是 JWT payload 部分的解码内容，不包含头部和签名。

---

# Bundle API

### 创建 Bundle

**接口**: `POST /api/bundles`

**请求**: CreateBundleRequest

```json
{
  "title": "string",  // 必填，min 1 字符
  "data": {
    "prompts": {
      "prompt_hash": PromptRecord  // 必填，至少一个
    },
    "files": {  // 可选，文件 diffs 和 annotations
      "file_path": {
        "annotations": {
          "prompt_hash": [  // 行号或行范围数组
            10,              // 单行
            [1, 5],          // 行范围 [start, end]
            ...
          ]
        },
        "diff": "string",
        "base_content": "string"
      }
    }
  }
}
```

**响应**: CreateBundleResponse (200)

```json
{
  "success": true,
  "id": "bundle_id",
  "url": "https://app.com/bundle_id"
}
```

**错误**: ApiErrorResponse (400, 500)

---

# CAS API

### 上传 CAS 对象

**接口**: `POST /worker/cas/upload`

**请求**: CasUploadRequest

```json
{
  "objects": [
    {
      "content": {},     // 具体的 JSON 内容
      "hash": "string",
      "metadata": {      // 可选，为空时不序列化
        "key": "value"
      }
    }
  ]
}
```

**响应**: CasUploadResponse (200)

```json
{
  "results": [
    {
      "hash": "abc123",
      "status": "ok",  // "ok" 或 "error"
      "error": null    // 可选，错误信息
    }
  ],
  "success_count": 1,
  "failure_count": 0
}
```

**示例类型**: CasMessagesObject

```json
{
  "content": {
    "messages": [
      {
        "role": "user",
        "content": "帮我实现一个功能"
      },
      {
        "role": "assistant",
        "content": "好的，我来帮你..."
      }
    ]
  },
  "hash": "msg_hash_123"
}
```

### 读取 CAS 对象

**接口**: `GET /worker/cas/?hashes=hash1,hash2,...`

**查询参数**:
- `hashes`: 逗号分隔的 hash 列表，最多 100 个

**响应**: CAPromptStoreReadResponse (200)

```json
{
  "results": [
    {
      "hash": "hash1",
      "status": "ok",
      "content": {},  // CAS 对象内容
      "error": null
    }
  ],
  "success_count": 1,
  "failure_count": 0
}
```

**404 响应**: 所有 hash 都未找到时返回空结果

```json
{
  "results": [],
  "success_count": 0,
  "failure_count": 2
}
```

---

# Metrics API

### 上传指标

**接口**: `POST /worker/metrics/upload`

**请求**: MetricsBatch

```json
{
  "v": 1,  // version: API 版本号，当前为 1
  "events": [
    {
      "t": 1704067200,  // timestamp: Unix 时间戳 (秒)
      "e": 1,           // event_id: 事件类型
      "v": {            // values: 事件特定的值，使用位置编码的 HashMap
        "0": 50,
        "1": 20
      },
      "a": {            // attrs: 通用属性，使用位置编码的 HashMap
        "0": "1.0.0",
        "20": "claude-code"
      }
    }
  ]
}
```

**响应**: MetricsUploadResponse (200, 401, 500)

```json
{
  "errors": [  // 失败的事件列表，空数组表示全部成功
    {
      "index": 0,     // 失败的事件在请求数组中的索引
      "error": "string"  // 错误信息
    }
  ]
}
```

**重试逻辑**:
- 首次尝试失败后，等待 60 秒重试一次
- 部分成功（200 响应但有 errors 数组）不重试
- 验证错误记录到 Sentry

---

# 数据类型详细定义

## Metrics 事件类型

### Event ID 1: Committed (提交事件)

**触发时机**: AI 辅助代码提交时

**Values 位置映射**:

| 位置 | JSON 字段 | 类型 | 说明 |
|------|-----------|------|------|
| 0 | `"0"` | u32 | human_additions (人工新增行数) |
| 1 | `"1"` | u32 | git_diff_deleted_lines (删除行数) |
| 2 | `"2"` | u32 | git_diff_added_lines (新增行数) |
| 3 | `"3"` | Vec[String] | tool_model_pairs ([0]=aggregate, [1+]=per tool) |
| 4 | `"4"` | Vec[u32] | mixed_additions (混合新增行数) |
| 5 | `"5"` | Vec[u32] | ai_additions (AI 新增行数) |
| 6 | `"6"` | Vec[u32] | ai_accepted (AI 接受行数) |
| 7 | `"7"` | Vec<u32> | total_ai_additions (总 AI 新增行数) |
| 8 | `"8"` | Vec<u32> | total_ai_deletions (总 AI 删除行数) |
| 9 | `"9"` | Vec<u64> | time_waiting_for_ai (等待 AI 时间 ms) |
| 10 | `"10"` | u64 | first_checkpoint_ts (第一个检查点时间戳) |
| 11 | `"11"` | String | commit_subject (提交标题) |
| 12 | `"12"` | String | commit_body (提交内容) |

**示例**:

```json
{
  "t": 1704067200,
  "e": 1,
  "v": {
    "0": 50,                    // human_additions
    "1": 20,                    // git_diff_deleted_lines
    "2": 150,                   // git_diff_added_lines
    "3": ["all", "claude-code:claude-3"],
    "4": [30, 20],              // mixed_additions
    "5": [100, 70],             // ai_additions
    "6": [80, 55],              // ai_accepted
    "7": [120, 80],             // total_ai_additions
    "8": [25, 15],              // total_ai_deletions
    "9": [5000, 3000],          // time_waiting_for_ai
    "10": 1704060000,           // first_checkpoint_ts
    "11": "Add new feature",    // commit_subject
    "12": "Initial commit"      // commit_body
  },
  "a": {
    "0": "1.0.0",
    "3": "abc123"
  }
}
```

### Event ID 2: AgentUsage (代理使用事件)

**触发时机**: 每次 AI 检查点时

**Values**: 空 (所有信息通过 attrs 传递，如 prompt_id, tool, model)

**示例**:

```json
{
  "t": 1704067200,
  "e": 2,
  "v": {},  // 空
  "a": {
    "0": "1.0.0",
    "20": "claude-code",
    "21": "claude-3",
    "22": "prompt_abc123"
  }
}
```

### Event ID 3: InstallHooks (安装钩子事件)

**触发时机**: 每个工具尝试安装钩子时（每工具一个事件）

**Values 位置映射**:

| 位置 | JSON 字段 | 类型 | 说明 |
|------|-----------|------|------|
| 0 | `"0"` | String | tool_id (工具 ID，如 "cursor", "fork") |
| 1 | `"1"` | String | status (状态: "not_found", "installed", "already_installed", "failed") |
| 2 | `"2"` | String | message (错误信息或警告，可选) |

**示例**:

```json
{
  "t": 1704067200,
  "e": 3,
  "v": {
    "0": "cursor",
    "1": "installed",
    "2": "Successfully installed"
  },
  "a": {
    "0": "1.0.0"
  }
}
```

### Event ID 4: Checkpoint (检查点事件)

**触发时机**: 每个文件的检查点（每文件一个事件）

**Values 位置映射**:

| 位置 | JSON 字段 | 类型 | 说明 |
|------|-----------|------|------|
| 0 | `"0"` | u64 | checkpoint_ts (检查点时间戳) |
| 1 | `"1"` | String | kind (类型: "human", "ai_agent", "ai_tab") |
| 2 | `"2"` | String | file_path (文件相对路径) |
| 3 | `"3"` | u32 | lines_added (新增行数) |
| 4 | `"4"` | u32 | lines_deleted (删除行数) |
| 5 | `"5"` | u32 | lines_added_sloc (新增代码行数) |
| 6 | `"6"` | u32 | lines_deleted_sloc (删除代码行数) |

**示例**:

```json
{
  "t": 1704067200,
  "e": 4,
  "v": {
    "0": 1704067200,
    "1": "ai_agent",
    "2": "src/main.rs",
    "3": 50,
    "4": 10,
    "5": 45,
    "6": 8
  },
  "a": {
    "0": "1.0.0",
    "20": "claude-code",
    "21": "claude-3"
  }
}
```

## EventAttributes 通用属性位置映射

所有 Metrics 事件共享以下属性 (使用位置编码的 `a` 字段):

| 位置 | JSON 字段 | 类型 | 必填 | 说明 |
|------|-----------|------|------|------|
| 0 | `"0"` | String | ✓ | git_ai_version (版本号) |
| 1 | `"1"` | String | ✗ | repo_url (仓库 URL) |
| 2 | `"2"` | String | ✗ | author (作者) |
| 3 | `"3"` | String | ✗ | commit_sha (提交 SHA) |
| 4 | `"4"` | String | ✗ | base_commit_sha (基础提交 SHA) |
| 5 | `"5"` | String | ✗ | branch (分支名) |
| 20 | `"20"` | String | ✗ | tool (工具名称，如 "claude-code") |
| 21 | `"21"` | String | ✗ | model (模型名称，如 "claude-3") |
| 22 | `"22"` | String | ✗ | prompt_id (提示 ID) |
| 23 | `"23"` | String | ✗ | external_prompt_id (外部提示 ID) |
| 30 | `"30"` | String (JSON) | ✗ | custom_attributes (自定义属性) |

**custom_attributes 字段说明**:
- 类型：JSON 字符串 (String)，需要解析为 JSON 对象使用
- 用途：存储额外的自定义属性
- 示例：`"30": "{\"custom_field\":\"value\",\"another\":123}"`

---

## SparseArray (位置编码数组) 说明

**格式**: `HashMap<String, serde_json::Value>`

**编码规则**:
- **缺失的键**: 字段未设置
- **值为 `null`**: 字段显式设置为 null
- **有具体值**: 字段已设置

**示例**:

```json
{
  "0": "1.0.0",                    // 位置 0 设置为字符串
  "3": 1704067200,                 // 位置 3 设置为数字
  "5": null,                       // 位置 5 显式为 null
  "20": ["item1", "item2"],        // 位置 20 设置为数组
  "30": "{\"key\":\"value\"}"      // 位置 30 为 JSON 字符串
  // 位置 1, 2, 4, 6... 未设置 (不存在键)
}
```

---

## API 版本信息

| API | 版本 | 说明 |
|-----|------|------|
| Metrics | 1 | 当前版本定义为 `METRICS_API_VERSION = 1` |

---

---

# 配置

## 配置文件位置

客户端按以下优先级搜索配置文件：

1. `~/.config/git-ai/config.toml`
2. `~/.git-ai/config.toml`
3. 项目目录内的 `.git-ai.toml`
4. 项目目录内的 `.git-ai/config.toml`

## API 配置

### api_base_url

API 服务器基础 URL。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `api_base_url` | String | `https://usegitai.com` | API 服务器地址 |

**环境变量**: `GIT_AI_API_BASE_URL`

**在配置文件中使用**:
```toml
api_base_url = "https://api.yourcompany.com"
```

### api_key

用于认证的 API Key，替代 OAuth 流程。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `api_key` | String | 无 | API Key |

**在配置文件中使用**:
```toml
api_key = "your-api-key-here"
```

**HTTP Header**: `X-API-Key: <api_key>`

---

## 遥测配置

### telemetry_enterprise_dsn

企业版 Sentry 数据源名称 (DSN)，用于错误和性能监控上报。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `telemetry_enterprise_dsn` | String | 无 | 企业版 Sentry DSN |

**优先级**: 配置文件 > 环境变量 > 编译时内置值

**环境变量**: `SENTRY_ENTERPRISE`

**DSN 格式**:
```
https://PUBLIC_KEY@HOST/PROJECT_ID
```

**示例**: `https://abc123@o1234.ingest.sentry.io/5678`

**在配置文件中使用**:
```toml
[telemetry]
enterprise_dsn = "https://your-public-key@your-sentry-host.project.id"
```

### OSS 遥测配置

| 配置项 | 类型 | 环境变量 | 说明 |
|--------|------|----------|------|
| `SENTRY_OSS` | String | `SENTRY_OSS` | OSS 版 Sentry DSN |
| `POSTHOG_API_KEY` | String | `POSTHOG_API_KEY` | PostHog API Key |
| `POSTHOG_HOST` | String | `POSTHOG_HOST` | PostHog Host (默认: `https://us.i.posthog.com`) |

**禁用 OSS 遥测**:
```toml
[telemetry]
oss_disabled = true
```

---

---

# Releases API

## 获取发布信息

**接口**: `GET /worker/releases`

**请求**:

```http
GET /worker/releases
```

**请求 Headers**:
- `User-Agent`: `git-ai/x.x.x`
- `X-Distinct-ID`: 自动生成的 UUID

**响应**: ReleasesResponse (200)

```json
{
  "channels": {
    "latest": {
      "version": "v1.2.3",
      "checksum": "abc123def45678901234567890..."
    },
    "next": {
      "version": "v1.2.4-next",
      "checksum": "def78901234567890123456789..."
    },
    "enterprise-latest": {
      "version": "v1.2.3",
      "checksum": "abc123def45678901234567890..."
    },
    "enterprise-next": {
      "version": "v1.2.4-next",
      "checksum": "def78901234567890123456789..."
    }
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| version | String | 发行版本标签（如 "v1.2.3"） |
| checksum | String | SHA256 校验和（64 字符十六进制） |

### 发布渠道

| 渠道名称 | 说明 |
|----------|------|
| `latest` | 最新稳定版 |
| `next` | 下一个版本（预发布） |
| `enterprise-latest` | 企业版最新稳定版 |
| `enterprise-next` | 企业版下一个版本（预发布） |

---

## 下载发布文件

### 获取 SHA256SUMS

**接口**: `GET /worker/releases/{channel}/download/SHA256SUMS`

**路径参数**:
- `channel`: 发布渠道（如 "latest"、"next"、"enterprise-latest"、"enterprise-next"）

**请求**:

```http
GET /worker/releases/latest/download/SHA256SUMS
```

**响应** (200 - 纯文本):

```
594de6cf107e8ffb6efd9029bf727b465ab55a9b4c4c3995eb3e628c857dc423  git-ai-linux-arm64
88db3c0c7fc62a815579ec0ca42535c2b83ab18d9e3af8efe345dee96677b1d8  git-ai-linux-x64
75d1692d347c3e08a208dc6373df4cee2b5ffd0e2aee62ccb1bb47aae866b2c8  install.sh
```

**格式**: `<checksum>  <filename>`（两个空格分隔）

### 下载安装脚本

**平台**: Windows

**接口**: `GET /worker/releases/{channel}/download/install.ps1`

**路径参数**:
- `channel`: 发布渠道

**请求**:

```http
GET /worker/releases/latest/download/install.ps1
```

**响应** (200 - PowerShell 脚本):

```powershell
# PowerShell 安装脚本内容
```

**平台**: Linux/macOS

**接口**: `GET /worker/releases/{channel}/download/install.sh`

**路径参数**:
- `channel`: 发布渠道

**请求**:

```http
GET /worker/releases/latest/download/install.sh
```

**响应** (200 - Shell 脚本):

```bash
#!/bin/bash
# Shell 安装脚本内容
```

**环境变量**: 脚本执行时会注入 `GIT_AI_RELEASE_TAG` 环境变量，值为版本标签

---

## 开发参考

### 源代码文件

| 组件 | 文件路径 |
|------|----------|
| 配置 | `src/config.rs` |
| 遥测上报 | `src/observability/flush.rs` |
| 升级更新 | `src/commands/upgrade.rs` |
| OAuth 客户端 | `src/auth/client.rs` |
| OAuth 类型 | `src/auth/types.rs` |
| 凭证存储 | `src/auth/credentials.rs` |
| 认证状态 | `src/auth/state.rs` |
| 身份解析 | `src/auth/identity.rs` |
| API 客户端 | `src/api/client.rs` |
| API 类型定义 | `src/api/types.rs` |
| Bundle API | `src/api/bundle.rs` |
| CAS API | `src/api/cas.rs` |
| Metrics API | `src/api/metrics.rs` |
| Metrics 类型 | `src/metrics/types.rs` |
| Metrics 事件 | `src/metrics/events.rs` |
| Event 属性 | `src/metrics/attrs.rs` |
| 位置编码 | `src/metrics/pos_encoded.rs` |

| 组件 | 文件路径 |
|------|----------|
| OAuth 客户端 | `src/auth/client.rs` |
| OAuth 类型 | `src/auth/types.rs` |
| 凭证存储 | `src/auth/credentials.rs` |
| 认证状态 | `src/auth/state.rs` |
| 身份解析 | `src/auth/identity.rs` |
| API 客户端 | `src/api/client.rs` |
| API 类型定义 | `src/api/types.rs` |
| Bundle API | `src/api/bundle.rs` |
| CAS API | `src/api/cas.rs` |
| Metrics API | `src/api/metrics.rs` |
| Metrics 类型 | `src/metrics/types.rs` |
| Metrics 事件 | `src/metrics/events.rs` |
| Event 属性 | `src/metrics/attrs.rs` |
| 位置编码 | `src/metrics/pos_encoded.rs` |

### 数据流

```
Client (Rust) → minreq → Server API
                       ↓
                   Database/Storage
```

### 认证流程

1. 客户端尝试从本地加载存储的凭证
2. 如果 access_token 有效（5 分钟缓冲），直接使用
3. 如果过期，使用 refresh_token 刷新
4. 使用 Mutex 防止进程内并发刷新
5. 刷新失败则返回 None（未登录）
