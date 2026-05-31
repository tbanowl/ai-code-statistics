# Stats Blame Repo Person Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adjust stats blame persistence to repository and repository-person dimensions, using today's stat date, removing contributor IDs, file persistence, and AI ratio fields.

**Architecture:** Keep `StatsBlameRepo` for repository snapshots and `StatsBlameRepoContributor` for repository-person rows. File blame remains an in-memory aggregation input only. Repository status updates record both last blame commit SHA and last successful stat date.

**Tech Stack:** Python 3.10, Flask, SQLAlchemy 2, pytest, MySQL DDL, Vue 3, TypeScript.

---

## File Structure

- Modify `core/database/models.py`: add `StatsRepository.last_stat_date`; remove stats blame `ai_ratio`; remove `StatsBlameRepoContributor.contributor_id`; change uniqueness to contributor identity.
- Modify `core/database/blame_stats_db.py`: update repository status method; update batch save signature; remove file table writes from batch flow; remove `ai_ratio` and `contributor_id` from query responses.
- Modify `core/scheduler/tasks/git_blame_stats_task.py`: default stat date to today; save only repo and repo-contributor objects; call repository status update with stat date.
- Modify `core/services/blame_stats_service.py`: stop exposing `files_results` as persisted output, or keep it only as private/in-memory compatibility.
- Modify `sql/metrics_schema_mysql.sql`: reflect new schema.
- Create `sql/stats_blame_repo_person_migration_mysql.sql`: old database migration.
- Modify `api/routes/stats_repo.py`: remove file-level blame endpoint.
- Modify `frontend/src/api/stats.ts`, `frontend/src/api/repo.ts`, `frontend/src/views/welcome/index.vue`, `frontend/src/views/metrics/repo-list/index.vue`: remove stats blame `ai_ratio` and `contributor_id` usage.
- Modify tests under `tests/unit/test_database/`, `tests/unit/test_scheduler/`, and `tests/unit/test_services/`.

## Task 1: Backend Tests for New Persistence Contract

**Files:**
- Modify: `tests/unit/test_database/test_blame_stats_db.py`
- Modify: `tests/unit/test_scheduler/test_git_blame_stats_task.py`

- [ ] **Step 1: Write failing database tests**

Add tests that assert repository status updates include `last_stat_date`, repeated branch saves replace repo/person rows, and query payloads exclude `ai_ratio`/`contributor_id`.

- [ ] **Step 2: Run database tests and verify RED**

Run: `pytest tests/unit/test_database/test_blame_stats_db.py -v`

Expected: FAIL because `last_stat_date` and the new save signature/fields do not exist yet.

- [ ] **Step 3: Write failing scheduler tests**

Add tests that default `stat_date` to today and `_save_branch_stats()` saves no file objects.

- [ ] **Step 4: Run scheduler tests and verify RED**

Run: `pytest tests/unit/test_scheduler/test_git_blame_stats_task.py -v`

Expected: FAIL because default date still uses yesterday and file objects are still passed.

## Task 2: Backend Schema and Persistence Implementation

**Files:**
- Modify: `core/database/models.py`
- Modify: `core/database/blame_stats_db.py`
- Modify: `core/scheduler/tasks/git_blame_stats_task.py`
- Modify: `core/services/blame_stats_service.py`

- [ ] **Step 1: Implement model changes**

Add `last_stat_date`, remove `ai_ratio`, remove `contributor_id`, update unique constraints.

- [ ] **Step 2: Implement DB method changes**

Rename/update repository status method to accept `commit_sha` and `stat_date`. Update batch save to accept only repo and repo-contributor objects. Remove file table delete/insert from the active path. Return no removed fields from queries.

- [ ] **Step 3: Implement scheduler changes**

Use today's date by default. Build only repo and repo-contributor ORM objects. Normalize missing contributor email to empty string. Update repository status after successful branch saves.

- [ ] **Step 4: Run backend tests and verify GREEN**

Run: `pytest tests/unit/test_database/test_blame_stats_db.py tests/unit/test_scheduler/test_git_blame_stats_task.py tests/unit/test_services/test_blame_stats_service.py -v`

Expected: PASS.

## Task 3: SQL and API Contract Update

**Files:**
- Modify: `sql/metrics_schema_mysql.sql`
- Create: `sql/stats_blame_repo_person_migration_mysql.sql`
- Modify: `api/routes/stats_repo.py`

- [ ] **Step 1: Update schema and migration SQL**

Reflect `last_stat_date`, no `ai_ratio`, no `contributor_id`, and no file stats tables in the active schema.

- [ ] **Step 2: Remove file blame API route**

Delete `GET /api/stats-repo/blame/file/<repo_id>` route so callers cannot request removed persistence.

- [ ] **Step 3: Run API/import checks**

Run: `python -m compileall core api`

Expected: exit 0.

## Task 4: Frontend Contract Update

**Files:**
- Modify: `frontend/src/api/stats.ts`
- Modify: `frontend/src/api/repo.ts`
- Modify: `frontend/src/views/welcome/index.vue`
- Modify: `frontend/src/views/metrics/repo-list/index.vue`

- [ ] **Step 1: Remove removed fields from TypeScript types**

Delete `BlameRepoStatItem.ai_ratio` and `ContributorStat.contributor_id`.

- [ ] **Step 2: Remove AI ratio columns from stats blame UI**

Remove the AI ratio table columns and formatter usage that only served those columns.

- [ ] **Step 3: Run frontend build/type check**

Run: `pnpm build` in `frontend/`

Expected: exit 0.

## Task 5: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run diagnostics**

Run LSP diagnostics on changed Python, SQL, and Vue/TS files.

- [ ] **Step 2: Run focused tests**

Run backend focused pytest suite and frontend build.

- [ ] **Step 3: Review diff**

Run `git diff` and verify changes match the approved design only.
