import { http } from "@/utils/http";

// 通用响应类型
type R<T> = { success: boolean; data: T; error?: string };

// 任务项类型
export type JobItem = {
  id: string;
  name: string;
  enabled: boolean;
  cron: string;
  next_run_time: string | null;
  status: "running" | "idle";
  last_execution: string | null;
};

// 任务状态类型
export type JobStatus = {
  job_id: string;
  status: "running" | "idle" | "pending";
  next_run_time: string | null;
  last_execution: string | null;
};

// 任务执行记录类型
export type ExecutionItem = {
  id: string;
  job_id: string;
  start_time: number;
  end_time: number | null;
  status: "running" | "success" | "failed";
  error: string | null;
  output: string | null;
};

// 任务触发响应类型
export type TriggerJobResponse = {
  execution_id: string;
  status: string;
  job_id: string;
};

// 任务执行详情类型
export type ExecutionDetail = {
  id: string;
  job_id: string;
  start_time: number;
  end_time: number | null;
  status: "running" | "success" | "failed";
  error: string | null;
  output: string | null;
};

/** 获取所有任务列表 */
export const getJobs = () => {
  return http.request<R<{ jobs: JobItem[] }>>("get", "/api/v1/scheduler/jobs");
};

/** 获取任务状态 */
export const getJobStatus = (jobId: string) => {
  return http.request<R<JobStatus>>("get", "/api/v1/scheduler/jobs/status", {
    params: { jobId }
  });
};

/** 手动触发任务 */
export const triggerJob = (jobId: string) => {
  return http.request<R<TriggerJobResponse>>("post", "/api/v1/scheduler/jobs/trigger", {
    params: { jobId }
  });
};

/** 获取任务执行历史 */
export const getJobExecutions = (
  jobId: string,
  options?: {
    limit?: number;
    status?: "running" | "success" | "failed";
  }
) => {
  return http.request<
    R<{ executions: ExecutionItem[]; job_id: string; count: number }>
  >("get", "/api/v1/scheduler/jobs/history/executions", {
    params: {
      jobId,
      ...options
    }
  });
};

/** 获取任务执行详情 */
export const getExecutionDetail = (jobId: string, executionId: string) => {
  return http.request<R<ExecutionDetail>>("get", "/api/v1/scheduler/jobs/execution-detail", {
    params: { jobId, executionId }
  });
};
