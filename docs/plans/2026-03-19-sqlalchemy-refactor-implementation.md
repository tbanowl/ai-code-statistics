# SQLAlchemy 数据库重构 - 实现计划

**设计文档**: [2026-03-19-sqlalchemy-refactor-design.md](./2026-03-19-sqlalchemy-refactor-design.md)
**日期**: 2026-03-19
**版本**: 1.0

---

## 阶段 1: 基础设施搭建

### 1.1 创建新目录结构和基础文件

创建 `core/database/` 的新文件：

- [ ] `core/database/base.py` - SQLAlchemy 引擎、Session、DeclarativeBase
- [ ] `core/database/base_db.py` - BaseDatabase 基础类
- [ ] `core/database/models.py` - 所有 ORM 模型
- [ ] `core/database/metrics_db.py` - MetricsDatabase 类
- [ ] `core/database/dimensions_db.py` - DimensionsDatabase 类

### 1.2 实现模块导出

- [ ] 更新 `core/database/__init__.py` 导出新类

---

## 阶段 2: ORM 模型实现

### 2.1 基础模型

- [ ] 实现 `BaseModel` 基类（`to_dict()` 方法、`now_ts()` 辅助函数）

### 2.2 Metrics 事件表模型

- [ ] `MetricsEventsRaw`
- [ ] `MetricsEventsCommitted`
- [ ] `MetricsEventsCheckpoint`
- [ ] `MetricsEventsAgentUsage`
- [ ] `MetricsEventsInstallHooks`

### 2.3 CAS 对象表模型

- [ ] `CasObjects`

### 2.4 汇总统计表模型

- [ ] `MetricsDailyStats`
- [ ] `MetricsWeeklyStats`
- [ ] `MetricsMonthlyStats`
- [ ] `MetricsRepoStats`
- [ ] `MetricsContributorStats`

### 2.5 维度主表模型

- [ ] `MetricsRepo`
- [ ] `MetricsContributor`
- [ ] `MetricsRepoContributor`

---

## 阶段 3: 数据库操作类实现

### 3.1 BaseDatabase 基类

- [ ] 实现 `__init__()` - 配置解析
- [ ] 实现 `engine` 属性 - 延迟初始化引擎
- [ ] 实现 `init_db()` - 创建所有表结构
- [ ] 实现 `close()` - 关闭引擎

### 3.2 MetricsDatabase 类

#### 原始批次操作
- [ ] `save_metrics_raw()`
- [ ] `get_metrics_raw_by_batch_id()`

#### Committed 事件操作
- [ ] `save_committed_event()`
- [ ] `get_committed_events_in_range()`
- [ ] `get_committed_events_by_date_range()`
- [ ] `get_committed_events_by_repo()`
- [ ] `get_committed_events_by_author()`

#### 其他事件操作
- [ ] `save_checkpoint_event()`
- [ ] `get_checkpoint_events_in_range()`
- [ ] `save_agent_usage_event()`
- [ ] `save_install_hooks_event()`

#### CAS 操作
- [ ] `save_cas_object()`
- [ ] `get_cas_object()`

#### 辅助查询
- [ ] `get_all_repo_urls()`
- [ ] `get_all_authors()`

### 3.3 DimensionsDatabase 类

#### 汇总统计表操作
- [ ] `save_metrics_daily_stat()`
- [ ] `get_metrics_daily_stat()`
- [ ] `get_latest_daily_stat()`
- [ ] `save_metrics_weekly_stat()`
- [ ] `get_latest_weekly_stat()`
- [ ] `save_metrics_monthly_stat()`
- [ ] `get_latest_monthly_stat()`
- [ ] `save_metrics_repo_stat()`
- [ ] `save_metrics_contributor_stat()`
- [ ] `get_latest_metrics_stat()`

