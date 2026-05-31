<script setup lang="ts">
import dayjs from "dayjs";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useDark, useECharts } from "@pureadmin/utils";
import { message } from "@/utils/message";
import {
  getContributorStats,
  getDailyStats,
  getRepoStats,
  getStats,
  triggerStatsAggregate,
  getBlameRepoStats,
  type BlameRepoStatItem,
  type DailyStatItem,
  type StatsData
} from "@/api/stats";

defineOptions({
  name: "Welcome"
});

type RankingItem = {
  name: string;
  aiAcceptedLines: number;
  humanLines: number;
  aiPercentage: number;
};

type SummaryCard = {
  title: string;
  value: string;
  subtitle: string;
  loading: boolean;
  error: string | null;
};

const DEFAULT_RANGE_DAYS = 30;
const DAILY_FETCH_LIMIT = 100;
const DAILY_TABLE_LIMIT = 20;

const { isDark } = useDark();
const chartTheme = computed(() => (isDark.value ? "dark" : "light"));

const statsData = ref<StatsData | null>(null);
const repoTotal = ref(0);
const contributorTotal = ref(0);
const dailyRows = ref<DailyStatItem[]>([]);
const dailyTotal = ref(0);
const lastUpdatedAt = ref("");

const blameRows = ref<BlameRepoStatItem[]>([]);
const blameTotal = ref(0);
const blamePage = ref(1);
const blamePageSize = ref(20);
const blameLoading = ref(false);
const blameError = ref<string | null>(null);

const summaryLoading = ref(false);
const repositoriesLoading = ref(false);
const contributorsLoading = ref(false);
const dailyLoading = ref(false);
const aggregateLoading = ref(false);

const summaryError = ref<string | null>(null);
const repositoriesError = ref<string | null>(null);
const contributorsError = ref<string | null>(null);
const dailyError = ref<string | null>(null);

const startDate = computed(() =>
  Number(
    dayjs()
      .subtract(DEFAULT_RANGE_DAYS - 1, "day")
      .format("YYYYMMDD")
  )
);
const endDate = computed(() => Number(dayjs().format("YYYYMMDD")));

const rangeLabel = computed(
  () => `${formatStatDate(startDate.value)} ~ ${formatStatDate(endDate.value)}`
);
const lastUpdatedLabel = computed(() => lastUpdatedAt.value || "尚未加载");

const trendLabels = computed(() =>
  (statsData.value?.items ?? []).map(item =>
    formatStatDate(item.stat_date, true)
  )
);
const aiAcceptedTrend = computed(() =>
  (statsData.value?.items ?? []).map(item => toNumber(item.ai_accepted_lines))
);
const humanTrend = computed(() =>
  (statsData.value?.items ?? []).map(item => toNumber(item.human_lines))
);
const hasTrendData = computed(() => trendLabels.value.length > 0);

const summaryCards = computed<SummaryCard[]>(() => {
  const summary = statsData.value?.summary;

  return [
    {
      title: "AI 接受行数",
      value: summary ? formatNumber(summary.total_ai_accepted) : "--",
      subtitle: "近 30 天累计被接受的 AI 代码行数",
      loading: summaryLoading.value,
      error: summaryError.value
    },
    {
      title: "AI 占比",
      value: summary ? formatPercent(summary.avg_ai_percentage) : "--",
      subtitle: "AI 接受行数 / (AI 接受行数 + 人工行数)",
      loading: summaryLoading.value,
      error: summaryError.value
    },
    {
      title: "仓库总数",
      value: repositoriesLoading.value ? "--" : formatNumber(repoTotal.value),
      subtitle: "已接入统计的仓库数量",
      loading: repositoriesLoading.value,
      error: repositoriesError.value
    },
    {
      title: "贡献者总数",
      value: contributorsLoading.value
        ? "--"
        : formatNumber(contributorTotal.value),
      subtitle: "已纳入统计的贡献者数量",
      loading: contributorsLoading.value,
      error: contributorsError.value
    }
  ];
});

const repositoryRankings = computed(() =>
  buildRankings(dailyRows.value, "repo_name")
);
const contributorRankings = computed(() =>
  buildRankings(dailyRows.value, "contributor_name")
);
const dailyTableRows = computed(() =>
  dailyRows.value.slice(0, DAILY_TABLE_LIMIT)
);

const trendChartRef = ref();
const { setOptions } = useECharts(trendChartRef, {
  theme: chartTheme
});

