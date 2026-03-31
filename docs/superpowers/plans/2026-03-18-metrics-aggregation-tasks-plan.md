# Metrics 汇总统计定时任务实现计划

**日期**: 2026-03-18
**设计文档**: docs/superpowers/specs/2026-03-18-metrics-aggregation-tasks-design.md
**状态**: 待实现

## 实现概述

根据设计文档,实现 Metrics 数据的多维度汇总统计定时任务系统。采用混合分层架构:服务层封装聚合逻辑,任务层负责调度。

## 实现阶段

### Phase 1: 基础设施层 (P0)

#### Step 1.1: 扩展 Database 基类
**文件**: `core/database/base.py`
**任务**: 在 `Database` 抽象类中新增统计相关的抽象方法

**新增方法**:
```python
# 时间维度统计
@abstractmethod
def save_daily_stat(self, stat: MetricsDailyStat) -> int
@abstractmethod
def save_weekly_stat(self, stat: MetricsWeeklyStat) -> int
@abstractmethod
def save_monthly_stat(self, stat: MetricsMonthlyStat) -> int
@abstractmethod
def get_latest_daily_stat(self) -> Optional[MetricsDailyStat]
@abstractmethod
def get_latest_weekly_stat(self) -> Optional[MetricsWeeklyStat]
@abstractmethod
def get_latest_monthly_stat(self) -> Optional[MetricsMonthlyStat]

# 维度统计
@abstractmethod
def save_repo_stat(self, stat: MetricsRepoStat) -> int
@abstractmethod
def save_contributor_stat(self, stat: MetricsContributorStat) -> int
@abstractmethod
def get_all_repo_urls(self) -> List[str]
@abstractmethod
def get_all_authors(self) -> List[str]

# 查询辅助
@abstractmethod
def get_committed_events_by_date_range(self, start_ts: int, end_ts: int) -> List[Dict]
@abstractmethod
def get_committed_events_by_repo(self, repo_url: str) -> List[Dict]
@abstractmethod
def get_committed_events_by_author(self, author: str) -> List[Dict]
```

**验证**: 确保所有抽象方法都有正确的类型注解

---

#### Step 1.2: 实现 SQLiteDatabase 新增方法
**文件**: `core/database/sqlite.py`
**任务**: 实现 Step 1.1 中定义的所有抽象方法

**关键实现**:
- 使用 `INSERT OR REPLACE` 实现 UPSERT 语义
- 查询方法返回字典列表,便于后续处理
- 使用参数化查询防止 SQL 注入

**验证**:
- 每个方法都能正确执行
- UPSERT 逻辑正确(重复执行不会产生重复数据)

---

#### Step 1.3: 创建 MetricsAggregationService
**文件**: `core/services/metrics_aggregation_service.py` (新建)
**任务**: 创建聚合服务类,封装所有聚合业务逻辑

**类结构**:
```python
class MetricsAggregationService:
    def __init__(self, database: Database):
        self.database = database
        self.logger = Logger.get_logger('services.metrics_aggregation')

    # 时间维度聚合
    def aggregate_daily_stats(self, force_full: bool = False) -> Dict
    def aggregate_weekly_stats(self, force_full: bool = False) -> Dict
    def aggregate_monthly_stats(self, force_full: bool = False) -> Dict

    # 维度聚合
    def aggregate_repo_stats(self) -> Dict
    def aggregate_contributor_stats(self) -> Dict

    # 内部辅助方法
    def _is_first_run(self, stat_type: str) -> bool
    def _calculate_metrics(self, events: List[Dict]) -> Dict
    def _extract_repo_id(self, repo_url: str) -> str
```

**验证**: 服务类可以正确初始化

---

### Phase 2: 时间维度统计 (P1)

#### Step 2.1: 实现日统计聚合逻辑
**文件**: `core/services/metrics_aggregation_service.py`
**任务**: 实现 `aggregate_daily_stats()` 方法

