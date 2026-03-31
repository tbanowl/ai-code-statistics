<template>
  <div class="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-6">
    <div class="max-w-7xl mx-auto space-y-6">
      <div class="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
        <div class="grid grid-cols-1 md:grid-cols-5 gap-3">
          <input ref="startDateInput" class="input" placeholder="Start Date" readonly />
          <input ref="endDateInput" class="input" placeholder="End Date" readonly />
          <select v-model="filters.repoId" class="input">
            <option value="">All Repositories</option>
            <option v-for="repo in repositories" :key="repo.id" :value="repo.id">{{ repo.repo_name || repo.repo_path }}</option>
          </select>
          <select v-model="filters.contributorId" class="input">
            <option value="">All Contributors</option>
            <option v-for="contributor in contributors" :key="contributor.id" :value="contributor.id">{{ contributor.name }}</option>
          </select>
          <div class="flex gap-2">
            <button class="btn-primary flex-1" :disabled="loading" @click="refreshData">{{ loading ? 'Loading...' : 'Query' }}</button>
            <button class="btn-secondary" @click="showTriggerModal = true">Trigger</button>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <div class="card">
          <div class="label">AI Generated</div>
          <div class="value">{{ summary.total_ai_generated }}</div>
        </div>
        <div class="card">
          <div class="label">AI Accepted</div>
          <div class="value">{{ summary.total_ai_accepted }}</div>
        </div>
        <div class="card">
          <div class="label">Human Lines</div>
          <div class="value">{{ summary.total_human }}</div>
        </div>
        <div class="card">
          <div class="label">AI Percentage</div>
          <div class="value">{{ summary.avg_ai_percentage }}%</div>
        </div>
      </div>

      <div class="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
        <h2 class="text-sm uppercase tracking-wider text-zinc-400 mb-3">Trend</h2>
        <VChart class="h-80" :option="trendOption" autoresize />
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div class="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
          <h2 class="text-sm uppercase tracking-wider text-zinc-400 mb-3">By Repository</h2>
          <VChart class="h-72" :option="repoBarOption" autoresize />
        </div>
        <div class="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
          <h2 class="text-sm uppercase tracking-wider text-zinc-400 mb-3">By Contributor</h2>
          <VChart class="h-72" :option="contributorBarOption" autoresize />
        </div>
      </div>

      <div class="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4 overflow-auto">
        <h2 class="text-sm uppercase tracking-wider text-zinc-400 mb-3">Daily Details</h2>
        <table class="w-full text-sm">
          <thead class="text-zinc-400">
            <tr>
              <th class="text-left py-2">Date</th>
              <th class="text-left py-2">Repository</th>
              <th class="text-left py-2">Contributor</th>
              <th class="text-right py-2">AI Generated</th>
              <th class="text-right py-2">AI Accepted</th>
              <th class="text-right py-2">Human</th>
              <th class="text-right py-2">AI %</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in dailyRows" :key="row.id" class="border-t border-zinc-800">
              <td class="py-2">{{ formatDate(row.stat_date) }}</td>
              <td class="py-2">{{ displayRepo(row) }}</td>
              <td class="py-2">{{ displayContributor(row) }}</td>
              <td class="py-2 text-right">{{ row.ai_generated_lines || 0 }}</td>
              <td class="py-2 text-right">{{ row.ai_accepted_lines || 0 }}</td>
              <td class="py-2 text-right">{{ row.human_lines || 0 }}</td>
              <td class="py-2 text-right">{{ aiPercent(row) }}%</td>
            </tr>
          </tbody>
        </table>
        <div class="flex justify-end gap-2 mt-3">
          <button class="btn-secondary" :disabled="page <= 1" @click="changePage(page - 1)">Prev</button>
          <button class="btn-secondary" :disabled="page >= totalPages" @click="changePage(page + 1)">Next</button>
        </div>
      </div>
    </div>

    <div v-if="showTriggerModal" class="fixed inset-0 bg-black/60 flex items-center justify-center p-4">
      <div class="w-full max-w-md rounded-xl border border-zinc-700 bg-zinc-900 p-4 space-y-4">
        <h3 class="font-semibold">Trigger Aggregation</h3>
        <div class="text-sm text-zinc-400">Use current filters as payload.</div>
        <div class="flex justify-end gap-2">
          <button class="btn-secondary" @click="showTriggerModal = false">Cancel</button>
          <button class="btn-primary" @click="submitTrigger">Submit</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import flatpickr from 'flatpickr'
