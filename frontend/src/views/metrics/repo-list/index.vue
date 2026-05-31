<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { PureTableBar } from "@/components/RePureTableBar";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { getPickerShortcuts } from "@/views/monitor/utils";
import { getBlameRepoStats, type BlameRepoStatItem } from "@/api/stats";

import Refresh from "~icons/ep/refresh";

defineOptions({
  name: "MetricsRepoList"
});

const loading = ref(false);
const dataList = ref<BlameRepoStatItem[]>([]);
const dateRange = ref<[Date, Date] | []>([]);

const form = reactive({
  repo_name: "",
  branch: ""
});

const pagination = ref({
  total: 0,
  page: 1,
  page_size: 20,
  background: true
});

const columns = computed(() => [
  { label: "统计日期", prop: "stat_date", width: 120, slot: "statDate" },
  { label: "仓库", prop: "repo_name", minWidth: 180 },
  { label: "分支", prop: "branch", minWidth: 140 },
  { label: "AI 代码行数", prop: "ai_lines", width: 130 },
  { label: "人工代码行数", prop: "non_ai_lines", width: 130 },
  { label: "总代码行数", prop: "total_lines", width: 130 }
]);

const defaultDateRange = (): [Date, Date] => {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 29);
  start.setHours(0, 0, 0, 0);
  end.setHours(23, 59, 59, 999);
  return [start, end];
};

const formatDate = (d: Date) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}${m}${day}`;
};

const formatStatDate = (value: number) => {
  const text = String(value).padStart(8, "0");
  const year = text.slice(0, 4);
  const month = text.slice(4, 6);
  const day = text.slice(6, 8);
  return `${year}-${month}-${day}`;
};

const formatNumber = (value: number) => {
  return new Intl.NumberFormat("en-US").format(value);
};

const buildParams = () => {
  const [start, end] = dateRange.value.length === 2 ? dateRange.value : [];

  return {
    page: pagination.value.page,
    page_size: pagination.value.page_size,
    start_date: start ? formatDate(start) : undefined,
    end_date: end ? formatDate(end) : undefined,
    repo_id: form.repo_name || undefined,
    branch: form.branch || undefined
  };
};

const onSearch = async () => {
  loading.value = true;
  try {
    const res = await getBlameRepoStats(buildParams());
    dataList.value = res.data || [];
    pagination.value.total = res.pagination?.total || 0;
  } finally {
    loading.value = false;
  }
};

const resetForm = async () => {
  form.repo_name = "";
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
      <el-form-item label="仓库名称" prop="repo_name">
        <el-input
          v-model="form.repo_name"
          placeholder="请输入仓库名称关键字"
          clearable
          class="w-52!"
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
      <el-form-item label="统计日期">
        <el-date-picker
          v-model="dateRange"
          :shortcuts="getPickerShortcuts()"
          type="daterange"
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

    <PureTableBar title="仓库AI代码量" :columns="columns" @refresh="onSearch">
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
          <template #statDate="{ row }">
            <span class="single-line-cell">{{
              formatStatDate(row.stat_date)
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