watch(
  [trendLabels, aiAcceptedTrend, humanTrend, chartTheme],
  async () => {
    if (!hasTrendData.value) return;

    await nextTick();

    setOptions({
      color: ["#409eff", "#67c23a"],
      tooltip: {
        trigger: "axis"
      },
      legend: {
        bottom: 0,
        data: ["AI 接受行数", "人工行数"]
      },
      grid: {
        top: 24,
        left: 18,
        right: 18,
        bottom: 48,
        containLabel: true
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: trendLabels.value
      },
      yAxis: {
        type: "value",
        splitLine: {
          lineStyle: {
            type: "dashed"
          }
        }
      },
      series: [
        {
          name: "AI 接受行数",
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 8,
          areaStyle: {
            opacity: 0.18
          },
          data: aiAcceptedTrend.value
        },
        {
          name: "人工行数",
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 8,
          areaStyle: {
            opacity: 0.08
          },
          data: humanTrend.value
        }
      ]
    });
  },
  { immediate: true }
);

onMounted(() => {
  refreshDashboard();
});

async function refreshDashboard() {
  await Promise.allSettled([
    fetchSummary(),
    fetchRepositoryCount(),
    fetchContributorCount(),
    fetchDailyRows(),
    fetchBlameRows()
  ]);

  lastUpdatedAt.value = dayjs().format("YYYY-MM-DD HH:mm:ss");
}

async function fetchSummary() {
  summaryLoading.value = true;
  summaryError.value = null;

  try {
    const response = await getStats({
      start_date: startDate.value,
      end_date: endDate.value,
      granularity: "daily"
    });

    statsData.value = response.data;
  } catch (error) {
    statsData.value = null;
    summaryError.value = getErrorMessage(error, "总览数据加载失败");
  } finally {
    summaryLoading.value = false;
  }
}

async function fetchRepositoryCount() {
  repositoriesLoading.value = true;
  repositoriesError.value = null;

  try {
    const response = await getRepoStats({
      page: 1,
      page_size: 1
    });

    repoTotal.value = response.pagination?.total ?? response.data.length;
  } catch (error) {
    repoTotal.value = 0;
    repositoriesError.value = getErrorMessage(error, "仓库列表加载失败");
  } finally {
    repositoriesLoading.value = false;
  }
}

async function fetchContributorCount() {
  contributorsLoading.value = true;
  contributorsError.value = null;

  try {
    const response = await getContributorStats({
      page: 1,
      page_size: 1
    });

    contributorTotal.value = response.pagination?.total ?? response.data.length;
  } catch (error) {
    contributorTotal.value = 0;
    contributorsError.value = getErrorMessage(error, "贡献者列表加载失败");
  } finally {
    contributorsLoading.value = false;
  }
}

async function fetchDailyRows() {
  dailyLoading.value = true;
  dailyError.value = null;

  try {
    const response = await getDailyStats({
      page: 1,
      page_size: DAILY_FETCH_LIMIT,
      start_date: startDate.value,
      end_date: endDate.value
    });

    dailyRows.value = response.data;
    dailyTotal.value = response.pagination?.total ?? response.data.length;
  } catch (error) {
    dailyRows.value = [];
    dailyTotal.value = 0;
    dailyError.value = getErrorMessage(error, "按天明细加载失败");
  } finally {
    dailyLoading.value = false;
  }
}

async function fetchBlameRows() {
  blameLoading.value = true;
  blameError.value = null;

  try {
    const response = await getBlameRepoStats({
      page: blamePage.value,
      page_size: blamePageSize.value,
      start_date: startDate.value,
      end_date: endDate.value
    });

    blameRows.value = response.data;
    blameTotal.value = response.pagination?.total ?? response.data.length;
  } catch (error) {
    blameRows.value = [];
    blameTotal.value = 0;
    blameError.value = getErrorMessage(error, "仓库归因统计加载失败");
  } finally {
    blameLoading.value = false;
  }
}

async function handleTriggerAggregate() {
  aggregateLoading.value = true;

  try {
    const response = await triggerStatsAggregate({
      start_date: startDate.value,
      end_date: endDate.value
    });

    message(response.data.message || "聚合任务已提交", {
      type: "success"
    });
  } catch (error) {
    message(getErrorMessage(error, "触发聚合失败"), {
      type: "error"
    });
  } finally {
    aggregateLoading.value = false;
  }
}