**核心逻辑**:
1. 检查是否首次运行(统计表是否为空)
2. 首次运行: 从最早的 committed 事件开始,按天分组聚合
3. 增量运行: 获取最后统计日期,只处理之后的数据
4. 按天分组计算统计指标
5. 批次处理,单天失败不影响其他天
6. 返回执行结果

**验证**:
- 首次运行能处理所有历史数据
- 增量运行只处理新数据
- 单天失败不影响其他天

---

#### Step 2.2: 创建 DailyStatsTask
**文件**: `core/scheduler/daily_stats_task.py` (新建)
**任务**: 创建日统计定时任务

**任务配置**:
```python
@scheduled(cron="0 2 * * *", job_id="daily_stats", name="日统计任务")
class DailyStatsTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context=None):
        service = MetricsAggregationService(self.database)
        return service.aggregate_daily_stats()
```

**验证**: 任务能被调度器自动注册和执行

---

#### Step 2.3: 实现周统计聚合逻辑
**文件**: `core/services/metrics_aggregation_service.py`
**任务**: 实现 `aggregate_weekly_stats()` 方法

**核心逻辑**:
1. 智能检测首次运行
2. 按周(year + week)分组聚合
3. 计算周开始和结束时间戳
4. 批次处理

**验证**: 周统计数据正确,周边界计算准确

---

#### Step 2.4: 创建 WeeklyStatsTask
**文件**: `core/scheduler/weekly_stats_task.py` (新建)
**任务**: 创建周统计定时任务

**任务配置**:
```python
@scheduled(cron="0 3 * * 1", job_id="weekly_stats", name="周统计任务")
class WeeklyStatsTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context=None):
        service = MetricsAggregationService(self.database)
        return service.aggregate_weekly_stats()
```

**验证**: 任务在每周一 03:00 执行

---

#### Step 2.5: 实现月统计聚合逻辑
**文件**: `core/services/metrics_aggregation_service.py`
**任务**: 实现 `aggregate_monthly_stats()` 方法

**核心逻辑**:
1. 智能检测首次运行
2. 按月(year + month)分组聚合
3. 计算月开始和结束时间戳
4. 批次处理

**验证**: 月统计数据正确,月边界计算准确

---

#### Step 2.6: 创建 MonthlyStatsTask
**文件**: `core/scheduler/monthly_stats_task.py` (新建)
**任务**: 创建月统计定时任务

**任务配置**:
```python
@scheduled(cron="0 4 1 * *", job_id="monthly_stats", name="月统计任务")
class MonthlyStatsTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context=None):
        service = MetricsAggregationService(self.database)
        return service.aggregate_monthly_stats()
```

**验证**: 任务在每月 1 号 04:00 执行

---

### Phase 3: 维度统计 (P2)

#### Step 3.1: 实现仓库统计聚合逻辑
**文件**: `core/services/metrics_aggregation_service.py`
**任务**: 实现 `aggregate_repo_stats()` 方法

**核心逻辑**:
1. 获取所有仓库 URL 列表
2. 对每个仓库,查询其所有 committed 事件
3. 计算累计统计指标
4. UPSERT 到 metrics_repo_stats
5. 按仓库批次处理,单个失败不影响其他

**验证**:
- 所有仓库都被正确统计
- 单个仓库失败不影响其他

---

#### Step 3.2: 创建 RepoStatsTask
**文件**: `core/scheduler/repo_stats_task.py` (新建)
**任务**: 创建仓库统计定时任务

**任务配置**:
```python
@scheduled(cron="0 5 * * *", job_id="repo_stats", name="仓库统计任务")
class RepoStatsTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context=None):
        service = MetricsAggregationService(self.database)
        return service.aggregate_repo_stats()
```

**验证**: 任务每天 05:00 执行

---

#### Step 3.3: 实现贡献者统计聚合逻辑
**文件**: `core/services/metrics_aggregation_service.py`
**任务**: 实现 `aggregate_contributor_stats()` 方法

**核心逻辑**:
1. 获取所有作者列表
2. 对每个作者,按不同粒度(daily/weekly/monthly)分组聚合
3. 计算统计指标和仓库分布
4. UPSERT 到 metrics_contributor_stats
5. 按作者批次处理

