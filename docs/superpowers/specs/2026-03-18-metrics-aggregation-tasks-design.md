# Metrics 汇总统计定时任务设计方案

**日期**: 2026-03-18
**版本**: 1.0
**状态**: 设计完成

## 1. 概述

本设计方案定义了基于 Metrics 基础数据表的汇总统计定时任务实现方案。系统将从 `metrics_events_committed` 表读取原始事件数据,按不同维度(时间、仓库、贡献者)进行聚合统计,并存储到对应的汇总表中。

### 1.1 目标

- 实现 5 个维度的数据汇总: 日统计、周统计、月统计、仓库统计、贡献者统计
- 支持增量聚合(时间维度)和全量重算(实体维度)的混合模式
- 提供分散调度机制,避免资源竞争
- 实现智能检测,自动处理历史数据
- 支持部分容错,单批次失败不影响整体

### 1.2 涉及的数据表

**源表**:
- `metrics_events_committed` - Committed 事件原始数据

**目标表**:
- `metrics_daily_stats` - 按天汇总
- `metrics_weekly_stats` - 按周汇总
- `metrics_monthly_stats` - 按月汇总
- `metrics_repo_stats` - 按仓库汇总
- `metrics_contributor_stats` - 按贡献者多粒度汇总

## 2. 整体架构

### 2.1 系统分层

```
┌─────────────────────────────────────┐
│   定时任务层 (Scheduler Tasks)      │
│  - DailyStatsTask                   │
│  - WeeklyStatsTask                  │
│  - MonthlyStatsTask                 │
│  - RepoStatsTask                    │
│  - ContributorStatsTask             │
└──────────────┬──────────────────────┘
               │ 调用
               ↓
┌─────────────────────────────────────┐
│   服务层 (Service Layer)            │
│  MetricsAggregationService          │
│  - aggregate_daily_stats()          │
│  - aggregate_weekly_stats()         │
│  - aggregate_monthly_stats()        │
│  - aggregate_repo_stats()           │
│  - aggregate_contributor_stats()    │
└──────────────┬──────────────────────┘
               │ 查询/更新
               ↓
┌─────────────────────────────────────┐
│   数据访问层 (Database Layer)       │
│  - metrics_events_committed (源表)  │
│  - metrics_*_stats (统计表)         │
└─────────────────────────────────────┘
```

**设计原则**:
- **任务层**: 轻量级,仅负责调度和参数传递
- **服务层**: 封装所有聚合业务逻辑,可被任务、API、脚本复用
- **数据层**: 提供统一的数据访问接口

### 2.2 调度时间表

| 任务 | Cron 表达式 | 执行时间 | 聚合模式 | 说明 |
|------|------------|---------|---------|------|
| DailyStatsTask | `0 2 * * *` | 每天 02:00 | 增量 | 聚合昨天的数据 |
| WeeklyStatsTask | `0 3 * * 1` | 每周一 03:00 | 增量 | 聚合上周数据 |
| MonthlyStatsTask | `0 4 1 * *` | 每月 1 号 04:00 | 增量 | 聚合上月数据 |
| RepoStatsTask | `0 5 * * *` | 每天 05:00 | 全量 | 全量重算仓库统计 |
| ContributorStatsTask | `0 6 * * *` | 每天 06:00 | 全量 | 全量重算贡献者统计 |

**调度策略**: 分散调度,避免资源竞争和相互影响

## 3. 数据流设计

### 3.1 增量聚合流程 (时间维度统计)

```
┌─────────────────────┐
│ 检查统计表是否为空   │
└──────┬──────────────┘
       │
       ├─ 为空 → 全量模式
       │         └→ 从最早的 committed 事件开始
       │            └→ 按时间粒度分组聚合所有历史数据
       │
       └─ 有数据 → 增量模式
                 └→ 获取最后统计时间点
                    └→ 只处理该时间点之后的数据
```

**日统计增量逻辑**:
1. 查询 `metrics_daily_stats` 表的最大 `date_ts`
2. 从 `metrics_events_committed` 读取 `timestamp > 最大date_ts` 的记录
3. 按天(date)分组聚合
4. 生成新的日统计记录并 UPSERT

**周统计增量逻辑**:
1. 查询 `metrics_weekly_stats` 表的最大 `week_start_ts`
2. 从 `metrics_events_committed` 读取 `timestamp > 最大week_start_ts` 的记录
3. 按周(year + week)分组聚合
4. 生成新的周统计记录并 UPSERT

**月统计增量逻辑**:
1. 查询 `metrics_monthly_stats` 表的最大 `month_start_ts`
2. 从 `metrics_events_committed` 读取 `timestamp > 最大month_start_ts` 的记录
3. 按月(year + month)分组聚合
4. 生成新的月统计记录并 UPSERT

### 3.2 全量聚合流程 (维度统计)

