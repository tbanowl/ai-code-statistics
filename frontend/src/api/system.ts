import { http } from "@/utils/http";

type Result = {
  code: number;
  message: string;
  data?: Array<any>;
};

type ResultTable = {
  code: number;
  message: string;
  data?: {
    list: Array<any>;
    total?: number;
    pageSize?: number;
    currentPage?: number;
  };
};

export const getUserList = (data?: object) => {
  return http.request<ResultTable>("post", "/api/user", { data });
};

export const getAllRoleList = () => {
  return http.request<Result>("get", "/api/list-all-role");
};

export const getRoleIds = (data?: object) => {
  return http.request<Result>("post", "/api/list-role-ids", { data });
};

export const getRoleList = (data?: object) => {
  return http.request<ResultTable>("post", "/api/role", { data });
};

export const getMenuList = (data?: object) => {
  return http.request<Result>("post", "/api/menu", { data });
};

export const getDeptList = (data?: object) => {
  return http.request<Result>("post", "/api/dept", { data });
};

export const getOnlineLogsList = (data?: object) => {
  return http.request<ResultTable>("post", "/api/online-logs", { data });
};

export const getLoginLogsList = (data?: object) => {
  return http.request<ResultTable>("post", "/api/login-logs", { data });
};

export const getOperationLogsList = (data?: object) => {
  return http.request<ResultTable>("post", "/api/operation-logs", { data });
};

export const getSystemLogsList = (data?: object) => {
  return http.request<ResultTable>("post", "/api/system-logs", { data });
};

export const getSystemLogsDetail = (data?: object) => {
  return http.request<Result>("post", "/api/system-logs-detail", { data });
};

export const getRoleMenu = (data?: object) => {
  return http.request<Result>("post", "/api/menu", { data });
};

export const getRoleMenuIds = (data?: object) => {
  return http.request<Result>(
    "get",
    `/api/role/${(data as any)?.roleId}/menu-ids`
  );
};

export const addUser = (data?: object) => {
  return http.request<Result>("post", "/api/user/add", { data });
};

export const updateUser = (id: number, data?: object) => {
  return http.request<Result>("put", `/api/user/${id}`, { data });
};

export const deleteUser = (id: number) => {
  return http.request<Result>("delete", `/api/user/${id}`);
};

export const resetUserPassword = (data?: object) => {
  return http.request<Result>("post", "/api/user/reset-password", { data });
};

export const addRole = (data?: object) => {
  return http.request<Result>("post", "/api/role/add", { data });
};

export const updateRole = (id: number, data?: object) => {
  return http.request<Result>("put", `/api/role/${id}`, { data });
};

export const deleteRole = (id: number) => {
  return http.request<Result>("delete", `/api/role/${id}`);
};

export const setRoleMenus = (data?: object) => {
  return http.request<Result>("post", "/api/role/menu", { data });
};

export const addMenu = (data?: object) => {
  return http.request<Result>("post", "/api/menu/add", { data });
};

export const updateMenu = (id: number, data?: object) => {
  return http.request<Result>("put", `/api/menu/${id}`, { data });
};

export const deleteMenu = (id: number) => {
  return http.request<Result>("delete", `/api/menu/${id}`);
};

export const addDept = (data?: object) => {
  return http.request<Result>("post", "/api/dept/add", { data });
};

export const updateDept = (id: number, data?: object) => {
  return http.request<Result>("put", `/api/dept/${id}`, { data });
};

export const deleteDept = (id: number) => {
  return http.request<Result>("delete", `/api/dept/${id}`);
};
