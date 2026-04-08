<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import dayjs from "dayjs";
import { PureTableBar } from "@/components/RePureTableBar";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { getPickerShortcuts } from "@/views/monitor/utils";
import { getCommittedReport, type CommittedReportItem } from "@/api/stats";

import Refresh from "~icons/ep/refresh";

defineOptions({
  name: "MetricsCommitList"
});

const formRef = ref();
const tableRef = ref();
const loading = ref(false);
const dataList = ref<CommittedReportItem[]>([]);
const dateRange = ref<[Date, Date] | []>([]);

const form = reactive({
  repo_url: "",
  author: "",
  branch: ""
});

const pagination = ref({
  total: 0,
  page: 1,
  page_size: 20,
  background: true
});

const columns = computed(() => [
  { label: "仓库地址", prop: "repo_url", width: 180, slot: "repoUrl" },
  { label: "提交者", prop: "author", minWidth: 140 },
  { label: "分支", prop: "branch", minWidth: 140, maxWidth: 200 },
  { label: "提交时间", prop: "timestamp", width: 170, slot: "timestamp" },
  { label: "人工添加行数", prop: "human_additions", width: 120 },
  {
    label: "Git diff 删除行数",
    prop: "git_diff_deleted_lines",
    width: 140
  },
  { label: "Git diff 添加行数", prop: "git_diff_added_lines", width: 140 },
  {
    label: "第一个检查点时间",
    prop: "first_checkpoint_ts",
    width: 170,
    slot: "firstCheckpointTs"
  },
  { label: "提交主题", prop: "commit_subject", minWidth: 120, maxWidth: 200 },
  {
    label: "提交正文",
    prop: "commit_body",
    minWidth: 120,
    maxWidth: 200,
    slot: "commitBody"
  },
  { label: "工具", prop: "tool_model_pairs", width: 180 },
  { label: "混编行数", prop: "mixed_additions", width: 110 },
  { label: "AI 添加行数", prop: "ai_additions", width: 110 },
  { label: "AI 接受行数", prop: "ai_accepted", width: 110 },
  { label: "AI 累积总添加行数", prop: "total_ai_additions", width: 150 },
  { label: "AI 累积总删除行数", prop: "total_ai_deletions", width: 150 },
  {
    label: "Commit SHA",
    prop: "base_commit_sha",
    minWidth: 180,
    slot: "baseCommitSha"
  }
]);

const defaultDateRange = (): [Date, Date] => {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 29);
  start.setHours(0, 0, 0, 0);
  end.setHours(23, 59, 59, 999);
  return [start, end];
};

const formatTimestamp = (value?: number | null) => {
  if (!value) return "-";
  return dayjs(value).format("YYYY-MM-DD HH:mm:ss");
};

