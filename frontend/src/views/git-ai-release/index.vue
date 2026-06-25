<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { PureTableBar } from "@/components/RePureTableBar";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { message } from "@/utils/message";
import {
  activateGitAiRelease,
  deleteGitAiRelease,
  getGitAiReleaseChannels,
  getGitAiReleaseDetail,
  getGitAiReleaseList,
  releaseArtifactDownloadUrl,
  uploadGitAiRelease,
  type GitAiReleaseArtifact,
  type GitAiReleaseItem
} from "@/api/gitAiRelease";

import AddFill from "~icons/ri/add-circle-line";
import Check from "~icons/ep/check";
import Delete from "~icons/ep/delete";
import Refresh from "~icons/ep/refresh";
import UploadFilled from "~icons/ep/upload-filled";
import View from "~icons/ep/view";

defineOptions({ name: "GitAiReleaseManage" });

const requiredFiles = ["install.ps1", "git-ai-windows-x64.exe"];
const channels = ["latest", "next", "enterprise-latest", "enterprise-next"];

const loading = ref(false);
const dataList = ref<GitAiReleaseItem[]>([]);
const channelCards = ref<Record<string, { version: string; checksum: string }>>({});

const uploadVisible = ref(false);
const uploadLoading = ref(false);
const uploadFiles = ref<File[]>([]);
const uploadForm = ref({
  tag: "",
  version: "",
  channel: "latest",
  description: ""
});

const detailVisible = ref(false);
const detailLoading = ref(false);
const detailRelease = ref<GitAiReleaseItem | null>(null);
const detailArtifacts = ref<GitAiReleaseArtifact[]>([]);

const columns = [
  { label: "Tag", prop: "tag", width: 120, slot: "tag" },
  { label: "通道", prop: "channel", width: 150, slot: "channel" },
  { label: "状态", prop: "status", width: 100, slot: "status" },
  { label: "文件数", prop: "artifact_count", width: 90 },
  { label: "总大小", prop: "total_size_bytes", width: 100, slot: "size" },
  {
    label: "SHA256SUMS",
    prop: "sha256sums_checksum",
    minWidth: 220,
    slot: "checksum"
  },
  { label: "上传时间", prop: "created_at", width: 170, slot: "createdAt" },
  { label: "操作", fixed: "right", minWidth: 250, slot: "operation" }
];

const artifactColumns = [
  { label: "文件名", prop: "filename", minWidth: 210, slot: "filename" },
  { label: "类型", prop: "artifact_type", minWidth: 100 },
  { label: "平台", prop: "platform", minWidth: 120 },
  { label: "大小", prop: "size_bytes", minWidth: 100, slot: "artifactSize" },
  { label: "SHA-256", prop: "sha256", minWidth: 260, slot: "artifactSha" }
];

const selectedFileNames = computed(() =>
  uploadFiles.value.map(file => file.name)
);

const missingFiles = computed(() =>
  requiredFiles.filter(name => !selectedFileNames.value.includes(name))
);

const formatTime = (ts?: number | null) => {
  if (!ts) return "-";
  return new Date(ts).toLocaleString("zh-CN");
};

const formatBytes = (value?: number) => {
  if (!value) return "0 B";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
};

const shortHash = (value: string) => (value ? `${value.slice(0, 12)}…` : "-");

const loadChannels = async () => {
  const result = await getGitAiReleaseChannels();
  channelCards.value = result.channels || {};
};

const onSearch = async () => {
  loading.value = true;
  try {
    const result = await getGitAiReleaseList();
    dataList.value = result.releases || result.data?.releases || [];
    await loadChannels();
  } catch {
    message("获取发布列表失败", { type: "error" });
  } finally {
    loading.value = false;
  }
};

const openUpload = () => {
  uploadForm.value = { tag: "", version: "", channel: "latest", description: "" };
  uploadFiles.value = [];
  uploadVisible.value = true;
};

const handleFileChange = (_file: unknown, fileList: Array<{ raw?: File }>) => {
  uploadFiles.value = fileList
    .map(file => file.raw)
    .filter((file): file is File => Boolean(file));
};

