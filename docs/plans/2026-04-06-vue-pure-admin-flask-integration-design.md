# Vue-Pure-Admin 与 Flask 后端对接设计文档

**日期**: 2026-04-06  
**状态**: 已批准  
**方案**: Vite 开发代理 + 环境变量配置

## 1. 项目背景

项目已将前端框架迁移到 vue-pure-admin，需要与现有的 Flask 后端（运行在 localhost:8888）进行对接。当前状态为完全未对接，需要建立前后端通信机制。

### 核心需求

- Flask 后端运行在 8888 端口
- 前端开发服务运行在 8848 端口
- 保留 vue-pure-admin 的 mock 认证系统
- 主要对接 `/api/stats` 统计数据 API
- 开发环境避免 CORS 问题
- 生产环境支持灵活部署

## 2. 整体架构

### 开发环境架构

```
前端 (localhost:8848) → Vite Proxy → Flask (localhost:8888)
                ↓
            /api/stats/* 请求被代理
```

### 生产环境架构

```
前端 (静态文件) → 直接请求 → Flask (配置的后端地址)
                ↓
            通过 VITE_API_BASE_URL 环境变量配置
```

### 数据流

1. **前端发起请求**: 组件调用 API 函数（如 `getOverallStats()`）
2. **Axios 拦截器**: 添加认证 token（如果需要）、处理请求头
3. **环境判断**:
   - 开发环境: 请求 `/api/stats` → Vite proxy 转发到 `http://localhost:8888/api/stats`
   - 生产环境: 请求 `${VITE_API_BASE_URL}/api/stats`
4. **Flask 处理**: 返回 JSON 数据
5. **响应拦截器**: 统一处理错误、格式化数据
6. **组件接收**: 更新 UI

## 3. 配置文件修改

### 3.1 环境变量配置

**`.env.development`** - 开发环境
```bash
# 平台本地运行端口号
VITE_PORT = 8848

# 开发环境读取配置文件路径
VITE_PUBLIC_PATH = /

# 开发环境路由历史模式
VITE_ROUTER_HISTORY = "hash"

# 后端 API 地址（开发环境通过 proxy 代理，配置为空）
VITE_API_BASE_URL = ""
```

**`.env.production`** - 生产环境
```bash
# 线上环境平台打包路径
VITE_PUBLIC_PATH = /

# 线上环境路由历史模式
VITE_ROUTER_HISTORY = "hash"

# 是否在打包时使用cdn替换本地库
VITE_CDN = false

# 是否启用gzip压缩或brotli压缩
VITE_COMPRESSION = "none"

# 后端 API 地址（生产环境配置实际后端地址）
VITE_API_BASE_URL = "http://localhost:8888"
```

### 3.2 Vite 配置修改

**`vite.config.ts`** - 添加开发代理

在 `server` 配置中添加 `proxy` 选项：

```typescript
server: {
  port: VITE_PORT,
  host: "0.0.0.0",
  // 配置代理，将 /api 请求转发到 Flask 后端
  proxy: {
    "/api": {
      target: "http://localhost:8888",
      changeOrigin: true,
      rewrite: (path) => path  // 保持路径不变
    }
  },
  warmup: {
    clientFiles: ["./index.html", "./src/{views,components}/*"]
  }
}
```

**关键配置说明**:
- `target`: Flask 后端地址
- `changeOrigin`: 修改请求头中的 origin，避免后端拒绝请求
- `rewrite`: 保持路径不变，不做重写

## 4. API 接口层设计

### 4.1 创建统计数据 API 模块

**`src/api/stats.ts`** - 新建文件

```typescript
import { http } from "@/utils/http";

// 响应类型定义
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

// API 函数
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
  return http.request("get", "/api/stats/contributors", { params });
};
```

### 4.2 Flask API 端点映射

| 前端 API 函数 | HTTP 方法 | Flask 端点 | 说明 |
|--------------|----------|-----------|------|
| `getOverallStats()` | GET | `/api/stats/overall` | 获取整体统计数据 |
| `getRepoStats()` | GET | `/api/stats/repos` | 获取仓库统计列表 |
| `getContributorStats()` | GET | `/api/stats/contributors` | 获取贡献者统计列表 |

## 5. 错误处理与响应拦截

### 5.1 响应拦截器增强

在 `src/utils/http/index.ts` 的响应拦截器中添加统一错误处理：

```typescript
/** 响应拦截 */
private httpInterceptorsResponse(): void {
  const instance = PureHttp.axiosInstance;
  instance.interceptors.response.use(
    (response: PureHttpResponse) => {
      const $config = response.config;
      
      // 优先判断post/get等方法是否传入回调
      if (typeof $config.beforeResponseCallback === "function") {
        $config.beforeResponseCallback(response);
        return response.data;
      }
      if (PureHttp.initConfig.beforeResponseCallback) {
        PureHttp.initConfig.beforeResponseCallback(response);
        return response.data;
      }
      
      // Flask 返回的数据直接透传
      return response.data;
    },
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
      
      return Promise.reject($error);
    }
  );
}
```

