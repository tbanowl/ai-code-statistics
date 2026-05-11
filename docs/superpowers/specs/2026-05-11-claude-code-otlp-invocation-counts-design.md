# Claude Code OTLP Logs 调用次数接收设计

## 背景

本项目已有 Git-AI Metrics 数据链路：Git-AI 客户端通过 `POST /worker/metrics/upload` 上传 JSON 事件，服务端先写入 `metrics_events_raw`，再由 `MetricsEventProcessorTask` 定时解析为 `metrics_events_*` 表。该链路面向 Git-AI 代码归因与统计，不应被 Claude Code OTLP 需求耦合或破坏。

经核对 Claude Code OTEL 能力，OTEL metrics 不稳定暴露插件名和 Skill 名；插件名和 Skill 名应从 OTEL logs/events 读取，核心事件为 `claude_code.skill_activated`。本设计因此新增一条独立 OTLP Logs 接收链路，通过 `/v1/logs` 接收 Claude Code logs/events，只记录插件和 Skill 调用次数，并从 `OTEL_RESOURCE_ATTRIBUTES` 中读取自定义用户信息 `org.user=userId`。

实现必须不修改现有 `/worker/metrics/upload` 接口代码，也不改变现有 Git-AI Metrics 处理流程。

## 目标

- 新增标准化 OTLP HTTP Logs 接收入口 `/v1/logs`。
- 从 Claude Code `claude_code.skill_activated` 事件中记录插件和 Skill 调用次数。
- 记录插件名、Skill 名、触发方式以及自定义用户信息 `org.user`。
- 保持现有 Git-AI Metrics 接口和处理逻辑不变。
- 将 OTLP logs 解析、数据持久化、错误处理封装为独立模块，便于后续关闭、替换或扩展。
- 在设计文档中明确 Claude Code 侧 OTEL logs 相关配置。

## 非目标

- 不使用 `/v1/metrics` 作为本需求的数据来源，因为 metrics 无法稳定提供插件名和 Skill 名。
- 不接收或处理 traces。
- 不统计代码行数、token、耗时、模型质量、成功率等指标。
- 不修改 Rust Git-AI 客户端。
- 不改动 `api/routes/git_ai_worker.py`、`core/services/metrics_service.py`、`core/scheduler/tasks/metrics_event_processor_task.py` 的既有逻辑。
- 第一阶段不强制支持 OTLP Protobuf 二进制解码；优先支持 OTLP JSON logs 映射，降低依赖和实现风险。

## Claude Code 侧配置

Claude Code 需要开启 OTEL logs 导出，并开启工具详情门控，否则自定义/插件 Skill 名通常会被折叠为占位值。

推荐环境变量：

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8888
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://localhost:8888/v1/logs
export OTEL_LOG_TOOL_DETAILS=1
export OTEL_SERVICE_NAME=claude-code
export OTEL_RESOURCE_ATTRIBUTES=org.user=userId
```

配置说明：

- `CLAUDE_CODE_ENABLE_TELEMETRY=1`：开启 Claude Code 遥测。
- `OTEL_LOGS_EXPORTER=otlp`：启用 OTLP logs 导出。
- `OTEL_EXPORTER_OTLP_PROTOCOL=http/json`：第一阶段要求 Claude Code 以 OTLP JSON 发送 logs。
- `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://localhost:8888/v1/logs`：将 logs 发送到本项目新增接收端。
- `OTEL_LOG_TOOL_DETAILS=1`：关键开关。开启后 logs 中可包含真实 Skill 名、自定义/插件命令名、MCP/tool 细节等；不开启时第三方插件 Skill 可能只显示为 `custom_skill`。
- `OTEL_SERVICE_NAME=claude-code`：写入 resource 属性 `service.name`。
- `OTEL_RESOURCE_ATTRIBUTES=org.user=userId`：写入自定义用户信息，服务端解析 `org.user` 作为用户维度。实际部署时将 `userId` 替换为真实用户 ID。

## 接口设计

新增文件：`api/routes/otel_receiver.py`。

新增 Flask 蓝图：`otel_receiver_bp`。

端点：

- `POST /v1/logs`：兼容 OTLP HTTP Logs 默认路径。
- 可选别名 `POST /worker/otel/v1/logs`：项目内命名空间入口，便于和现有 worker API 组织在一起。

