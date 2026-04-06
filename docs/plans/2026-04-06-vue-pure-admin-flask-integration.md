# Vue-Pure-Admin 与 Flask 后端对接实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 配置 vue-pure-admin 前端与 Flask 后端（8888端口）的开发和生产环境对接

**Architecture:** 使用 Vite 开发代理在开发环境自动转发 API 请求到 Flask 后端，生产环境通过环境变量配置后端地址。保留 vue-pure-admin 的 mock 认证系统，仅对接统计数据 API。

**Tech Stack:** Vue 3, Vite, TypeScript, Axios, Flask

---

## Task 1: 配置环境变量

**Files:**
- Modify: `frontend/.env.development`
- Modify: `frontend/.env.production`

**Step 1: 添加开发环境 API 配置**

编辑 `frontend/.env.development`，在文件末尾添加：

```bash
# 后端 API 地址（开发环境通过 proxy 代理，配置为空）
VITE_API_BASE_URL = ""
```

**Step 2: 添加生产环境 API 配置**

编辑 `frontend/.env.production`，在文件末尾添加：

```bash
# 后端 API 地址（生产环境配置实际后端地址）
VITE_API_BASE_URL = "http://localhost:8888"
```

**Step 3: 验证配置**

检查两个文件确保配置正确添加：

```bash
cat frontend/.env.development | grep VITE_API_BASE_URL
cat frontend/.env.production | grep VITE_API_BASE_URL
```

Expected: 两个命令都能输出对应的配置行

**Step 4: 提交更改**

```bash
git add frontend/.env.development frontend/.env.production
git commit -m "config: 添加前端 API 地址环境变量配置"
```

---

## Task 2: 配置 Vite 开发代理

**Files:**
- Modify: `frontend/vite.config.ts:22-32`

**Step 1: 读取当前 server 配置**

查看 `frontend/vite.config.ts` 中的 server 配置块（约第 22-32 行）：

```bash
cat frontend/vite.config.ts | grep -A 10 "server:"
```

**Step 2: 添加 proxy 配置**

在 `server` 配置对象中，`host: "0.0.0.0"` 之后，`warmup` 之前添加 proxy 配置：

```typescript
server: {
  // 端口号
  port: VITE_PORT,
  host: "0.0.0.0",
  // 本地跨域代理 https://cn.vitejs.dev/config/server-options.html#server-proxy
  proxy: {
    "/api": {
      target: "http://localhost:8888",
      changeOrigin: true,
      rewrite: (path) => path
    }
  },
  // 预热文件以提前转换和缓存结果，降低启动期间的初始页面加载时长并防止转换瀑布
  warmup: {
    clientFiles: ["./index.html", "./src/{views,components}/*"]
  }
}
```

**关键点:**
- `target`: Flask 后端地址 `http://localhost:8888`
- `changeOrigin: true`: 修改请求头中的 origin
- `rewrite: (path) => path`: 保持路径不变，不做重写

**Step 3: 验证语法**

运行 TypeScript 类型检查：

```bash
cd frontend && pnpm typecheck
```

Expected: 无类型错误

**Step 4: 提交更改**

```bash
git add frontend/vite.config.ts
git commit -m "config: 配置 Vite 开发代理转发 API 请求到 Flask 后端"
```

---

## Task 3: 创建统计数据 API 模块

**Files:**
- Create: `frontend/src/api/stats.ts`

**Step 1: 创建 API 文件**

创建 `frontend/src/api/stats.ts` 文件，包含完整的类型定义和 API 函数：

```typescript
import { http } from "@/utils/http";

// 整体统计响应类型
export type StatsResult = {
  code: number;
  message: string;
  data: {
    ai_generated_lines: number;
    ai_accepted_lines: number;
    human_lines: number;
    ai_percentage: number;
    total_lines: number;
  };
};

// 仓库统计响应类型
export type RepoStatsResult = {
  code: number;
  message: string;
  data: {
    items: Array<{
      repo_path: string;
      ai_accepted_lines: number;
      human_lines: number;
      ai_percentage: number;
    }>;
    total: number;
    page: number;
    page_size: number;
  };
};

// 贡献者统计响应类型
export type ContributorStatsResult = {
  code: number;
  message: string;
  data: {
    items: Array<{
      contributor: string;
      ai_accepted_lines: number;
      human_lines: number;
      ai_percentage: number;
    }>;
    total: number;
    page: number;
    page_size: number;
  };
};

/** 获取整体统计数据 */
export const getOverallStats = () => {
  return http.request<StatsResult>("get", "/api/stats/overall");
};

/** 获取仓库统计列表 */
export const getRepoStats = (params?: { page?: number; page_size?: number }) => {
  return http.request<RepoStatsResult>("get", "/api/stats/repos", { params });
};

/** 获取贡献者统计列表 */
export const getContributorStats = (params?: { page?: number; page_size?: number }) => {
  return http.request<ContributorStatsResult>("get", "/api/stats/contributors", { params });
};
```

**Step 2: 验证语法**

运行 TypeScript 类型检查：

```bash
cd frontend && pnpm typecheck
```

Expected: 无类型错误

**Step 3: 提交更改**

```bash
git add frontend/src/api/stats.ts
git commit -m "feat: 添加统计数据 API 模块"
```

