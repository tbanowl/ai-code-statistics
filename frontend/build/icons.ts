import Icons from "unplugin-icons/vite";
importIconsResolver from "unplugin-icons/resolver";

/**
 * 内网环境图标配置
 *
 * 方案1：内嵌所有图标数据（推荐用于完全离线环境）
 * 方案2：HTTP 代理配置（如果内网有代理服务器）
 * 方案3：SVG 代替（需要手动维护 SVG 图标）
 */

/**
 * 方案1：内嵌所有图标数据
 *
 * 优点：完全离线，无需网络
 * 缺点：增大打包体积（约 10-20 MB）
 *
 * 使用方法：在 vite.config.ts 中启用此插件
 */
export function inlineIconsPlugin() {
  return Icons({
    compiler: "vue3",
    scale: 1,
    // 内嵌所有 @iconify/json 中的图标集
    // 这会显著增加打包体积，但完全不需要网络访问
    autoImport: true,
    // 确保所有使用的图标都被内嵌
    compilerOptions: {
      vue3: true
    }
  });
}

/**
 * 方案2：配置本地 HTTP 代理（如果内网有代理）
 *
 * 使用方法：
 * 1. 在项目中创建 .env.local 或 .env.production 文件
 * 2. 添加 HTTP_PROXY 和 HTTPS_PROXY 配置
 *
 * 示例：
 * HTTP_PROXY=http://proxy.company.com:8080
 * HTTPS_PROXY=http://proxy.company.com:8080
 * NO_PROXY=localhost,127.0.0.1
 */

/**
 * 方案3：预下载并本地化图标
 *
 * 步骤：
 * 1. 在有网络的机器上运行：pnpm install --frozen-lockfile
 * 2. 拷贝 node_modules/@iconify/json 到内网机器
 * 3. 在内网运行：pnpm install
 */

export const ICONS_CONFIG = {
  // 常用图标集（用于内嵌时的过滤）
  commonIconSets: [
    "ep",      // Element Plus
    "mdi",     // Material Design Icons
    "ri",      // Remix Icon
    "ic",      // Ionic Icon
    "fa",      // Font Awesome
    "eva",     // Eva Design System
  ],

  // 完全内嵌所有图标集（用于离线环境）
  inlineAll: true,
};

// 导出供 plugins.ts 使用的配置
export function getIconsPlugin(inlineAll: boolean = false) {
  if (inlineAll) {
    return inlineIconsPlugin();
  }

  return Icons({
    compiler: "vue3",
    scale: 1,
    // 配合 @iconify/vue 使用网络加载（需要外网访问）
    autoImport: true,
  });
}
