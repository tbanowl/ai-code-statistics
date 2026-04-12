<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { PureTableBar } from "@/components/RePureTableBar";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { message } from "@/utils/message";
import {
  getRepoList,
  updateRepoStatsFlag,
  getAllRepoBranchConfigs,
  createRepoBranchConfig,
  updateRepoBranchConfig,
  deleteRepoBranchConfig,
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
import AddFill from "~icons/ri/add-circle-line";
import Delete from "~icons/ep/delete";
import EditIcon from "~icons/ep/edit";

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
const currentRepoId4Branch = ref("");

const branchDialogVisible = ref(false);
const branchDialogLoading = ref(false);
const branchDialogMode = ref<"add" | "edit">("add");
const branchDialogForm = ref({
  branch_pattern: "",
  pattern_type: "exact",
  enabled: 1
});
const branchDialogEditId = ref("");

watch(
  () => branchDialogForm.value.pattern_type,
  (type) => {
    if (type === "special") {
      branchDialogForm.value.branch_pattern = "all";
    } else if (branchDialogForm.value.branch_pattern === "all") {
      branchDialogForm.value.branch_pattern = "";
    }
  }
);

const contributorDrawerVisible = ref(false);
const contributorLoading = ref(false);
const contributorStats = ref<ContributorStat[]>([]);

const sshDialogVisible = ref(false);
const sshDialogLoading = ref(false);
const selectedSshKeyId = ref<string | null>(null);
const currentRepoId = ref<string>("");

const branchPatternTypeMap = {
  exact: "精确匹配",
  wildcard: "通配符",
  special: "特殊规则"
};

const columns = [
  {
    label: "仓库名称",
    prop: "repo_name",
    width: 120,
    slot: "repoName"
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
    width: 300,
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
  currentRepoId4Branch.value = row.id;
  branchDrawerVisible.value = true;
  branchLoading.value = true;
  try {
    const { data } = await getAllRepoBranchConfigs(row.id);
    branchConfigs.value = data?.configs || [];
  } catch {
    message("获取分支配置失败", { type: "error" });
    branchConfigs.value = [];
  } finally {
    branchLoading.value = false;
  }
};

const refreshBranchConfigs = async () => {
  branchLoading.value = true;
  try {
    const { data } = await getAllRepoBranchConfigs(currentRepoId4Branch.value);
    branchConfigs.value = data?.configs || [];
  } catch {
    message("获取分支配置失败", { type: "error" });
  } finally {
    branchLoading.value = false;
  }
};

const openBranchAdd = () => {
  branchDialogMode.value = "add";
  branchDialogForm.value = {
    branch_pattern: "",
    pattern_type: "exact",
    enabled: 1
  };
  branchDialogEditId.value = "";
  branchDialogVisible.value = true;
};

const openBranchEdit = (row: BranchConfig) => {
  branchDialogMode.value = "edit";
  branchDialogForm.value = {
    branch_pattern: row.branch_pattern,
    pattern_type: row.pattern_type,
    enabled: row.enabled
  };
  branchDialogEditId.value = row.id;
  branchDialogVisible.value = true;
};

const handleBranchDialogConfirm = async () => {
  if (!branchDialogForm.value.branch_pattern.trim()) {
    message("分支模式不能为空", { type: "warning" });
    return;
  }
  branchDialogLoading.value = true;
  try {
    if (branchDialogMode.value === "add") {
      await createRepoBranchConfig(
        currentRepoId4Branch.value,
        branchDialogForm.value
      );
      message("添加成功", { type: "success" });
    } else {
      await updateRepoBranchConfig(
        currentRepoId4Branch.value,
        branchDialogEditId.value,
        branchDialogForm.value
      );
      message("更新成功", { type: "success" });
    }
    branchDialogVisible.value = false;
    refreshBranchConfigs();
  } catch {
    message(branchDialogMode.value === "add" ? "添加失败" : "更新失败", {
      type: "error"
    });
  } finally {
    branchDialogLoading.value = false;
  }
};

const handleBranchDelete = async (row: BranchConfig) => {
  try {
    await deleteRepoBranchConfig(currentRepoId4Branch.value, row.id);
    message("删除成功", { type: "success" });
    refreshBranchConfigs();
  } catch {
    message("删除失败", { type: "error" });
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
          <template #repoName="{ row }">
            <el-tooltip
              v-if="row.repo_name"
              :content="row.repo_name"
              placement="top-start"
              effect="dark"
            >
              <span class="single-line-cell cursor-help">{{
                row.repo_name
              }}</span>
            </el-tooltip>
            <span v-else class="single-line-cell">-</span>
          </template>
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
      size="600px"
    >
      <div class="flex items-center mb-3">
        <span class="text-sm text-gray-500">仓库: {{ currentRepoName }}</span>
        <div class="flex-1" />
        <el-button
          type="primary"
          :icon="useRenderIcon(AddFill)"
          size="small"
          @click="openBranchAdd"
        >
          新增
        </el-button>
      </div>
      <el-table v-loading="branchLoading" :data="branchConfigs" border>
        <el-table-column
          prop="branch_pattern"
          label="分支模式"
          min-width="110"
        />
        <el-table-column prop="pattern_type" label="类型" width="90">
          <template #default="{ row }">
            {{ branchPatternTypeMap[row.pattern_type] || row.pattern_type }}
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="启用" width="70">
          <template #default="{ row }">
            <el-tag :type="row.enabled === 1 ? 'success' : 'info'" size="small">
              {{ row.enabled === 1 ? "是" : "否" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :icon="useRenderIcon(EditIcon)"
              @click="openBranchEdit(row)"
              >编辑</el-button
            >
            <el-popconfirm
              title="确认删除？"
              @confirm="handleBranchDelete(row)"
            >
              <template #reference>
                <el-button link type="danger" :icon="useRenderIcon(Delete)"
                  >删除</el-button
                >
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-dialog
      v-model="branchDialogVisible"
      :title="branchDialogMode === 'add' ? '新增分支配置' : '编辑分支配置'"
      width="440px"
      destroy-on-close
    >
      <el-form :model="branchDialogForm" label-width="90px">
        <el-form-item label="匹配类型" required>
          <el-select v-model="branchDialogForm.pattern_type" class="w-full">
            <el-option label="精确匹配" value="exact" />
            <el-option label="通配符" value="wildcard" />
            <el-option label="特殊规则" value="special" />
          </el-select>
          <div class="el-form-item__tip">
            <p><b>精确匹配</b>：完全匹配分支名，如 <code>main</code></p>
            <p><b>通配符</b>：支持 <code>*</code> 通配，如 <code>release/*</code></p>
            <p><b>特殊规则</b>：内置规则，如所有分支</p>
          </div>
        </el-form-item>
        <el-form-item label="分支模式" required>
          <el-select
            v-if="branchDialogForm.pattern_type === 'special'"
            v-model="branchDialogForm.branch_pattern"
            class="w-full"
          >
            <el-option label="所有分支" value="all" />
          </el-select>
          <el-input
            v-else
            v-model="branchDialogForm.branch_pattern"
            :placeholder="branchDialogForm.pattern_type === 'wildcard' ? '如 release/*' : '如 main'"
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch
            v-model="branchDialogForm.enabled"
            :active-value="1"
            :inactive-value="0"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="branchDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="branchDialogLoading"
          @click="handleBranchDialogConfirm"
          >确定</el-button
        >
      </template>
    </el-dialog>

    <el-drawer
      v-model="contributorDrawerVisible"
      title="贡献者统计"
      direction="rtl"
      size="500px"
    >
      <div class="mb-4 text-sm text-gray-500">仓库: {{ currentRepoName }}</div>
      <el-table :data="contributorStats" :loading="contributorLoading" border>
        <el-table-column
          prop="contributor_name"
          label="贡献者"
          min-width="120"
        />
        <el-table-column prop="ai_lines" label="AI代码行" min-width="100" />
        <el-table-column
          prop="non_ai_lines"
          label="非AI代码行"
          min-width="100"
        />
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
        <el-button
          type="primary"
          :loading="sshDialogLoading"
          @click="confirmBindSshKey"
        >
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

.single-line-cell {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
