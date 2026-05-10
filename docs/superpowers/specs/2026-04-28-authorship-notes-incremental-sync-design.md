# Authorship Notes 强一致增量同步设计

## 背景

当前 `authorship_notes` 的 REST 同步在客户端 fetch 和 push 时都会先调用 `/worker/authorship_notes/list` 获取仓库下的全量 `commit_shas`，再与本地 Git Notes 做差集。这会让响应体和本地比对成本随仓库历史线性增长，即使绝大多数 notes 已经同步过，仍然重复传输全量清单。

代码中已经存在部分增量基础：服务端 `list_notes(repo_url, since_commit_time)` 支持按 `commit_time` 过滤，客户端类型也有 `since_commit_time` 字段。但 `commit_time` 是 Git 提交时间，不代表 note 内容在服务端的变更时间，无法可靠发现旧 commit 的 note 被更新、重写或补录。因此本设计采用服务端变更序号和内容哈希实现强一致增量同步。

## 目标

1. 避免每次同步拉取仓库全量 `commit_shas`。
2. 能发现“本地已有 commit 的 note 内容发生变化”的情况。
3. 不依赖 `note_blob_oid` 判断一致性，因为不同客户端可能生成不同的 Git note blob oid。
4. 保持旧客户端基本可用，新客户端优先使用增量摘要协议。
5. 同步失败时不推进本地水位，避免漏同步。

## 非目标

1. 本阶段不要求实现远端删除同步；如果后续需要，可基于墓碑字段扩展。
2. 本阶段不重构 Git Notes 存储格式。
3. 本阶段不改变 `/batch` 返回完整 note 内容的职责。

## 推荐方案

使用服务端生成的 `change_seq` 作为增量水位，使用 `content_hash = sha256(note_content)` 作为跨客户端稳定的一致性摘要。

`note_blob_oid` 继续作为调试或兼容字段保留，但不参与同步一致性判断。

## 数据模型

在 `authorship_notes` 表新增字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `content_hash` | VARCHAR(71) / VARCHAR(64) | `note_content` 的 SHA-256 摘要；可统一存十六进制字符串，协议层可展示为 `sha256:<hex>` |
| `change_seq` | BIGINT NOT NULL | 服务端单调递增变更序号，用于增量 list 水位 |

推荐新增索引：

```sql
CREATE INDEX idx_authorship_notes_repo_change_seq
ON authorship_notes(repo_url, change_seq);
```

已有约束继续保留：

```sql
UNIQUE(repo_url, commit_sha)
```

### `change_seq` 生成要求

`change_seq` 必须由数据库侧可靠生成，避免多服务实例并发时出现重复或回退。可选实现：

1. 使用 MySQL `AUTO_INCREMENT` 辅助表生成全局序号；
2. 使用单独的 sequence/counter 表，在事务内更新并读取；
3. 如果数据库支持原生 sequence，则使用原生 sequence。

不要在应用层使用 `SELECT MAX(change_seq) + 1`。

### 写入规则

`create_or_update_note` 和 `batch_push_notes` 统一执行以下逻辑：

1. 计算 `new_hash = sha256(note_content)`；
2. 如果 `(repo_url, commit_sha)` 不存在：插入 note，写入 `content_hash`，分配新的 `change_seq`；
3. 如果记录存在且 `content_hash != new_hash`：更新 note 内容、作者、分支、`content_hash`、`updated_at`，并分配新的 `change_seq`；
4. 如果记录存在且 `content_hash == new_hash`：跳过内容更新和 `change_seq` 更新，避免重复 push 造成无意义变更。

## API 设计

### `POST /worker/authorship_notes/list`

保留旧的 `commit_shas` 字段，新增增量摘要字段。

请求：