function buildRankings(
  rows: DailyStatItem[],
  key: "repo_name" | "contributor_name"
): RankingItem[] {
  const grouped = new Map<
    string,
    { aiAcceptedLines: number; humanLines: number }
  >();

  rows.forEach(row => {
    const name = sanitizeName(row[key]);
    const current = grouped.get(name) ?? {
      aiAcceptedLines: 0,
      humanLines: 0
    };

    current.aiAcceptedLines += toNumber(row.ai_accepted_lines);
    current.humanLines += toNumber(row.human_lines);

    grouped.set(name, current);
  });

  return Array.from(grouped.entries())
    .map(([name, item]) => {
      const total = item.aiAcceptedLines + item.humanLines;

      return {
        name,
        aiAcceptedLines: item.aiAcceptedLines,
        humanLines: item.humanLines,
        aiPercentage: total > 0 ? (item.aiAcceptedLines / total) * 100 : 0
      };
    })
    .sort((left, right) => right.aiAcceptedLines - left.aiAcceptedLines)
    .slice(0, 5);
}

function sanitizeName(value: string | null | undefined) {
  if (!value || !value.trim()) return "未命名";
  return value;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(toNumber(value));
}

function formatPercent(value: number | string) {
  return `${toNumber(value).toFixed(2)}%`;
}

function formatStatDate(value: number, short = false) {
  const text = String(value).padStart(8, "0");
  const year = text.slice(0, 4);
  const month = text.slice(4, 6);
  const day = text.slice(6, 8);

  return short ? `${month}-${day}` : `${year}-${month}-${day}`;
}

function toNumber(value: number | string | null | undefined) {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  return 0;
}