import 'flatpickr/dist/flatpickr.min.css'
import { fetchContributors, fetchDailyStats, fetchRepositories, fetchStats, triggerAggregate } from '../services/api.js'

use([CanvasRenderer, LineChart, BarChart, GridComponent, LegendComponent, TooltipComponent])

const startDateInput = ref(null)
const endDateInput = ref(null)
const loading = ref(false)
const repositories = ref([])
const contributors = ref([])
const statsItems = ref([])
const summary = ref({
  total_ai_generated: 0,
  total_ai_accepted: 0,
  total_human: 0,
  avg_ai_percentage: 0
})
const dailyRows = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showTriggerModal = ref(false)

const today = new Date()
const weekAgo = new Date(today)
weekAgo.setDate(today.getDate() - 7)

const filters = ref({
  startDate: weekAgo.toISOString().slice(0, 10),
  endDate: today.toISOString().slice(0, 10),
  repoId: '',
  contributorId: ''
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const repositoryNameMap = computed(() => {
  const map = new Map()
  for (const repo of repositories.value) {
    map.set(repo.id, repo.repo_name || repo.repo_path || repo.id)
  }
  return map
})

const contributorNameMap = computed(() => {
  const map = new Map()
  for (const contributor of contributors.value) {
    map.set(contributor.id, contributor.name || contributor.contributor_uid || contributor.id)
  }
  return map
})

const trendOption = computed(() => {
  const x = statsItems.value.map(item => formatDate(item.stat_date))
  return {
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#d4d4d8' } },
    grid: { left: 20, right: 20, top: 30, bottom: 20, containLabel: true },
    xAxis: { type: 'category', data: x, axisLabel: { color: '#a1a1aa' } },
    yAxis: [{ type: 'value', axisLabel: { color: '#a1a1aa' } }],
    series: [
      { name: 'AI Generated', type: 'line', smooth: true, data: statsItems.value.map(i => i.ai_generated_lines || 0) },
      { name: 'AI Accepted', type: 'line', smooth: true, data: statsItems.value.map(i => i.ai_accepted_lines || 0) },
      { name: 'Human', type: 'line', smooth: true, data: statsItems.value.map(i => i.human_lines || 0) },
      { name: 'AI %', type: 'line', smooth: true, data: statsItems.value.map(i => i.ai_percentage || 0) }
    ]
  }
})

const repoBarOption = computed(() => {
  const aggregate = new Map()
  for (const row of dailyRows.value) {
    const key = displayRepo(row)
    aggregate.set(key, (aggregate.get(key) || 0) + (row.ai_generated_lines || 0) + (row.human_lines || 0))
  }
  const entries = Array.from(aggregate.entries()).slice(0, 10)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 20, right: 20, top: 10, bottom: 60, containLabel: true },
    xAxis: { type: 'category', data: entries.map(e => e[0]), axisLabel: { color: '#a1a1aa', rotate: 20 } },
    yAxis: { type: 'value', axisLabel: { color: '#a1a1aa' } },
    series: [{ type: 'bar', data: entries.map(e => e[1]), itemStyle: { color: '#f59e0b' } }]
  }
})

const contributorBarOption = computed(() => {
  const aggregate = new Map()
  for (const row of dailyRows.value) {
    const key = displayContributor(row)
    aggregate.set(key, (aggregate.get(key) || 0) + (row.ai_generated_lines || 0) + (row.human_lines || 0))
  }
  console.log(aggregate)
  const entries = Array.from(aggregate.entries()).slice(0, 10)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 20, right: 20, top: 10, bottom: 60, containLabel: true },
    xAxis: { type: 'category', data: entries.map(e => e[0]), axisLabel: { color: '#a1a1aa', rotate: 20 } },
    yAxis: { type: 'value', axisLabel: { color: '#a1a1aa' } },
    series: [{ type: 'bar', data: entries.map(e => e[1]), itemStyle: { color: '#38bdf8' } }]
  }
})

