# Authorship Notes Rewrite API Design

## Context

The project already exposes REST Notes endpoints through two equivalent
prefixes:

- `/worker/authorship_notes`
- `/worker/notes`

The existing endpoints support single-note upsert, batch fetch, batch push,
list, and search. Writes are last-content-wins by `(repo_url, commit_sha)`.
Incremental sync is based on server-computed `content_hash` and monotonic
`change_seq`.

That model is not enough for history rewrite flows. When a client has already
pushed an AI-authored note for commit `B`, and a later rebase or cherry-pick
replaces that authored commit with commit `D`, a normal `/push` can upload the
target note for `D` but cannot tell the server that `B` is no longer an active
authorship note. The server may then count both commits as active AI-authored
work.

The upstream client-side design emits rewrite mappings from events such as
pending rebase pick consumption, completed rebase, cherry-pick, and amend.
This spec defines the REST contract that lets those mappings update the server
atomically.

## Goals

- Add a REST endpoint that writes target authorship notes and supersedes source
  notes in one atomic operation.
- Preserve historical source notes for audit instead of deleting them.
- Make rewrite requests idempotent by `rewrite_id`.
- Keep existing `/worker/authorship_notes/*` and `/worker/notes/*` behavior
  compatible for normal note sync.
- Ensure default active-note and metrics queries ignore superseded source notes.

## Non-Goals

- Do not implement client-side pending rebase pick storage in this service.
- Do not infer rewrite mappings by patch similarity or note content similarity.
- Do not delete source notes from the server.
- Do not change the normal `/push` semantics for non-rewrite note sync.

## Current Interface Baseline

The existing REST Notes interface remains supported:

| Method | Path | Purpose |
| --- | --- | --- |
| `PUT` | `/worker/authorship_notes` and `/worker/notes` | Create or update one note |
| `POST` | `/worker/authorship_notes/get` and `/worker/notes/get` | Fetch one note by `repo_url + commit_sha` |
| `POST` | `/worker/authorship_notes/batch` and `/worker/notes/batch` | Fetch note contents for commit SHAs |
| `POST` | `/worker/authorship_notes/push` and `/worker/notes/push` | Batch upsert normal notes |
| `POST` | `/worker/authorship_notes/list` and `/worker/notes/list` | List note summaries for sync |
| `POST` | `/worker/authorship_notes/search` and `/worker/notes/search` | Search note content |

Normal `/push` remains an upsert API. It must not supersede another commit
unless the client calls the rewrite API with explicit source-to-target
mappings.

## New Endpoint

Add:

```text
POST /worker/authorship_notes/rewrite
```

Also register the compatibility alias:

```text
POST /worker/notes/rewrite
```

The alias matches the existing route pattern where `/worker/notes` and
`/worker/authorship_notes` expose equivalent REST Notes capabilities.

## Request

```json
{
  "repo_url": "https://github.com/org/repo",
  "rewrite_id": "sha256(repo_url + operation + source + target + target_note_blob_oid)",
  "operation": "rebase_conflict_manual_commit",
  "branch": "main",
  "original_head": "B",
  "new_head": "D",
  "mappings": [
    {
      "source_commit": "B",
      "target_commit": "D",
      "source_note_blob_oid": "old-note-blob",
      "target_note_blob_oid": "new-note-blob",
      "target_content": "{...authorship log...}",
      "commit_time": 1710000000,
      "author_name": "User",
      "author_email": "user@example.com",
      "disposition": "supersede_source"
    }
  ]
}
```

### Request Fields

| Field | Required | Description |
| --- | --- | --- |
| `repo_url` | Yes | Repository URL. The service normalizes it with the existing repo URL normalizer. |
| `rewrite_id` | Yes | Client-generated idempotency key for the rewrite operation. |
| `operation` | Yes | Rewrite kind. Initial accepted values are `rebase_conflict_manual_commit`, `rebase_complete`, `cherry_pick_complete`, and `amend`. |
| `branch` | Yes | Branch name associated with the target note. This follows the existing `/push` requirement and avoids creating target notes without branch context. |
| `original_head` | No | Head before the rewrite operation, used for audit and debugging. |
| `new_head` | No | Head after the rewrite operation, used for audit and debugging. |
| `mappings` | Yes | Non-empty list of source-to-target note mappings. |

### Mapping Fields

