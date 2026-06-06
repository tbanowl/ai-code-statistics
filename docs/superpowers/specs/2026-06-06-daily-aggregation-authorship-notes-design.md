# Daily Aggregation Authorship Notes Design

## Goal

Update `daily_aggregation_task` so commit-based daily statistics can optionally count only commits that have authorship notes, and record the latest commit SHA processed by the daily aggregation path on `stats_repositories`.

## Requirements

- Add a new `stats_repositories` field dedicated to daily aggregation progress.
- Do not reuse or change `last_blame_commit_sha`; it remains owned by Git Blame statistics.
- Add a daily aggregation configuration switch. When enabled, only `metrics_events_committed` rows whose `(repo_url, commit_sha)` exists in `authorship_notes` are counted.
- Keep the current counting behavior by default when the switch is not configured or is `false`.
- Derive every `stat_date` from the committed event `timestamp`, not from the task execution time.
- After a successful aggregation, update the repository row with the latest counted committed event SHA for that repository.

## Data Model

Add `stats_repositories.last_daily_aggregation_commit_sha VARCHAR(40) NULL`.

Update these schema surfaces:

- `core/database/models.py`
- `sql/metrics_schema_mysql.sql`
- a new migration SQL file for existing MySQL databases

The field records the most recent committed event SHA successfully counted by `daily_aggregation_task` for the repository. It is nullable so existing repositories do not need backfill before the task runs again.

## Configuration

Add:

```yaml
scheduler:
  jobs:
    daily_aggregation:
      require_authorship_notes: false
```

`false` preserves the existing behavior. `true` enables the authorship note existence check. Manual trigger context may also provide the same boolean to override the configured value for one run.

## Aggregation Flow

`DailyAggregationTask.execute()` keeps its date range handling for selecting committed events. For each day window it queries committed events from `StatsDatabase.query_committed_events(...)`.

The query result must include:

- normalized `repo_url`
- parsed author name and email
- `commit_sha`
- committed event `timestamp`
- existing metric totals

`DailyAggregationTask` derives `stat_date` from each returned event timestamp, in local process time, using `datetime.fromtimestamp(event_timestamp / 1000).strftime("%Y%m%d")`. It does not use the loop cursor or current system time for persisted `stat_date`.

Aggregation groups by `(stat_date, repo_path, author_name, author_email)`. This keeps behavior correct if a manual time range crosses day boundaries or if event timestamps do not align perfectly with a loop day.

After all daily stat upserts for a day window succeed, the task updates `stats_repositories.last_daily_aggregation_commit_sha` for each repository that had counted events. The value is the counted event with the greatest committed event timestamp for that repository; ties may use stable query/order behavior and do not need special semantics.

## Authorship Notes Gate

When `require_authorship_notes` is true, `StatsDatabase.query_committed_events(...)` filters committed events using the database:

```sql
EXISTS (
  SELECT 1
  FROM authorship_notes
  WHERE authorship_notes.repo_url = normalized committed repo url
    AND authorship_notes.commit_sha = metrics_events_committed.commit_sha
)
```

The implementation should use the ORM model and existing indexes where possible. Repository URLs are normalized with the same `normalize_repo_url()` helper used elsewhere before matching, so notes and metrics use one identity format.

Rows with empty commit SHA cannot pass the authorship-notes gate.

## Error Handling

If the notes gate is disabled, missing or empty commit SHA does not prevent the event from being counted, but such events cannot advance `last_daily_aggregation_commit_sha`.

If the notes gate is enabled and no note exists, the event is skipped. This is expected behavior, not an error.

If updating `last_daily_aggregation_commit_sha` fails, the task should fail with the same transaction/error behavior as other database writes so a caller can rerun the aggregation.

## Testing

Add focused tests before implementation:

- With `require_authorship_notes=true`, committed events without a matching `authorship_notes` row are not returned for aggregation.
- With `require_authorship_notes=false`, committed events are returned as before.
- `DailyAggregationTask` writes `stats_commit_daily.stat_date` from each event timestamp.
- `DailyAggregationTask` updates `stats_repositories.last_daily_aggregation_commit_sha` to the latest counted commit SHA per repository.

Run daily aggregation related tests and Python syntax verification for touched modules.
