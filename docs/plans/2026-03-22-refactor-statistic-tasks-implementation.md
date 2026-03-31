# 重构定时统计任务 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完全重构统计系统，使用 XID 主键 + 毫秒时间戳。创建新的 `stats_` 前缀统计表，修改原始事件表和 CAS 表为 XID，删除所有旧统计代码，实现新的聚合任务和 v2 API，构建 ECharts 前端 Dashboard。

**Architecture:** 
- 所有表（包括原始事件表）使用 XID 主键 + 毫秒时间戳
- 新统计表：`stats_repositories`, `stats_contributors`, `stats_repo_contributors`, `stats_daily_stats`
- 单一聚合任务 `DailyAggregationTask` 替代 8 个旧任务
- 新 v2 API：仓库/贡献者分页、统计查询（图表+明细表格）、手动触发
- Vue 3 + ECharts 前端 Dashboard

**Tech Stack:** Python 3 / Flask / SQLAlchemy 2.0 / APScheduler / xid-python / Vue 3 / ECharts / vue-echarts / Tailwind CSS

---

## Task 1: Add xid-python dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Install xid-python**

```bash
pip install xid-python
```

**Step 2: Verify installation**

```bash
python -c "import xid; print('XID example:', xid.Xid().string())"
```

Expected: `XID example: cq1234567890abcdef01` (20-character string)

**Step 3: Add to requirements.txt**

Append `xid-python` to `requirements.txt`.

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add xid-python dependency for XID primary keys"
```

---

## Task 2: Update existing models to use XID (原始事件表和 CAS 表)

**Files:**
- Modify: `core/database/models.py` (update 7 existing model classes)

**Step 1: Add XID generator function at top of models.py**

After the imports and before `ModelBase`, add:

```python
import xid

def gen_xid() -> str:
    """生成 XID 字符串"""
    return xid.Xid().string()
```

**Step 2: Update MetricsEventsRaw model**

Change:
```python
id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
```

To:
```python
id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
```

**Step 3: Update MetricsEventsCommitted model**

Change:
```python
id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
raw_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('metrics_events_raw.id', ondelete='CASCADE'))
```

To:
```python
id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
raw_id: Mapped[str] = mapped_column(String(20), ForeignKey('metrics_events_raw.id', ondelete='CASCADE'))
```

**Step 4: Update MetricsEventsCheckpoint model**

Same changes as Step 3 (id → String(20), raw_id → String(20)).

**Step 5: Update MetricsEventsAgentUsage model**

Same changes as Step 3.

**Step 6: Update MetricsEventsInstallHooks model**

Same changes as Step 3.

**Step 7: Update CasObjects model**

Change:
```python
id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
```

To:
```python
id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
```

**Step 8: Update TaskExecution model**

Same change as Step 7.

**Step 9: Verify models load**

```bash
python -c "from core.database.models import MetricsEventsRaw, CasObjects, TaskExecution; print('Models loaded successfully')"
```

**Step 10: Commit**

```bash
git add core/database/models.py
git commit -m "refactor: change metrics/CAS tables to use XID primary keys"
```

---

## Task 3: Fix MetricsService timestamp precision (秒 → 毫秒)

**Files:**
- Modify: `core/services/metrics_service.py`

**Step 1: Fix received_at timestamp (line 27)**

Change:
```python
received_at = int(datetime.now().timestamp())
```

To:
```python
received_at = int(datetime.now().timestamp() * 1000)
```

**Step 2: Fix created_at timestamp (line 61)**

Change:
```python
now = int(datetime.now().timestamp())
```

To:
```python
now = int(datetime.now().timestamp() * 1000)
```

**Step 3: Verify service loads**

```bash
python -c "from core.services.metrics_service import MetricsService; print('MetricsService loaded')"
```

**Step 4: Commit**

```bash
git add core/services/metrics_service.py
git commit -m "fix: use millisecond timestamps in MetricsService"
```

---

## Task 4: Create new stats models (stats_ 前缀表)

**Files:**
- Modify: `core/database/models.py` (append 4 new model classes)

**Step 1: Add UniqueConstraint to imports**

At the top of `models.py`, update the import:

```python
from sqlalchemy import (
    String, BigInteger, Integer, Text, ForeignKey,
    Numeric, JSON, UniqueConstraint
)
```

**Step 2: Append new models after TaskExecution class**

```python
# ============================================================================
# 新统计表（v2 — stats_ 前缀）
# ============================================================================

class StatsRepository(ModelBase):
    """仓库表（v2）"""
    __tablename__ = 'stats_repositories'

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts, onupdate=now_ts)


class StatsContributor(ModelBase):
    """贡献者表（v2）"""
    __tablename__ = 'stats_contributors'

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    contributor_uid: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts, onupdate=now_ts)


class StatsRepoContributor(ModelBase):
    """仓库贡献者关系表（v2）"""
    __tablename__ = 'stats_repo_contributors'

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    repo_id: Mapped[str] = mapped_column(String(20), nullable=False)
    contributor_id: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts, onupdate=now_ts)

    __table_args__ = (
        UniqueConstraint('repo_id', 'contributor_id', name='uq_stats_repo_contributor'),
    )


class StatsDailyStat(ModelBase):
    """每日统计表（v2）— 以 (天, 仓库, 贡献者) 为三维联合维度"""
    __tablename__ = 'stats_daily_stats'

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_xid)
    stat_date: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    repo_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=True)
    contributor_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    contributor_name: Mapped[str] = mapped_column(String(255), nullable=True)
    ai_generated_lines: Mapped[int] = mapped_column(Integer, default=0)
    ai_accepted_lines: Mapped[int] = mapped_column(Integer, default=0)
    human_lines: Mapped[int] = mapped_column(Integer, default=0)
    ai_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    git_ai_version: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts, onupdate=now_ts)

    __table_args__ = (
        UniqueConstraint('stat_date', 'repo_id', 'contributor_id', name='uq_stats_daily_stat'),
    )
