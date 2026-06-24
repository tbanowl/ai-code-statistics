import { http } from "@/utils/http";

type R<T> = { success: boolean; data?: T; error?: string } & T;

export type GitAiReleaseItem = {
  id: string;
  tag: string;
  version: string;
  channel: string;
  status: "active" | "inactive";
  sha256sums_checksum: string;
  description?: string | null;
  created_by?: string | null;
  artifact_count?: number;
  total_size_bytes?: number;
  created_at: number;
  published_at?: number | null;
};

export type GitAiReleaseArtifact = {
  id: string;
  filename: string;
  artifact_type: string;
  platform?: string | null;
  sha256: string;
  size_bytes: number;
  content_type: string;
};

export const getGitAiReleaseChannels = () =>
  http.request<{
    channels: Record<
      string,
      { tag: string; version: string; checksum: string; platforms: string[] }
    >;
  }>("get", "/worker/releases/");

export const getGitAiReleaseList = (params?: {
  channel?: string;
  status?: string;
}) =>
  http.request<R<{ releases: GitAiReleaseItem[] }>>(
    "get",
    "/worker/releases/admin/list",
    { params }
  );

export const getGitAiReleaseDetail = (id: string) =>
  http.request<
    R<{ release: GitAiReleaseItem; artifacts: GitAiReleaseArtifact[] }>
  >("get", `/worker/releases/admin/${id}`);

export const uploadGitAiRelease = (data: FormData) =>
  http.request<R<{ release: GitAiReleaseItem }>>(
    "post",
    "/worker/releases/admin/upload",
    { data },
    { headers: { "Content-Type": "multipart/form-data" } }
  );

export const activateGitAiRelease = (id: string) =>
  http.request<R<{ release: GitAiReleaseItem }>>(
    "post",
    `/worker/releases/admin/${id}/activate`
  );

export const deleteGitAiRelease = (id: string) =>
  http.request<R<unknown>>("delete", `/worker/releases/admin/${id}`);

export const releaseArtifactDownloadUrl = (channel: string, filename: string) =>
  `/worker/releases/${channel}/download/${encodeURIComponent(filename)}`;
