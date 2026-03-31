# 仓库和作者维度表设计文档

## 概述

本设计为 Git-AI Metrics 项目新增三张维度表：
- `metrics_repos` - 仓库维度主表
- `metrics_contributors` - 作者维度主表
- `metrics_repo_contributors` - 仓库作者关联表

这些表用于记录仓库和作者的累计代码统计信息，支持从多个维度展示 AI 代码使用情况。

## 设计目标

1. 建立仓库和作者两个独立维度主表，便于查询和统计
2. 记录累计的 AI 代码量和人类代码量
3. 使用定时任务定期更新统计数据
4. 提供清晰的 API 接口供前端使用

## 数据表结构

### metrics_repos - 仓库维度主表

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | INTEGER | 是 | 主键，自增 |
| repo_id | TEXT | 是 | 仓库唯一标识 |
| repo_name | TEXT | 是 | 仓库名称 |
| repo_url | TEXT | 是 | 仓库 URL |
| provider_type | TEXT | 否 | 代码托管商类型 |
| branch | TEXT | 否 | 主要统计分支 |
| total_lines | INTEGER | 是 | 累计总代码行数 |
| ai_lines | INTEGER | 是 | 累计 AI 生成代码行数 |
| human_lines | INTEGER | 是 | 累计人类代码行数 |
| ai_percentage | REAL | 是 | 累计 AI 代码占比 |
| total_commits | INTEGER | 是 | 累计总提交数 |
| ai_commits | INTEGER | 是 | 累计包含 AI 的提交数 |
| tool_model_breakdown | TEXT (JSON) | 否 | 工具-模型使用分布统计 |
| first_commit_ts | INTEGER | 否 | 首次提交时间戳 |
| last_commit_ts | INTEGER | 否 | 最新提交时间戳 |
| created_at | INTEGER | 是 | 记录创建时间 |
| updated_at | INTEGER | 是 | 记录更新时间 |

**索引：**
- `idx_repos_repo_id` - on `(repo_id)`
- `idx_repos_repo_name` - on `(repo_name)`

**约束：**
- `UNIQUE(repo_id)`

### metrics_contributors - 作者维度主表

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | INTEGER | 是 | 主键，自增 |
| author | TEXT | 是 | 作者唯一标识 |
| author_email | TEXT | 否 | 作者邮箱 |
| total_lines | INTEGER | 是 | 累计总代码行数 |
| ai_lines | INTEGER | 是 | 累计 AI 生成代码行数 |
| human_lines | INTEGER | 是 | 累计人类代码行数 |
| ai_percentage | REAL | 是 | 累计 AI 代码占比 |
| total_commits | INTEGER | 是 | 累计总提交数 |
| ai_commits | INTEGER | 是 | 累计包含 AI 的提交数 |
| tool_model_breakdown | TEXT (JSON) | 否 | 工具-模型使用分布统计 |
| first_commit_ts | INTEGER | 否 | 首次提交时间戳 |
| last_commit_ts | INTEGER | 否 | 最新提交时间戳 |
| repos_count | INTEGER | 是 | 参与仓库数量 |
| created_at | INTEGER | 是 | 记录创建时间 |
| updated_at | INTEGER | 是 | 记录更新时间 |

**索引：**
- `idx_contributors_author` - on `(author)`
- `idx_contributors_author_email` - on `(author_email)`

**约束：**
- `UNIQUE(author)`

### metrics_repo_contributors - 仓库作者关联表

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | INTEGER | 是 | 主键，自增 |
| repo_id | TEXT | 是 | 仓库唯一标识 |
| author | TEXT | 是 | 作者唯一标识 |
| first_seen_ts | INTEGER | 否 | 首次发现时间 |
| last_seen_ts | INTEGER | 否 | 最后发现时间 |
| created_at | INTEGER | 是 | 记录创建时间 |
| updated_at | INTEGER | 是 | 记录更新时间 |

**索引：**
- `idx_repo_contributors_repo_author` - on `(repo_id, author)` - 唯一约束

**约束：**
- `UNIQUE(repo_id, author)`

## 表关系

```
metrics_repos (1) ←→ (N) metrics_repo_contributors ←→ (1) metrics_contributors
```

- 一个仓库可以有多个作者
- 一个作者可以参与多个仓库
- 关联表仅记录关系，不保存统计信息

## 数据模型定义

### MetricsRepo

```python
@dataclass_json
@dataclass
class MetricsRepo:
    """仓库维度主表 - 记录仓库的累计代码统计信息"""
    # === 仓库识别信息 ===
    repo_id: str  # 仓库唯一标识，如 owner/repo 或项目的唯一ID
    repo_name: str  # 仓库名称，用于展示
    repo_url: str  # 仓库的完整URL地址
    provider_type: Optional[str] = None  # 代码托管商类型，如 github/gitea/gitlab
    branch: Optional[str] = None  # 主要统计分支名称

    # === 代码量统计 ===
    total_lines: int = 0  # 累计总代码行数（人类+AI）
    ai_lines: int = 0  # 累计AI生成的代码行数
    human_lines: int = 0  # 累计人类手动编写的代码行数
    ai_percentage: float = 0.0  # AI代码占比百分比 (ai_lines / total_lines * 100)

    # === 提交统计 ===
    total_commits: int = 0  # 累计总提交次数
    ai_commits: int = 0  # 累计包含AI生成的提交次数

    # === 工具模型分布 ===
    tool_model_breakdown: Optional[str] = None  # JSON字符串，记录不同工具和模型的代码贡献分布

    # === 时间范围 ===
    first_commit_ts: Optional[int] = None  # 首次提交的Unix时间戳
    last_commit_ts: Optional[int] = None  # 最新提交的Unix时间戳

    # === 元数据 ===
    created_at: int = 0  # 记录创建时间
    updated_at: int = 0  # 记录更新时间
```