```
┌─────────────────────────────┐
│ 从 committed 表读取所有数据  │
└──────┬──────────────────────┘
       │
       ├→ 按 repo_url 分组
       │  └→ 计算每个仓库的统计指标
       │     └→ UPSERT 到 metrics_repo_stats
       │
       └→ 按 author 分组
          └→ 按不同粒度(daily/weekly/monthly)分组
             └→ 计算每个作者的统计指标
                └→ UPSERT 到 metrics_contributor_stats
```

**仓库统计全量逻辑**:
1. 从 `metrics_events_committed` 读取所有记录
2. 按 `repo_url` 分组
3. 对每个仓库计算累计统计指标
4. UPSERT 到 `metrics_repo_stats`

**贡献者统计全量逻辑**:
1. 从 `metrics_events_committed` 读取所有记录
2. 按 `author` + `granularity` + 时间字段分组
3. 对每个作者在每个时间粒度计算统计指标
4. UPSERT 到 `metrics_contributor_stats`

## 4. 核心聚合逻辑

### 4.1 通用统计指标计算

所有统计维度都包含以下核心指标:

```python
# 代码行数统计
human_additions = event.human_additions or 0
ai_additions_array = json.loads(event.ai_additions or '[]')
ai_lines = sum(ai_additions_array)
total_lines = human_additions + ai_lines

# AI 占比
ai_percentage = (ai_lines / total_lines * 100) if total_lines > 0 else 0

# 提交统计
total_commits = count(distinct commit_sha)
commits_with_ai = count(distinct commit_sha where sum(ai_additions) > 0)

# 工具模型分布
tool_model_breakdown = {
    "tool/model": lines_count,
    ...
}
```

### 4.2 日统计聚合算法

**输入**: 某一天(date)的所有 committed 事件
**输出**: 一条 `MetricsDailyStat` 记录

**分组**: 按 `date(from_timestamp(timestamp))` 分组

**字段计算**:
- `date`: 日期字符串 (YYYY-MM-DD)
- `date_ts`: 当天 00:00:00 的时间戳
- `total_lines`: sum(human_additions + sum(ai_additions))
- `ai_lines`: sum(sum(ai_additions))
- `ai_percentage`: (ai_lines / total_lines * 100)
- `total_commits`: count(distinct commit_sha)
- `commits_with_ai`: count(distinct commit_sha where ai_additions > 0)
- `tool_model_breakdown`: JSON 对象,统计各工具模型的代码行数
- `start_date`: 当天最早的 timestamp
- `end_date`: 当天最晚的 timestamp

### 4.3 周统计聚合算法

**输入**: 某一周的所有 committed 事件
**输出**: 一条 `MetricsWeeklyStat` 记录

**分组**: 按 `year + week_of_year(from_timestamp(timestamp))` 分组

**字段计算**:
- `year`: 年份
- `week`: 周数 (1-53)
- `week_start`: 周一日期字符串
- `week_start_ts`: 周一 00:00:00 时间戳
- `week_end`: 周日日期字符串
- `week_end_ts`: 周日 23:59:59 时间戳
- 其他字段同日统计

### 4.4 月统计聚合算法

**输入**: 某一月的所有 committed 事件
**输出**: 一条 `MetricsMonthlyStat` 记录

**分组**: 按 `year + month(from_timestamp(timestamp))` 分组

**字段计算**:
- `year`: 年份
- `month`: 月份 (1-12)
- `month_start`: 月初日期字符串
- `month_start_ts`: 月初 00:00:00 时间戳
- `month_end`: 月末日期字符串
- `month_end_ts`: 月末 23:59:59 时间戳
- 其他字段同日统计

### 4.5 仓库统计聚合算法

**输入**: 所有 committed 事件
**输出**: 每个仓库一条 `MetricsRepoStat` 记录

**分组**: 按 `repo_url` 分组

**字段计算**:
- `repo_id`: 从 repo_url 提取 (如 "owner/repo")
- `repo_name`: 从 repo_url 提取仓库名
- `repo_url`: 仓库 URL
- `provider_type`: 从 URL 推断 (github/gitlab/gitea)
- `branch`: 最常见的 branch 值
- `total_lines`, `ai_lines`, `ai_percentage`: 同日统计
- `total_commits`, `commits_with_ai`: 同日统计
- `tool_model_breakdown`: 同日统计
- `start_date`: min(timestamp)
- `end_date`: max(timestamp)

### 4.6 贡献者统计聚合算法

**输入**: 所有 committed 事件
**输出**: 每个作者在每个粒度下的多条 `MetricsContributorStat` 记录

**分组**: 按 `author + granularity + 时间字段` 分组

**粒度处理**:
- `granularity='daily'`: 按 author + date 分组
- `granularity='weekly'`: 按 author + year_week 分组
- `granularity='monthly'`: 按 author + year_month 分组