const removeUploadFile = (file: { name: string }) => {
  uploadFiles.value = uploadFiles.value.filter(item => item.name !== file.name);
};

const handleUpload = async () => {
  if (!uploadForm.value.tag.trim()) {
    message("Tag 不能为空", { type: "warning" });
    return;
  }
  if (missingFiles.value.length > 0) {
    message(`缺少必需文件：${missingFiles.value.join("、")}`, { type: "warning" });
    return;
  }
  const formData = new FormData();
  formData.append("tag", uploadForm.value.tag.trim());
  formData.append("version", uploadForm.value.version.trim() || uploadForm.value.tag.trim());
  formData.append("channel", uploadForm.value.channel);
  formData.append("description", uploadForm.value.description.trim());
  uploadFiles.value.forEach(file => formData.append("files", file));

  uploadLoading.value = true;
  try {
    await uploadGitAiRelease(formData);
    message("上传成功，发布包已进入待激活状态", { type: "success" });
    uploadVisible.value = false;
    await onSearch();
  } catch {
    message("上传发布包失败", { type: "error" });
  } finally {
    uploadLoading.value = false;
  }
};

const openDetail = async (row: GitAiReleaseItem) => {
  detailVisible.value = true;
  detailLoading.value = true;
  try {
    const result = await getGitAiReleaseDetail(row.id);
    detailRelease.value = result.release || result.data?.release || row;
    detailArtifacts.value = result.artifacts || result.data?.artifacts || [];
  } catch {
    message("获取发布详情失败", { type: "error" });
  } finally {
    detailLoading.value = false;
  }
};

const handleActivate = async (row: GitAiReleaseItem) => {
  try {
    await activateGitAiRelease(row.id);
    message("激活成功", { type: "success" });
    await onSearch();
  } catch {
    message("激活失败", { type: "error" });
  }
};

const handleDelete = async (row: GitAiReleaseItem) => {
  try {
    await deleteGitAiRelease(row.id);
    message("删除成功", { type: "success" });
    await onSearch();
  } catch {
    message("删除失败，active 发布不能直接删除", { type: "error" });
  }
};

onMounted(onSearch);
</script>