### MetricsContributor

```python
@dataclass_json
@dataclass
class MetricsContributor:
    """作者维度主表 - 记录作者的累计代码统计信息"""
    # === 作者识别信息 ===
    author: str  # 作者唯一标识
    author_email: Optional[str] = None  # 作者邮箱

    # === 代码量统计 ===
    total_lines: int = 0  # 累计总代码行数
    ai_lines: int = 0  # 累计AI生成的代码行数
    human_lines: int = 0  # 累计人类代码行数
    ai_percentage: float = 0.0  # AI代码占比

    # === 提交统计 ===
    total_commits: int = 0  # 累计总提交次数
    ai_commits: int = 0  # 累计包含AI的提交次数

    # === 工具模型分布 ===
    tool_model_breakdown: Optional[str] = None  # 工具模型分布

    # === 时间范围 ===
    first_commit_ts: Optional[int] = None  # 首次提交时间戳
    last_commit_ts: Optional[int] = None  # 最新提交时间戳

    # === 活动范围 ===
    repos_count: int = 0  # 参与仓库数量

    # === 元数据 ===
    created_at: int = 0  # 记录创建时间
    updated_at: int = 0  # 记录更新时间
```

### MetricsRepoContributor

```python
@dataclass_json
@dataclass
class MetricsRepoContributor:
    """仓库作者关联表 - 仅记录仓库与作者的关联关系"""
    # === 关联信息 ===
    repo_id: str  # 仓库唯一标识
    author: str  # 作者唯一标识

    # === 时间信息 ===
    first_seen_ts: Optional[int] = None  # 首次发现时间
    last_seen_ts: Optional[int] = None  # 最后发现时间

    # === 元数据 ===
    created_at: int = 0  # 记录创建时间
    updated_at: int = 0  # 记录更新时间
```

## 数据更新流程

### 调度任务设计

**任务名称：** `update_repo_contributor_stats`

**执行周期：** 每天执行一次（可通过配置调整）

### 处理逻辑

1. **数据范围**：获取自上次更新以来新增的 Committed 事件

2. **仓库统计聚合**：
   - 按 `repo_url` 分组
   - 计算总代码量：`git_diff_added_lines + git_diff_deleted_lines`
   - 解析 `total_ai_additions` 和 `total_ai_deletions` 获取 AI 代码量
   - human_lines = total_lines - ai_lines
   - 统计总提交数和包含 AI 的提交数
   - 汇总 tool_model_pairs 工具模型分布
   - 记录首次和最后提交时间

3. **作者统计聚合**：
   - 按 `author` 分组
   - 与仓库统计相同的计算逻辑
   - 额外统计涉及的仓库数量

4. **关联表更新**：
   - 记录每个仓库-作者组合
   - 更新首次和最后发现时间

5. **更新策略**：
   - 使用 UPSERT（INSERT OR REPLACE）保证记录唯一性
   - 更新 `updated_at` 时间戳

## API 设计

### 路由前缀

统一使用 `/api/dimensions` 作为路由前缀，创建新的蓝图 `dimensions_bp`。

### 仓库相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dimensions/repos` | 获取仓库列表，支持分页和筛选 |
| GET | `/api/dimensions/repos/:repo_id` | 获取单个仓库详情 |
| GET | `/api/dimensions/repos/:repo_id/contributors` | 获取指定仓库的所有作者 |
| POST | `/api/dimensions/repos/sync` | 手动触发仓库统计更新 |

### 作者相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dimensions/contributors` | 获取作者列表，支持分页和筛选 |
| GET | `/api/dimensions/contributors/:author` | 获取单个作者详情 |
| GET | `/api/dimensions/contributors/:author/repos` | 获取指定作者参与的所有仓库 |
| POST | `/api/dimensions/contributors/sync` | 手动触发作者统计更新 |

### 关联相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dimensions/repo-contributors` | 获取仓库作者关联列表 |
| POST | `/api/dimensions/repo-contributors/sync` | 手动触发关联表更新 |

### 查询参数

**仓库列表：**
- `page`: 页码，默认 1
- `page_size`: 每页数量，默认 20
- `sort`: 排序字段（total_lines/ai_lines/ai_percentage/total_commits 等）

**作者列表：**
- `page`: 页码
- `page_size`: 每页数量
- `sort`: 排序字段

### 响应数据格式

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

## 工具模型分布 JSON 格式

tool_model_breakdown 字段使用 JSON 格式存储：

```json
{
  "claude-opus-4-6": {
    "total_lines": 1500,
    "total_commits": 10
  },
  "gpt-4-turbo": {
    "total_lines": 800,
    "total_commits": 5
  }
}
```

## 后续工作

本设计文档已完成，需要通过 writing-plans 技能创建详细的实现计划。

## 参考资料

- Git-AI Metrics API 文档
- 现有数据库表结构：`sql/metrics_schema_sqlite.sql`
- 现有数据模型：`core/models/metrics.py`
