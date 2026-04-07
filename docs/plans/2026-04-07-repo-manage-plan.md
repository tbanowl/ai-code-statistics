# 仓库管理模块实现计划

**设计文档**: docs/plans/2026-04-07-repo-manage-design.md  
**日期**: 2026-04-07

## 任务列表

### Task 1: 后端 — 新增 branch-configs 路由
**文件**: `api/routes/stats_repo.py`  
**改动**: 在文件末尾追加一个路由 `GET /api/stats-repo/<repo_id>/branch-configs`，调用已有的 `BlameStatsDatabase.get_repo_branch_configs(repo_id)`，返回 `{success, data: {configs, count}}`。

### Task 2: 后端 — 菜单初始化数据
**文件**: `core/database/system_db.py`  
**改动**: 在 `init_default_data` 中，在现有系统管理菜单之后追加「仓库管理」父菜单及两个子菜单记录，并将其 menu_id 加入 admin 角色权限。

```
仓库管理: parent_id=0, path=/repo-manage, icon=ri:git-repository-line, rank=2
  仓库列表: path=/repo-manage/list, component=repo-manage/list/index, rank=1
  SSH Key 管理: path=/repo-manage/ssh-key, component=repo-manage/ssh-key/index, rank=2
```

### Task 3: 前端 — API 模块
**文件**: `frontend/src/api/repo.ts`（新建）  
**内容**: 封装以下请求函数：
- `getRepoList(params)` → `GET /api/stats/repositories`
- `getRepoBranchConfigs(repoId)` → `GET /api/stats-repo/<repoId>/branch-configs`
- `getRepoContributors(repoId)` → `GET /api/stats-repo/blame/repo/<repoId>/contributors`
- `updateRepoSshKey(repoId, sshKeyId)` → `PUT /api/stats-repo/<repoId>/ssh-key`
- `updateRepoStatsFlag(repoId, flag)` → `PUT /api/stats-repo/<repoId>/stats-flag`
- `getSshKeys()` → `GET /api/stats-repo/ssh-keys`
- `addSshKey(data)` → `POST /api/stats-repo/ssh-key`
- `deleteSshKey(keyId)` → `DELETE /api/stats-repo/ssh-key/<keyId>`

### Task 4: 前端 — 仓库列表页
**文件**: `frontend/src/views/repo-manage/list/index.vue`（新建）  
**结构**:
- `<script setup>`: 搜索表单 ref、分页、表格数据、抽屉/弹窗状态
- 搜索栏：keyword 输入 + 搜索/重置
- `PureTableBar` + `pure-table`，列：仓库名、仓库地址、统计开关（el-switch）、SSH Key 名、操作
- 操作列三个按钮：分支配置、贡献者、绑定 SSH Key
- 分支配置抽屉：`el-drawer` + `el-table` 展示 branch_pattern/pattern_type/enabled
- 贡献者抽屉：`el-drawer` + `el-table` 展示贡献者统计
- 绑定 SSH Key 弹窗：`el-dialog` + `el-select`（选项来自 getSshKeys）+ 确认调用 updateRepoSshKey

### Task 5: 前端 — SSH Key 管理页
**文件**: `frontend/src/views/repo-manage/ssh-key/index.vue`（新建）  
**结构**:
- `PureTableBar` + `pure-table`，列：Key 名称、公钥（截断 40 字符）、创建时间、删除
- 顶部「新增 SSH Key」按钮
- 新增弹窗：key_name（必填）、public_key（textarea）、private_key（textarea 必填）
- 删除：`el-popconfirm` 二次确认

## 执行顺序

1 → 2 → 3 → 4 → 5（后端先行，前端依赖 API 模块）

## 注意事项

- 菜单初始化仅在数据库为空时执行（`init_default_data` 有 early return 保护），已有数据的环境需手动在菜单管理页添加
- `pure-table` / `PureTableBar` 用法参考 `frontend/src/views/system/user/index.vue`
- 图标用 `ri:git-repository-line`（已在 `frontend/src/components/ReIcon/data.ts` 中存在）