```

**Step 3: Verify new models load**

```bash
python -c "from core.database.models import StatsRepository, StatsContributor, StatsRepoContributor, StatsDailyStat; print('New stats models loaded')"
```

**Step 4: Test table creation**

```bash
python -c "
from core.database.base_db import BaseDatabase
db = BaseDatabase()
db.init_db()
print('All tables created successfully')
"
```

**Step 5: Commit**

```bash
git add core/database/models.py
git commit -m "feat: add v2 stats models (stats_repositories, stats_contributors, stats_repo_contributors, stats_daily_stats)"
```

---

## Task 5: Delete old stats/dimensions models from models.py

**Files:**
- Modify: `core/database/models.py` (delete 8 old model classes)

**Step 1: Delete old model classes**

Remove these 8 classes from `models.py`:
- `MetricsDailyStats`
- `MetricsWeeklyStats`
- `MetricsMonthlyStats`
- `MetricsRepoStats`
- `MetricsContributorStats`
- `MetricsRepo`
- `MetricsContributor`
- `MetricsRepoContributor`

**Step 2: Verify models still load**

```bash
python -c "from core.database.models import StatsRepository; print('Models load after deletion')"
```

**Step 3: Commit**

```bash
git add core/database/models.py
git commit -m "refactor: delete old stats/dimensions models (MetricsDailyStats, MetricsWeeklyStats, etc.)"
```

---

## Task 6: Create StatsDatabase (new DB access layer for v2 tables)

**Files:**
- Create: `core/database/stats_db.py`
- Modify: `core/database/__init__.py`

**Step 1: Create `core/database/stats_db.py`**

(File content will be provided in next segment due to length)

**Step 2: Update `core/database/__init__.py`**

Add import and export:

```python
from .stats_db import StatsDatabase

__all__ = [
    'Base',
    'session_scope',
    'BaseDatabase',
    'MetricsDatabase',
    'SchedulerDatabase',
    'StatsDatabase',
]
```

Remove `DimensionsDatabase` from imports and `__all__`.

**Step 3: Verify import**

```bash
python -c "from core.database import StatsDatabase; print('StatsDatabase imported')"
```

**Step 4: Commit**

```bash
git add core/database/stats_db.py core/database/__init__.py
git commit -m "feat: add StatsDatabase for v2 stats tables access"
```

---

## Task 7: Delete old database access classes and services

**Files:**
- Delete: `core/database/dimensions_db.py`
- Delete: `core/services/metrics_aggregation_service.py`

**Step 1: Delete DimensionsDatabase**

```bash
rm core/database/dimensions_db.py
```

**Step 2: Delete MetricsAggregationService**

```bash
rm core/services/metrics_aggregation_service.py
```

**Step 3: Verify app still loads (will have import errors from old tasks, fixed in next task)**

```bash
python -c "from core.database import MetricsDatabase, SchedulerDatabase; print('Core DB classes still work')"
```

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: delete old DimensionsDatabase and MetricsAggregationService"
```

---

## Task 8: Delete old scheduler tasks

**Files:**
- Delete: `core/scheduler/tasks/daily_stats_task.py`
- Delete: `core/scheduler/tasks/weekly_stats_task.py`
- Delete: `core/scheduler/tasks/monthly_stats_task.py`
- Delete: `core/scheduler/tasks/repo_stats_task.py`
- Delete: `core/scheduler/tasks/contributor_stats_task.py`
- Delete: `core/scheduler/tasks/dimensions_task.py`

**Step 1: Delete all 6 old task files**

```bash
rm core/scheduler/tasks/daily_stats_task.py
rm core/scheduler/tasks/weekly_stats_task.py
rm core/scheduler/tasks/monthly_stats_task.py
rm core/scheduler/tasks/repo_stats_task.py
rm core/scheduler/tasks/contributor_stats_task.py
rm core/scheduler/tasks/dimensions_task.py
```

**Step 2: Commit**

```bash
git add -A
git commit -m "refactor: delete 6 old scheduler tasks (daily/weekly/monthly/repo/contributor/dimensions)"
```

---

## Task 9: Delete old API routes

**Files:**
- Delete: `api/routes/dimensions.py`
- Delete: `api/routes/stats.py`
- Modify: `app.py` (remove blueprint registrations)

**Step 1: Delete old route files**

```bash
rm api/routes/dimensions.py
rm api/routes/stats.py
```

**Step 2: Remove blueprint imports and registrations from app.py**

Remove these lines from `app.py`:
```python
from api.routes.stats import stats_bp
from api.routes.dimensions import dimensions_bp
# ...
app.register_blueprint(stats_bp)
app.register_blueprint(dimensions_bp)
```

**Step 3: Verify app starts**

```bash
python -c "from app import app; print('App loads without old routes')"
```

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: delete old API routes (stats, dimensions)"
```

---

## Task 10: Update config.yaml (remove old task configs)

**Files:**
- Modify: `config.yaml`

**Step 1: Update scheduler section**

Replace the entire `scheduler.jobs` section with:

```yaml
scheduler:
  enabled: true
  timezone: Asia/Shanghai
  jobs:
    daily_aggregation:
      cron: "0 2 * * *"
      enabled: true
```

Remove all old task configs (daily_stats, weekly_stats, monthly_stats, repo_stats, contributor_stats, dimensions_update).

**Step 2: Verify config loads**

```bash
python -c "
from core.config.loader import load_config_by_path
config = load_config_by_path('config.yaml')
jobs = config.get('scheduler', {}).get('jobs', {})
print('daily_aggregation enabled:', jobs.get('daily_aggregation', {}).get('enabled'))
"
```

Expected: `daily_aggregation enabled: True`

**Step 3: Commit**

```bash
git add config.yaml
git commit -m "refactor: remove old task configs from config.yaml"
```

---

## Task 11: Create StatsDatabase implementation

**Files:**
- Create: `core/database/stats_db.py`

**Step 1: Create the file with repository methods**

Create `core/database/stats_db.py` with the following content (Part 1 - Repository methods):

```python
"""统计数据操作类（v2 — stats_ 前缀表）"""
import json
from typing import Dict, List, Optional
from sqlalchemy import and_, func, or_
from datetime import datetime, timedelta

