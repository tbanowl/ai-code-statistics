# stats_repositories 仓库路径层级字段 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `stats_repositories` 增加仓库路径层级字段，并在仓库维表创建/刷新时从 `repo_path` 解析填充。

**Architecture:** 在 ORM 模型上增加可空字符串字段；在 `StatsDatabase` 中新增小型解析函数并由 `get_or_create_repository()` 调用。SQL 建表脚本和 MySQL 迁移脚本同步字段定义。

**Tech Stack:** Python 3.10、SQLAlchemy 2.0、pytest、MySQL DDL。

---

### Task 1: 用测试锁定解析行为

**Files:**
- Modify: `tests/unit/test_database/test_sqlite.py`

- [x] **Step 1: 写多段路径失败测试**

```python
def test_get_or_create_repository_extracts_deep_path_levels(stats_db):
    repo_id = stats_db.get_or_create_repository("github.com/L5/L4/L3/L2/L1/R1/R2")

    repo = stats_db.get_repository_by_id(repo_id)

    assert repo["repo_path"] == "github.com/L5/L4/L3/L2/L1/R1/R2"
    assert repo["name_level1"] == "L1"
    assert repo["name_level2"] == "L2"
    assert repo["name_level3"] == "L3"
    assert repo["name_level4"] == "L4"
    assert repo["name_level5"] == "L5"
    assert repo["repo_short_name"] == "R1/R2"
```

- [x] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_database/test_sqlite.py::test_get_or_create_repository_extracts_deep_path_levels -q`
Expected: FAIL，原因是 `name_level1` 字段不存在。

- [x] **Step 3: 写短路径失败测试**

```python
def test_get_or_create_repository_extracts_short_path_levels(stats_db):
    repo_id = stats_db.get_or_create_repository("https://github.com/org/team/repo.git")

    repo = stats_db.get_repository_by_id(repo_id)

    assert repo["repo_path"] == "github.com/org/team/repo"
    assert repo["name_level1"] == "org"
    assert repo["name_level2"] == "team"
    assert repo["name_level3"] is None
    assert repo["name_level4"] is None
    assert repo["name_level5"] is None
    assert repo["repo_short_name"] == "repo"
```

- [x] **Step 4: 写 5 层 + 单短名测试**

```python
def test_get_or_create_repository_extracts_single_segment_short_name_after_five_levels(stats_db):
    repo_id = stats_db.get_or_create_repository("github.com/L5/L4/L3/L2/L1/R1")

    repo = stats_db.get_repository_by_id(repo_id)

    assert repo["name_level1"] == "L1"
    assert repo["name_level2"] == "L2"
    assert repo["name_level3"] == "L3"
    assert repo["name_level4"] == "L4"
    assert repo["name_level5"] == "L5"
    assert repo["repo_short_name"] == "R1"
```

- [x] **Step 5: 写正好 5 段路径测试**

```python
def test_get_or_create_repository_extracts_exactly_five_levels(stats_db):
    repo_id = stats_db.get_or_create_repository("github.com/L5/L4/L3/L2/L1")

    repo = stats_db.get_repository_by_id(repo_id)

    assert repo["name_level1"] == "L1"
    assert repo["name_level2"] == "L2"
    assert repo["name_level3"] == "L3"
    assert repo["name_level4"] == "L4"
    assert repo["name_level5"] == "L5"
    assert repo["repo_short_name"] is None
```

- [x] **Step 6: 写旧记录回填测试**

```python
def test_get_or_create_repository_backfills_existing_repository_name_parts(stats_db):
    with session_scope(stats_db.engine) as session:
        session.add(
            StatsRepository(
                id="repoexisting0000001",
                repo_path="github.com/L5/L4/L3/L2/L1/R1/R2",
                repo_name="L5/L4/L3/L2/L1/R1/R2",
            )
        )

    repo_id = stats_db.get_or_create_repository("github.com/L5/L4/L3/L2/L1/R1/R2")

    repo = stats_db.get_repository_by_id(repo_id)

    assert repo_id == "repoexisting0000001"
    assert repo["name_level1"] == "L1"
    assert repo["name_level5"] == "L5"
    assert repo["repo_short_name"] == "R1/R2"
