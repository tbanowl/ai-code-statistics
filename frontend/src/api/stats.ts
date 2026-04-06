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