<template>
  <div class="main release-page">
    <div class="channel-grid">
      <el-card v-for="channel in channels" :key="channel" shadow="never" class="channel-card">
        <div class="channel-name">{{ channel }}</div>
        <div class="channel-version">
          {{ channelCards[channel]?.version || "未激活" }}
        </div>
        <div class="channel-checksum">
          {{ shortHash(channelCards[channel]?.checksum || "") }}
        </div>
      </el-card>
    </div>

    <PureTableBar title="Git-AI 发布管理" :columns="columns" @refresh="onSearch">
      <template #buttons>
        <el-button :icon="useRenderIcon(Refresh)" @click="onSearch">刷新</el-button>
        <el-button type="primary" :icon="useRenderIcon(AddFill)" @click="openUpload">
          上传发布包
        </el-button>
      </template>
      <template v-slot="{ size, dynamicColumns }">
        <pure-table row-key="id" adaptive :adaptiveConfig="{ offsetBottom: 108 }" align-whole="center"
          table-layout="auto" :loading="loading" :size="size" :data="dataList" :columns="dynamicColumns"
          :header-cell-style="{
            background: 'var(--el-fill-color-light)',
            color: 'var(--el-text-color-primary)'
          }">
          <template #tag="{ row }">
            <span class="font-mono font-semibold">{{ row.tag }}</span>
          </template>
          <template #channel="{ row }">
            <el-tag effect="plain">{{ row.channel }}</el-tag>
          </template>
          <template #status="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === "active" ? "已激活" : "待激活" }}
            </el-tag>
          </template>
          <template #size="{ row }">
            {{ formatBytes(row.total_size_bytes) }}
          </template>
          <template #checksum="{ row }">
            <span class="font-mono text-xs">{{ shortHash(row.sha256sums_checksum) }}</span>
          </template>
          <template #createdAt="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
          <template #operation="{ row }">
            <el-button link type="primary" :size="size" :icon="useRenderIcon(View)" @click="openDetail(row)">
              详情
            </el-button>
            <el-popconfirm v-if="row.status !== 'active'" :title="`确认激活 ${row.tag} 到 ${row.channel}？`"
              @confirm="handleActivate(row)">
              <template #reference>
                <el-button link type="success" :size="size" :icon="useRenderIcon(Check)">
                  激活
                </el-button>
              </template>
            </el-popconfirm>
            <el-popconfirm v-if="row.status !== 'active'" :title="`确认删除 ${row.tag}？`" @confirm="handleDelete(row)">
              <template #reference>
                <el-button link type="danger" :size="size" :icon="useRenderIcon(Delete)">
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </pure-table>
      </template>
    </PureTableBar>

    <el-dialog v-model="uploadVisible" title="上传 Git-AI Windows 发布包" width="min(640px, 92vw)" destroy-on-close>
      <el-alert class="mb-4" type="info" :closable="false"
        title="第一版只支持 Windows，必须上传 install.ps1 和 git-ai-windows-x64.exe。SHA256SUMS 由服务端生成。" />
      <el-form :model="uploadForm" label-width="90px">
        <el-form-item label="Tag" required>
          <el-input v-model="uploadForm.tag" placeholder="例如 v1.2.3" />
        </el-form-item>
        <el-form-item label="Version">
          <el-input v-model="uploadForm.version" placeholder="默认等于 Tag" />
        </el-form-item>
        <el-form-item label="Channel" required>
          <el-select v-model="uploadForm.channel" class="w-full">
            <el-option v-for="channel in channels" :key="channel" :label="channel" :value="channel" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="uploadForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="文件" required>
          <el-upload drag multiple :auto-upload="false" :on-change="handleFileChange" :on-remove="removeUploadFile">
            <el-icon class="el-icon--upload">
              <UploadFilled />
            </el-icon>
            <div class="el-upload__text">拖拽或点击选择本地构建文件</div>
          </el-upload>
          <div class="required-files">
            <el-tag v-for="name in requiredFiles" :key="name"
              :type="selectedFileNames.includes(name) ? 'success' : 'danger'" effect="plain">
              {{ name }}
            </el-tag>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadLoading" @click="handleUpload">
          上传
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="发布详情" width="min(880px, 92vw)" destroy-on-close>
      <el-skeleton v-if="detailLoading" :rows="5" animated />
      <template v-else>
        <el-descriptions v-if="detailRelease" :column="2" border class="mb-4">
          <el-descriptions-item label="Tag">{{ detailRelease.tag }}</el-descriptions-item>
          <el-descriptions-item label="通道">{{ detailRelease.channel }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detailRelease.status }}</el-descriptions-item>
          <el-descriptions-item label="上传时间">{{ formatTime(detailRelease.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="SHA256SUMS" :span="2">
            <span class="hash-text">{{ detailRelease.sha256sums_checksum }}</span>
          </el-descriptions-item>
        </el-descriptions>
        <pure-table row-key="id" align-whole="center" table-layout="auto" :data="detailArtifacts"
          :columns="artifactColumns">
          <template #filename="{ row }">
            <a class="artifact-link"
              :href="detailRelease ? releaseArtifactDownloadUrl(detailRelease.channel, row.filename) : '#'"
              target="_blank">
              {{ row.filename }}
            </a>
          </template>
          <template #artifactSize="{ row }">{{ formatBytes(row.size_bytes) }}</template>
          <template #artifactSha="{ row }">
            <span class="hash-text">{{ row.sha256 }}</span>
          </template>
        </pure-table>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.main {
  padding: 20px;
}

.channel-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.channel-card {
  border-color: var(--el-border-color-light);
}

.channel-name {
  min-width: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  overflow-wrap: anywhere;
}

.channel-version {
  min-width: 0;
  margin-top: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 20px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  overflow-wrap: anywhere;
}

.channel-checksum {
  min-width: 0;
  margin-top: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  overflow-wrap: anywhere;
}

.required-files {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.artifact-link {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: var(--el-color-primary);
}

.hash-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
  word-break: break-all;
}

@media (max-width: 1200px) {
  .channel-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .main {
    padding: 12px;
  }

  .channel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
