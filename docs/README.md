# 文档

## 设计文档

- [架构设计文档](plans/2026-03-11-architecture-design.md)
- [实现计划](plans/2026-03-11-refactor-implementation.md)

## API 文档

### 统计分析 API

- `POST /api/v1/stats/analyze` - 执行统计分析
- `GET /api/v1/stats/latest` - 获取最新统计结果
- `GET /api/v1/stats/history` - 获取统计历史记录
- `GET /api/v1/stats/{stat_id}` - 获取指定统计详情

### 项目管理 API

- `GET /api/v1/projects/` - 获取项目列表
- `GET /api/v1/projects/departments` - 获取部门列表

### 调度管理 API

- `GET /api/v1/scheduler/jobs` - 获取所有任务
- `GET /api/v1/scheduler/jobs/{job_id}` - 获取任务状态
