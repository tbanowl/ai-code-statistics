import { http } from "@/utils/http";

// 通用响应类型
export type ApiResponse<T> = {
  success: boolean;
  data: T;
  pagination?: {
    total: number;
    page: number;
    page_size: number;
  };
};

// 统计项类型
export type StatItem = {
  ai_generated_lines: number;
  ai_accepted_lines: number;
  human_lines: number;
  ai_percentage: number;
};

// 统计汇总类型
export type StatSummary = {
  total_ai_generated: number;
  total_ai_accepted: number;
  total_human: number;
  avg_ai_percentage: number;
};

// 统计过滤器类型
export type StatFilters = {
  repo_id: string | null;
  repo_name: string | null;
  contributor_id: string | null;
  contributor_name: string | null;
};

// 整体统计数据类型
export type StatsData = {
  items: StatItem[];
  summary: StatSummary;
  filters: StatFilters;
};

// 仓库统计项类型
export type RepoStatItem = {
  repo_path: string;
  ai_accepted_lines: number;
  human_lines: number;
  ai_percentage: number;
};

// 贡献者统计项类型
export type ContributorStatItem = {
  contributor: string;
  ai_accepted_lines: number;
  human_lines: number;
  ai_percentage: number;
};

/** 获取整体统计数据 */
export const getStats = (params: {
  start_date: number;
  end_date: number;
  granularity?: "daily" | "weekly" | "monthly";
  repo_id?: string;
  contributor_id?: string;
}) => {
  return http.request<ApiResponse<StatsData>>("get", "/api/stats/", { params });
};

/** 获取仓库统计列表 */
export const getRepoStats = (params?: {
  page?: number;
  page_size?: number;
  keyword?: string;
}) => {
  return http.request<ApiResponse<RepoStatItem[]>>("get", "/api/stats/repositories", {
    params,
  });
};

/** 获取贡献者统计列表 */
export const getContributorStats = (params?: {
  page?: number;
  page_size?: number;
  keyword?: string;
}) => {
  return http.request<ApiResponse<ContributorStatItem[]>>(
    "get",
    "/api/stats/stats/contributors",
    { params }
  );
};
