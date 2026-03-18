# Swagger 实现重构设计文档

**日期**: 2026-03-17
**状态**: 已批准

## 概述

本文档描述了重新设计 Swagger API 文档实现的方案，将文档从代码注释中分离出来，采用 YAML 文件结合反射自动生成的方式，提高可维护性和开发体验。

## 背景

当前项目使用 Flasgger，通过在每个 API 函数的文档字符串中嵌入 YAML 来定义 Swagger 文档。这种方式存在以下问题：
- 文档与代码紧密耦合，路由文件变得冗长
- 维护困难，API 变更需要同时修改两处
- 缺少集中管理和复用能力
- 新开发者需要在代码中查找文档定义

## 设计目标

- 文档与代码适度分离，提高可维护性
- 自动从代码提取基础结构，减少重复书写
- 支持手动补充复杂描述和示例
- 按蓝图组织文档，职责清晰
- 保持与现有 Flasgger 集成的兼容性

## 整体架构

### 目录结构

```
project/
├── docs/
│   └── api/                          # API 文档目录
│       ├── stats.yaml                # 统计分析 API 文档
│       ├── projects.yaml             # 项目管理 API 文档
│       ├── scheduler.yaml            # 调度任务 API 文档
│       ├── git_ai.yaml               # Git-AI 用户界面 API 文档
│       ├── metrics.yaml              # Worker Metrics API 文档
│       ├── cas.yaml                  # Worker CAS API 文档
│       ├── oauth.yaml                # Worker OAuth API 文档
│       └── releases.yaml             # Worker Releases API 文档
├── scripts/
│   └── generate_docs.py             # 文档生成脚本
├── core/
│   └── swagger/                      # Swagger 模块
│       ├── __init__.py
│       ├── scanner.py                # 路由扫描器
│       ├── generator.py              # 文档生成器
│       └── loader.py                 # YAML 加载器
└── api/routes/                       # 路由实现（不变）
    ├── stats.py
    ├── projects.py
    └── ...
```

### 架构流程

1. `generate_docs.py` 扫描 Flask 应用的所有蓝图和路由
2. 通过反射提取路由的基础信息（路径、方法、参数）
3. 加载对应的 YAML 文件，提取人工补充的描述和示例
4. 合并生成最终的 Swagger 配置，注入到应用中

## 组件设计

### 1. 路由扫描器 (scanner.py)

**职责**：扫描 Flask 应用，提取路由信息

**接口**：
- `scan_routes(app)` - 扫描所有端点，返回路由元数据列表
- `extract_route_info(rule)` - 从 Flask 规则提取路径、方法、装饰器等信息

**提取内容**：
- 路径
- HTTP 方法
- 路由函数签名
- 参数名
- 默认值
- 函数 docstring（作为描述回退）

### 2. YAML 加载器 (loader.py)

**职责**：加载和解析蓝图对应的 YAML 文档文件

**接口**：
- `load_blueprint_doc(blueprint_name)` - 加载指定蓝图的文档
- `merge_with_route(route_info, doc_data)` - 合并路由信息和文档数据

**支持的数据结构**：
- 端点描述
- 参数说明
- 响应示例
- 错误码定义

### 3. 文档生成器 (generator.py)

**职责**：合并扫描结果和 YAML，生成 Swagger 配置

**接口**：
- `generate_swagger_spec(app, docs_base_path)` - 生成完整的 Swagger 规范
- `to_swagger_format(route_info, merged_doc)` - 转换为 Swagger 格式

**输出**：符合 Swagger 2.0 规范的配置字典

## YAML 文档结构

每蓝图的 YAML 文件格式：

```yaml
# docs/api/stats.yaml
tags:
  - name: stats
    description: 统计分析 API

endpoints:
  /analyze:
    POST:
      summary: 执行统计分析
      description: 根据指定的日期范围和部门，统计分析 AI 代码占比
      parameters:
        - name: start_date
          in: body
          required: true
          type: string
          format: date-time
          description: 开始日期（ISO 8601 格式）
          example: "2026-03-01T00:00:00Z"
        # ... 其他参数

  /latest:
    GET:
      summary: 获取最新统计结果
      description: 获取数据库中最新的统计记录
      responses:
        200:
          description: 获取成功
          schema:
            type: object
            properties:
              success: {type: boolean, example: true}
              data: {type: object, description: 统计记录详情}
```

只有描述、示例等非结构化部分需要手动填写，基础信息由扫描器自动提取。

## 数据流

### 文档生成流程

```
用户执行 python scripts/generate_docs.py
    ↓
scanner.py 扫描 app.py 中的所有蓝图
    ↓
提取每个端点：路径、方法、函数名、参数签名
    ↓
loader.py 读取 docs/api/*.yaml 按蓝图名匹配
    ↓
合并：路由基础信息 + YAML 描述/示例
    ↓
generator.py 构建 Swagger 配置字典
    ↓
生成的配置写入 swagger_config.json 或直接嵌入代码
    ↓
应用启动时 Flasgger 加载配置
```

### 应用启动流程

```
app.py 启动
    ↓
加载 swagger_config.json（或内置配置）
    ↓
创建 Swagger(app, template=loaded_config)
    ↓
访问 /swagger 查看 UI
```

## 错误处理

### 文档生成时的错误处理

- **YAML 文件不存在**：记录警告，使用扫描器提取的基础信息生成最小文档
- **YAML 格式错误**：抛出异常并显示具体行号，终止生成
- **路由与文档不匹配**：记录警告，跳过该端点但不影响其他端点
- **函数签名解析失败**：记录警告，使用基础文档并标记 `⚠️ 参数需文档说明`

### 应用启动时的错误处理

- **Swagger 配置缺失**：禁用 Swagger UI，记录警告
- **配置格式无效**：禁用 Swagger UI，记录错误详情
- **Flasgger 初始化失败**：捕获异常，应用继续运行但不提供文档

### 日志级别

- 不匹配/缺失：WARNING
- 格式错误/初始化失败：ERROR

## 测试策略

### 单元测试

- `test_scanner.py` - 测试路由扫描器能否正确提取路径、方法、参数
- `test_loader.py` - 测试 YAML 加载、解析、合并逻辑
- `test_generator.py` - 测试生成的 Swagger 配置是否符合规范

### 集成测试

- `test_generate_docs.py` - 测试完整生成流程，验证输出一致性
- `test_app_startup.py` - 测试应用启动时能否正确加载 Swagger 配置

### 文档验证

- 为关键端点编写测试，验证生成的文档与实际 API 一致性
- 使用断言检查 Swagger JSON 格式是否符合规范

## 配置说明

### config.yaml

```yaml
swagger:
  enabled: true
  title: "Git AI Code Metrics API"
  version: "2.0.0"
  description: "统计 GitLab/GitHub 仓库中 AI 生成代码的占比"
  docs_path: "docs/api"  # YAML 文档目录
  output_path: "swagger_config.json"  # 生成输出路径
```

## 迁移计划

1. 创建 `core/swagger` 模块和 `scripts/generate_docs.py`
2. 为每个蓝图创建对应的 YAML 文档文件
3. 从现有代码注释中提取文档内容到 YAML 文件
4. 运行生成脚本测试
5. 更新 `app.py` 集成新的生成流程
6. 验证 Swagger UI 正常工作

## 未来扩展

- 支持从数据模型自动生成 Schema 定义
- 添加文档版本管理
- 支持多语言文档
- 与前端类型生成工具集成
