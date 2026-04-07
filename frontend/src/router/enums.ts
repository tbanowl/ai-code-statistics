// 完整版菜单比较多，将 rank 抽离出来，在此方便维护

const home = 0, // 平台规定只有 home 路由的 rank 才能为 0 ，所以后端在返回 rank 的时候需要从非 0 开始
  error = 1,
  frame = 2,
  permission = 3,
  system = 4,
  monitor = 5,
  tabs = 6,
  about = 7;

export { home, error, frame, permission, system, monitor, tabs, about };
