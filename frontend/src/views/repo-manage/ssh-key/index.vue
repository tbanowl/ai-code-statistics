<script setup lang="ts">
import { ref, onMounted } from "vue";
import { PureTableBar } from "@/components/RePureTableBar";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { message } from "@/utils/message";
import {
  getSshKeys,
  addSshKey,
  deleteSshKey,
  type SshKeyItem
} from "@/api/repo";

import AddFill from "~icons/ri/add-circle-line";
import Delete from "~icons/ep/delete";
import Refresh from "~icons/ep/refresh";

defineOptions({ name: "RepoManageSshKey" });

const loading = ref(false);
const dataList = ref<SshKeyItem[]>([]);

const dialogVisible = ref(false);
const dialogLoading = ref(false);
const form = ref({ key_name: "", public_key: "", private_key: "" });

const columns = [
  { label: "Key 名称", prop: "key_name", minWidth: 150 },
  { label: "公钥", prop: "public_key", minWidth: 200, slot: "publicKey" },
  { label: "创建时间", prop: "created_at", minWidth: 160, slot: "createdAt" },
  { label: "操作", fixed: "right", minWidth: 80, slot: "operation" }
];

const onSearch = async () => {
  loading.value = true;
  try {
    const { data } = await getSshKeys();
    dataList.value = data?.ssh_keys || [];
  } catch {
    message("获取 SSH Key 列表失败", { type: "error" });
  } finally {
    loading.value = false;
  }
};

const openDialog = () => {
  form.value = { key_name: "", public_key: "", private_key: "" };
  dialogVisible.value = true;
};

const handleAdd = async () => {
  if (!form.value.key_name.trim()) {
    message("Key 名称不能为空", { type: "warning" });
    return;
  }
  if (!form.value.private_key.trim()) {
    message("私钥不能为空", { type: "warning" });
    return;
  }
  dialogLoading.value = true;
  try {
    await addSshKey(form.value);
    message("添加成功", { type: "success" });
    dialogVisible.value = false;
    onSearch();
  } catch {
    message("添加失败", { type: "error" });
  } finally {
    dialogLoading.value = false;
  }
};

const handleDelete = async (row: SshKeyItem) => {
  try {
    await deleteSshKey(row.id);
    message("删除成功", { type: "success" });
    onSearch();
  } catch {
    message("删除失败", { type: "error" });
  }
};

const formatTime = (ts: number) => {
  if (!ts) return "-";
  return new Date(ts).toLocaleString("zh-CN");
};

onMounted(onSearch);
</script>

<template>
  <div class="main">
    <PureTableBar title="SSH Key 管理" :columns="columns" @refresh="onSearch">
      <template #buttons>
        <el-button
          type="primary"
          :icon="useRenderIcon(AddFill)"
          @click="openDialog"
        >
          新增 SSH Key
        </el-button>
      </template>
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
          <template #publicKey="{ row }">
            <span class="font-mono text-xs">
              {{ row.public_key ? row.public_key.slice(0, 40) + "…" : "-" }}
            </span>
          </template>
          <template #createdAt="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
          <template #operation="{ row }">
            <el-popconfirm
              :title="`确认删除 ${row.key_name}？`"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button
                  class="reset-margin"
                  link
                  type="danger"
                  :size="size"
                  :icon="useRenderIcon(Delete)"
                >
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </pure-table>
      </template>
    </PureTableBar>

    <el-dialog
      v-model="dialogVisible"
      title="新增 SSH Key"
      width="520px"
      destroy-on-close
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.key_name" placeholder="请输入 Key 名称" />
        </el-form-item>
        <el-form-item label="公钥">
          <el-input
            v-model="form.public_key"
            type="textarea"
            :rows="3"
            placeholder="请输入公钥内容（可选）"
          />
        </el-form-item>
        <el-form-item label="私钥" required>
          <el-input
            v-model="form.private_key"
            type="textarea"
            :rows="5"
            placeholder="请输入私钥内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogLoading" @click="handleAdd">
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
</style>
