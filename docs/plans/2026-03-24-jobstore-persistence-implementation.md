# JobStore 持久化实施计划

## 概述

基于设计文档 `2026-03-24-jobstore-persistence-design.md` 实现基于 APScheduler SQLAlchemyJobStore 的任务持久化功能。

## 前置条件

- APScheduler 3.11.2 已安装
- SQLAlchemy 已配置并正常工作
- 现有数据库（SQLite/PostgreSQL）可访问

---

## 实施步骤

### 步骤 1: 修改调度器配置加载

**文件:** `core/config/__init__.py` 或相关配置模块

**任务:**
- 扩展配置加载器，支持 `scheduler.jobstore` 和 `scheduler.job_defaults` 配置项
- 添加配置验证

**预期变更:**
```yaml
scheduler:
  jobstore:
    type: sqlalchemy
    tablename: apscheduler_jobs  # 可选
  job_defaults:
    coalesce: true
    max_instances: 1
    misfire_grace_time: 300
```

---

### 步骤 2: 修改 AICodeScheduler 初始化

**文件:** `core/scheduler/scheduler.py`

**任务:**
- 导入 `SQLAlchemyJobStore` 和 `apscheduler.jobstores.sqlalchemy`
- 添加 `_get_engine_from_db` 方法获取现有 engine
- 修改 `__init__` 方法配置 `jobstores` 和 `job_defaults`
- 添加 JobStore 连接失败的降级逻辑

**代码改动:**
```python
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

class AICodeScheduler:
    def __init__(self, config: Dict):
        # 配置 JobStore
        engine = self._get_engine_from_db()
        jobstores = None
        try:
            jobstores = {
                'default': SQLAlchemyJobStore(engine=engine)
            }
        except Exception as e:
            self.logger.warning(f"JobStore 初始化失败，使用内存模式: {e}")

        # 配置默认任务行为
        job_defaults = config.get('scheduler', {}).get('job_defaults', {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300
        })

        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            job_defaults=job_defaults,
            timezone=config.get('scheduler', {}).get('timezone', 'Asia/Shanghai')
        )
```

---

### 步骤 3: 添加 engine 获取方法

**文件:** `core/scheduler/scheduler.py`

**任务:**
- 实现 `_get_engine_from_db` 方法
- 从 SchedulerDatabase 或其他 Database 实例获取 SQLAlchemy engine

**代码改动:**
```python
def _get_engine_from_db(self):
    """从现有 Database 实例获取 SQLAlchemy engine"""
    if hasattr(self, 'scheduler_db') and self.scheduler_db:
        return self.scheduler_db.engine
    # 备用：创建新的 engine
    from core.database import create_database
    db = create_database(self.config.get('database', {}))
    return db.engine
```

---

### 步骤 4: 创建 SQL 脚本

**文件:** `sql/apscheduler_schema_sqlite.sql`

**内容:**
```sql
-- APScheduler JobStore 表结构 - SQLite

CREATE TABLE IF NOT EXISTS apscheduler_jobs (
    id VARCHAR(191) NOT NULL,
    next_run_time REAL,
    job_state BLOB NOT NULL,
    PRIMARY KEY (id)
);
```

**文件:** `sql/apscheduler_schema_postgresql.sql`

**内容:**
```sql
-- APScheduler JobStore 表结构 - PostgreSQL

CREATE TABLE IF NOT EXISTS apscheduler_jobs (
    id VARCHAR(191) NOT NULL,
    next_run_time TIMESTAMP WITH TIME ZONE,
    job_state BYTEA NOT NULL,
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_apscheduler_jobs_next_run_time
ON apscheduler_jobs (next_run_time);
```

---

### 步骤 5: 更新 config.yaml 示例

**文件:** `config.yaml` 和 `.env.example`

**任务:**
- 添加 `scheduler.jobstore` 和 `scheduler.job_defaults` 配置项
- 添加注释说明每个配置的作用

---

### 步骤 6: 更新 CLAUDE.md 文档

**文件:** `CLAUDE.md`

**任务:**
- 在调度器部分添加 JobStore 相关说明
- 更新配置说明 section

---

### 步骤 7: 编写单元测试

**文件:** `tests/test_scheduler_jobstore.py` (新建)

**测试用例:**
1. `test_jobstore_initialization` - JobStore 初始化成功
2. `test_jobstore_with_existing_engine` - 使用现有 engine
3. `test_jobstore_fallback_to_memory` - JobStore 失败时降级
4. `test_job_defaults_configuration` - job_defaults 配置生效
5. `test_task_registration_with_jobstore` - 任务注册后持久化
6. `test_task_recovery_on_restart` - 重启后任务恢复

---

### 步骤 8: 编写集成测试

**文件:** `tests/integration/test_scheduler_persistence.py` (新建)

**测试用例:**
1. `test_persistence_full_cycle` - 完整的生命周期测试
2. `test_next_run_time_persistence` - 保存和恢复 next_run_time
3. `test_task_state_serialization` - 任务状态序列化/反序列化
4. `test_manual_trigger_updates_next_run` - 手动触发后更新

---

### 步骤 9: 数据库迁移测试

**任务:**
- 测试 SQLite 环境下表创建和操作
- 测试 PostgreSQL 环境下表创建和操作
- 验证索引创建

---

### 步骤 10: 文档更新

**任务:**
- 更新 README.md 添加 JobStore 说明
- 更新相关 API 文档（如有）
- 添加部署注意事项

---

## 验收标准

### 功能验收
1. ✅ Scheduler 启动时成功创建 JobStore
2. ✅ 自动任务写入 `apscheduler_jobs` 表
3. ✅ 重启后任务自动恢复，调度状态正确
4. ✅ `task_executions` 表功能不受影响
5. ✅ 配置项 `job_defaults` 正确生效

### 性能验收
1. ✅ Scheduler 启动时间无明显增加
2. ✅ 任务调度延迟无显著变化

### 兼容性验收
1. ✅ SQLite 环境正常运行
2. ✅ PostgreSQL 环境正常运行
3. ✅ 向后兼容现有数据和功能

---

## 风险和缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| JobStore 初始化失败 | 持久化功能不可用 | 降级到内存模式，记录日志 |
| 数据库表结构变更 | 数据迁移问题 | 提供手动 DDL 脚本 |
| 任务注册冲突 | 代码变更不生效 | 配置决定覆盖或跳过逻辑 |

---

## 实施时间估计

| 步骤 | 工作量 |
|------|--------|
| 步骤 1-2: 调度器改造 | 2小时 |
| 步骤 3: engine 获取 | 1小时 |
| 步骤 4: SQL 脚本 | 0.5小时 |
| 步骤 5-6: 配置和文档 | 1小时 |
| 步骤 7-9: 测试 | 3小时 |
| 步骤 10: 文档更新 | 0.5小时 |
| 总计 | 约 8 小时 |

---

## 依赖项

- 无外部依赖
- 需要测试数据库环境（SQLite/PostgreSQL）

---

## 后续优化

1. 添加 JobStore 健康检查
2. 支持 Redis JobStore（如需多进程协调）
3. 添加任务执行历史与 JobStore 的关联查询