#### 维度主表操作
- [ ] `save_metrics_repo()`
- [ ] `get_metrics_repo()`
- [ ] `get_metrics_repos()` - 支持分页和排序
- [ ] `save_metrics_contributor()`
- [ ] `get_metrics_contributor()`
- [ ] `get_metrics_contributors()` - 支持分页和排序
- [ ] `save_metrics_repo_contributor()`
- [ ] `get_metrics_repo_contributors()` - 支持筛选

---

## 阶段 4: 更新服务层

### 4.1 MetricsService

- [ ] 更新 `core/services/metrics_service.py` 使用新的 `MetricsDatabase`
- [ ] 替换所有 `dataclass_json` 模型导入为 SQLAlchemy 模型

### 4.2 CasService

- [ ] 更新 `core/services/cas_service.py` 使用新的 `MetricsDatabase`

### 4.3 MetricsAggregationService

- [ ] 更新 `core/services/metrics_aggregation_service.py` 使用新的 `DimensionsDatabase`

---

## 阶段 5: 更新 API 路由

### 5.1 Metrics API

- [ ] 更新 `api/routes/metrics.py` 使用新的 `MetricsDatabase`

### 5.2 Stats API

- [ ] 更新 `api/routes/stats.py` 使用新的 `DimensionsDatabase`

### 5.3 Dimensions API

- [ ] 更新 `api/routes/dimensions.py` 使用新的 `DimensionsDatabase`

---

## 阶段 6: 清理旧代码

### 6.1 删除旧文件

- [ ] 删除 `core/database/base.py`（旧版）
- [ ] 删除 `core/database/factory.py`（旧版）
- [ ] 删除 `core/database/sqlite.py`（旧版）
- [ ] 删除 `core/models/metrics.py`（dataclass 模型）
- [ ] 删除 `core/models/stats.py`（如存在）

### 6.2 清理 schema SQL 文件

- [ ] 标记 `sql/metrics_schema_sqlite.sql` 为已废弃
- [ ] 标记 `sql/metrics_schema_postgresql.sql` 为已废弃
- [ ] 或保留用于参考

---

## 阶段 7: 依赖和配置

### 7.1 依赖更新

- [ ] 更新 `requirements.txt`
  - 添加 `sqlalchemy>=2.0.0`
  - 评估是否添加 `pysqlite3-binary`

### 7.2 配置示例

- [ ] 更新 `config.yaml` 配置示例
- [ ] 更新 `.env.example`（如适用）

---

## 阶段 8: 测试更新

### 8.1 数据库测试

- [ ] 更新 `tests/unit/test_database/test_db_base.py`
- [ ] 更新 `tests/unit/test_database/test_sqlite.py`
- [ ] 创建 `tests/unit/test_database/test_metrics_db.py`
- [ ] 创建 `tests/unit/test_database/test_dimensions_db.py`

### 8.2 服务层测试

- [ ] 更新 `tests/unit/test_services/test_cas_service.py`
- [ ] 更新 `tests/unit/test_services/test_metrics_aggregation_service.py`

### 8.3 集成测试

- [ ] 更新 `tests/integration/test_dimensions_db.py`
- [ ] 更新 `tests/integration/test_dimensions_api.py`

---

## 阶段 9: 文档更新

- [ ] 更新 `CLAUDE.md` 中的数据库相关文档
- [ ] 更新 README（如适用）

---

## 执行顺序建议

1. 先完成 **阶段 1-3**（基础设施、模型、操作类）
2. 在本地测试新代码功能
3. 完成 **阶段 4-5**（服务层、API 更新）
4. 运行现有测试并修复问题
5. 完成 **阶段 6**（删除旧代码）
6. 完成 **阶段 7-9**（依赖、测试、文档）

---

## 注意事项

1. **数据不迁移**: 本实现计划假设数据库可重新初始化或数据可接受丢失
2. **向后兼容**: API 接口保持不变，仅内部实现更改
3. **测试覆盖**: 每个阶段完成后运行对应测试确保功能正常