**字段计算**:
- `author`: 作者名
- `author_email`: 作者邮箱 (如果有)
- `granularity`: 粒度 (daily/weekly/monthly)
- `date`: 日期 (仅 daily 粒度)
- `year_week`: 年周 (仅 weekly 粒度,格式: "2026-W11")
- `year_month`: 年月 (仅 monthly 粒度,格式: "2026-03")
- `date_ts`: 时间戳
- `total_commits`, `total_lines`, `ai_lines`, `ai_percentage`: 同日统计
- `repos_breakdown`: JSON 对象,统计该作者在各仓库的代码行数

## 5. 错误处理与容错机制

### 5.1 批次处理策略

**时间维度统计** - 按天/周/月批次处理:

```python
success_count = 0
failed_items = []

for time_unit in time_range:
    try:
        aggregate_single_unit(time_unit)
        success_count += 1
    except Exception as e:
        logger.error(f"时间单位 {time_unit} 聚合失败: {e}")
        failed_items.append(time_unit)
        continue  # 继续处理下一个
```

**维度统计** - 按实体批次处理:

```python
success_count = 0
failed_items = []

for entity in entity_list:
    try:
        aggregate_single_entity(entity)
        success_count += 1
    except Exception as e:
        logger.error(f"实体 {entity} 聚合失败: {e}")
        failed_items.append(entity)
        continue  # 继续处理下一个
```

### 5.2 数据一致性保证

**UPSERT 策略**:
- PostgreSQL: 使用 `INSERT ... ON CONFLICT (unique_key) DO UPDATE SET ...`
- SQLite: 使用 `INSERT OR REPLACE INTO ...`
- 确保重复执行任务不会产生重复数据

**唯一键定义**:
- `metrics_daily_stats`: `date`
- `metrics_weekly_stats`: `(year, week)`
- `metrics_monthly_stats`: `(year, month)`
- `metrics_repo_stats`: `(repo_id, repo_name)`
- `metrics_contributor_stats`: `(author, granularity, date, year_week, year_month)`

**时间戳自动更新**:
- 每次 UPDATE 时,`updated_at` 字段通过数据库触发器自动更新
- 首次 INSERT 时,`created_at` 和 `updated_at` 都设置为当前时间

### 5.3 任务执行结果

每个任务返回统一格式:

```python
{
    "success": True,           # 任务是否整体成功
    "processed": 30,           # 成功处理的批次数
    "failed": 2,               # 失败的批次数
    "duration": 12.5,          # 执行耗时(秒)
    "details": {
        "failed_items": ["2024-03-15", "2024-03-16"]  # 失败的具体项
    }
}
```

## 6. 数据库接口扩展

### 6.1 Database 基类新增方法

需要在 `core/database/base.py` 的 `Database` 抽象类中新增以下方法:

```python
# ========== 时间维度统计方法 ==========

@abstractmethod
def save_daily_stat(self, stat: MetricsDailyStat) -> int:
    """保存或更新日统计"""
    pass

@abstractmethod
def save_weekly_stat(self, stat: MetricsWeeklyStat) -> int:
    """保存或更新周统计"""
    pass

@abstractmethod
def save_monthly_stat(self, stat: MetricsMonthlyStat) -> int:
    """保存或更新月统计"""
    pass

@abstractmethod
def get_latest_daily_stat(self) -> Optional[MetricsDailyStat]:
    """获取最新的日统计记录"""
    pass

@abstractmethod
def get_latest_weekly_stat(self) -> Optional[MetricsWeeklyStat]:
    """获取最新的周统计记录"""
    pass

@abstractmethod
def get_latest_monthly_stat(self) -> Optional[MetricsMonthlyStat]:
    """获取最新的月统计记录"""
    pass

# ========== 维度统计方法 ==========

@abstractmethod
def save_repo_stat(self, stat: MetricsRepoStat) -> int:
    """保存或更新仓库统计"""
    pass

@abstractmethod
def save_contributor_stat(self, stat: MetricsContributorStat) -> int:
    """保存或更新贡献者统计"""
    pass

@abstractmethod
def get_all_repo_urls(self) -> List[str]:
    """获取所有仓库 URL 列表"""
    pass

@abstractmethod
def get_all_authors(self) -> List[str]:
    """获取所有作者列表"""
    pass

# ========== 查询辅助方法 ==========

@abstractmethod
def get_committed_events_by_date_range(self, start_ts: int, end_ts: int) -> List[Dict]:
    """按时间范围查询 committed 事件"""
    pass

@abstractmethod
def get_committed_events_by_repo(self, repo_url: str) -> List[Dict]:
    """按仓库查询 committed 事件"""
    pass

@abstractmethod
def get_committed_events_by_author(self, author: str) -> List[Dict]:
    """按作者查询 committed 事件"""
    pass
```

