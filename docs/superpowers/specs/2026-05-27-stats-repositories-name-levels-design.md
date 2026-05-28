# stats_repositories 仓库路径层级字段设计

## 目标

为 `stats_repositories` 表增加仓库路径层级字段，便于按组织/部门/项目层级聚合仓库统计数据。字段从归一化后的 `repo_path` 中解析并在仓库维表记录上持久化。

## 字段

在 `StatsRepository` / `stats_repositories` 增加以下可空字段，数据库类型均为 `VARCHAR(50)`：

- `name_level1`
- `name_level2`
- `name_level3`
- `name_level4`
- `name_level5`
- `repo_short_name`

## 解析规则

先使用既有 `normalize_repo_url()` 将仓库地址归一化为 `host/path`，再复用 `StatsDatabase._extract_repo_name()` 去掉域名，得到路径段数组。

示例：`github.com/L5/L4/L3/L2/L1/R1/R2` 去掉域名后为 `L5/L4/L3/L2/L1/R1/R2`。

当路径段数大于或等于 5：

- 前 5 段作为层级来源，按反向关系写入：`name_level1=L1`、`name_level2=L2`、`name_level3=L3`、`name_level4=L4`、`name_level5=L5`
- 第 6 段及之后用 `/` 拼接为 `repo_short_name`，例如 `R1/R2`；如果正好 5 段，`repo_short_name` 保持 `NULL`

当路径段数小于 5：

- 固定最后一段为 `repo_short_name`
- 之前的段从 `name_level1` 开始顺序填充
- 缺失字段保持 `NULL`

示例：`github.com/org/team/repo` 得到 `name_level1=org`、`name_level2=team`、`repo_short_name=repo`。

## 写入位置

`StatsDatabase.get_or_create_repository()` 是仓库维表的集中创建入口。新建仓库时写入层级字段；已存在仓库再次被访问时刷新层级字段，使旧数据可随业务访问逐步补齐。

## 数据库脚本

- 新库：更新 `sql/metrics_schema_mysql.sql`
- 旧库：新增 `sql/stats_repositories_name_levels_migration_mysql.sql`，使用 `ALTER TABLE` 添加字段并回填已有记录

## 验证

新增 `tests/unit/test_database/test_sqlite.py` 覆盖：

- 多于 5 段路径的层级反向映射与多段 `repo_short_name`
- 多于 5 段路径但只有单段短名的映射
- 小于 5 段路径的顺序填充与缺失字段为 `NULL`
