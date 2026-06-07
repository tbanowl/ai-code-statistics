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

export type PaginationData = NonNullable<ApiResponse<unknown>["pagination"]>;

// 统计项类型
export type StatItem = {
  stat_date: number;
  human_additions: number;
  unknown_additions: number;
  git_diff_deleted_lines: number;
  git_diff_added_lines: number;
  mixed_additions: number;
  ai_additions: number;
  ai_accepted: number;
  total_ai_additions: number;
  total_ai_deletions: number;
};

// 统计汇总类型
export type StatSummary = {
  total_ai_generated: number;
  total_ai_accepted: number;
  total_human: number;
  total_lines: number;
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
  id: string;
  repo_path: string;
  repo_name: string | null;
  repo_stats_flag?: number;
  ssh_key_id?: string | null;
  created_at: number;
  updated_at: number;
};

// 贡献者统计项类型
export type ContributorStatItem = {
  id: string;
  contributor_uid: string;
  name: string;
  email: string | null;
  created_at: number;
  updated_at: number;
};

export type DailyStatItem = {
  id: string;
  stat_date: number;
  repo_id: string;
  repo_name: string | null;
  contributor_name: string | null;
  contributor_email: string | null;
  human_additions: number;
  unknown_additions: number;
  git_diff_deleted_lines: number;
  git_diff_added_lines: number;
  mixed_additions: number;
  ai_additions: number;
  ai_accepted: number;
  total_ai_additions: number;
  total_ai_deletions: number;
  created_at: number;
  updated_at: number;
};

export type CommittedReportItem = {
  id: string;
  repo_url: string;
  author: string;
  branch: string;
  timestamp: number;
  commit_date: number;
  human_additions: number;
  git_diff_deleted_lines: number;
  git_diff_added_lines: number;
  first_checkpoint_ts: number | null;
  commit_subject: string;
  commit_body: string;
  tool_model_pairs: string;
  mixed_additions: number;
  ai_additions: number;
  ai_accepted: number;
  total_ai_additions: number;
  total_ai_deletions: number;
  base_commit_sha: string;
};

export type TriggerAggregateData = {
  execution_id: string;
  status: string;
  message: string;
};

export type BlameRepoStatItem = {
  id: string;
  repo_id: string;
  repo_name: string;
  stat_date: number;
  branch: string;
  ai_lines: number;
  non_ai_lines: number;
  total_lines: number;
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
  return http.request<ApiResponse<RepoStatItem[]>>(
    "get",
    "/api/stats/repositories",
    {
      params
    }
  );
};

/** 获取贡献者统计列表 */
export const getContributorStats = (params?: {
  page?: number;
  page_size?: number;
  keyword?: string;
}) => {
  return http.request<ApiResponse<ContributorStatItem[]>>(
    "get",
    "/api/stats/contributors",
    { params }
  );
};

export const getDailyStats = (params?: {
  page?: number;
  page_size?: number;
  start_date?: number;
  end_date?: number;
  repo_id?: string;
  contributor_id?: string;
}) => {
  return http.request<ApiResponse<DailyStatItem[]>>("get", "/api/stats/daily", {
    params
  });
};

export const getCommittedReport = (params?: {
  page?: number;
  page_size?: number;
  start_date?: number;
  end_date?: number;
  repo_url?: string;
  author?: string;
  branch?: string;
  repo_id?: string;
  contributor_id?: string;
}) => {
  return http.request<ApiResponse<CommittedReportItem[]>>(
    "get",
    "/api/stats/commits",
    {
      params
    }
  );
};

export const triggerStatsAggregate = (payload?: {
  start_date?: number;
  end_date?: number;
  repo_id?: string;
  contributor_id?: string;
}) => {
  return http.request<ApiResponse<TriggerAggregateData>>(
    "post",
    "/api/stats/stats/aggregate",
    {
      data: payload ?? {}
    }
  );
};

export const getBlameRepoStats = (params?: {
  page?: number;
  page_size?: number;
  start_date?: number | string;
  end_date?: number | string;
  repo_id?: string;
}) => {
  return http.request<ApiResponse<BlameRepoStatItem[]>>(
    "get",
    "/api/stats-repo/blame/repos",
    { params }
  );
};
