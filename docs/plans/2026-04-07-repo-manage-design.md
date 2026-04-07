# 仓库管理模块设计文档

**日期**: 2026-04-07  
**方案**: A（抽屉式管理型）

## 目标

在现有动态菜单体系下新增「仓库管理」父级菜单，包含两个子菜单：仓库列表、SSH Key 管理。

## 菜单结构

```
仓库管理（parent, path=/repo-manage, icon=ri:git-repository-line, rank=2）
├── 仓库列表（path=/repo-manage/list, component=repo-manage/list/index）
└── SSH Key 管理（path=/repo-manage/ssh-key, component=repo-manage/ssh-key/index）
```

菜单记录追加到 `system_db.py` 的 `init_default_data`（仅首次初始化时插入）。

## 页面设计

### 仓库列表页

- 搜索栏：仓库地址关键词 + 搜索/重置
- 表格列：仓库名称、仓库地址、统计开关（toggle）、已绑定 SSH Key、操作
- 操作：「分支配置」「贡献者」「绑定 SSH Key」
  - 分支配置 → 右侧抽屉，展示 `stats_repo_branch_config` 列表（只读）
  - 贡献者 → 右侧抽屉，展示贡献者统计表
  - 绑定 SSH Key → 弹窗，下拉选择 + 确认

### SSH Key 管理页

- 顶部「新增 SSH Key」按钮
- 表格列：Key 名称、公钥（截断）、创建时间、删除操作
- 新增弹窗：Key 名称、公钥、私钥

## 接口

| 接口 | 状态 |
|------|------|
| `GET /api/stats/repositories` | 已有 |
| `PUT /api/stats-repo/<id>/stats-flag` | 已有 |
| `GET /api/stats-repo/<id>/ssh-status` | 已有 |
| `PUT /api/stats-repo/<id>/ssh-key` | 已有 |
| `GET /api/stats-repo/blame/repo/<id>/contributors` | 已有 |
| `GET /api/stats-repo/ssh-keys` | 已有 |
| `POST /api/stats-repo/ssh-key` | 已有 |
| `DELETE /api/stats-repo/ssh-key/<id>` | 已有 |
| `GET /api/stats-repo/<id>/branch-configs` | **新增**（路由，DB 方法已有） |

## 文件变更

**新增：**
- `frontend/src/views/repo-manage/list/index.vue`
- `frontend/src/views/repo-manage/ssh-key/index.vue`
- `frontend/src/api/repo.ts`

**修改：**
- `api/routes/stats_repo.py` — 新增 `GET /<repo_id>/branch-configs` 路由
- `core/database/system_db.py` — `init_default_data` 追加菜单记录