| Field | Required | Description |
| --- | --- | --- |
| `source_commit` | Yes | Commit whose active authorship note is replaced. |
| `target_commit` | Yes | Commit receiving the rewritten authorship note. |
| `source_note_blob_oid` | No | Source note blob oid, retained for audit. |
| `target_note_blob_oid` | No | Target note blob oid, retained for audit and debugging. |
| `target_content` | Yes | Authorship note content to store for `target_commit`. |
| `commit_time` | No | Target commit time in Unix seconds. |
| `author_name` | Yes | Target commit author name. |
| `author_email` | Yes | Target commit author email. |
| `disposition` | Yes | Initial accepted value is `supersede_source`. Future values may represent copy-only mappings where both commits remain active. |

## Response

Successful rewrite:

```json
{
  "ok": true,
  "data": {
    "created": 1,
    "updated": 0,
    "superseded": 1,
    "unchanged": 0,
    "conflicts": []
  }
}
```

Partial conflict response:

```json
{
  "ok": true,
  "data": {
    "created": 0,
    "updated": 0,
    "superseded": 0,
    "unchanged": 0,
    "conflicts": [
      {
        "source_commit": "B",
        "target_commit": "D",
        "reason": "target_note_conflict",
        "remote_content_hash": "sha256:remote",
        "local_content_hash": "sha256:local"
      }
    ]
  }
}
```

Idempotency conflict:

```json
{
  "ok": false,
  "error": "rewrite_id already exists with different request content"
}
```

Use HTTP `409` for idempotency conflicts. Use HTTP `400` for malformed
requests, unknown operations, empty mappings, missing required mapping fields,
or unsupported dispositions.

## Server Semantics

The endpoint runs each request in one database transaction:

1. Normalize `repo_url`.
2. Validate required request fields and every mapping.
3. Compute a stable `request_hash` from the normalized request body using
   deterministic JSON serialization with sorted object keys and normalized
   `repo_url`.
4. Look up `rewrite_id`.
5. If the rewrite exists with the same `request_hash`, return the stored or
   recomputed idempotent result without creating new rows or advancing
   `change_seq`.
6. If the rewrite exists with a different `request_hash`, return HTTP `409`.
7. For each mapping, compute `target_content_hash` from `target_content`.
8. Create or update the target note for `target_commit`.
9. Mark the source note for `source_commit` as `superseded` when
   `disposition == "supersede_source"`.
10. Insert the rewrite mapping edge.
11. Advance `change_seq` only for notes whose active content or status changed.

The source note is not deleted. It remains available for audit and explicit
historical lookup.

## Conflict Rules

Target note handling:

- If the target note does not exist, create it and count `created += 1`.
- If the target note exists with the same content hash, count
  `unchanged += 1`.
- If the target note exists with different content and the existing rewrite
  mapping for `source_commit -> target_commit` belongs to the same
  `rewrite_id`, update the target and count `updated += 1`.
- If the target note exists with different content and a different rewrite
  mapping already owns the target, append a conflict item with
  `reason = "target_note_conflict"` and do not overwrite it.

Source note handling:

- If the source note exists and is active, mark it `superseded`.
- If the source note already has the same `superseded_by` and
  `superseded_rewrite_id`, count it as idempotently unchanged.
- If the source note is superseded by another target or rewrite, append a
  conflict item with `reason = "source_already_superseded"`.
- If the source note is missing, still write the target note and mapping edge,
  but include a conflict item with `reason = "source_note_missing"` so callers
  can audit the degraded rewrite.

## Data Model

Extend `authorship_notes`:

| Column | Type | Default | Description |
| --- | --- | --- | --- |
| `status` | string | `active` | `active` or `superseded`. |
| `superseded_by` | string nullable | `NULL` | Target commit that replaced this source note. |
| `superseded_at` | bigint nullable | `NULL` | Server timestamp in milliseconds. |
| `superseded_rewrite_id` | string nullable | `NULL` | Rewrite request that superseded this note. |

Recommended indexes:

```sql
CREATE INDEX idx_authorship_notes_repo_status
ON authorship_notes(repo_url, status);

CREATE INDEX idx_authorship_notes_superseded_rewrite
ON authorship_notes(repo_url, superseded_rewrite_id);
```

Add `authorship_note_rewrites`:

| Column | Type | Description |
| --- | --- | --- |
| `id` | string | Internal XID primary key. |
| `rewrite_id` | string | Unique client idempotency key. |
| `repo_url` | string | Normalized repository URL. |
| `operation` | string | Rewrite operation. |
| `branch` | string nullable | Branch name. |
| `original_head` | string nullable | Audit head before rewrite. |
| `new_head` | string nullable | Audit head after rewrite. |
| `request_hash` | string | Stable hash of normalized request body. |
| `created_at` | bigint | Server timestamp in milliseconds. |

Constraints and indexes:

```sql
UNIQUE(rewrite_id)
CREATE INDEX idx_authorship_note_rewrites_repo ON authorship_note_rewrites(repo_url);
```