const trimRepoUrl = (value: string) => {
  if (!value) return "-";

  try {
    const url = new URL(value);
    return url.pathname.replace(/^\/+/, "") || value;
  } catch {
    const normalized = value
      .replace(/^[a-z]+:\/\//i, "")
      .replace(/^[^@]+@/, "")
      .replace(/^[^/:]+[:/]/, "");
    return normalized.replace(/^\/+/, "") || value;
  }
};

const buildParams = () => {
  const [start, end] = dateRange.value.length === 2 ? dateRange.value : [];

  return {
    page: pagination.value.page,
    page_size: pagination.value.page_size,
    start_date: start?.getTime(),
    end_date: end?.getTime(),
    repo_url: form.repo_url || undefined,
    author: form.author || undefined,
    branch: form.branch || undefined
  };
};

const onSearch = async () => {
  loading.value = true;
  try {
    const res = await getCommittedReport(buildParams());
    dataList.value = res.data || [];
    pagination.value.total = res.pagination?.total || 0;
  } finally {
    loading.value = false;
  }
};

const resetForm = async () => {
  form.repo_url = "";
  form.author = "";
  form.branch = "";
  dateRange.value = defaultDateRange();
  pagination.value.page = 1;
  await onSearch();
};

const handleSizeChange = async (size: number) => {
  pagination.value.page_size = size;
  pagination.value.page = 1;
  await onSearch();
};

const handleCurrentChange = async (page: number) => {
  pagination.value.page = page;
  await onSearch();
};

const handleSearch = async () => {
  pagination.value.page = 1;
  await onSearch();
};

onMounted(async () => {
  dateRange.value = defaultDateRange();
  await onSearch();
});
</script>

<template>
  <div class="main">
    <el-form
      ref="formRef"
      :inline="true"
      :model="form"
      class="search-form bg-bg_color w-full pl-8 pt-3 overflow-auto"
    >
      <el-form-item label="仓库地址" prop="repo_url">
        <el-input
          v-model="form.repo_url"
          placeholder="请输入仓库地址关键字"
          clearable
          class="w-52!"
        />
      </el-form-item>
      <el-form-item label="提交者" prop="author">
        <el-input
          v-model="form.author"
          placeholder="请输入提交者"
          clearable
          class="w-42!"
        />
      </el-form-item>
      <el-form-item label="分支" prop="branch">
        <el-input
          v-model="form.branch"
          placeholder="请输入分支"
          clearable
          class="w-42!"
        />
      </el-form-item>
      <el-form-item label="提交时间">
        <el-date-picker
          v-model="dateRange"
          :shortcuts="getPickerShortcuts()"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始日期时间"
          end-placeholder="结束日期时间"
        />
      </el-form-item>
      <el-form-item>
        <el-button
          type="primary"
          :icon="useRenderIcon('ri:search-line')"
          :loading="loading"
          @click="handleSearch"
        >
          搜索
        </el-button>
        <el-button :icon="useRenderIcon(Refresh)" @click="resetForm">
          重置
        </el-button>
      </el-form-item>
    </el-form>

    <PureTableBar title="提交列表" :columns="columns" @refresh="onSearch">
      <template v-slot="{ size, dynamicColumns }">
        <pure-table
          ref="tableRef"
          row-key="id"
          adaptive
          :adaptiveConfig="{ offsetBottom: 108 }"
          align-whole="center"
          showOverflowTooltip
          table-layout="auto"
          :loading="loading"
          :size="size"
          :data="dataList"
          :columns="dynamicColumns"
          :pagination="{ ...pagination, size }"
          :header-cell-style="{
            background: 'var(--el-fill-color-light)',
            color: 'var(--el-text-color-primary)'
          }"
          @page-size-change="handleSizeChange"
          @page-current-change="handleCurrentChange"
        >
          <template #repoUrl="{ row }">
            <span class="single-line-cell">{{
              trimRepoUrl(row.repo_url)
            }}</span>
          </template>
          <template #timestamp="{ row }">
            <span class="single-line-cell">{{
              formatTimestamp(row.timestamp)
            }}</span>
          </template>
          <template #firstCheckpointTs="{ row }">
            <span class="single-line-cell">{{
              formatTimestamp(
                row.first_checkpoint_ts
                  ? row.first_checkpoint_ts * 1000
                  : undefined
              )
            }}</span>
          </template>
          <template #commitBody="{ row }">
            <el-tooltip
              v-if="row.commit_body"
              :content="row.commit_body"
              placement="top-start"
              effect="dark"
            >
              <span class="single-line-cell cursor-help">{{
                row.commit_body
              }}</span>
            </el-tooltip>
            <span v-else class="single-line-cell">-</span>
          </template>
          <template #baseCommitSha="{ row }">
            <span class="single-line-cell">{{
              row.base_commit_sha || "-"
            }}</span>
          </template>
        </pure-table>
      </template>
    </PureTableBar>
  </div>
</template>

<style lang="scss" scoped>
:deep(.el-table__inner-wrapper::before) {
  height: 0;
}

.search-form {
  :deep(.el-form-item) {
    margin-bottom: 12px;
  }
}

.single-line-cell {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
