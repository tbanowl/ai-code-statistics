# Git AI 统计工具 - Vue 前端重构设计文档

**日期：** 2026-03-12
**版本：** 1.0.0
**作者：** Claude Code
**状态：** ✅ 已完成

## 1. 概述

将现有单体 `index.html` 重构为 **Vue 3 + Vite + Tailwind CSS** 项目，提升代码可维护性和开发体验。

### 目标

- 将纯 HTML/JS 前端拆分为可复用的 Vue 组件
- 保持现有设计风格和 UI 体验
- 更新 API 调用以适配新的后端接口规范

---

## 2. 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3 (Composition API) |
| 构建工具 | Vite 5 |
| 样式 | Tailwind CSS 3 |
| 日期选择 | Flatpickr |
| 图标 | Lucide |
| HTTP | fetch API |

---

## 3. 项目结构

```
frontend/
├── index.html                 # 入口 HTML
├── package.json               # 依赖配置
├── vite.config.js            # Vite 配置
├── tailwind.config.js         # Tailwind 配置
├── postcss.config.js          # PostCSS 配置
│
├── public/
│   └── favicon.ico
│
└── src/
    ├── main.js                # 应用入口
    ├── App.vue                # 主组件（包含所有功能）
    │
    └── assets/
        └── styles/
            └── main.css       # 全局样式（滚动条等）
```

> **说明**：原计划中的独立组件（DepartmentSelector、RepositoryList、StatsOverview、RepoDetails）已合并到 App.vue 中实现，简化了项目结构和状态管理。

---

## 4. 组件设计

### 4.1 App.vue（主组件 - 实际实现）

**职责：** 页面布局、日期选择、部门选择、仓库列表、统计分析、结果展示

**State：**
```js
{
  allReposData: null,        // 仓库和部门完整数据
  selectedDepartments: Set(), // 选中的部门列表
  startDatePicker: null,      // 开始日期选择器实例
  endDatePicker: null,        // 结束日期选择器实例
  loading: false,             // 加载状态
  statsResult: null,          // 统计分析结果
  expandedRepos: Set(),       // 展开的仓库详情索引
  commitSearchTexts: {},      // Commit 搜索文本
  toast: { show, message, type } // Toast 通知状态
}
```

**关键逻辑：**
- 页面初始化：调用 `GET /api/v1/projects/` 加载数据
- 部门选择：支持多选，动态更新仓库列表
- 日期联动：start/end 日期选择器约束逻辑
- 分析按钮：调用 `POST /api/v1/stats/analyze`
- 结果展示：
  - 总体统计卡片
  - 各仓库详情（可展开/折叠）
  - Commit 详细列表（支持搜索过滤）

---

## 5. 数据流

### 5.1 全局状态（App.vue）

```js
export default {
  data() {
    return {
      allReposData: null,        // API: GET /api/v1/projects/
      selectedDepartments: new Set(), // 用户选择
      statsResult: null,         // API: POST /api/v1/stats/analyze
      loading: false,
    }
  }
}
```

### 5.2 API 映射

| 原接口 | 新接口 | 方法 | 返回格式 |
|--------|--------|------|----------|
| `/git-ai-stats/repos` | `GET /api/v1/projects/` | GET | `{success: true, data: {...}}` |
| `/git-ai-stats/analyze` | `POST /api/v1/stats/analyze` | POST | `{success: true, data: {...}}` |

**请求载荷示例：**
```json
{
  "start_date": "2026-03-05T00:00:00.000Z",
  "end_date": "2026-03-12T00:00:00.000Z",
  "departments": ["前端", "后端"]
}
```

---

## 6. 样式与依赖

### 6.1 package.json

```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "flatpickr": "^4.6.13",
    "lucide": "^0.400.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

### 6.2 样式迁移

- 保留 `index.html` 中所有自定义 CSS（变量、滚动条、动画等）
- Flatpickr 相关样式通过 CDN 加载
- Lucide Icons 在组件 `onMounted` 时调用 `lucide.createIcons()`

---

## 7. 错误处理

| 场景 | 处理方式 |
|------|---------|
| 无部门配置 | 显示提示，直接展示所有仓库 |
| 未选择部门 | Toast 提示，阻止统计分析 |
| API 失败 | Toast 显示错误信息 |
| 无搜索结果 | 显示"未找到匹配的提交记录" |
| 日期选择无效 | Toast 提示，禁用分析按钮 |

---

## 8. 实施进度

### ✅ 已完成

1. ✅ 创建前端项目基础结构（package.json、vite.config.js、tailwind.config.js 等）
2. ✅ 配置 Tailwind CSS 和 PostCSS
3. ✅ 创建全局样式文件
4. ✅ 实现 App.vue 主组件（包含所有功能）
5. ✅ 实现 API 调用和数据处理
6. ✅ 实现部门选择和仓库列表展示
7. ✅ 实现日期选择（Flatpickr）和联动逻辑
8. ✅ 实现统计分析和结果展示
9. ✅ 实现 Commit 详细列表和搜索过滤
10. ✅ 实现 Toast 通知和加载状态
11. ✅ 配置 Vite API 代理
12. ✅ 安装依赖并测试运行
13. ✅ 端到端测试通过

---

## 9. 使用说明

### 开发环境

```bash
# 启动后端（端口 8888）
python app.py

# 启动前端开发服务器（端口 3000）
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000` 查看应用。

### 生产构建

```bash
cd frontend
npm run build
```

构建产物位于 `frontend/dist/` 目录。

---

## 10. API 接口说明

### GET /api/v1/projects/

获取项目列表，按部门分组。

**响应示例：**
```json
{
  "success": true,
  "data": {
    "departments": ["前端", "后端"],
    "repos_by_department": {
      "前端": [{"id": "111", "name": "web-app", "branch": "main"}],
      "后端": [{"id": "222", "name": "api-server", "branch": "master"}]
    },
    "all_repos": [...]
  }
}
```

### POST /api/v1/stats/analyze

执行统计分析。

**请求体：**
```json
{
  "start_date": "2026-03-05T00:00:00.000Z",
  "end_date": "2026-03-12T00:00:00.000Z",
  "departments": ["前端"]
}
```

**响应示例：**
```json
{
  "success": true,
  "data": {
    "overall_percentage": 45.2,
    "total_lines": 15000,
    "total_ai_lines": 6780,
    "total_commits": 120,
    "commits_with_ai": 55,
    "repo_details": [...]
  }
}
```

---

## 11. 后续优化建议

1. **组件拆分**：如果项目规模扩大，可以将 App.vue 中的功能拆分为独立组件
2. **状态管理**：考虑使用 Pinia 进行更复杂的状态管理
3. **类型支持**：添加 TypeScript 支持
4. **测试**：添加单元测试和 E2E 测试
5. **国际化**：添加多语言支持
6. **主题切换**：支持亮色/暗色主题切换

---

**重构完成日期：** 2026-03-12
**测试状态：** ✅ 通过
