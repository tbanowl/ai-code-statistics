<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { PureTableBar } from "@/components/RePureTableBar";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { message } from "@/utils/message";
import dayjs from "dayjs";
import {
  getJobs,
  triggerJob,
  getJobExecutions,
  type JobItem,
  type ExecutionItem
} from "@/api/schedules";

import Refresh from "~icons/ep/refresh";
import List from "~icons/ep/list";

defineOptions({
  name: "SchedulesList"
});

const loading = ref(false);
const triggerLoading = ref(false);
const dataList = ref<JobItem[]>([]);

const executionsDrawerVisible = ref(false);
const executionsLoading = ref(false);
const executionsList = ref<ExecutionItem[]>([]);
const currentJob = ref<JobItem | null>(null);

const columns = computed(() => [
  {
    label: "任务ID",
    prop: "id",
    minWidth: 180
  },
  {
    label: "任务名称",
    prop: "name",
    minWidth: 150
  },
  {
    label: "Cron表达式",
    prop: "corn",
    minWidth: 150
  },
  {
    label: "状态",
    prop: "status",
    minWidth: 100,
    slot: "status"
  },
  {
    label: "下次执行时间",
    prop: "next_run_time",
    minWidth: 170,
    slot: "nextRunTime"
  },
  {
    label: "操作",
    fixed: "right",
    width: 200,
    slot: "operation"
  }
]);

const statusMap = {
  running: "运行中",
  idle: "空闲"
};

const statusTagMap = {
  running: "success",
  idle: "info"
} as const;

const formatTimestamp = (value?: string | null) => {
  if (!value) return "-";
  return dayjs(value).format("YYYY-MM-DD HH:mm:ss");
};

const onSearch = async () => {
  loading.value = true;
  try {
    const res = await getJobs();
    dataList.value = res.data?.jobs || [];
  } catch {
    message("获取任务列表失败", { type: "error" });
  } finally {
    loading.value = false;
  }
};

const handleTriggerJob = async (row: JobItem) => {
  triggerLoading.value = true;
  try {
    await triggerJob(row.id);
    message("任务触发成功", { type: "success" });
    onSearch();
  } catch (err: any) {
    const error = err?.error || err?.message || "任务触发失败";
    message(error, { type: "error" });
  } finally {
    triggerLoading.value = false;
  }
};

const executionStatusTagMap = {
  pending: "pending",
  completed: "completed",
  failed: "danger"
} as const;

const executionStatusMap = {
  pending: "运行中",
  completed: "成功",
  failed: "失败"
};

const openExecutionsDrawer = async (row: JobItem) => {
  currentJob.value = row;
  executionsDrawerVisible.value = true;
  await fetchExecutions(row.id);
};

const fetchExecutions = async (jobId: string) => {
  executionsLoading.value = true;
  try {
    const res = await getJobExecutions(jobId, { limit: 20 });
    executionsList.value = res.data?.executions || [];
  } catch {
    message("获取执行历史失败", { type: "error" });
    executionsList.value = [];
  } finally {
    executionsLoading.value = false;
  }
};

const handleRefreshExecutions = () => {
  if (currentJob.value) {
    fetchExecutions(currentJob.value.id);
  }
};

onMounted(() => {
  onSearch();
});
</script>

<template>
  <div class="main">
    <PureTableBar title="任务列表" :columns="columns" @refresh="onSearch">
      <template v-slot="{ size, dynamicColumns }">
        <pure-table
          row-key="id"
          adaptive
          :adaptiveConfig="{ offsetBottom: 108 }"
          align-whole="center"
          table-layout="auto"
          :loading="loading"
          :size="size"
          :data="dataList"
          :columns="dynamicColumns"
          :header-cell-style="{
            background: 'var(--el-fill-color-light)',
            color: 'var(--el-text-color-primary)'
          }"
        >
          <template #status="{ row }">
            <el-tag :type="statusTagMap[row.status]">
              {{ statusMap[row.status] }}
            </el-tag>
          </template>
          <template #enabled="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">
              {{ row.enabled ? "启用" : "禁用" }}
            </el-tag>
          </template>
          <template #nextRunTime="{ row }">
            <span class="single-line-cell">{{
              formatTimestamp(row.next_run_time)
            }}</span>
          </template>
          <template #lastExecution="{ row }">
            <span class="single-line-cell">{{
              formatTimestamp(row.last_execution)
            }}</span>
          </template>
          <template #operation="{ row }">
            <el-button
              class="reset-margin"
              link
              type="primary"
              :size="size"
              :loading="triggerLoading"
              :disabled="row.status === 'running'"
              @click="handleTriggerJob(row)"
            >
              执行任务
            </el-button>
            <el-button
              class="reset-margin"
              link
              type="primary"
              :size="size"
              :icon="useRenderIcon(List)"
              @click="openExecutionsDrawer(row)"
            >
              执行历史
            </el-button>
          </template>
        </pure-table>
      </template>
    </PureTableBar>

    <!-- 执行历史抽屉 -->
    <el-drawer
      v-model="executionsDrawerVisible"
      title="执行历史"
      direction="rtl"
      size="800px"
    >
      <template #header>
        <div class="flex-bc items-center w-full">
          <span>执行历史</span>
          <div v-if="currentJob" class="text-sm text-gray-500">
            {{ currentJob.name }} ({{ currentJob.id }})
          </div>
        </div>
      </template>
      <el-button
        :icon="useRenderIcon(Refresh)"
        @click="handleRefreshExecutions"
        class="mb-4"
      >
        刷新
      </el-button>
      <el-table :data="executionsList" :loading="executionsLoading" border>
        <el-table-column prop="start_time" label="开始时间" min-width="170">
          <template #default="{ row }">
            {{ formatTimestamp(new Date(row.started_at).toISOString()) }}
          </template>
        </el-table-column>
        <el-table-column prop="end_time" label="结束时间" min-width="170">
          <template #default="{ row }">
            {{
              row.finished_at
                ? formatTimestamp(new Date(row.finished_at).toISOString())
                : "-"
            }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag :type="executionStatusTagMap[row.status]">
              {{ executionStatusMap[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="error"
          label="错误信息"
          min-width="200"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            {{ row.error || "-" }}
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<style lang="scss" scoped>
.main {
  padding: 20px;
}

.single-line-cell {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
