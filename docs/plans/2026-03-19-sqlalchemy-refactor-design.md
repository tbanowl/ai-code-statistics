# SQLAlchemy 数据库重构设计

**日期**: 2026-03-19
**版本**: 1.0
**状态**: 待实现

## 概述

本文档描述使用 SQLAlchemy 2.0 现代 ORM 重构 `core/database/` 模块的设计方案。

### 重构目标

- 简化数据访问代码，减少原生 SQL
- 使用 SQLAlchemy 统一支持多种数据库（SQLite、PostgreSQL、MySQL）
- 利用 ORM 的查询能力提升开发效率
- 完全替换现有的 dataclass 模型为 SQLAlchemy 模型
- 解耦 Metrics 原始数据操作和维度统计操作

### 设计原则

- **简洁**: 最小化目录结构，避免过度抽象
- **统一**: 不区分 SQLite/PostgreSQL 实现，由 SQLAlchemy 方言自动处理
- **解耦**: Metrics 原始数据和维度统计职责分离
- **现代**: 使用 SQLAlchemy 2.0 新特性（MappedColumn、类型注解）

---

## 架构设计

### 目录结构

```
core/database/
├── __init__.py        # 模块导出
├── base.py            # 引擎、Session、模型基类
├── models.py          # 所有 ORM 模型
├── base_db.py         # 基础数据库类（共享引擎和初始化）
├── metrics_db.py      # Metrics 原始数据操作
└── dimensions_db.py   # 维度统计操作
```

### 职责划分

| 模块 | 职责 |
|------|------|
| `base.py` | SQLAlchemy 引擎工厂、Session 上下文管理器、DeclarativeBase |
| `models.py` | 所有数据表的 ORM 模型定义 |
| `base_db.py` | 共享的引擎初始化、表结构创建 |
| `metrics_db.py` | Metrics 事件表、CAS 对象表的操作 |
| `dimensions_db.py` | 汇总统计表、维度主表的操作 |

---

## 模块设计

### 1. base.py - 基础设施