### 5.2 错误处理策略

- **404 错误**: 提示 API 接口不存在
- **500 错误**: 提示服务器错误
- **网络错误**: 提示检查后端服务是否启动（开发时常见）
- **保持原有逻辑**: 不影响 mock 认证和其他 API

## 6. 开发与部署流程

### 6.1 开发流程

**步骤 1: 启动后端服务**
```bash
# 在项目根目录
python app.py
# Flask 运行在 http://localhost:8888
```

**步骤 2: 启动前端开发服务**
```bash
cd frontend
pnpm install  # 首次需要安装依赖
pnpm dev      # 启动开发服务器，运行在 http://localhost:8848
```

**步骤 3: 访问应用**
- 浏览器访问 `http://localhost:8848`
- 前端的 `/api/stats/*` 请求会自动代理到 `http://localhost:8888/api/stats/*`

### 6.2 生产构建流程

**步骤 1: 配置生产环境变量**
```bash
# 编辑 frontend/.env.production
VITE_API_BASE_URL = "http://your-backend-domain:8888"
# 或者使用相对路径（如果前后端部署在同一域名）
VITE_API_BASE_URL = ""
```

**步骤 2: 构建前端**
```bash
cd frontend
pnpm build
# 输出到 frontend/dist 目录
```

**步骤 3: 部署**

**方式 A: Flask 托管前端（推荐，当前项目方式）**
- Flask 的 `app.py` 已配置静态文件目录指向 `frontend/dist`
- 直接运行 `python app.py`，访问 `http://localhost:8888` 即可
- 前后端在同一端口，无需 CORS 配置

**方式 B: 独立部署**
- 前端部署到 Nginx/CDN
- 后端独立运行
- 需要在 `.env.production` 中配置完整的后端地址

### 6.3 验证清单

**开发环境验证**:
- [ ] 前端能正常启动在 8848 端口
- [ ] 后端能正常启动在 8888 端口
- [ ] 浏览器控制台 Network 显示 `/api/stats` 请求成功
- [ ] 统计数据能正常显示

**生产环境验证**:
- [ ] 前端构建成功，dist 目录生成
- [ ] Flask 能正确托管静态文件
- [ ] 访问根路径能看到前端页面
- [ ] API 请求能正常响应

## 7. 关键设计决策

### 7.1 为什么选择 Vite Proxy 方案

**优点**:
- 开发体验好，自动避免 CORS 问题
- 不需要修改 Flask 后端代码
- 生产环境灵活配置，支持不同部署场景
- 符合现代前端开发最佳实践

**为什么不选择其他方案**:
- **Flask CORS 方案**: 需要修改后端代码，增加维护成本
- **Mock 逐步迁移方案**: 需要维护两套代码，复杂度高

### 7.2 保留 Mock 认证的原因

- vue-pure-admin 的认证系统已经完整，无需重写
- 当前主要需求是对接统计数据 API，不涉及真实用户认证
- 降低迁移复杂度，专注于数据对接

### 7.3 不修改 HTTP 工具配置的原因

- vue-pure-admin 的 axios 封装已经很完善
- 通过 Vite proxy 可以透明代理，无需修改 baseURL
- 保持前端代码的纯净性和可维护性

## 8. 注意事项

1. **开发时必须同时启动前后端服务**: Vite proxy 依赖后端服务运行
2. **生产环境需要正确配置 VITE_API_BASE_URL**: 否则 API 请求会失败
3. **Flask 返回数据格式**: 确保 Flask API 返回的 JSON 格式符合前端类型定义
4. **CORS 问题**: 开发环境通过 proxy 解决，生产环境如果独立部署需要配置 CORS

## 9. 后续扩展

如果未来需要对接更多 API（如 Metrics API、Git-AI API），只需：

1. 在 `vite.config.ts` 的 proxy 中添加对应路径
2. 在 `src/api/` 下创建对应的 API 模块
3. 定义类型并实现 API 函数

示例：
```typescript
// vite.config.ts
proxy: {
  "/api": { target: "http://localhost:8888", changeOrigin: true },
  "/worker": { target: "http://localhost:8888", changeOrigin: true }
}

// src/api/metrics.ts
export const getMetricsDaily = () => {
  return http.request("get", "/worker/metrics/daily");
};
```

## 10. 总结

本设计采用 Vite 开发代理 + 环境变量配置方案，实现 vue-pure-admin 前端与 Flask 后端的无缝对接。方案的核心优势是：

- **开发体验优秀**: 自动处理 CORS，前后端分离开发
- **配置简单**: 只需修改 Vite 配置和环境变量
- **生产灵活**: 支持同域部署和跨域部署
- **维护成本低**: 不修改后端代码，不修改 HTTP 工具

该方案已经过用户确认，可以进入实施阶段。
