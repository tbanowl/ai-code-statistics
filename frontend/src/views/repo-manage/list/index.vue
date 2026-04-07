<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { PureTableBar } from "@/components/RePureTableBar";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { message } from "@/utils/message";
import {
  getRepoList,
  updateRepoStatsFlag,
  getRepoBranchConfigs,
  getRepoContributors,
  getSshKeys,
  updateRepoSshKey,
  type RepoItem,
  type SshKeyItem,
  type BranchConfig,
  type ContributorStat
} from "@/api/repo";

import Refresh from "~icons/ep/refresh";
import Search from "~icons/ep/search";

defineOptions({
  name: "RepoManageList"
});

const loading = ref(false);
const dataList = ref<RepoItem[]>([]);
const sshKeys = ref<SshKeyItem[]>([]);
const keyword = ref("");
const pagination = ref({
  total: 0,
  page: 1,
  page_size: 10,
  background: true
});

const branchDrawerVisible = ref(false);
const branchLoading = ref(false);
const branchConfigs = ref<BranchConfig[]>([]);
const currentRepoName = ref("");

const contributorDrawerVisible = ref(false);
const contributorLoading = ref(false);
const contributorStats = ref<ContributorStat[]>([]);

const sshDialogVisible = ref(false);
const sshDialogLoading = ref(false);
const selectedSshKeyId = ref<string | null>(null);
const currentRepoId = ref<string>("");

const columns = [
  {
    label: "仓库名称",
    prop: "repo_name",
    minWidth: 150
  },
  {
    label: "仓库地址",
    prop: "repo_path",
    minWidth: 200
  },
  {
    label: "统计开关",
    prop: "repo_stats_flag",
    minWidth: 100,
    slot: "statsFlag"
  },
  {
    label: "已绑定SSH Key",
    prop: "ssh_key_id",
    minWidth: 150,
    slot: "sshKey"
  },
  {
    label: "操作",
    fixed: "right",
    minWidth: 240,
    slot: "operation"
  }
];

const sshKeyNameMap = computed(() => {
  const map = new Map<string, string>();
  sshKeys.value.forEach(key => {
    map.set(key.id, key.key_name);
  });
  return map;
});

const onSearch = async () => {
  loading.value = true;
  try {
    const res = await getRepoList({
      page: pagination.value.page,
      page_size: pagination.value.page_size,
      keyword: keyword.value || undefined
    });
    dataList.value = res.data || [];
    pagination.value.total = res.pagination?.total || 0;
  } catch {
    message("获取仓库列表失败", { type: "error" });
  } finally {
    loading.value = false;
  }
};

const resetSearch = () => {
  keyword.value = "";
  pagination.value.page = 1;
  onSearch();
};

const handleSizeChange = (size: number) => {
  pagination.value.page_size = size;
  onSearch();
};

const handleCurrentChange = (page: number) => {
  pagination.value.page = page;
  onSearch();
};

const handleStatsFlagChange = async (row: RepoItem, value: number) => {
  try {
    await updateRepoStatsFlag(row.id, value);
    message("更新成功", { type: "success" });
  } catch {
    message("更新失败", { type: "error" });
    row.repo_stats_flag = value === 1 ? 0 : 1;
  }
};

const openBranchDrawer = async (row: RepoItem) => {
  currentRepoName.value = row.repo_name || row.repo_path;
  branchDrawerVisible.value = true;
  branchLoading.value = true;
  try {
    const { data } = await getRepoBranchConfigs(row.id);
    branchConfigs.value = data?.configs || [];
  } catch {
    message("获取分支配置失败", { type: "error" });
    branchConfigs.value = [];
  } finally {
    branchLoading.value = false;
  }
};

const openContributorDrawer = async (row: RepoItem) => {
  currentRepoName.value = row.repo_name || row.repo_path;
  contributorDrawerVisible.value = true;
  contributorLoading.value = true;
  try {
    const { data } = await getRepoContributors(row.id);
    contributorStats.value = data?.stats || [];
  } catch {
    message("获取贡献者统计失败", { type: "error" });
    contributorStats.value = [];
  } finally {
    contributorLoading.value = false;
  }
};

const openSshDialog = (row: RepoItem) => {
  currentRepoId.value = row.id;
  selectedSshKeyId.value = row.ssh_key_id;
  sshDialogVisible.value = true;
};

const confirmBindSshKey = async () => {
  sshDialogLoading.value = true;
  try {
    await updateRepoSshKey(currentRepoId.value, selectedSshKeyId.value);
    message("绑定成功", { type: "success" });
    sshDialogVisible.value = false;
    onSearch();
  } catch {
    message("绑定失败", { type: "error" });
  } finally {
    sshDialogLoading.value = false;
  }
};

