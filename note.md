# note


## GIT-AI 数据接口

### Metrics API

Metrics 数据接口，接口地址: /worker/metrics/upload

#### 数据结构

##### MetricsData

| Key | Name | Type | Description |
| --- | ---- | ---- | ----------- |
| v | version | u8 | Metrics API 版本号，目前固定为 1 |
| events | events | MetricEvent | Metrics 事件 |

##### MetricEvent

| Key | Name | Type | Description |
| --- | ---- | ---- | ----------- |
| t | timestamp | int | 时间戳 |
| e | event_id | MetricEventId | 事件类型ID |
| v | values | {} | 对应事件的数据结构 |
| a | attrs | EventAttributes | 事件属性 |

```rust
pub enum MetricEventId {
    Committed = 1, // git commit
    AgentUsage = 2, // 
    InstallHooks = 3, // 安装 hooks
    Checkpoint = 4, // git-ai checkpoint
}
```

##### CommittedValues 

Values for Event ID 1: committed

在 AI 代码提交时记录。

**Scalar fields:**

| Position | Name | Type | Description |
|----------|------|------|-------------|
| 0 | human_additions | u32 | 人类添加行数 |
| 1 | git_diff_deleted_lines | u32 | 删除行数 |
| 2 | git_diff_added_lines | u32 | 新增行数 |

**Array fields (parallel arrays, index 0 = "all" for aggregate, index 1+ = per tool/model):**

| Position | Name | Type |
|----------|------|------|
| 3 | tool_model_pairs | `Vec<String>` |
| 4 | mixed_additions | `Vec<u32>` |
| 5 | ai_additions | `Vec<u32>` |
| 6 | ai_accepted | `Vec<u32>` |
| 7 | total_ai_additions | `Vec<u32>` |
| 8 | total_ai_deletions | `Vec<u32>` |
| 9 | time_waiting_for_ai | `Vec<u64>` |
| 10 | first_checkpoint_ts | u64 |
| 11 | commit_subject | String |
| 12 | commit_body | String |

##### AgentUsageValues

Values for Event ID 2: agent_usage

Recorded on every AI checkpoint to track agent usage.
Uses attributes (prompt_id, tool, model) rather than event-specific values.

```rust
pub struct AgentUsageValues {}
```

##### InstallHooksValues

Value positions for "install_hooks" event.
One event per tool attempted during install-hooks.

```rust
pub mod install_hooks_pos {
    pub const TOOL_ID: usize = 0; // String - tool id (e.g., "cursor", "fork")
    pub const STATUS: usize = 1; // String - "not_found", "installed", "already_installed", "failed"
    pub const MESSAGE: usize = 2; // Option<String> - error message or warnings
}
```

Values for Event ID 3: install_hooks

Recorded for each tool during git-ai install-hooks command.
One event per tool attempted.

**Fields:**
| Position | Name | Type |
|----------|------|------|
| 0 | tool_id | String |
| 1 | status | String |
| 2 | message | `Option<String>` |

##### CheckpointValues

Value positions for "checkpoint" event.
One event per file in the checkpoint.

```rust
pub mod checkpoint_pos {
    pub const CHECKPOINT_TS: usize = 0; // u64 - checkpoint timestamp
    pub const KIND: usize = 1; // String ("human", "ai_agent", "ai_tab")
    pub const FILE_PATH: usize = 2; // String - full relative file path
    pub const LINES_ADDED: usize = 3; // u32 - for this file
    pub const LINES_DELETED: usize = 4; // u32 - for this file
    pub const LINES_ADDED_SLOC: usize = 5; // u32 - for this file
    pub const LINES_DELETED_SLOC: usize = 6; // u32 - for this file
}
```

Values for Event ID 4: checkpoint

Recorded for each file in a checkpoint.
Uses EventAttributes for standard metadata (repo_url, author, tool, model, etc.)

**Fields:**
| Position | Name | Type |
|----------|------|------|
| 0 | checkpoint_ts | u64 |
| 1 | kind | String |
| 2 | file_path | String |
| 3 | lines_added | u32 |
| 4 | lines_deleted | u32 |
| 5 | lines_added_sloc | u32 |
| 6 | lines_deleted_sloc | u32 |

##### EventAttributes 

| Position | Name | Type | Required |
|----------|------|------|----------|
| 0 | git_ai_version | String | Yes |
| 1 | repo_url | String | No (nullable) |
| 2 | author | String | No (nullable) |
| 3 | commit_sha | String | No (nullable) |
| 4 | base_commit_sha | String | No (nullable) |
| 5 | branch | String | No (nullable) |
| 20 | tool | String | No (nullable) | Agent 工具，claude、opencode、codex 等等
| 21 | model | String | No (nullable) |
| 22 | prompt_id | String | No (nullable) |
| 23 | external_prompt_id | String | No (nullable) |