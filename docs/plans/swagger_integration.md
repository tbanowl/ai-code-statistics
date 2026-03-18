# Flask Swagger 集成计划

## 任务概述
为 Flask 项目集成 Swagger (使用 flasgger)，为所有 API 端点提供交互式文档。

## 技术方案
- 使用 `flasgger` 库
- 访问路径: `/swagger`
- 文档范围: 所有 API (stats, projects, scheduler, git_ai, metrics, cas, oauth, releases)

## 实施步骤

### 1. 添加依赖
- 在 `requirements.txt` 添加 `flasgger`

### 2. 添加 Swagger 配置
- 在 `config.yaml` 中添加 swagger 配置节
- 支持开关控制（enabled, title, version, description）
- 支持是否在生产环境禁用

### 3. 初始化 Swagger
- 在 `app.py` 中配置 Swagger
- 注册 Swagger UI 路由
- 处理静态资源冲突问题

### 4. 为每个 API 蓝图添加文档注释

#### 4.1 stats_bp (`api/routes/stats.py`)
- `POST /api/stats/analyze` - 执行统计分析
- `GET /api/stats/latest` - 获取最新统计结果
- `GET /api/stats/history` - 获取统计历史记录
- `GET /api/stats/<stat_id>` - 获取指定统计详情

#### 4.2 projects_bp (`api/routes/projects.py`)
- 需要先查看文件内容以确定具体端点

#### 4.3 scheduler_bp (`api/routes/scheduler.py`)
- 需要先查看文件内容以确定具体端点

#### 4.4 git_ai_bp (`api/routes/git_ai.py`)
- 需要先查看文件内容以确定具体端点

#### 4.5 metrics_bp, cas_bp, oauth_bp, releases_bp (`api/routes/git_ai_worker.py`)
- `POST /worker/metrics/upload` - 上传 metrics 数据
- `POST /worker/cas/upload` - 上传 CAS 对象
- `GET /worker/cas/` - 读取 CAS 对象
- `POST /worker/oauth/device/code` - 获取设备授权码
- `POST /worker/oauth/token` - 交换令牌
- `GET /worker/releases/` - 获取发布信息

### 5. 创建公共 Schema 定义
- 统一响应格式: `SuccessResponse`, `ErrorResponse`, `DataResponse`
- 定义常用参数类型

### 6. 验证测试
- 启动应用，访问 `/swagger` 确认 UI 正常加载
- 测试每个端点的文档是否正确显示
- 验证 "Try it out" 功能是否可用

## 关键文件修改

### 新建文件
- `core/config/swagger.py` - Swagger 配置相关工具函数（可选）

### 修改文件
1. `requirements.txt` - 添加 `flasgger`
2. `config.yaml` - 添加 swagger 配置
3. `app.py` - 初始化 Swagger
4. `api/routes/stats.py` - 添加 swagger 注释
5. `api/routes/projects.py` - 添加 swagger 注释
6. `api/routes/scheduler.py` - 添加 swagger 注释
7. `api/routes/git_ai.py` - 添加 swagger 注释
8. `api/routes/git_ai_worker.py` - 添加 swagger 注释

## 风险与注意事项

1. **静态资源冲突** - `/swagger` 路径可能被前端路由捕获
   - 解决方案: 确保在 Flask 路由中优先处理 `/swagger`

2. **性能影响** - 生产环境可能不需要暴露 API 文档
   - 解决方案: 通过配置开关控制

3. **安全问题** - Swagger 可能暴露敏感信息
   - 解决方案: 生产环境关闭或增加认证

4. **文档维护** - 需要保持代码与文档同步
   - 解决方案: 将文档注释内联在代码中

## 验收标准
- [ ] 访问 `/swagger` 能看到 Swagger UI
- [ ] 所有 API 端点都有文档说明
- [ ] 每个 API 都有正确的请求/响应 schema
- [ ] "Try it out" 功能正常工作
- [ ] 通过配置可以开启/关闭 Swagger