const fetchSshKeys = async () => {
  try {
    const { data } = await getSshKeys();
    sshKeys.value = data?.ssh_keys || [];
  } catch {
    sshKeys.value = [];
  }
};

onMounted(() => {
  onSearch();
  fetchSshKeys();
});
</script>

<template>
  <div class="main">
    <el-form :inline="true" class="search-form bg-bg_color w-full pl-8 pt-3">
      <el-form-item label="关键词：" prop="keyword">
        <el-input
          v-model="keyword"
          placeholder="请输入仓库名称或地址"
          clearable
          class="w-45!"
          @keyup.enter="onSearch"
        />
      </el-form-item>
      <el-form-item>
        <el-button
          type="primary"
          :icon="useRenderIcon(Search)"
          :loading="loading"
          @click="onSearch"
        >
          搜索
        </el-button>
        <el-button :icon="useRenderIcon(Refresh)" @click="resetSearch">
          重置
        </el-button>
      </el-form-item>
    </el-form>

    <PureTableBar title="仓库列表" :columns="columns" @refresh="onSearch">
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
          :pagination="{ ...pagination, size }"
          :header-cell-style="{
            background: 'var(--el-fill-color-light)',
            color: 'var(--el-text-color-primary)'
          }"
          @page-size-change="handleSizeChange"
          @page-current-change="handleCurrentChange"
        >
          <template #statsFlag="{ row }">
            <el-switch
              v-model="row.repo_stats_flag"
              :active-value="1"
              :inactive-value="0"
              @change="(val: number) => handleStatsFlagChange(row, val)"
            />
          </template>
          <template #sshKey="{ row }">
            <span v-if="row.ssh_key_id && sshKeyNameMap.get(row.ssh_key_id)">
              {{ sshKeyNameMap.get(row.ssh_key_id) }}
            </span>
            <span v-else class="text-gray-400">未绑定</span>
          </template>
          <template #operation="{ row }">
            <el-button
              class="reset-margin"
              link
              type="primary"
              :size="size"
              @click="openBranchDrawer(row)"
            >
              分支配置
            </el-button>
            <el-button
              class="reset-margin"
              link
              type="primary"
              :size="size"
              @click="openContributorDrawer(row)"
            >
              贡献者
            </el-button>
            <el-button
              class="reset-margin"
              link
              type="primary"
              :size="size"
              @click="openSshDialog(row)"
            >
              绑定 SSH Key
            </el-button>
          </template>
        </pure-table>
      </template>
    </PureTableBar>

    <el-drawer
      v-model="branchDrawerVisible"
      title="分支配置"
      direction="rtl"
      size="500px"
    >
      <div class="mb-4 text-sm text-gray-500">
        仓库: {{ currentRepoName }}
      </div>
      <el-table :data="branchConfigs" :loading="branchLoading" border>
        <el-table-column prop="branch_pattern" label="分支模式" min-width="150" />
        <el-table-column prop="pattern_type" label="类型" min-width="100" />
        <el-table-column prop="enabled" label="启用" min-width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled === 1 ? 'success' : 'info'">
              {{ row.enabled === 1 ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-drawer
      v-model="contributorDrawerVisible"
      title="贡献者统计"
      direction="rtl"
      size="500px"
    >
      <div class="mb-4 text-sm text-gray-500">
        仓库: {{ currentRepoName }}
      </div>
      <el-table :data="contributorStats" :loading="contributorLoading" border>
        <el-table-column prop="contributor_name" label="贡献者" min-width="120" />
        <el-table-column prop="ai_lines" label="AI代码行" min-width="100" />
        <el-table-column prop="non_ai_lines" label="非AI代码行" min-width="100" />
        <el-table-column prop="total_lines" label="总行数" min-width="100" />
      </el-table>
    </el-drawer>

    <el-dialog
      v-model="sshDialogVisible"
      title="绑定 SSH Key"
      width="400px"
      destroy-on-close
    >
      <el-form label-width="100px">
        <el-form-item label="SSH Key：">
          <el-select
            v-model="selectedSshKeyId"
            placeholder="请选择 SSH Key"
            clearable
            class="w-full"
          >
            <el-option
              v-for="key in sshKeys"
              :key="key.id"
              :label="key.key_name"
              :value="key.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sshDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sshDialogLoading" @click="confirmBindSshKey">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.main {
  padding: 20px;
}

.search-form {
  :deep(.el-form-item) {
    margin-bottom: 12px;
  }
}
</style>