```

### Task 2: 实现 ORM 字段和解析逻辑

**Files:**
- Modify: `core/database/models.py`
- Modify: `core/database/stats_db.py`

- [x] **Step 1: 在 `StatsRepository` 增加字段**

```python
name_level1: Mapped[str] = mapped_column(String(50), nullable=True)
name_level2: Mapped[str] = mapped_column(String(50), nullable=True)
name_level3: Mapped[str] = mapped_column(String(50), nullable=True)
name_level4: Mapped[str] = mapped_column(String(50), nullable=True)
name_level5: Mapped[str] = mapped_column(String(50), nullable=True)
repo_short_name: Mapped[str] = mapped_column(String(50), nullable=True)
```

- [x] **Step 2: 新增 `_extract_repo_name_parts()`**

```python
@staticmethod
def _extract_repo_name_parts(repo_path: str) -> Dict[str, Optional[str]]:
    repo_name = StatsDatabase._extract_repo_name(repo_path)
    result = {
        "name_level1": None,
        "name_level2": None,
        "name_level3": None,
        "name_level4": None,
        "name_level5": None,
        "repo_short_name": None,
    }
    if not repo_name or repo_name == UNKNOWN_REPO:
        result["repo_short_name"] = repo_name
        return result

    parts = [part for part in repo_name.split("/") if part]
    if not parts:
        result["repo_short_name"] = UNKNOWN_REPO
        return result

    if len(parts) >= 5:
        level_parts = parts[:5]
        result["name_level1"] = level_parts[-1]
        result["name_level2"] = level_parts[-2]
        result["name_level3"] = level_parts[-3]
        result["name_level4"] = level_parts[-4]
        result["name_level5"] = level_parts[-5]
        result["repo_short_name"] = "/".join(parts[5:]) or None
        return result

    for index, part in enumerate(parts[:-1], start=1):
        result[f"name_level{index}"] = part
    result["repo_short_name"] = parts[-1]
    return result
```

- [x] **Step 3: 在 `get_or_create_repository()` 调用解析结果**

```python
name_parts = self._extract_repo_name_parts(normalized_path)
...
self._apply_repo_name_parts(row, name_parts)
...
record = StatsRepository(repo_path=normalized_path, repo_name=extracted_name, **name_parts)
```

### Task 3: 同步 SQL 脚本

**Files:**
- Modify: `sql/metrics_schema_mysql.sql`
- Create: `sql/stats_repositories_name_levels_migration_mysql.sql`

- [x] **Step 1: 在建表脚本添加字段**

```sql
name_level1 VARCHAR(50) COMMENT '仓库路径一级名称',
name_level2 VARCHAR(50) COMMENT '仓库路径二级名称',
name_level3 VARCHAR(50) COMMENT '仓库路径三级名称',
name_level4 VARCHAR(50) COMMENT '仓库路径四级名称',
name_level5 VARCHAR(50) COMMENT '仓库路径五级名称',
repo_short_name VARCHAR(50) COMMENT '仓库短名称',
```

- [x] **Step 2: 新增 MySQL 迁移脚本**

```sql
ALTER TABLE stats_repositories
    ADD COLUMN name_level1 VARCHAR(50) NULL COMMENT '仓库路径一级名称' AFTER repo_name,
    ADD COLUMN name_level2 VARCHAR(50) NULL COMMENT '仓库路径二级名称' AFTER name_level1,
    ADD COLUMN name_level3 VARCHAR(50) NULL COMMENT '仓库路径三级名称' AFTER name_level2,
    ADD COLUMN name_level4 VARCHAR(50) NULL COMMENT '仓库路径四级名称' AFTER name_level3,
    ADD COLUMN name_level5 VARCHAR(50) NULL COMMENT '仓库路径五级名称' AFTER name_level4,
    ADD COLUMN repo_short_name VARCHAR(50) NULL COMMENT '仓库短名称' AFTER name_level5;
```

- [x] **Step 3: 在迁移脚本中回填已有记录**

```sql
UPDATE stats_repositories AS repo
JOIN (...) AS parsed ON parsed.id = repo.id
SET
    name_level1 = CASE ... END,
    name_level2 = CASE ... END,
    name_level3 = CASE ... END,
    name_level4 = CASE ... END,
    name_level5 = CASE ... END,
    repo_short_name = CASE ... END;
```

### Task 4: 验证

**Files:**
- Test: `tests/unit/test_database/test_sqlite.py`
- Test: `tests/unit/test_models/test_stats.py`
- Test: `tests/unit/test_models/test_dimensions.py`

- [x] **Step 1: 运行相关测试**

Run: `pytest tests/unit/test_database/test_sqlite.py tests/unit/test_models/test_stats.py tests/unit/test_models/test_dimensions.py -q`
Expected: PASS。

- [x] **Step 2: 运行 LSP 诊断**

Run diagnostics on changed Python files.
Expected: no diagnostics。

- [x] **Step 3: 手工驱动 ORM 使用面**

Run a one-off Python script that creates an in-memory SQLite schema, calls `StatsDatabase.get_or_create_repository()` with `github.com/L5/L4/L3/L2/L1/R1/R2`, and prints `get_repository_by_id()`.
Expected: printed dictionary contains `name_level1=L1` and `repo_short_name=R1/R2`。