function getErrorMessage(error: unknown, fallback: string) {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = error.response;

    if (
      typeof response === "object" &&
      response !== null &&
      "data" in response
    ) {
      const data = response.data;

      if (typeof data === "object" && data !== null && "error" in data) {
        const responseError = data.error;

        if (typeof responseError === "string" && responseError.trim()) {
          return responseError;
        }
      }
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
}
</script>

<template>
  <div class="welcome-dashboard">
    <el-card
      shadow="never"
      class="page-header-card mb-4.5"
      :body-style="{ padding: '20px' }"
    >
      <div class="page-header">
        <div>
          <h2 class="page-title">AI 代码统计总览</h2>
          <p class="page-description">
            默认展示近 30 天全局数据，帮助你快速判断团队 AI
            使用规模与代码接受趋势。
          </p>
          <div class="header-tags">
            <el-tag effect="plain" round>全局汇总</el-tag>
            <el-tag effect="plain" round type="success">{{
              rangeLabel
            }}</el-tag>
            <el-tag effect="plain" round type="info">
              最近更新：{{ lastUpdatedLabel }}
            </el-tag>
          </div>
        </div>

        <div class="header-actions">
          <el-button plain @click="refreshDashboard">刷新数据</el-button>
          <el-button
            type="primary"
            :loading="aggregateLoading"
            @click="handleTriggerAggregate"
          >
            手动触发聚合
          </el-button>
        </div>
      </div>
    </el-card>

    <el-row :gutter="24" class="mb-4.5">
      <el-col
        v-for="card in summaryCards"
        :key="card.title"
        :xs="24"
        :sm="12"
        :lg="6"
        class="mb-4.5"
      >
        <el-card
          shadow="never"
          class="summary-card"
          :body-style="{ padding: '20px' }"
        >
          <div class="summary-card__label">{{ card.title }}</div>
          <div class="summary-card__value">
            <el-skeleton v-if="card.loading" animated :rows="1">
              <template #template>
                <el-skeleton-item
                  variant="text"
                  style="width: 60%; height: 32px"
                />
              </template>
            </el-skeleton>
            <span v-else>{{ card.value }}</span>
          </div>
          <div v-if="card.error" class="summary-card__error">
            {{ card.error }}
          </div>
          <div v-else class="summary-card__subtitle">{{ card.subtitle }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card
      shadow="never"
      class="mb-4.5"
      :body-style="{ padding: '20px 20px 12px' }"
    >
      <template #header>
        <div class="card-header">
          <div>
            <span class="card-title">30 天趋势</span>
            <p class="card-tip">AI 接受行数与人工行数的按天变化</p>
          </div>
        </div>
      </template>

      <div v-loading="summaryLoading" class="trend-panel">
        <el-empty
          v-if="summaryError"
          :image-size="72"
          :description="summaryError"
        />
        <el-empty
          v-else-if="!hasTrendData"
          :image-size="72"
          description="近 30 天暂无趋势数据"
        />
        <div v-else ref="trendChartRef" class="trend-chart" />
      </div>
    </el-card>

    <el-row :gutter="24" class="mb-4.5">
      <el-col :xs="24" :lg="12" class="mb-4.5">
        <el-card shadow="never" class="h-full">
          <template #header>
            <div class="card-header">
              <div>
                <span class="card-title">近期活跃仓库</span>
                <p class="card-tip">基于最近 100 条按天统计明细聚合</p>
              </div>
              <el-tag effect="plain" round
                >{{ formatNumber(repoTotal) }} 个仓库</el-tag
              >
            </div>
          </template>

          <el-empty
            v-if="dailyError"
            :image-size="72"
            :description="dailyError"
          />
          <el-table
            v-else
            v-loading="dailyLoading"
            :data="repositoryRankings"
            stripe
            size="large"
            show-overflow-tooltip
          >
            <el-table-column type="index" label="#" width="60" />
            <el-table-column prop="name" label="仓库" min-width="200" />
            <el-table-column
              prop="aiAcceptedLines"
              label="AI 接受行数"
              min-width="130"
            >
              <template #default="{ row }">
                {{ formatNumber(row.aiAcceptedLines) }}
              </template>
            </el-table-column>
            <el-table-column prop="humanLines" label="人工行数" min-width="120">
              <template #default="{ row }">
                {{ formatNumber(row.humanLines) }}
              </template>
            </el-table-column>
            <el-table-column prop="aiPercentage" label="AI 占比" width="100">
              <template #default="{ row }">
                <el-tag effect="plain" round type="primary">
                  {{ formatPercent(row.aiPercentage) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12" class="mb-4.5">
        <el-card shadow="never" class="h-full">
          <template #header>
            <div class="card-header">
              <div>
                <span class="card-title">近期活跃贡献者</span>
                <p class="card-tip">基于最近 100 条按天统计明细聚合</p>
              </div>
              <el-tag effect="plain" round type="success">
                {{ formatNumber(contributorTotal) }} 位贡献者
              </el-tag>
            </div>
          </template>

          <el-empty
            v-if="dailyError"
            :image-size="72"
            :description="dailyError"
          />
          <el-table
            v-else
            v-loading="dailyLoading"
            :data="contributorRankings"
            stripe
            size="large"
            show-overflow-tooltip
          >
            <el-table-column type="index" label="#" width="60" />
            <el-table-column prop="name" label="贡献者" min-width="180" />
            <el-table-column
              prop="aiAcceptedLines"
              label="AI 接受行数"
              min-width="130"
            >
              <template #default="{ row }">
                {{ formatNumber(row.aiAcceptedLines) }}
              </template>
            </el-table-column>
            <el-table-column prop="humanLines" label="人工行数" min-width="120">
              <template #default="{ row }">
                {{ formatNumber(row.humanLines) }}
              </template>
            </el-table-column>
            <el-table-column prop="aiPercentage" label="AI 占比" width="100">
              <template #default="{ row }">
                <el-tag effect="plain" round type="success">
                  {{ formatPercent(row.aiPercentage) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <span class="card-title">按天统计明细</span>
            <p class="card-tip">
              展示最近 {{ DAILY_TABLE_LIMIT }} 条记录，共
              {{ formatNumber(dailyTotal) }} 条
            </p>
          </div>
        </div>
      </template>

      <el-empty v-if="dailyError" :image-size="72" :description="dailyError" />
      <el-table
        v-else
        v-loading="dailyLoading"
        :data="dailyTableRows"
        stripe
        size="large"
        show-overflow-tooltip
      >
        <el-table-column prop="stat_date" label="统计日期" width="120">
          <template #default="{ row }">
            {{ formatStatDate(row.stat_date) }}
          </template>
        </el-table-column>
        <el-table-column prop="repo_name" label="仓库" min-width="180" />
        <el-table-column
          prop="contributor_name"
          label="贡献者"
          min-width="150"
        />
        <el-table-column
          prop="ai_accepted_lines"
          label="AI 接受行数"
          min-width="130"
        >
          <template #default="{ row }">
            {{ formatNumber(row.ai_accepted_lines) }}
          </template>
        </el-table-column>
        <el-table-column prop="human_lines" label="人工行数" min-width="120">
          <template #default="{ row }">
            {{ formatNumber(row.human_lines) }}
          </template>
        </el-table-column>
        <el-table-column prop="ai_percentage" label="AI 占比" width="100">
          <template #default="{ row }">
            <el-tag effect="plain" round>
              {{ formatPercent(row.ai_percentage) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-card shadow="never" class="mt-4.5">
      <template #header>
        <div class="card-header">
          <div>
            <span class="card-title">仓库代码归因统计</span>
            <p class="card-tip">以仓库、分支、日期为维度的代码行数归因报表</p>
          </div>
          <el-tag effect="plain" round type="info">
            共 {{ formatNumber(blameTotal) }} 条
          </el-tag>
        </div>
      </template>

      <el-empty v-if="blameError" :image-size="72" :description="blameError" />
      <template v-else>
        <el-table
          v-loading="blameLoading"
          :data="blameRows"
          stripe
          size="large"
          show-overflow-tooltip
        >
          <el-table-column prop="stat_date" label="统计日期" width="120">
            <template #default="{ row }">
              {{ formatStatDate(row.stat_date) }}
            </template>
          </el-table-column>
          <el-table-column prop="repo_name" label="仓库" min-width="180" />
          <el-table-column prop="branch" label="分支" min-width="140" />
          <el-table-column prop="ai_lines" label="AI 代码行数" min-width="130">
            <template #default="{ row }">
              {{ formatNumber(row.ai_lines) }}
            </template>
          </el-table-column>
          <el-table-column prop="non_ai_lines" label="人工代码行数" min-width="130">
            <template #default="{ row }">
              {{ formatNumber(row.non_ai_lines) }}
            </template>
          </el-table-column>
        </el-table>
        <div class="blame-pagination">
          <el-pagination
            v-model:current-page="blamePage"
            v-model:page-size="blamePageSize"
            :total="blameTotal"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @current-change="fetchBlameRows"
            @size-change="fetchBlameRows"
          />
        </div>
      </template>
    </el-card>
  </div>
</template>

<style lang="scss" scoped>
.welcome-dashboard {
  .page-header-card {
    overflow: hidden;

    :deep(.el-card__body) {
      padding: 24px !important;
    }
  }

  .page-header {
    display: flex;
    gap: 24px;
    align-items: center;
    justify-content: space-between;

    .page-title {
      margin: 0;
      font-size: 28px;
      font-weight: 700;
      line-height: 1.15;
      letter-spacing: -0.02em;
    }

    .page-description {
      max-width: 720px;
      margin: 10px 0 0;
      color: var(--el-text-color-secondary);
      line-height: 1.8;
    }

    .header-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 16px;
    }

    .header-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      justify-content: flex-end;
      align-items: center;
      flex-shrink: 0;

      .el-button {
        min-width: 120px;
      }
    }
  }

  .summary-card {
    min-height: 148px;

    .summary-card__label {
      color: var(--el-text-color-secondary);
      font-size: 14px;
    }

    .summary-card__value {
      margin: 16px 0 10px;
      font-size: 32px;
      font-weight: 700;
      line-height: 1.2;
    }

    .summary-card__subtitle {
      color: var(--el-text-color-secondary);
      font-size: 13px;
      line-height: 1.6;
    }

    .summary-card__error {
      color: var(--el-color-danger);
      font-size: 13px;
      line-height: 1.6;
    }
  }

  .card-header {
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
  }

  .card-title {
    font-size: 16px;
    font-weight: 600;
  }

  .card-tip {
    margin: 4px 0 0;
    color: var(--el-text-color-secondary);
    font-size: 13px;
    line-height: 1.6;
  }

  .trend-panel {
    min-height: 360px;
  }

  .trend-chart {
    width: 100%;
    height: 360px;
  }

  .blame-pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}

:deep(.el-card) {
  --el-card-border-color: transparent;
}

@media (width <= 768px) {
  .welcome-dashboard {
    .page-header,
    .card-header {
      flex-direction: column;
      align-items: flex-start;
    }

    .header-actions {
      width: 100%;
      justify-content: flex-start;

      .el-button {
        min-width: 0;
      }
    }

    .summary-card {
      min-height: auto;
    }
  }
}
</style>