```python
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from contextlib import contextmanager

class Base(DeclarativeBase):
    """SQLAlchemy 模型基类"""
    pass

@contextmanager
def session_scope(engine: Engine):
    """Session 上下文管理器，自动处理提交和回滚"""
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### 2. models.py - ORM 模型

使用 SQLAlchemy 2.0 新特性：

```python
from sqlalchemy import String, BigInteger, Integer, Text, ForeignKey, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class BaseModel(Base):
    """模型基类，提供通用字段"""
    __abstract__ = True

    def to_dict(self) -> dict:
        """转换为字典"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

def now_ts() -> int:
    """返回当前时间戳（毫秒）"""
    return int(time.time() * 1000)

# 示例：Metrics 事件表
class MetricsEventsCommitted(BaseModel):
    __tablename__ = 'metrics_events_committed'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    raw_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('metrics_events_raw.id', ondelete='CASCADE'))
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    repo_url: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    ai_additions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # ... 更多字段
```

**模型列表**：

- `MetricsEventsRaw` - 原始事件表
- `MetricsEventsCommitted` - Committed 事件表
- `MetricsEventsCheckpoint` - Checkpoint 事件表
- `MetricsEventsAgentUsage` - AgentUsage 事件表
- `MetricsEventsInstallHooks` - InstallHooks 事件表
- `CasObjects` - CAS 对象表
- `MetricsDailyStats` - 按天统计
- `MetricsWeeklyStats` - 按周统计
- `MetricsMonthlyStats` - 按月统计
- `MetricsRepoStats` - 按仓库统计
- `MetricsContributorStats` - 按贡献者统计（多粒度）
- `MetricsRepo` - 仓库维度主表
- `MetricsContributor` - 作者维度主表
- `MetricsRepoContributor` - 仓库作者关联表

### 3. base_db.py - 基础数据库类

```python
from sqlalchemy import create_engine, Engine
from typing import Dict
from .base import Base as ModelBase

class BaseDatabase:
    """数据库基础类，提供引擎和初始化能力"""

    def __init__(self, config: Dict):
        self.config = config
        self.url = config.get('url', 'sqlite:///data/ai_stats.db')
        self.echo = config.get('echo', False)
        self._engine = None

    @property
    def engine(self) -> Engine:
        """延迟初始化引擎"""
        if self._engine is None:
            self._engine = create_engine(self.url, echo=self.echo, pool_pre_ping=True)
        return self._engine

    def init_db(self) -> None:
        """初始化数据库表结构"""
        ModelBase.metadata.create_all(self.engine)

    def close(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            self._engine.dispose()
```

### 4. metrics_db.py - Metrics 原始数据操作

```python
from .base_db import BaseDatabase, session_scope
from .models import MetricsEventsRaw, MetricsEventsCommitted, CasObjects, ...

class MetricsDatabase(BaseDatabase):
    """Metrics 原始数据操作类"""

    def save_metrics_raw(self, batch_id: str, version: int, event_count: int,
                        payload_json: str, received_at: int) -> int:
        """保存原始 metrics batch"""

    def save_committed_event(self, event: Dict) -> int:
        """保存 Committed 事件"""

    def get_committed_events_in_range(self, start: datetime, end: datetime) -> List[Dict]:
        """获取时间范围内的 Committed 事件"""

    def get_committed_events_by_repo(self, repo_url: str) -> List[Dict]:
        """按仓库查询 Committed 事件"""

    # ... 更多方法
```

### 5. dimensions_db.py - 维度统计操作

```python
from .base_db import BaseDatabase, session_scope
from .models import MetricsRepo, MetricsContributor, StatsTables, ...

class DimensionsDatabase(BaseDatabase):
    """维度统计操作类"""

    def save_metrics_repo(self, repo_data: Dict) -> int:
        """保存仓库维度记录"""

    def get_metrics_repo(self, repo_id: str) -> Optional[Dict]:
        """获取仓库维度记录"""

    def save_metrics_daily_stat(self, stat: Dict) -> int:
        """保存按天统计"""

    def get_metrics_repos(self, page: int, page_size: int, sort: str) -> Dict:
        """获取仓库维度列表，支持分页和排序"""

    # ... 更多方法
```

---

## 配置

### config.yaml

```yaml
database:
  url: sqlite:///data/ai_stats.db
  echo: false
```

### PostgreSQL 示例

```yaml
database:
  url: postgresql://username:password@localhost:5432/dbname
  echo: false
```

### MySQL 示例

```yaml
database:
  url: mysql://username:password@localhost:3306/dbname
  echo: false
```

---

## 使用示例

### 初始化数据库

```python
from core.database.metrics_db import MetricsDatabase
from core.database.dimensions_db import DimensionsDatabase

db_config = {'url': 'sqlite:///data/ai_stats.db'}

# 只需要初始化一次，MetricsDatabase 和 DimensionsDatabase 共享引擎
metrics_db = MetricsDatabase(db_config)
metrics_db.init_db()

dimensions_db = DimensionsDatabase(db_config)
# 不需要再次 init_db
```

### 保存和查询数据

```python
# 保存 Metrics 原始数据
raw_id = metrics_db.save_metrics_raw('batch-001', 1, 10, '{...}', 1710844800000)
metrics_db.save_committed_event({'raw_id': raw_id, 'timestamp': 1710844900000, 'repo_url': '...', 'author': '...'})

# 保存维度数据
dimensions_db.save_metrics_repo({'repo_id': 'owner/repo', 'repo_name': 'repo', 'repo_url': '...'})
dimensions_db.save_metrics_daily_stat({'date': '2024-03-19', 'total_lines': 1000, 'ai_lines': 500})

# 查询数据
events = metrics_db.get_committed_events_in_range(start, end)
repos = dimensions_db.get_metrics_repos(page=1, page_size=20, sort='ai_percentage')
```

---

## 数据迁移策略

本重构**不处理现有数据迁移**，假设：

1. 数据库可以重新初始化
2. 或现有数据可以接受丢失

如需数据迁移，需另行开发迁移脚本。

---

## 依赖更新

需要在 `requirements.txt` 中添加：

```
sqlalchemy>=2.0.0
```

可选的数据库驱动：

```
pysqlite3-binary  # Windows 上更好的 SQLite 支持（可选）
asyncpg           # PostgreSQL（如需异步）
aiomysql          # MySQL（如需异步）
```

---

## 影响范围

需要修改的文件：

1. `core/database/` - 完全重写
2. `core/models/metrics.py` - 删除，替换为 `core/database/models.py`
3. `core/models/stats.py` - 删除，相关逻辑移入 `core/database/models.py`
4. `core/services/metrics_service.py` - 更新为使用新的 Database 类
5. `core/services/cas_service.py` - 更新为使用新的 Database 类
6. `core/services/metrics_aggregation_service.py` - 更新为使用新的 Database 类
7. `api/routes/metrics.py` - 更新为使用新的 Database 类
8. `api/routes/stats.py` - 更新为使用新的 Database 类
9. `api/routes/dimensions.py` - 更新为使用新的 Database 类
10. `tests/` - 更新所有相关测试
11. `requirements.txt` - 添加 SQLAlchemy 依赖

---

## 下一步

设计已确认，下一步调用 `writing-plans` 技能创建详细的实现计划。