**验证**:
- 所有作者在各粒度下都被正确统计
- repos_breakdown 正确

---

#### Step 3.4: 创建 ContributorStatsTask
**文件**: `core/scheduler/contributor_stats_task.py` (新建)
**任务**: 创建贡献者统计定时任务

**任务配置**:
```python
@scheduled(cron="0 6 * * *", job_id="contributor_stats", name="贡献者统计任务")
class ContributorStatsTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context=None):
        service = MetricsAggregationService(self.database)
        return service.aggregate_contributor_stats()
```

**验证**: 任务每天 06:00 执行

---

## 关键实现细节

### 智能检测逻辑
```python
def _is_first_run(self, stat_type: str) -> bool:
    if stat_type == 'daily':
        return self.database.get_latest_daily_stat() is None
    elif stat_type == 'weekly':
        return self.database.get_latest_weekly_stat() is None
    elif stat_type == 'monthly':
        return self.database.get_latest_monthly_stat() is None
    return False
```

### 批次处理模式
```python
success_count = 0
failed_items = []

for item in items:
    try:
        process_single_item(item)
        success_count += 1
    except Exception as e:
        logger.error(f"处理 {item} 失败: {e}")
        failed_items.append(item)
        continue

return {
    "success": len(failed_items) == 0,
    "processed": success_count,
    "failed": len(failed_items),
    "details": {"failed_items": failed_items}
}
```

### 统计指标计算
```python
def _calculate_metrics(self, events: List[Dict]) -> Dict:
    total_lines = 0
    ai_lines = 0
    total_commits = set()
    commits_with_ai = set()
    tool_model_breakdown = {}

    for event in events:
        human_additions = event.get('human_additions') or 0
        ai_additions_json = event.get('ai_additions') or '[]'
        ai_additions = sum(json.loads(ai_additions_json))

        total_lines += human_additions + ai_additions
        ai_lines += ai_additions

        commit_sha = event.get('commit_sha')
        if commit_sha:
            total_commits.add(commit_sha)
            if ai_additions > 0:
                commits_with_ai.add(commit_sha)

        # 更新工具模型分布
        tool = event.get('tool')
        model = event.get('model')
        if tool and model:
            key = f"{tool}/{model}"
            tool_model_breakdown[key] = tool_model_breakdown.get(key, 0) + ai_additions

    return {
        'total_lines': total_lines,
        'ai_lines': ai_lines,
        'ai_percentage': round(ai_lines / total_lines * 100, 2) if total_lines > 0 else 0,
        'total_commits': len(total_commits),
        'commits_with_ai': len(commits_with_ai),
        'tool_model_breakdown': json.dumps(tool_model_breakdown)
    }
```

## 测试策略

### 单元测试
- 测试每个聚合方法的核心逻辑
- 测试智能检测逻辑
- 测试批次处理和错误处理

### 集成测试
- 准备测试数据(committed 事件)
- 执行聚合任务
- 验证统计表数据正确性

### 手动测试
- 首次运行测试(空表)
- 增量运行测试(有历史数据)
- 错误场景测试(部分数据异常)

## 实施顺序

1. **Phase 1 (基础设施)**: 必须先完成,为后续提供基础
2. **Phase 2 (时间维度)**: 按 日→周→月 顺序实现,逐步验证
3. **Phase 3 (维度统计)**: 在时间维度稳定后实现
4. **测试**: 每个 Phase 完成后进行测试

## 预期成果

完成后将实现:
- ✅ 5 个聚合任务自动运行
- ✅ 智能检测历史数据并自动处理
- ✅ 增量聚合提高效率
- ✅ 部分容错保证数据完整性
- ✅ 服务层可复用于 API 或脚本

## 风险与注意事项

1. **数据量**: 如果 committed 事件数据量很大,首次全量聚合可能耗时较长
2. **时区**: 时间戳转换需要注意时区问题
3. **并发**: 虽然任务分散调度,但仍需注意数据库连接池大小
4. **数据一致性**: UPSERT 操作需要正确的唯一键约束