---

## Task 4: 增强响应拦截器错误处理

**Files:**
- Modify: `frontend/src/utils/http/index.ts:124-148`

**Step 1: 定位响应拦截器**

查看 `frontend/src/utils/http/index.ts` 中的 `httpInterceptorsResponse` 方法（约第 124-148 行）

**Step 2: 增强错误处理逻辑**

在响应拦截器的 error 处理部分，替换现有的错误处理逻辑：

找到这段代码：
```typescript
(error: PureHttpError) => {
  const $error = error;
  $error.isCancelRequest = Axios.isCancel($error);
  // 所有的响应异常 区分来源为取消请求/非取消请求
  return Promise.reject($error);
}
```

替换为：
```typescript
(error: PureHttpError) => {
  const $error = error;
  $error.isCancelRequest = Axios.isCancel($error);
  
  // 统一错误处理
  if (error.response) {
    const status = error.response.status;
    if (status === 404) {
      message("API 接口不存在", { type: "error" });
    } else if (status === 500) {
      message("服务器错误", { type: "error" });
    }
  } else if (error.request) {
    message("网络连接失败，请检查后端服务是否启动", { type: "error" });
  }
  
  // 所有的响应异常 区分来源为取消请求/非取消请求
  return Promise.reject($error);
}
```

**Step 3: 验证语法**

运行 TypeScript 类型检查：

```bash
cd frontend && pnpm typecheck
```

Expected: 无类型错误

**Step 4: 提交更改**

```bash
git add frontend/src/utils/http/index.ts
git commit -m "feat: 增强 HTTP 响应拦截器错误处理"
```

---

## Task 5: 端到端测试验证

**Files:**
- Test: 手动测试前后端对接

**Step 1: 启动 Flask 后端**

在项目根目录启动后端服务：

```bash
python app.py
```

Expected: 输出显示服务运行在 `http://localhost:8888`

**Step 2: 启动前端开发服务**

在新终端窗口启动前端：

```bash
cd frontend && pnpm dev
```

Expected: 输出显示服务运行在 `http://localhost:8848`

**Step 3: 测试 API 代理**

在浏览器打开开发者工具，访问 `http://localhost:8848`

在控制台执行测试请求：

```javascript
fetch('/api/stats/overall')
  .then(r => r.json())
  .then(d => console.log('API Response:', d))
  .catch(e => console.error('API Error:', e))
```

Expected: 
- Network 面板显示请求到 `/api/stats/overall`
- 请求成功返回 200 状态码
- 控制台输出 Flask 返回的统计数据

**Step 4: 验证错误处理**

停止 Flask 后端服务，在浏览器控制台再次执行上述请求：

Expected: 页面右上角显示错误提示 "网络连接失败，请检查后端服务是否启动"

**Step 5: 测试生产构建**

重新启动 Flask 后端，然后构建前端：

```bash
cd frontend && pnpm build
```

Expected: 
- 构建成功，生成 `frontend/dist` 目录
- 无构建错误或警告

**Step 6: 测试生产部署**

访问 `http://localhost:8888`（Flask 托管前端静态文件）

Expected:
- 能看到前端页面
- API 请求能正常工作

**Step 7: 创建验证文档**

创建 `docs/verification-checklist.md` 记录验证结果：

```markdown
# Vue-Pure-Admin 与 Flask 对接验证清单

## 开发环境验证 (2026-04-06)

- [x] 前端能正常启动在 8848 端口
- [x] 后端能正常启动在 8888 端口
- [x] 浏览器控制台 Network 显示 `/api/stats` 请求成功
- [x] API 代理正常工作，请求被转发到后端
- [x] 错误处理正常，后端停止时显示友好提示

## 生产环境验证 (2026-04-06)

- [x] 前端构建成功，dist 目录生成
- [x] Flask 能正确托管静态文件
- [x] 访问根路径能看到前端页面
- [x] API 请求能正常响应

## 测试人员

- 测试人: [Your Name]
- 测试日期: 2026-04-06
```

**Step 8: 提交验证文档**

```bash
git add docs/verification-checklist.md
git commit -m "docs: 添加前后端对接验证清单"
```

---

## 完成标准

所有任务完成后，应该达到以下状态：

1. ✅ 环境变量配置完成（开发和生产）
2. ✅ Vite 代理配置完成，开发环境自动转发 API 请求
3. ✅ 统计数据 API 模块创建完成，类型定义清晰
4. ✅ HTTP 错误处理增强，提供友好的错误提示
5. ✅ 端到端测试通过，前后端能正常通信
6. ✅ 生产构建成功，Flask 能托管前端静态文件

## 后续扩展

如需对接更多 API（如 Metrics API、Git-AI API），只需：

1. 在 `vite.config.ts` 的 proxy 中添加对应路径（如 `/worker`）
2. 在 `src/api/` 下创建对应的 API 模块
3. 定义类型并实现 API 函数

## 注意事项

- 开发时必须同时启动前后端服务
- 生产环境需要正确配置 `VITE_API_BASE_URL`
- 确保 Flask API 返回的 JSON 格式符合前端类型定义
- 如遇到 CORS 问题，检查 Vite proxy 配置是否正确