function toMsStart(dateStr) {
  return new Date(`${dateStr}T00:00:00`).getTime()
}

function toMsEnd(dateStr) {
  return new Date(`${dateStr}T23:59:59`).getTime()
}

function formatDate(ts) {
  if (!ts) return '-'
  return new Date(ts).toLocaleDateString()
}

function aiPercent(row) {
  const human = row.human_lines || 0
  const ai = row.ai_accepted_lines || 0
  const totalLines = ai + human
  if (totalLines === 0) return 0
  return ((ai / totalLines) * 100).toFixed(2)
}

function displayRepo(row) {
  if (row.repo_name) return row.repo_name
  if (row.repo_id && repositoryNameMap.value.has(row.repo_id)) {
    return repositoryNameMap.value.get(row.repo_id)
  }
  return row.repo_id || 'Unknown'
}

function displayContributor(row) {
  if (row.contributor_name) return row.contributor_name
  if (row.contributor_id && contributorNameMap.value.has(row.contributor_id)) {
    return contributorNameMap.value.get(row.contributor_id)
  }
  return row.contributor_id || 'Unknown'
}

async function loadFilters() {
  const [repoResp, contributorResp] = await Promise.all([
    fetchRepositories({ page: 1, page_size: 100 }),
    fetchContributors({ page: 1, page_size: 100 })
  ])
  repositories.value = repoResp.data || []
  contributors.value = contributorResp.data || []
}

async function refreshData() {
  loading.value = true
  try {
    const params = {
      start_date: toMsStart(filters.value.startDate),
      end_date: toMsEnd(filters.value.endDate),
      granularity: 'daily'
    }
    if (filters.value.repoId) params.repo_id = filters.value.repoId
    if (filters.value.contributorId) params.contributor_id = filters.value.contributorId

    const [statsResp, dailyResp] = await Promise.all([
      fetchStats(params),
      fetchDailyStats({ ...params, page: page.value, page_size: pageSize.value })
    ])

    statsItems.value = statsResp.data?.items || []
    summary.value = statsResp.data?.summary || summary.value
    dailyRows.value = dailyResp.data || []
    total.value = dailyResp.pagination?.total || 0
  } finally {
    loading.value = false
  }
}

async function submitTrigger() {
  const payload = {
    start_date: toMsStart(filters.value.startDate),
    end_date: toMsEnd(filters.value.endDate),
    repo_id: filters.value.repoId || undefined,
    contributor_id: filters.value.contributorId || undefined
  }
  await triggerAggregate(payload)
  showTriggerModal.value = false
}

async function changePage(nextPage) {
  page.value = nextPage
  await refreshData()
}

onMounted(async () => {
  await loadFilters()

  // Initialize flatpickr for start date
  flatpickr(startDateInput.value, {
    dateFormat: 'Y-m-d',
    defaultDate: filters.value.startDate,
    maxDate: new Date(),
    onChange: (selectedDates) => {
      filters.value.startDate = selectedDates[0] ? selectedDates[0].toISOString().slice(0, 10) : ''
    }
  })

  // Initialize flatpickr for end date
  flatpickr(endDateInput.value, {
    dateFormat: 'Y-m-d',
    defaultDate: filters.value.endDate,
    maxDate: new Date(),
    onChange: (selectedDates) => {
      filters.value.endDate = selectedDates[0] ? selectedDates[0].toISOString().slice(0, 10) : ''
    }
  })

  await refreshData()
})
</script>

<style scoped>
.input {
  @apply rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm;
}

.btn-primary {
  @apply rounded-lg bg-amber-400 px-3 py-2 text-sm font-semibold text-zinc-950 disabled:opacity-50;
}

.btn-secondary {
  @apply rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm;
}

.card {
  @apply rounded-xl border border-zinc-800 bg-zinc-900/70 p-4;
}

.label {
  @apply text-xs uppercase tracking-wider text-zinc-400;
}

.value {
  @apply mt-2 text-2xl font-semibold;
}
</style>