### 6.2 实现类需要实现的方法

`SQLiteDatabase` 和未来的 `PostgreSQLDatabase`、`MySQLDatabase` 都需要实现上述所有抽象方法。

## 7. 文件结构

```
core/
├── services/
│   ├── __init__.py
│   ├── metrics_service.py              # 已存在 - Metrics 数据接收处理
│   ├── metrics_aggregation_service.py  # 新增 - Metrics 聚合服务
│   ├── oauth_service.py                # 已存在
│   └── cas_service.py                  # 已存在
├── scheduler/
│   ├── __init__.py
│   ├── base.py                         # 已存在 - 任务基类
│   ├── scheduled.py                    # 已存在 - 调度装饰器
│   ├── task_meta.py                    # 已存在 - 任务元类
│   ├── registry.py                     # 已存在 - 任务注册表
│   ├── scheduler.py                    # 已存在 - 调度器
│   ├── dimensions_task.py              # 已存在 - 维度表更新任务
│   ├── daily_stats_task.py             # 新增 - 日统计任务
│   ├── weekly_stats_task.py            # 新增 - 周统计任务
│   ├── monthly_stats_task.py           # 新增 - 月统计任务
│   ├── repo_stats_task.py              # 新增 - 仓库统计任务
│   └── contributor_stats_task.py       # 新增 - 贡献者统计任务
├── database/
│   ├── __init__.py
│   ├── base.py                         # 需扩展 - 新增抽象方法
│   ├── factory.py                      # 已存在
│   └── sqlite.py                       # 需扩展 - 实现新增方法
└── models/
    ├── __init__.py
    ├── stats.py                        # 已存在
    └── metrics.py                      # 已存在 - 包含所有 Metrics 模型
```

## 8. 实现优先级

### Phase 1: 基础设施 (P0)
1. 扩展 `Database` 基类,新增抽象方法
2. 在 `SQLiteDatabase` 中实现新增方法
3. 创建 `MetricsAggregationService` 服务类

### Phase 2: 时间维度统计 (P1)
1. 实现日统计聚合逻辑
2. 创建 `DailyStatsTask` 任务
3. 实现周统计聚合逻辑
4. 创建 `WeeklyStatsTask` 任务
5. 实现月统计聚合逻辑
6. 创建 `MonthlyStatsTask` 任务

### Phase 3: 维度统计 (P2)
1. 实现仓库统计聚合逻辑
2. 创建 `RepoStatsTask` 任务
3. 实现贡献者统计聚合逻辑
4. 创建 `ContributorStatsTask` 任务

### Phase 4: 测试与优化 (P3)
1. 单元测试
2. 集成测试
3. 性能优化
4. 文档完善

## 9. 关键技术决策

### 9.1 为什么选择混合模式?

**时间维度用增量**:
- 时间维度数据按时间顺序增长,天然适合增量处理
- 每次只需处理新增的时间段,效率高
- 历史数据不会变化,无需重新计算

**维度统计用全量**:
- 仓库和贡献者的统计需要汇总所有历史数据
- 全量重算逻辑简单,不需要维护增量状态
- 每天执行一次,性能可接受

### 9.2 为什么选择分散调度?

- 避免多个任务同时执行造成数据库负载峰值
- 任务间完全解耦,互不影响
- 便于单独监控和调试每个任务
- 符合现有项目的任务设计模式

### 9.3 为什么选择服务层模式?

- 业务逻辑集中管理,易于测试和维护
- 服务层方法可被任务、API、脚本复用
- 任务类保持轻量,只负责调度
- 符合项目现有的 `MetricsService` 设计模式

## 10. 未来扩展

### 10.1 手动触发 API

可以添加 API 端点手动触发聚合:

```python
POST /api/metrics/aggregate
{
    "type": "daily",
    "date_range": ["2024-03-01", "2024-03-31"]
}
```

### 10.2 增量优化

如果数据量增长到全量重算性能不足,可以将维度统计也改为增量模式:
- 维护 `last_processed_id` 或 `last_processed_timestamp`
- 只处理新增的 committed 事件
- 更新对应的仓库/贡献者统计记录

### 10.3 实时聚合

如果需要更实时的统计数据,可以:
- 在 Metrics 上传时触发实时聚合
- 使用消息队列异步处理
- 缓存热点数据

## 11. 总结

本设计方案采用**混合分层模式**,通过服务层封装聚合逻辑,任务层负责调度,实现了:

✅ 增量聚合(时间维度) + 全量重算(实体维度)的混合模式
✅ 分散调度,避免资源竞争
✅ 智能检测,自动处理历史数据
✅ 部分容错,单批次失败不影响整体
✅ 代码复用性高,易于测试和维护
✅ 符合项目现有架构模式

该方案在效率、简洁性、可维护性之间取得了良好平衡,适合当前项目需求。