请求格式第一阶段支持 `Content-Type: application/json`。服务端按 OTLP JSON Logs 结构解析：

```json
{
  "resourceLogs": [
    {
      "resource": {
        "attributes": [
          {"key": "service.name", "value": {"stringValue": "claude-code"}},
          {"key": "org.user", "value": {"stringValue": "userId"}}
        ]
      },
      "scopeLogs": [
        {
          "logRecords": [
            {
              "timeUnixNano": "1770000000000000000",
              "attributes": [
                {"key": "event.name", "value": {"stringValue": "skill_activated"}},
                {"key": "skill.source", "value": {"stringValue": "plugin"}},
                {"key": "plugin.name", "value": {"stringValue": "superpowers"}},
                {"key": "skill.name", "value": {"stringValue": "brainstorming"}},
                {"key": "invocation_trigger", "value": {"stringValue": "user-slash"}}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

响应格式：

```json
{
  "success": true,
  "accepted": 1,
  "skipped": 0,
  "errors": []
}
```

错误策略：

- JSON 结构非法或无法解析：返回 `400`。
- 合法 OTLP logs 但无目标事件：返回 `200`，`accepted=0`。
- 部分 log record 字段缺失或非法：返回 `200`，增加 `skipped` 和 `errors`，继续处理其他记录。
- 服务端持久化异常：返回 `500`，日志记录异常详情。

## 日志事件映射

服务端只处理 Claude Code Skill 激活事件。

目标事件判定：

- log record 属性 `event.name == "skill_activated"`，或 body/属性中出现等价事件名 `claude_code.skill_activated`。

核心属性映射：

- `skill.source`：Skill 来源，期望值包括 `bundled`、`userSettings`、`projectSettings`、`plugin`。
- `plugin.name`：插件名，例如 `/superpowers:brainstorming` 对应 `superpowers`。该字段依赖 `OTEL_LOG_TOOL_DETAILS=1` 或官方 marketplace 插件元数据。
- `skill.name`：Skill 名，例如 `brainstorming`。第三方插件 Skill 在未开启 `OTEL_LOG_TOOL_DETAILS=1` 时可能为 `custom_skill`，此类记录不作为可靠 Skill 名统计。
- `invocation_trigger`：触发方式，例如 `user-slash`、`claude-proactive`、`nested-skill`。
- resource 属性 `org.user`：自定义用户 ID，来自 `OTEL_RESOURCE_ATTRIBUTES=org.user=userId`。
- resource 属性 `service.name`：服务名，通常为 `claude-code`。
- resource 属性 `service.version`：服务版本，可为空。

记录规则：

- `skill.source == "plugin"` 且存在有效 `plugin.name` 和有效 `skill.name` 时，写入一条 `category="skill"` 的调用记录，`plugin_name` 保存插件名，`skill_name` 保存 Skill 名，`count=1`。
- `skill.name == "custom_skill"` 时跳过，并在 `errors` 中说明需要开启 `OTEL_LOG_TOOL_DETAILS=1`。
- 缺少 `plugin.name` 但 `skill.source == "plugin"` 时跳过，避免错误归因。
- 非 `skill_activated` 事件全部跳过。

## 服务层设计

新增文件：`core/services/otel_logs_service.py`。

核心职责：

- 校验并遍历 OTLP JSON 的 `resourceLogs -> scopeLogs -> logRecords`。
- 从 resource attributes 提取 `service.name`、`service.version`、`org.user`。
- 从 log record attributes 提取 `event.name`、`skill.source`、`plugin.name`、`skill.name`、`invocation_trigger`。
- 只识别 `skill_activated` 事件。
- 将每个有效记录标准化为内部调用记录。
- 调用数据库层批量写入。
- 返回 `accepted/skipped/errors` 统计。

服务层不依赖现有 `MetricsService`，避免与 Git-AI Metrics 事件编号、原始事件表和定时任务耦合。

## 数据层设计

新增 ORM 模型：`OtelInvocationCount`。

建议表名：`otel_invocation_counts`。

字段：

- `id`：XID 主键。
- `source`：来源，默认 `claude_code`。
- `category`：调用类型，第一阶段固定为 `skill`。
- `plugin_name`：插件名称，例如 `superpowers`。
- `skill_name`：Skill 名称，例如 `brainstorming`。
- `invocation_trigger`：触发方式，例如 `user-slash`。
- `org_user`：自定义用户 ID，来自 resource 属性 `org.user`。
- `service_name`：OTEL resource 中的 `service.name`。
- `service_version`：OTEL resource 中的 `service.version`。
- `count`：调用次数，第一阶段固定为 `1`。
- `time_unix_nano`：OTLP log record 时间戳，可为空。
- `received_at`：服务端接收时间，毫秒。
- `created_at`：记录创建时间，毫秒。

新增数据库访问文件：`core/database/otel_logs_db.py`。

核心方法：

- `save_invocation_counts(records: list[OtelInvocationCount]) -> int`

第一阶段按 log record 逐条保存，不做 upsert 聚合，以保留原始调用事件语义。后续如果需要报表，可通过查询层按时间窗口、`org_user`、`plugin_name`、`skill_name` 聚合 `sum(count)`。

## 应用集成

`app.py` 只新增蓝图导入和注册：

- `from api.routes.otel_receiver import otel_receiver_bp`
- `app.register_blueprint(otel_receiver_bp)`

这不修改现有接口代码，只是在应用启动时注册新入口。

## 配置

新增可选配置节：

```yaml
otel:
  receiver:
    enabled: true
    logs:
      enabled: true
      accept_json: true
      accept_protobuf: false
      max_log_records_per_request: 1000
      require_org_user: true