from .base_db import BaseDatabase
from .base import session_scope
from .models import (
    StatsRepository, StatsContributor, StatsRepoContributor, StatsDailyStat,
    MetricsEventsCommitted, MetricsEventsCheckpoint,
    gen_xid, now_ts,
)


class StatsDatabase(BaseDatabase):
    """统计数据操作类（v2）"""

    # ========== 仓库 ==========

    def get_or_create_repository(self, repo_url: str, repo_name: str) -> StatsRepository:
        """获取或创建仓库记录"""
        with session_scope(self.engine) as session:
            repo = session.query(StatsRepository).filter(
                StatsRepository.repo_url == repo_url
            ).first()
            if not repo:
                repo = StatsRepository(
                    id=gen_xid(),
                    repo_url=repo_url,
                    repo_name=repo_name,
                    created_at=now_ts(),
                    updated_at=now_ts(),
                )
                session.add(repo)
                session.flush()
            return repo

    def get_repositories(self, page: int = 1, page_size: int = 20,
                         keyword: Optional[str] = None) -> Dict:
        """获取仓库列表，支持分页和关键词搜索"""
        with session_scope(self.engine) as session:
            query = session.query(StatsRepository)
            if keyword:
                query = query.filter(StatsRepository.repo_name.like(f'%{keyword}%'))
            query = query.order_by(StatsRepository.created_at.desc())
            total = query.count()
            results = query.offset((page - 1) * page_size).limit(page_size).all()
            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'items': [r.to_dict() for r in results]
            }

    def get_repository_by_id(self, repo_id: str) -> Optional[Dict]:
        """按 ID 获取仓库"""
        with session_scope(self.engine) as session:
            repo = session.query(StatsRepository).filter(StatsRepository.id == repo_id).first()
            return repo.to_dict() if repo else None
```

**Step 2: Commit Part 1**

```bash
git add core/database/stats_db.py
git commit -m "feat: add StatsDatabase - repository methods"
```

---

## Task 12: Add contributor and relationship methods to StatsDatabase

**Files:**
- Modify: `core/database/stats_db.py` (append methods)

**Step 1: Append contributor methods**

```python
    # ========== 贡献者 ==========

    def get_or_create_contributor(self, name: str, contributor_uid: str, 
                                   email: Optional[str] = None) -> StatsContributor:
        """获取或创建贡献者记录"""
        with session_scope(self.engine) as session:
            contributor = session.query(StatsContributor).filter(
                StatsContributor.contributor_uid == contributor_uid
            ).first()
            if not contributor:
                contributor = StatsContributor(
                    id=gen_xid(),
                    name=name,
                    email=email,
                    contributor_uid=contributor_uid,
                    created_at=now_ts(),
                    updated_at=now_ts(),
                )
                session.add(contributor)
                session.flush()
            return contributor

    def get_contributors(self, page: int = 1, page_size: int = 20,
                         keyword: Optional[str] = None) -> Dict:
        """获取贡献者列表"""
        with session_scope(self.engine) as session:
            query = session.query(StatsContributor)
            if keyword:
                query = query.filter(or_(
                    StatsContributor.name.like(f'%{keyword}%'),
                    StatsContributor.email.like(f'%{keyword}%')
                ))
            query = query.order_by(StatsContributor.created_at.desc())
            total = query.count()
            results = query.offset((page - 1) * page_size).limit(page_size).all()
            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'items': [r.to_dict() for r in results]
            }

    def get_contributor_by_id(self, contributor_id: str) -> Optional[Dict]:
        """按 ID 获取贡献者"""
        with session_scope(self.engine) as session:
            c = session.query(StatsContributor).filter(StatsContributor.id == contributor_id).first()
            return c.to_dict() if c else None

    # ========== 仓库贡献者关系 ==========

    def get_or_create_repo_contributor(self, repo_id: str, contributor_id: str) -> StatsRepoContributor:
        """获取或创建仓库贡献者关系"""
        with session_scope(self.engine) as session:
            rc = session.query(StatsRepoContributor).filter(
                and_(
                    StatsRepoContributor.repo_id == repo_id,
                    StatsRepoContributor.contributor_id == contributor_id
                )
            ).first()
            if not rc:
                rc = StatsRepoContributor(
                    id=gen_xid(),
                    repo_id=repo_id,
                    contributor_id=contributor_id,
                    created_at=now_ts(),
                    updated_at=now_ts(),
                )
                session.add(rc)
                session.flush()
            return rc
```

**Step 2: Commit**

```bash
git add core/database/stats_db.py
git commit -m "feat: add StatsDatabase - contributor and relationship methods"
```

---

## Task 13: Add daily stats methods to StatsDatabase

**Files:**
- Modify: `core/database/stats_db.py` (append methods)

**Step 1: Append daily stats UPSERT method**

```python
    # ========== 每日统计 ==========

    def upsert_daily_stat(self, stat_date: int, repo_id: str, contributor_id: str,
                          repo_name: str, contributor_name: str,
                          ai_generated_lines: int, ai_accepted_lines: int,
                          human_lines: int, ai_percentage: float,
                          git_ai_version: Optional[str] = None) -> StatsDailyStat:
        """插入或更新每日统计记录（UPSERT 语义）"""
        with session_scope(self.engine) as session:
            # 查询是否存在
            existing = session.query(StatsDailyStat).filter(
                and_(
                    StatsDailyStat.stat_date == stat_date,
                    StatsDailyStat.repo_id == repo_id,
                    StatsDailyStat.contributor_id == contributor_id
                )
            ).first()

            ts = now_ts()
            if existing:
                # 存在则更新
                existing.repo_name = repo_name
                existing.contributor_name = contributor_name
                existing.ai_generated_lines = ai_generated_lines
                existing.ai_accepted_lines = ai_accepted_lines
                existing.human_lines = human_lines
                existing.ai_percentage = ai_percentage
                existing.git_ai_version = git_ai_version
                existing.updated_at = ts
                session.flush()
                return existing
            else:
                # 不存在则插入
                stat = StatsDailyStat(
                    id=gen_xid(),
                    stat_date=stat_date,
                    repo_id=repo_id,
                    repo_name=repo_name,
                    contributor_id=contributor_id,
                    contributor_name=contributor_name,
                    ai_generated_lines=ai_generated_lines,
                    ai_accepted_lines=ai_accepted_lines,
                    human_lines=human_lines,
                    ai_percentage=ai_percentage,
                    git_ai_version=git_ai_version,
                    created_at=ts,
                    updated_at=ts,
                )
                session.add(stat)
                session.flush()
                return stat