```json
{
  "repo_url": "https://example.com/org/repo.git",
  "since_change_seq": 12345,
  "limit": 1000
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `repo_url` | 是 | 仓库 URL |
| `since_change_seq` | 否 | 只返回 `change_seq > since_change_seq` 的记录；缺省时可返回全量摘要 |
| `limit` | 否 | 分页大小，服务端应设置默认值和最大值 |

响应：

```json
{
  "ok": true,
  "data": {
    "commit_shas": ["abc123"],
    "items": [
      {
        "commit_sha": "abc123",
        "content_hash": "sha256:...",
        "change_seq": 12346,
        "updated_at": 1775973635847
      }
    ],
    "next_change_seq": 12346,
    "has_more": false
  }
}
```

排序规则：服务端按 `change_seq ASC` 返回。`next_change_seq` 是本页最大 `change_seq`；只有客户端成功应用本页和所有后续分页后，才能推进本地水位。

### `POST /worker/authorship_notes/batch`

保持现有按 `commit_shas` 批量拉完整内容的职责。可在返回项中附带 `content_hash` 和 `change_seq`，便于客户端校验响应与 list 摘要一致。

```json
{
  "ok": true,
  "data": {
    "notes": [
      {
        "commit_sha": "abc123",
        "content": "...",
        "content_hash": "sha256:...",
        "change_seq": 12346
      }
    ],
    "missing": []
  }
}
```

### `POST /worker/authorship_notes/push`

请求可继续保持现有结构。服务端不信任客户端传入的 `content_hash`，即使未来客户端附带 hash，服务端也必须基于收到的 `content` 自行计算。

响应建议增加幂等统计：

```json
{
  "ok": true,
  "data": {
    "created": 1,
    "updated": 2,
    "unchanged": 10
  }
}
```

## 客户端同步流程

### 本地同步状态

客户端为每个 `repo_url` 保存本地水位：

```json
{
  "repo_url": "https://example.com/org/repo.git",
  "last_change_seq": 12346
}
```

存储位置可以是 `.git/ai/rest_notes_sync_state/<normalized_repo>.json`，也可以复用现有本地数据库。关键要求是：只有在远端摘要分页和必要的 `/batch` 内容都成功应用到本地 Git Notes 后，才能推进 `last_change_seq`。

### Fetch 增量流程

1. 读取本地 `last_change_seq`，没有则从 `0` 开始；
2. 调用 `/list(repo_url, since_change_seq=last_change_seq, limit=N)`；
3. 对每个 `item`：
   - 本地没有该 commit 的 note：加入 `to_fetch`；
   - 本地存在 note：读取本地 note 内容并计算 `sha256`，若与 `content_hash` 不同则加入 `to_fetch`；
4. 对 `to_fetch` 调 `/batch` 获取完整 note 内容；
5. 用 `notes_add_batch` 写入本地 Git Notes；
6. 如果 `has_more=true`，继续下一页；
7. 所有分页成功后，将本地 `last_change_seq` 更新为最后成功页的 `next_change_seq`。

### Push 增量流程

Push 侧目标是避免为了判断远端是否已有 note 而拉全量清单。

推荐流程：

1. 枚举本地 Git Notes；
2. 为本地 note 内容计算 `content_hash`；
3. 获取远端摘要清单。初始版本可以复用 `/list` 分页拉摘要；后续如本地 note 很多，可增加 `/diff` 接口，让客户端提交 `{commit_sha, content_hash}` 摘要，由服务端返回缺失或不同的 commit；
4. 只 push 远端缺失或 hash 不同的 note；
5. 服务端用 `content_hash` 做幂等判断，重复 push 不推进 `change_seq`。

## 删除同步扩展

如果后续需要同步删除，新增字段：

| 字段 | 说明 |
| --- | --- |
| `deleted_at` | 删除时间，毫秒时间戳 |
| `is_deleted` | 是否为墓碑记录 |

删除时不物理删除行，而是写墓碑并推进 `change_seq`。`/list` 返回 `deleted=true`，客户端据此删除本地 note。当前阶段先不实现，避免扩大范围。

## 迁移策略

1. 新增 `content_hash` 和 `change_seq` 字段；
2. 为所有历史记录回填 `content_hash = sha256(note_content)`；
3. 为历史记录分配稳定递增的 `change_seq`，可按 `updated_at ASC, id ASC` 排序；
4. 创建 `(repo_url, change_seq)` 索引；
5. 服务端先兼容返回旧 `commit_shas` 与新 `items`；
6. 新客户端切换到 `items + content_hash + change_seq` 协议；
7. 稳定后可逐步降低旧全量路径使用频率。

## 测试计划

### 服务端

1. 插入新 note 时生成 `content_hash` 和 `change_seq`；
2. 相同内容重复 push 返回 `unchanged`，不更新 `change_seq`；
3. 同一 `commit_sha` 内容变化时更新 `content_hash` 并推进 `change_seq`；
4. `/list` 按 `change_seq ASC` 分页返回，`since_change_seq` 只返回更大的记录；
5. `/batch` 返回内容与 hash 对应。

### 客户端

1. 本地缺失 note 时 fetch 会 batch 拉取并写入；
2. 本地已有 note 但 hash 不同，会重新拉取并覆盖；
3. 本地已有 note 且 hash 相同，不会 batch 拉取；
4. 分页中途失败不推进 `last_change_seq`；
5. 不同 `note_blob_oid` 但相同 note 内容，不触发重复同步。

## 风险与处理

| 风险 | 处理 |
| --- | --- |
| 多实例并发导致 `change_seq` 冲突 | 使用数据库侧 sequence/counter，禁止应用层 max+1 |
| 历史数据没有 hash/seq | 上线 migration 一次性回填 |
| 本地状态推进过早造成漏同步 | 所有分页和 batch 应用成功后再更新水位 |
| 内容 hash 与协议格式不一致 | 固定 SHA-256，hash 输入为 UTF-8 `note_content` 原文 |
| 旧客户端不识别新响应 | 保留 `commit_shas` 字段和旧参数语义 |

## 实施顺序建议

1. 服务端 schema migration：新增字段、回填、索引、sequence 生成机制；
2. 服务端 DB/service/API：写入 hash/seq，list 返回摘要分页；
3. 服务端测试覆盖幂等、更新、分页；
4. 客户端 fetch：本地状态、水位分页、hash 比对、batch 拉取；
5. 客户端 push：基于 hash 摘要减少无效 push；
6. 客户端测试覆盖 hash 一致性和失败不推进水位。