```

第一阶段若配置缺失，默认启用 JSON logs 接收。`require_org_user=true` 时，没有 `org.user` 的有效 Skill 事件会被跳过，避免用户维度缺失。

## 安全与稳定性

- 限制单请求 log record 数量，避免过大 payload 造成内存压力。
- 忽略未知事件和未知属性，降低兼容风险。
- 所有跳过原因进入响应 `errors` 和服务日志，但不泄露完整 payload。
- `plugin.name`、`skill.name`、`org.user` 应限制长度并截断异常长值。
- `OTEL_LOG_TOOL_DETAILS=1` 会让 Claude Code logs 携带更详细的工具输入信息；服务端只提取白名单字段，不保存完整 log payload，降低敏感信息落库风险。

## 测试策略

单元测试：

- 解析有效 `claude_code.skill_activated` OTLP JSON logs。
- 提取 `plugin.name`、`skill.name`、`invocation_trigger`。
- 从 resource attributes 提取 `org.user`。
- 跳过非 `skill_activated` 事件。
- 跳过 `skill.name == "custom_skill"` 并返回明确错误说明。
- 在 `require_org_user=true` 时跳过缺少 `org.user` 的记录。

路由测试：

- `POST /v1/logs` 成功写入。
- `POST /worker/otel/v1/logs` 成功写入。
- 非法 JSON 返回 `400`。
- 合法但无目标事件返回 `200 accepted=0`。

回归检查：

- 现有 `/worker/metrics/upload` 测试保持不变。
- 确认 `api/routes/git_ai_worker.py` 未修改。

## 后续扩展

- 支持 OTLP Protobuf：引入官方 OTLP proto 定义或 OpenTelemetry Python proto 包，增加 `application/x-protobuf` 解码。
- 增加查询 API：按日期、用户、插件、Skill 聚合调用次数。
- 增加前端报表：展示插件和 Skill 调用排行榜。
- 增加认证：对 OTLP 接收端启用 API key 或现有中间件。
- 如后续 Claude Code metrics 稳定暴露插件和 Skill 维度，可再新增 `/v1/metrics` 解析作为补充来源，但不作为第一阶段依赖。

## 验收标准

- 新增 OTLP JSON Logs 接收接口 `/v1/logs` 可接收 Claude Code `skill_activated` 事件并写入 `otel_invocation_counts`。
- 每条有效记录保存 `plugin_name`、`skill_name`、`org_user` 和 `invocation_trigger`。
- 文档记录 Claude Code 侧 OTEL logs 必需配置，包含 `OTEL_LOG_TOOL_DETAILS=1` 和 `OTEL_RESOURCE_ATTRIBUTES=org.user=userId`。
- 现有 `/worker/metrics/upload` 接口代码不被修改。
- 非目标 OTLP logs 不导致请求失败。
- 单元测试、路由测试和现有 Metrics 回归测试通过。