```

**Step 2: Append query methods**

```python
    def get_daily_stats_paginated(self, page: int = 1, page_size: int = 20,
                                   start_date: Optional[int] = None,
                                   end_date: Optional[int] = None,
                                   repo_id: Optional[str] = None,
                                   contributor_id: Optional[str] = None) -> Dict:
        """分页查询每日统计明细（用于表格）"""
        with session_scope(self.engine) as session:
            query = session.query(StatsDailyStat)
            
            if start_date:
                query = query.filter(StatsDailyStat.stat_date >= start_date)
            if end_date:
                query = query.filter(StatsDailyStat.stat_date <= end_date)
            if repo_id:
                query = query.filter(StatsDailyStat.repo_id == repo_id)
            if contributor_id:
                query = query.filter(StatsDailyStat.contributor_id == contributor_id)
            
            query = query.order_by(StatsDailyStat.stat_date.desc())
            total = query.count()
            results = query.offset((page - 1) * page_size).limit(page_size).all()
            
            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'items': [r.to_dict() for r in results]
            }

    def get_aggregated_stats(self, start_date: int, end_date: int,
                             repo_id: Optional[str] = None,
                             contributor_id: Optional[str] = None,
                             granularity: str = 'daily') -> List[Dict]:
        """查询聚合统计数据（用于图表），支持 daily/weekly/monthly 粒度"""
        with session_scope(self.engine) as session:
            query = session.query(
                StatsDailyStat.stat_date,
                func.sum(StatsDailyStat.ai_generated_lines).label('ai_generated_lines'),
                func.sum(StatsDailyStat.ai_accepted_lines).label('ai_accepted_lines'),
                func.sum(StatsDailyStat.human_lines).label('human_lines'),
            ).filter(
                and_(
                    StatsDailyStat.stat_date >= start_date,
                    StatsDailyStat.stat_date <= end_date
                )
            )

            if repo_id:
                query = query.filter(StatsDailyStat.repo_id == repo_id)
            if contributor_id:
                query = query.filter(StatsDailyStat.contributor_id == contributor_id)

            query = query.group_by(StatsDailyStat.stat_date).order_by(StatsDailyStat.stat_date.asc())
            results = query.all()

            items = []
            for row in results:
                total = (row.human_lines or 0) + (row.ai_accepted_lines or 0)
                pct = round((row.ai_accepted_lines or 0) / total * 100, 2) if total > 0 else 0
                items.append({
                    'stat_date': row.stat_date,
                    'ai_generated_lines': row.ai_generated_lines or 0,
                    'ai_accepted_lines': row.ai_accepted_lines or 0,
                    'human_lines': row.human_lines or 0,
                    'ai_percentage': pct,
                })

            # 对 weekly/monthly 做应用层分组
            if granularity in ('weekly', 'monthly'):
                items = self._group_by_granularity(items, granularity)

            return items

    def _group_by_granularity(self, items: List[Dict], granularity: str) -> List[Dict]:
        """将日级数据按周或月分组"""
        grouped = {}
        for item in items:
            dt = datetime.fromtimestamp(item['stat_date'] / 1000)
            if granularity == 'weekly':
                year, week, _ = dt.isocalendar()
                key = f"{year}-W{week:02d}"
                monday = dt - timedelta(days=dt.weekday())
                key_ts = int(monday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
            else:  # monthly
                key = f"{dt.year}-{dt.month:02d}"
                key_ts = int(dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)

            if key not in grouped:
                grouped[key] = {
                    'stat_date': key_ts,
                    'period': key,
                    'ai_generated_lines': 0,
                    'ai_accepted_lines': 0,
                    'human_lines': 0,
                }
            grouped[key]['ai_generated_lines'] += item['ai_generated_lines']
            grouped[key]['ai_accepted_lines'] += item['ai_accepted_lines']
            grouped[key]['human_lines'] += item['human_lines']

        result = []
        for item in grouped.values():
            total = item['human_lines'] + item['ai_accepted_lines']
            item['ai_percentage'] = round(item['ai_accepted_lines'] / total * 100, 2) if total > 0 else 0
            result.append(item)

        return sorted(result, key=lambda x: x['stat_date'])
```

**Step 3: Commit**

```bash
git add core/database/stats_db.py
git commit -m "feat: add StatsDatabase - daily stats UPSERT and query methods"
```

---

## Task 14: Add event query methods to StatsDatabase

**Files:**
- Modify: `core/database/stats_db.py` (append methods)

**Step 1: Append event query methods**

```python
    # ========== 事件查询（用于聚合任务） ==========

    def get_committed_events_grouped(self, start_ts: int, end_ts: int,
                                      repo_url: Optional[str] = None,
                                      author: Optional[str] = None) -> List[Dict]:
        """查询 committed 事件"""
        with session_scope(self.engine) as session:
            filters = [
                MetricsEventsCommitted.timestamp >= start_ts,
                MetricsEventsCommitted.timestamp < end_ts,
            ]
            if repo_url:
                filters.append(MetricsEventsCommitted.repo_url == repo_url)
            if author:
                filters.append(MetricsEventsCommitted.author == author)

            results = session.query(MetricsEventsCommitted).filter(and_(*filters)).all()
            return [r.to_dict() for r in results]

    def get_checkpoint_ai_agent_events(self, start_ts: int, end_ts: int,
                                        repo_url: Optional[str] = None,
                                        author: Optional[str] = None) -> List[Dict]:
        """查询 checkpoint 事件 (kind=ai_agent)"""
        with session_scope(self.engine) as session:
            filters = [
                MetricsEventsCheckpoint.timestamp >= start_ts,
                MetricsEventsCheckpoint.timestamp < end_ts,
                MetricsEventsCheckpoint.kind == 'ai_agent',
            ]
            if repo_url:
                filters.append(MetricsEventsCheckpoint.repo_url == repo_url)
            if author:
                filters.append(MetricsEventsCheckpoint.author == author)

            results = session.query(MetricsEventsCheckpoint).filter(and_(*filters)).all()
            return [r.to_dict() for r in results]
```

**Step 2: Verify StatsDatabase loads**

```bash
python -c "from core.database import StatsDatabase; db = StatsDatabase(); print('StatsDatabase complete')"
```

**Step 3: Commit**

```bash
git add core/database/stats_db.py
git commit -m "feat: add StatsDatabase - event query methods for aggregation"
```

---

## Task 15: Create DailyAggregationTask

**Files:**
- Create: `core/scheduler/tasks/daily_aggregation_task.py`

**Step 1: Create task file with helper functions**

```python
"""每日聚合任务（v2）— 替代旧的 8 个统计任务"""
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from core.scheduler.tasks.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.database.stats_db import StatsDatabase


def _extract_repo_name(repo_url: str) -> str:
    """从 URL 提取仓库名 (org/repo)"""
    if not repo_url:
        return ""
    url = repo_url.strip()
    if url.endswith('.git'):
        url = url[:-4]
    if url.startswith('git@'):
        parts = url.split(':')
        if len(parts) >= 2:
            return parts[-1]
    url = url.replace("https://", "").replace("http://", "")
    parts = url.split("/")
    if len(parts) >= 3:
        return "/".join(parts[1:])
    return repo_url


def _sum_ai_additions(ai_additions_json) -> int:
    """从 ai_additions JSON 字段计算 AI 代码行数"""
    if not ai_additions_json:
        return 0
    try:
        if isinstance(ai_additions_json, str):
            data = json.loads(ai_additions_json)
        else:
            data = ai_additions_json
        if isinstance(data, list):
            return sum(data)
        return 0
    except (json.JSONDecodeError, TypeError):
        return 0
```

**Step 2: Add task class**

```python
@scheduled(cron="0 2 * * *", job_id="daily_aggregation", name="每日聚合任务（v2）")
class DailyAggregationTask(BaseTask):
    """核心聚合任务，以 (天, 仓库, 贡献者) 为三维联合维度"""

    def execute(self, context: Optional[Dict] = None) -> Dict:
        self.logger.info("开始执行每日聚合任务（v2）")
        context = context or {}

        stats_db = StatsDatabase()

        # 确定日期范围
        start_date_ts = context.get('start_date')
        end_date_ts = context.get('end_date')
        repo_url_filter = context.get('repo_url')
        contributor_filter = context.get('contributor')

        if not start_date_ts or not end_date_ts:
            # 默认统计昨天
            yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            start_date_ts = int(yesterday.timestamp() * 1000)
            end_date_ts = int((yesterday + timedelta(days=1)).timestamp() * 1000) - 1

        self.logger.info(f"统计范围: {start_date_ts} ~ {end_date_ts}")

        # 遍历每一天
        current_ts = self._normalize_to_day_start(start_date_ts)
        end_day_ts = self._normalize_to_day_start(end_date_ts)

        success_count = 0
        failed_items = []

        while current_ts <= end_day_ts:
            next_day_ts = current_ts + 86400000
            try:
                count = self._aggregate_one_day(
                    stats_db, current_ts, next_day_ts,
                    repo_url_filter, contributor_filter
                )
                success_count += count
            except Exception as e:
                date_str = datetime.fromtimestamp(current_ts / 1000).strftime('%Y-%m-%d')
                self.logger.error(f"日期 {date_str} 聚合失败: {e}", exc_info=True)
                failed_items.append(date_str)

            current_ts = next_day_ts

        self.logger.info(f"每日聚合完成: 成功 {success_count} 条, 失败 {len(failed_items)} 天")

        return {
            "success": len(failed_items) == 0,
            "processed": success_count,
            "failed": len(failed_items),
            "details": {"failed_items": failed_items}
        }

    def _normalize_to_day_start(self, ts_ms: int) -> int:
        """将毫秒时间戳归一化到当天 00:00:00"""
        dt = datetime.fromtimestamp(ts_ms / 1000)
        day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(day_start.timestamp() * 1000)
```

**Step 3: Commit**

```bash
git add core/scheduler/tasks/daily_aggregation_task.py
git commit -m "feat: add DailyAggregationTask (part 1 - structure)"
```

---

## Task 16: Complete DailyAggregationTask aggregation logic

**Files:**
- Modify: `core/scheduler/tasks/daily_aggregation_task.py`

**Step 1: Add _aggregate_one_day method**

```python
    def _aggregate_one_day(self, stats_db: StatsDatabase,
                           day_start_ts: int, day_end_ts: int,
                           repo_url_filter: Optional[str],
                           contributor_filter: Optional[str]) -> int:
        """聚合单天数据，返回写入的记录数"""
        # 查询 committed 事件
        committed_events = stats_db.get_committed_events_grouped(
            day_start_ts, day_end_ts, repo_url_filter, contributor_filter
        )

        # 查询 checkpoint 事件 (kind=ai_agent)
        checkpoint_events = stats_db.get_checkpoint_ai_agent_events(
            day_start_ts, day_end_ts, repo_url_filter, contributor_filter
        )

        # 按 (repo_url, author) 分组聚合 committed
        committed_grouped = defaultdict(lambda: {
            'human_lines': 0, 'ai_accepted_lines': 0, 
            'git_ai_version': None, 'author_email': None
        })
        for event in committed_events:
            repo_url = event.get('repo_url') or 'unknown'
            author = event.get('author') or 'unknown'
            key = (repo_url, author)
            committed_grouped[key]['human_lines'] += event.get('human_additions') or 0
            committed_grouped[key]['ai_accepted_lines'] += _sum_ai_additions(event.get('ai_additions'))
            if event.get('git_ai_version'):
                committed_grouped[key]['git_ai_version'] = event['git_ai_version']
            # 提取 author_email（如果有）
            # 注意：当前 committed 事件表没有 author_email 字段，需要从其他地方获取或留空
            # 这里暂时留空，后续如果事件表有该字段可以添加

        # 按 (repo_url, author) 分组聚合 checkpoint
        checkpoint_grouped = defaultdict(lambda: {'ai_generated_lines': 0})
        for event in checkpoint_events:
            repo_url = event.get('repo_url') or 'unknown'
            author = event.get('author') or 'unknown'
            key = (repo_url, author)
            checkpoint_grouped[key]['ai_generated_lines'] += event.get('lines_added') or 0

        # 合并所有 keys
        all_keys = set(committed_grouped.keys()) | set(checkpoint_grouped.keys())

        count = 0
        for (repo_url, author) in all_keys:
            c_data = committed_grouped.get((repo_url, author), {})
            cp_data = checkpoint_grouped.get((repo_url, author), {})

            ai_generated = cp_data.get('ai_generated_lines', 0)
            ai_accepted = c_data.get('ai_accepted_lines', 0)
            human = c_data.get('human_lines', 0)
            total = human + ai_accepted
            ai_pct = round(ai_accepted / total * 100, 2) if total > 0 else 0.0

            # Upsert 维度表
            repo_name = _extract_repo_name(repo_url)
            repo = stats_db.get_or_create_repository(repo_url, repo_name)
            contributor = stats_db.get_or_create_contributor(
                name=author, 
                contributor_uid=author,
                email=c_data.get('author_email')
            )
            stats_db.get_or_create_repo_contributor(repo.id, contributor.id)

            # Upsert daily_stats
            stats_db.upsert_daily_stat(
                stat_date=day_start_ts,
                repo_id=repo.id,
                contributor_id=contributor.id,
                repo_name=repo_name,
                contributor_name=author,
                ai_generated_lines=ai_generated,
                ai_accepted_lines=ai_accepted,
                human_lines=human,
                ai_percentage=ai_pct,
                git_ai_version=c_data.get('git_ai_version'),
            )
            count += 1

        return count
```

**Step 2: Verify task loads**

```bash
python -c "from core.scheduler.tasks.daily_aggregation_task import DailyAggregationTask; print(DailyAggregationTask._schedule_meta)"
```

**Step 3: Commit**

```bash
git add core/scheduler/tasks/daily_aggregation_task.py
git commit -m "feat: complete DailyAggregationTask aggregation logic"
```

---

## Task 17: Create v2 API routes (Part 1 - repositories and contributors)

**Files:**
- Create: `api/routes/stats_v2.py`

**Step 1: Create file with repository and contributor endpoints**

```python
"""统计数据 v2 API 路由"""
import threading
from flask import Blueprint, request, jsonify
from core.database.stats_db import StatsDatabase
from core.config.loader import config_data
from core.config.logging import Logger
from core.scheduler.tasks.daily_aggregation_task import DailyAggregationTask
from core.database.scheduler_db import SchedulerDatabase

stats_v2_bp = Blueprint('stats_v2', __name__, url_prefix='/api/v2')

database = StatsDatabase()
scheduler_db = SchedulerDatabase()
logger = Logger.get_logger('api.stats_v2')


@stats_v2_bp.route('/repositories', methods=['GET'])
def get_repositories():
    """获取仓库列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        keyword = request.args.get('keyword')

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        result = database.get_repositories(page=page, page_size=page_size, keyword=keyword)

        return jsonify({
            'success': True,
            'data': result['items'],
            'pagination': {
                'total': result['total'],
                'page': result['page'],
                'page_size': result['page_size']
            }
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'获取仓库列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@stats_v2_bp.route('/contributors', methods=['GET'])
def get_contributors():
    """获取贡献者列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        keyword = request.args.get('keyword')

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        result = database.get_contributors(page=page, page_size=page_size, keyword=keyword)

        return jsonify({
            'success': True,
            'data': result['items'],
            'pagination': {
                'total': result['total'],
                'page': result['page'],
                'page_size': result['page_size']
            }
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'获取贡献者列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 2: Commit**

```bash
git add api/routes/stats_v2.py
git commit -m "feat: add v2 API - repositories and contributors endpoints"
```

---

## Task 18: Add stats query endpoints to v2 API

**Files:**
- Modify: `api/routes/stats_v2.py`

**Step 1: Append stats aggregation endpoint**

```python
@stats_v2_bp.route('/stats', methods=['GET'])
def get_stats():
    """查询统计数据（图表用）"""
    try:
        start_date = request.args.get('start_date', type=int)
        end_date = request.args.get('end_date', type=int)
        repo_id = request.args.get('repo_id')
        contributor_id = request.args.get('contributor_id')
        granularity = request.args.get('granularity', 'daily')

        if not start_date or not end_date:
            return jsonify({'success': False, 'error': 'start_date and end_date are required'}), 400

        if granularity not in ('daily', 'weekly', 'monthly'):
            return jsonify({'success': False, 'error': 'granularity must be daily, weekly, or monthly'}), 400

        items = database.get_aggregated_stats(
            start_date=start_date,
            end_date=end_date,
            repo_id=repo_id,
            contributor_id=contributor_id,
            granularity=granularity,
        )

        # 计算汇总
        total_generated = sum(i['ai_generated_lines'] for i in items)
        total_accepted = sum(i['ai_accepted_lines'] for i in items)
        total_human = sum(i['human_lines'] for i in items)
        total = total_human + total_accepted
        avg_pct = round(total_accepted / total * 100, 2) if total > 0 else 0

        return jsonify({
            'success': True,
            'data': {
                'items': items,
                'summary': {
                    'total_ai_generated': total_generated,
                    'total_ai_accepted': total_accepted,
                    'total_human': total_human,
                    'avg_ai_percentage': avg_pct,
                }
            }
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'查询统计数据失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 2: Append daily stats detail endpoint**

```python
@stats_v2_bp.route('/stats/daily', methods=['GET'])
def get_daily_stats():
    """查询每日统计明细（表格用）"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        start_date = request.args.get('start_date', type=int)
        end_date = request.args.get('end_date', type=int)
        repo_id = request.args.get('repo_id')
        contributor_id = request.args.get('contributor_id')

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        result = database.get_daily_stats_paginated(
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date,
            repo_id=repo_id,
            contributor_id=contributor_id,
        )

        return jsonify({
            'success': True,
            'data': result['items'],
            'pagination': {
                'total': result['total'],
                'page': result['page'],
                'page_size': result['page_size']
            }
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'查询每日统计明细失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 3: Commit**

```bash
git add api/routes/stats_v2.py
git commit -m "feat: add v2 API - stats query and daily detail endpoints"
```

---

## Task 19: Add manual trigger endpoint to v2 API

**Files:**
- Modify: `api/routes/stats_v2.py`

**Step 1: Append aggregate trigger endpoint**

```python
@stats_v2_bp.route('/stats/aggregate', methods=['POST'])
def trigger_aggregate():
    """手动触发聚合任务"""
    try:
        data = request.get_json(silent=True) or {}

        context = {}
        if data.get('start_date'):
            context['start_date'] = int(data['start_date'])
        if data.get('end_date'):
            context['end_date'] = int(data['end_date'])
        if data.get('repo_id'):
            repo = database.get_repository_by_id(data['repo_id'])
            if repo:
                context['repo_url'] = repo['repo_url']
        if data.get('contributor_id'):
            contributor = database.get_contributor_by_id(data['contributor_id'])
            if contributor:
                context['contributor'] = contributor['contributor_uid']

        # 创建执行记录
        execution_id = scheduler_db.create_task_execution('daily_aggregation')

        # 异步执行
        def run_task():
            task = DailyAggregationTask(config_data)
            task.run(execution_id=execution_id)

        thread = threading.Thread(target=run_task, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'data': {
                'execution_id': execution_id,
                'status': 'running',
                'message': '统计任务已提交'
            }
        })
    except Exception as e:
        logger.error(f'触发聚合任务失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 2: Commit**

```bash
git add api/routes/stats_v2.py
git commit -m "feat: add v2 API - manual aggregate trigger endpoint"
```

---

## Task 20: Register v2 API blueprint in app.py

**Files:**
- Modify: `app.py`

**Step 1: Add import**

After the existing route imports (around line 11-15), add:

```python
from api.routes.stats_v2 import stats_v2_bp
```

**Step 2: Register blueprint**

After the existing blueprint registrations (around line 48), add:

```python
app.register_blueprint(stats_v2_bp)
```

**Step 3: Verify routes**

```bash
python -c "
from app import app
v2_routes = [str(rule) for rule in app.url_map.iter_rules() if '/api/v2' in str(rule)]
print('V2 routes:', len(v2_routes))
for route in v2_routes:
    print('  ', route)
"
```

Expected: 5 routes (`/api/v2/repositories`, `/api/v2/contributors`, `/api/v2/stats`, `/api/v2/stats/daily`, `/api/v2/stats/aggregate`)

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: register v2 API blueprint in app"
```

---

## Task 21: Add frontend dependencies (ECharts)

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install ECharts**

```bash
cd frontend
npm install echarts vue-echarts
```

**Step 2: Verify installation**

```bash
cd frontend && node -e "const echarts = require('echarts'); console.log('ECharts version:', echarts.version)"
```

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add echarts and vue-echarts for dashboard"
```

---

## Task 22: Create frontend API service layer

**Files:**
- Create: `frontend/src/services/api.js`

**Step 1: Create API service**

```javascript
const BASE_URL = '/api/v2'

export async function fetchRepositories(params = {}) {
  const query = new URLSearchParams(params).toString()
  const res = await fetch(`${BASE_URL}/repositories?${query}`)
  return res.json()
}

export async function fetchContributors(params = {}) {
  const query = new URLSearchParams(params).toString()
  const res = await fetch(`${BASE_URL}/contributors?${query}`)
  return res.json()
}

export async function fetchStats(params = {}) {
  const query = new URLSearchParams(params).toString()
  const res = await fetch(`${BASE_URL}/stats?${query}`)
  return res.json()
}

export async function fetchDailyStats(params = {}) {
  const query = new URLSearchParams(params).toString()
  const res = await fetch(`${BASE_URL}/stats/daily?${query}`)
  return res.json()
}

export async function triggerAggregate(data = {}) {
  const res = await fetch(`${BASE_URL}/stats/aggregate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return res.json()
}
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: add frontend API service layer for v2 endpoints"
```

---

## Task 23: Create frontend Dashboard component (delegate to visual-engineering)

**Files:**
- Create: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/App.vue` (integrate Dashboard)

**Step 1: Delegate to visual-engineering subagent**

This task should be delegated to a `visual-engineering` category agent with `frontend-ui-ux` skill loaded.

**Delegation prompt:**

```
TASK: Create Vue 3 Dashboard component with ECharts visualizations

EXPECTED OUTCOME: 
- Dashboard.vue component with filters, metric cards, charts, and data table
- Integrated into App.vue
- Uses /api/v2 endpoints via services/api.js

REQUIRED TOOLS: Edit, Write, Read, Bash (for npm commands)

MUST DO:
1. Create frontend/src/views/Dashboard.vue with:
   - Filter bar: date range picker (flatpickr), repo selector, contributor selector, query button
   - 4 metric summary cards: AI生成量, AI采纳量, 人类代码量, AI占比
   - Trend line chart (ECharts): AI生成/采纳/人类代码/AI占比 over time
   - 2 bar charts (ECharts): by repository, by contributor
   - Paginated data table: daily stats detail with columns (日期, 仓库, 贡献者, AI生成, AI采纳, 人类, AI占比)
   - Manual trigger button: opens modal to select params and trigger aggregation

2. Use existing Tailwind CSS classes for styling (match current App.vue style)

3. Import and use:
   - import { fetchRepositories, fetchContributors, fetchStats, fetchDailyStats, triggerAggregate } from '@/services/api.js'
   - import { use } from 'echarts/core'
   - import { LineChart, BarChart } from 'echarts/charts'
   - import VChart from 'vue-echarts'

4. Default behavior: query last 7 days on mount

5. Update App.vue to import and render Dashboard component

MUST NOT DO:
- Do NOT create new API endpoints (use existing /api/v2/*)
- Do NOT modify backend code
- Do NOT add new npm dependencies beyond echarts/vue-echarts (already installed)

CONTEXT: 
- Current App.vue is 771 lines, single-file SPA
- Tailwind CSS already configured
- flatpickr already available
- lucide-vue-next for icons
```

**Step 2: After delegation completes, verify**

```bash
cd frontend && npm run build
```

**Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat: add Dashboard component with ECharts and data table"
```

---

## Task 24: Integration test - backend

**Step 1: Start the app**

```bash
python app.py
```

**Step 2: Test v2 API endpoints**

```bash
# Test repositories
curl http://localhost:8888/api/v2/repositories

# Test contributors
curl http://localhost:8888/api/v2/contributors

# Test stats (last 7 days)
START=$(python -c "import time; from datetime import datetime, timedelta; print(int((datetime.now() - timedelta(days=7)).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()*1000))")
END=$(python -c "import time; from datetime import datetime; print(int(datetime.now().timestamp()*1000))")
curl "http://localhost:8888/api/v2/stats?start_date=${START}&end_date=${END}"

# Test daily stats detail
curl "http://localhost:8888/api/v2/stats/daily?page=1&page_size=10"

# Test manual trigger
curl -X POST http://localhost:8888/api/v2/stats/aggregate \
  -H 'Content-Type: application/json' \
  -d '{}'
```

**Step 3: Verify database tables exist**

```bash
python -c "
from core.database.base_db import BaseDatabase
from sqlalchemy import inspect
db = BaseDatabase()
inspector = inspect(db.engine)
tables = inspector.get_table_names()
stats_tables = [t for t in tables if t.startswith('stats_')]
print('Stats tables:', stats_tables)
assert 'stats_repositories' in tables
assert 'stats_contributors' in tables
assert 'stats_repo_contributors' in tables
assert 'stats_daily_stats' in tables
print('All v2 tables exist')
"
```

---

## Task 25: Integration test - frontend

**Step 1: Build frontend**

```bash
cd frontend && npm run build
```

**Step 2: Start app and open browser**

```bash
python app.py
```

Open http://localhost:8888 in browser.

**Step 3: Verify Dashboard renders**

- Filter bar with date range, repo, contributor selectors
- 4 metric cards display
- Trend chart renders
- Distribution charts render
- Data table with pagination
- Manual trigger button works

**Step 4: Test manual trigger**

- Click "手动统计" button
- Select date range
- Submit
- Verify execution_id returned
- Check task_executions table for record

---

## Task 26: Final cleanup and commit

**Step 1: Run linter/formatter (if available)**

```bash
# Python
python -m black core/ api/ --check || true

# Frontend
cd frontend && npm run lint --if-present || true
```

**Step 2: Verify no old code references remain**

```bash
# Check for imports of deleted modules
grep -r "from core.database.dimensions_db" . --include="*.py" || echo "Clean"
grep -r "from core.services.metrics_aggregation_service" . --include="*.py" || echo "Clean"
grep -r "MetricsDailyStats" . --include="*.py" --exclude-dir=".git" || echo "Clean"
```

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete v2 statistics system refactor

- All tables use XID primary keys + millisecond timestamps
- New stats_ prefix tables (repositories, contributors, repo_contributors, daily_stats)
- Single DailyAggregationTask replaces 8 old tasks
- New v2 API with 5 endpoints
- Frontend Dashboard with ECharts + data table
- Deleted all old stats/dimensions code"
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Add xid-python | requirements.txt |
| 2 | Update existing models to XID | core/database/models.py |
| 3 | Fix MetricsService timestamps | core/services/metrics_service.py |
| 4 | Create new stats models | core/database/models.py |
| 5 | Delete old models | core/database/models.py |
| 6 | Create StatsDatabase | core/database/stats_db.py, __init__.py |
| 7-9 | Delete old code | dimensions_db.py, tasks/, routes/ |
| 10 | Update config | config.yaml |
| 11-14 | Implement StatsDatabase | core/database/stats_db.py |
| 15-16 | Create DailyAggregationTask | core/scheduler/tasks/daily_aggregation_task.py |
| 17-20 | Create v2 API | api/routes/stats_v2.py, app.py |
| 21-22 | Frontend setup | package.json, services/api.js |
| 23 | Dashboard component | frontend/src/views/Dashboard.vue |
| 24-26 | Integration tests & cleanup | — |

**Total: 26 tasks**

**Execution options:**

1. **Subagent-Driven (this session)** — Execute task-by-task with review between tasks
2. **Parallel Session (separate)** — Open new session with executing-plans skill for batch execution