Add `authorship_note_rewrite_mappings`:

| Column | Type | Description |
| --- | --- | --- |
| `id` | string | Internal XID primary key. |
| `rewrite_id` | string | Foreign key or logical reference to `authorship_note_rewrites.rewrite_id`. |
| `repo_url` | string | Normalized repository URL. |
| `source_commit` | string | Replaced commit. |
| `target_commit` | string | Replacement commit. |
| `source_note_blob_oid` | string nullable | Source note blob oid. |
| `target_note_blob_oid` | string nullable | Target note blob oid. |
| `target_content_hash` | string | Hash of target note content. |
| `disposition` | string | Mapping disposition. |
| `created_at` | bigint | Server timestamp in milliseconds. |

Constraints and indexes:

```sql
UNIQUE(repo_url, source_commit, target_commit, rewrite_id)
CREATE INDEX idx_authorship_note_rewrite_source
ON authorship_note_rewrite_mappings(repo_url, source_commit);
CREATE INDEX idx_authorship_note_rewrite_target
ON authorship_note_rewrite_mappings(repo_url, target_commit);
```

## Existing Endpoint Adjustments

Default reads return only active notes:

- `POST /worker/authorship_notes/list`
- `POST /worker/authorship_notes/batch`
- `POST /worker/authorship_notes/get`
- the `/worker/notes/*` aliases for the same endpoints

Add optional request field:

```json
{
  "include_superseded": true
}
```

When omitted or false, superseded notes are excluded from default sync. This
keeps old clients from reactivating source commits or counting both `B` and
`D` as active. Search should also default to active notes only, with the same
audit option.

`POST /worker/authorship_notes/push` remains unchanged except that newly
created notes should default to `status = "active"`. If `/push` updates a
superseded note directly, the service should keep its `superseded` status
unless the request explicitly uses a future restore API. This prevents a
generic push from accidentally undoing a rewrite.

## Metrics And Active-Note Queries

Any query that treats authorship notes as the active set must filter:

```sql
status = 'active'
```

or the equivalent compatibility condition during migration:

```sql
(status IS NULL OR status = 'active')
```

This applies to stats joins, blame-related note lookups, batch sync, and list
sync. Superseded notes remain queryable only when callers opt in for audit.

## Client Behavior

Clients keep using `/worker/authorship_notes/push` for normal new notes.

When a local rewrite event is produced and `notes_store = rest`, the client
calls `/worker/authorship_notes/rewrite` as part of rewrite side effects. It
must not rely on a later generic `/push` to express the source-to-target
relationship.

Initial rewrite events that should call this endpoint:

- pending rebase pick consumption, including manual conflict-resolution commit
- completed rebase mapping
- completed cherry-pick mapping
- amend mapping

Only mappings that replace prior active authorship should use
`disposition = "supersede_source"`.

## Swagger And Documentation

Update `docs/swagger/api/notes-rest.yaml` with:

- `POST /worker/authorship_notes/rewrite`
- `POST /worker/notes/rewrite`
- schemas for rewrite request, mapping, success response, and conflict item

Update API reference documentation to explain that `/push` is a normal upsert
and `/rewrite` is required for history-rewrite semantics.

## Testing

Add integration tests for:

- `POST /worker/authorship_notes/rewrite` creates the target note and
  supersedes the source note.
- `POST /worker/notes/rewrite` behaves the same as the canonical endpoint.
- Replaying the same `rewrite_id` and same request is idempotent.
- Replaying the same `rewrite_id` with different content returns HTTP `409`.
- Target note conflict returns a conflict item and does not overwrite the
  existing target.
- Source note already superseded by another rewrite returns a conflict item.
- `/list` excludes superseded source notes by default.
- `/batch` excludes superseded source notes by default.
- `/get` excludes superseded source notes by default unless
  `include_superseded = true`.
- `/push` does not restore a superseded note to active.

Add unit tests around the database/service layer for:

- `request_hash` stability after repo URL normalization.
- `change_seq` only advances when content or status changes.
- atomic rollback when one mapping fails before any durable rewrite record is
  committed.

## Migration And Compatibility

Existing rows in `authorship_notes` migrate to `status = "active"`.

During rollout, query code should treat `NULL` status as active so mixed
schema deployments do not hide all existing notes. After all deployments run
the migration, `status` can be made non-null with default `active`.

Servers that do not support `/rewrite` can still receive target notes through
`/push`, but they cannot suppress the replaced source notes. Clients should
feature-detect `/rewrite` or version-gate this behavior and log a warning when
falling back to `/push` for a rewrite event.
