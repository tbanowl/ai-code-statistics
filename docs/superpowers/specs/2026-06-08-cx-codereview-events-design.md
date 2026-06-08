# CX Code Review Events Ingestion Design

## Context

The schema now includes two code review event tables:

- `cx_codereview_bypasses` for `cx_codereview_issue_bypass` events.
- `cx_codereview_summaries` for `cx_codereview_push_summary` events.

The existing `cx_usage` endpoint uses a batch POST shape, validates each item, inserts valid events, and returns `accepted`, `duplicated`, and `failed` event IDs. The code review ingestion should follow that pattern while keeping code review data separate from command usage events.

## Approach

Add one dedicated batch endpoint:

`POST /api/v1/cx-aicode/codereview/events/batch`

The request body is:

```json
{
  "items": []
}
```

The endpoint accepts both supported code review event types in the same batch and routes each event by `eventType`:

- `cx_codereview_issue_bypass` -> `cx_codereview_bypasses`
- `cx_codereview_push_summary` -> `cx_codereview_summaries`

This keeps the collection client simple and avoids widening the existing command usage endpoint.

## API Behavior

The response mirrors the existing `cx_usage` batch endpoint:

```json
{
  "success": true,
  "accepted": ["evt_..."],
  "duplicated": [],
  "failed": []
}
```

- `success` is true only when no event failed validation or persistence.
- `accepted` contains event IDs inserted in this request.
- `duplicated` contains event IDs rejected by the unique `event_id` constraint.
- `failed` contains event IDs that failed validation or failed to persist for non-duplicate reasons.

If `items` is not an array, return `400`. If the batch is larger than 100, return `413`. If the database is unavailable for the whole request, return `503` and mark all valid event IDs as failed.

## Validation

Create a new schema module for code review events instead of expanding `api/schemas/cx_usage_schema.py`.

Common fields:

- Required: `eventId`, `schemaVersion`, `eventType`, `timestamp`.
- Optional: `specId`, `specIdSource`, `projectId`, `gitUserName`, `gitUserEmail`, `sessionId`, `pluginVersion`, `source`.
- `eventId` must match the existing `evt_...` pattern and fit the table length.
- `timestamp` must parse as ISO datetime and maps to `event_time`; keep the current `cx_usage` convention where a trailing `Z` is interpreted as `+08:00`.
- `gitUserEmail` is trimmed and lowercased.
- String fields are checked against the table column limits where fixed limits exist.
- JSON columns accept object or array values and store them as provided.

Bypass fields map to `cx_codereview_bypasses`:

- `pushId`, `commitSha`, `issueId`, `issueTitle`, `issueDescription`, `severity`, `filePath`, `lineRange`, `codeSnippet`, `impact`, `suggestion`, `ruleRef`, `response`, `reason`, `originalMarker`, `bypassedMarker`.

Summary fields map to `cx_codereview_summaries`:

- `pushId`, `commitSha`, `commitShort`, `pushBranch`, `pushRemote`, `reportPath`, `reviewStatus`, `bypassCount`, `finalScore`, `grade`, `issueCounts`, `submissionTime`.

`submissionTime` is parsed as ISO datetime when present, using the same timestamp convention. `bypassCount` is parsed as an integer. `finalScore` is parsed as a decimal-compatible value. Missing optional fields are stored as `NULL`.

## Persistence

Extend `core/database/cx_usage_db.py` with:

- `CxCodereviewBypass`
- `CxCodereviewSummary`
- `CxUsageDatabase.insert_codereview_batch(events, token_name=None)`

Each model should match the SQL schema. The `id VARCHAR(20)` primary keys use the existing `core.database.models.gen_xid()` helper.

`insert_codereview_batch` loops through validated events, builds the correct model from `eventType`, flushes each row, and handles:

- `IntegrityError` as duplicate event ID.
- Other exceptions as failed event ID.

The full source event is stored in `raw_event`.

## Route Structure

Add the route to `api/routes/cx_usage.py` under the existing blueprint prefix `/api/v1/cx-aicode`. The handler should match the shape of `events_batch()`:

1. Read JSON body.
2. Validate batch shape and size.
3. Validate each event independently.
4. Insert valid events through `CxUsageDatabase`.
5. Merge validation failures with persistence failures.
6. Return the existing batch response shape.

## Tests

Add focused tests for:

- Valid bypass event validation.
- Valid summary event validation.
- Invalid `eventType`.
- Invalid `timestamp`.
- Batch size and non-array validation.
- Bypass insertion.
- Summary insertion.
- Duplicate `eventId` handling.
- Same batch splitting into both destination tables.

Route tests should verify the endpoint path and response shape if the existing Flask test client setup is straightforward.

## Out Of Scope

- No frontend changes.
- No analytics or dashboard queries for the two new tables.
- No changes to the existing `/events/batch` command usage endpoint.
