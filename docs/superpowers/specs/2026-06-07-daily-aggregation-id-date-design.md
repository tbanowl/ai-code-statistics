# Daily Aggregation ID and Commit Date Design

## Context

The metrics event processor currently stores committed event timestamps in
milliseconds and keeps several numeric metrics only as JSON arrays. The daily
aggregation task reads committed events into Python, aggregates them in memory,
and advances `stats_repositories.last_daily_aggregation_commit_sha`.

The new requirement is to make committed event rows easier to aggregate in SQL,
track aggregation progress by committed event ID, and avoid missing data when
multiple batches for the same repository and day arrive at different times.

## Goals

- Store committed event timestamps as seconds and derive `yyyyMMdd` commit dates.
- Add numeric snapshot columns for JSON-array metrics on
  `metrics_events_committed`.
- Add `commit_date` to `authorship_notes` and `metrics_events_committed`.
- Replace old daily stat line fields with explicit committed metric fields.
- Aggregate by repository, day, and author using SQL `SUM`.
- Use `stats_repositories.last_daily_aggregation_id` as the per-repository
  progress marker.
- When `require_authorship_notes` is enabled, count only commits present in both
  `metrics_events_committed` and `authorship_notes`.

## Schema Changes

### metrics_events_committed

Change `timestamp` semantics from milliseconds to seconds for newly processed
events.

Add:

- `commit_date BIGINT/INT NULL`: `yyyyMMdd` derived from the second-level
  `timestamp`.
- `mixed_additions_total INT DEFAULT 0`
- `ai_additions_total INT DEFAULT 0`
- `ai_accepted_total INT DEFAULT 0`
- `total_ai_additions_total INT DEFAULT 0`
- `total_ai_deletions_total INT DEFAULT 0`
- `time_waiting_for_ai_total BIGINT/INT DEFAULT 0`

The `_total` columns are extracted from the first element of their corresponding
array fields. Missing values and empty arrays become `0`.

Indexes should support the new aggregation path:

- `(repo_url, id)`
- `(repo_url, commit_date)`
- existing commit SHA index remains useful for authorship joins.

### authorship_notes

Add:

- `commit_date BIGINT/INT NULL`: `yyyyMMdd` derived from `commit_time`.

`commit_time` is treated as seconds. Migration backfill may defensively handle
millisecond-like historical values by dividing by 1000 before formatting.

Recommended index:

- `(repo_url, commit_sha)`
- `(repo_url, commit_date)`

### stats_repositories

Add:

- `last_daily_aggregation_id VARCHAR(20) NULL`

Deprecate and remove from ORM use:

- `last_daily_aggregation_commit_sha`

The new marker stores the largest `metrics_events_committed.id` discovered in a
successful aggregation run for that repository.

### stats_commit_daily

Add numeric fields:

- `human_additions`
- `unknown_additions`
- `git_diff_deleted_lines`
- `git_diff_added_lines`
- `mixed_additions`
- `ai_additions`
- `ai_accepted`
- `total_ai_additions`
- `total_ai_deletions`

Remove old fields:

- `ai_lines`
- `ai_total_lines`
- `ai_accepted_lines`
- `human_lines`
- `total_lines`

Keep the existing identity model:

- `stat_date`
- `repo_id`
- `contributor_name`
- `contributor_email`

`stat_date` stores the same `yyyyMMdd` value as committed event `commit_date`.
No separate `stats_date` column is introduced.

## Metrics Event Processing

For committed events:

1. Read event timestamp from the raw event.
2. Store `MetricsEventsCommitted.timestamp` as seconds.
3. Compute `commit_date` from that second-level timestamp.
4. Continue storing the JSON-array metric fields for compatibility and display.
5. Populate the new `_total` numeric snapshot columns from the first array
   element.
6. Normalize `repo_url` as today.
7. Upsert by existing `uid` semantics.

Existing rows with millisecond timestamps need migration/backfill if production
data should participate in the new aggregation path.

## Daily Aggregation Flow

The task loops through `stats_repositories`. For each repository:

1. Read `repo_path` and `last_daily_aggregation_id`.
2. Query new committed rows for that repository using:
   - `repo_url = repo_path`
   - `id > last_daily_aggregation_id` when the marker is present
3. If `require_authorship_notes` is true, this discovery query joins
   `authorship_notes` on `(repo_url, commit_sha)` so only commits present in both
   tables can create affected dates.
4. From the discovered rows, collect distinct `commit_date` values and the
   largest committed event `id`.
5. For the affected dates, run a second SQL aggregation query over all matching
   rows for that repository and those dates, not only rows after the marker.
6. The SQL aggregation groups by:
   - `commit_date`
   - normalized repository URL
   - parsed author identity as represented in the stored committed event row
7. SQL computes sums for all daily stat metric fields.
8. Upsert `stats_commit_daily` using overwrite semantics for the affected
   `(stat_date, repo_id, contributor_name, contributor_email)` rows.
9. After all affected daily rows for the repository are written successfully,
   update `stats_repositories.last_daily_aggregation_id` to the largest
   discovered committed event ID.

The ID marker is only used to discover which dates changed. It is not used to
limit the final `SUM` query. This prevents missed data when a later run receives
more rows for a date that was already aggregated.

## Authorship Notes Filter

When `require_authorship_notes` is false, aggregation uses only
`metrics_events_committed`.

When `require_authorship_notes` is true, both the affected-date discovery query
and the date-level aggregation query join `authorship_notes`:

```sql
metrics_events_committed.repo_url = authorship_notes.repo_url
AND metrics_events_committed.commit_sha = authorship_notes.commit_sha
```

This makes the counted set equivalent to committed events that also have a
matching authorship note.

## Data Semantics

- `human_additions`: sum of committed event `human_additions`.
- `unknown_additions`: sum of committed event `unknown_additions` if present;
  until the source field exists, aggregate as `0`.
- `git_diff_deleted_lines`: sum of committed event `git_diff_deleted_lines`.
- `git_diff_added_lines`: sum of committed event `git_diff_added_lines`.
- `mixed_additions`: sum of committed event `mixed_additions_total`.
- `ai_additions`: sum of committed event `ai_additions_total`.
- `ai_accepted`: sum of committed event `ai_accepted_total`.
- `total_ai_additions`: sum of committed event `total_ai_additions_total`.
- `total_ai_deletions`: sum of committed event `total_ai_deletions_total`.

Author parsing follows the existing behavior: stored strings like
`Name <email@example.com>` are split into contributor name and email before
upserting daily stats.

## Error Handling

- If a repository has no new committed rows after the marker, skip it.
- If new rows have no valid `commit_date`, they should not advance the marker
  silently; the task should log or fail depending on the existing database
  error behavior.
- If any daily stat upsert fails, do not update
  `last_daily_aggregation_id` for that repository.
- If updating `last_daily_aggregation_id` fails, the task should fail so the
  next run can retry.

## Tests

Focused coverage:

- Metrics processor stores committed `timestamp` as seconds.
- Metrics processor computes `commit_date` from second-level timestamp.
- Metrics processor populates all new `_total` snapshot fields from first array
  values.
- SQL aggregation uses ID only to discover affected dates, then recomputes the
  complete affected date.
- A second run with more rows for a previously aggregated date overwrites daily
  stats with the full date total.
- `require_authorship_notes=true` counts only rows joined to
  `authorship_notes`.
- `last_daily_aggregation_id` advances only after successful aggregation.
- Daily stat upsert writes the new field names and no longer references removed
  `*_lines` fields.
- Schema/model tests cover the new columns.
