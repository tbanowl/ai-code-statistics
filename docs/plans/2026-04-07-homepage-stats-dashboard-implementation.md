# Homepage Stats Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the mock-driven `/welcome` homepage with a real stats overview dashboard powered by the existing `/api/stats` backend endpoints.

**Architecture:** Keep the current route and theme, but rebuild the welcome page around page-local data fetching. Normalize the stats API contract in `frontend/src/api/stats.ts`, then render KPI cards, a trend chart, two ranking tables, and a daily detail table with isolated loading and error states.

**Tech Stack:** Vue 3, TypeScript, Element Plus, vue-pure-admin, ECharts, Axios wrapper in `src/utils/http`

---

### Task 1: Normalize stats API contracts

**Files:**
- Modify: `frontend/src/api/stats.ts`

**Step 1: Expand the API types to cover homepage data needs**

- Add explicit types for trend items, repository rows, contributor rows, daily rows, and trigger-aggregate response.
- Keep the existing `{ success, data, pagination? }` envelope shape.

**Step 2: Fix incorrect endpoint paths**

- Change the contributor endpoint from `/api/stats/stats/contributors` to `/api/stats/contributors`.
- Add wrappers for `GET /api/stats/daily` and `POST /api/stats/stats/aggregate`.

**Step 3: Verify type usage in consumers**

- Ensure the welcome page can import all homepage-facing types from this file without local contract duplication.

---

### Task 2: Rebuild the welcome page around real dashboard data

**Files:**
- Modify: `frontend/src/views/welcome/index.vue`

**Step 1: Remove mock-data composition**

- Delete the current mock imports from `./data`.
- Remove the current demo-only KPI cards, progress list, and latest activity timeline.

**Step 2: Add page-local request orchestration**

- Compute default `start_date` and `end_date` for the last 30 days.
- Fetch these requests in parallel on mount:
  - `getStats`
  - `getRepoStats`
  - `getContributorStats`
  - `getDailyStats`
- Add an action for `triggerStatsAggregate`.

**Step 3: Add dashboard-specific view models**

- Derive 4 KPI cards from summary and pagination totals.
- Derive trend chart series from `getStats().data.items`.
- Derive repository and contributor Top 10 tables from their list responses.
- Derive daily detail rows from the daily stats response.

**Step 4: Add resilient UI states**

- Keep loading/error state per module instead of one page-wide failure state.
- Show friendly empty states when no data is returned.

---

### Task 3: Refresh or replace mock-shaped local chart and table components

**Files:**
- Modify if still useful: `frontend/src/views/welcome/components/charts/ChartBar.vue`
- Modify if still useful: `frontend/src/views/welcome/components/table/index.vue`
- Modify if still useful: `frontend/src/views/welcome/components/table/columns.tsx`
- Delete if unused after refactor: old mock-specific welcome component files

**Step 1: Decide what remains worth reusing**

- Reuse only components that fit real stats data with minimal reshaping.
- Prefer deleting dead mock-specific code over forcing compatibility.

**Step 2: Align chart/table inputs with real backend fields**

- Trend chart should accept labels + AI line + human line.
- Daily table should display real daily rows, not synthetic demo columns.

**Step 3: Keep the diff minimal**

- If a component becomes a thin wrapper around page-local rendering, inline it into `index.vue` instead of maintaining dead abstraction.

---

### Task 4: Validate the homepage end-to-end

**Files:**
- Verify: `frontend/src/api/stats.ts`
- Verify: `frontend/src/views/welcome/index.vue`
- Verify: any remaining welcome components touched during the refactor

**Step 1: Run diagnostics on modified files**

- Check TypeScript/Vue diagnostics and resolve any introduced errors.

**Step 2: Run typecheck**

Run: `pnpm typecheck`
Expected: exit 0

**Step 3: Run production build**

Run: `pnpm build`
Expected: exit 0

**Step 4: Review final diff for leftover mock coupling**

- Confirm the homepage no longer imports `frontend/src/views/welcome/data.ts`.
- Confirm the contributor API path matches the backend route.
