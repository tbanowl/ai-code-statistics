import type { iconType } from "./types";
import { h, defineComponent, type Component } from "vue";
import { FontIcon, IconifyIconOnline, IconifyIconOffline } from "../index";

/**
 * 检查是否在内网（离线）环境
 * 通过 VITE_INLINE_ICONS 环境变量判断
 */
function isOfflineMode(): boolean {
  return import.meta.env.VITE_INLINE_ICONS === "true" ||
         import.meta.env.VITE_OFFLINE_MODE === "true" ||
         typeof window !== "undefined" &&
         (window as any).VITE_INLINE_ICONS === "true";
}

/**
 * 支持 `iconfont`、自定义 `svg` 以及 `iconify` 中所有的图标
 * @see 点击查看文档图标篇 {@link https://pure-admin.cn/pages/icon/}
 * @param icon 必传 图标
 * @param attrs 可选 iconType 属性
 * @returns Component
 */
export function useRenderIcon(icon: any, attrs?: iconType): Component {
  // iconfont
  const ifReg = /^IF-/;
  // typeof icon === "function" 属于SVG
  if (ifReg.test(icon)) {
    // iconfont
    const name = icon.split(ifReg)[1];
    const iconName = name.slice(
      0,
      name.indexOf(" ") == -1 ? name.length : name.indexOf(" ")
    );
    const iconType = name.slice(name.indexOf(" ") + 1, name.length);
    return defineComponent({
      name: "FontIcon",
      render() {
        return h(FontIcon, {
          icon: iconName,
          iconType,
          ...attrs
        });
      }
    });
  } else if (typeof icon === "function" || typeof icon?.render === "function") {
    // svg
    return attrs ? h(icon, { ...attrs }) : icon;
  } else if (typeof icon === "object") {
    return defineComponent({
      name: "OfflineIcon",
      render() {
        return h(IconifyIconOffline, {
          icon: icon,
          ...attrs
        });
      }
    });
  } else {
    // 在内网环境强制使用离线组件，避免外网请求
    return defineComponent({
      name: "Icon",
      render() {
        if (!icon) return;
        const offlineMode = isOfflineMode();
        // 内网环境或离线模式下，强制使用离线组件
        if (offlineMode) {
          return h(IconifyIconOffline, {
            icon,
            ...attrs
          });
        }
        // 外网环境根据图标格式选择在线或离线组件
        const IconifyIcon = icon.includes(":")
          ? IconifyIconOnline
          : IconifyIconOffline;
        return h(IconifyIcon, {
          icon,
          ...attrs
        });
      }
    });
  }
}
