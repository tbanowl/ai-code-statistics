import { http } from "@/utils/http";

type R<T> = { success: boolean; data: T };
type Paged<T> = R<T[]> & { pagination?: { total: number; page: number; page_size: number } };

export type RepoItem = {
  id: string;
  repo_path: string;
  repo_name: string | null;
  repo_stats_flag: number;
  ssh_key_id: string | null;
  created_at: number;
};

export type SshKeyItem = {
  id: string;
  key_name: string;
  public_key: string;
  created_at: number;
};

export type BranchConfig = {
  id: string;
  branch_pattern: string;
  pattern_type: string;
  enabled: number;
};

export type ContributorStat = {
  contributor_id: string;
  contributor_name: string;
  ai_lines: number;
  non_ai_lines: number;
  total_lines: number;
};

export const getRepoList = (params?: { page?: number; page_size?: number; keyword?: string }) =>
  http.request<Paged<RepoItem>>("get", "/api/stats/repositories", { params });

export const updateRepoStatsFlag = (repoId: string, flag: number) =>
  http.request<R<unknown>>("put", `/api/stats-repo/${repoId}/stats-flag`, { data: { repo_stats_flag: flag } });

export const getRepoBranchConfigs = (repoId: string) =>
  http.request<R<{ configs: BranchConfig[]; count: number }>>("get", `/api/stats-repo/${repoId}/branch-configs`);

export const getRepoContributors = (repoId: string) =>
  http.request<R<{ stats: ContributorStat[]; count: number }>>("get", `/api/stats-repo/blame/repo/${repoId}/contributors`);

export const getSshKeys = () =>
  http.request<R<{ ssh_keys: SshKeyItem[]; count: number }>>("get", "/api/stats-repo/ssh-keys");

export const updateRepoSshKey = (repoId: string, sshKeyId: string | null) =>
  http.request<R<unknown>>("put", `/api/stats-repo/${repoId}/ssh-key`, { data: { ssh_key_id: sshKeyId } });

export const addSshKey = (data: { key_name: string; public_key?: string; private_key: string }) =>
  http.request<R<{ ssh_key: SshKeyItem }>>("post", "/api/stats-repo/ssh-key", { data });

export const deleteSshKey = (keyId: string) =>
  http.request<R<unknown>>("delete", `/api/stats-repo/ssh-key/${keyId}`);
