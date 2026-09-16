# API Reference

All `/api/*` endpoints require an `X-API-Key` header matching one of the
backend's `API_KEYS` (see [Configuration](configuration.md)). Responses
below show the Pydantic response model fields; see
`backend/app/api/schemas.py` for the source of truth.

Paginated list endpoints share a common envelope:

```json
{ "items": [...], "total": 0, "limit": 50, "offset": 0 }
```

## Application status & resubmissions

`backend/app/api/routers/status.py`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/status-check` | Synchronously dispatch an application-status check to the Celery worker and return the result (60s timeout) |
| `GET` | `/api/status-history` | Paginated history of status checks (`limit`, `offset`) |
| `GET` | `/api/resubmissions` | Paginated history of resubmission events (`limit`, `offset`) |

`StatusCheckOut`: `id`, `checked_at`, `status` (enum), `raw_text`,
`review_note`.

`ResubmissionEventOut`: `id`, `submitted_at`, `success`, `discord_notified`.

## Organizers

`backend/app/api/routers/organizers.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/games` | Distinct games with tournament activity — `list[str]` |
| `GET` | `/api/organizers/activity` | Weekly/monthly counts of newly-active organizers. Query: `interval` (`week`\|`month`, default `week`), `game` (optional filter) |
| `GET` | `/api/organizers/wait-estimate` | Pareto-frontier OLS regression over the top organizer IDs by `first_tournament_date`. Query: `organizer_id` (optional — adds a projected active date), `days` (optional — restricts to organizers whose `first_tournament_date` falls in the last N days, filtered before the frontier/regression calculation). 404 if not enough data |
| `POST` | `/api/organizers/backfill-first-tournament-date` | Back-populate `Organizer.first_tournament_date` from `OrganizerActivity` for rows where it's `NULL`. Returns `{"updated": <count>}` |
| `GET` | `/api/organizers/onboarding-history` | Daily/weekly counts of newly-onboarded organizers (by `onboarded_at`). Query: `interval` (`day`\|`week`, default `day`) |
| `GET` | `/api/organizers/onboarding-delta` | Avg/median days between `onboarded_at` and `first_tournament_date`, excluding negative deltas |
| `GET` | `/api/organizers/recently-onboarded` | Most recently detected organizers, ordered by `detected_at` desc. Query: `limit` (default 10, max 100) |
| `GET` | `/api/organizers/highest-id` | Highest known `organizer_id` across `Organizer` and `OrganizerActivity` tables. 404 if no data |
| `GET` | `/api/organizers/{organizer_id}/scrape` | Live `httpx` fetch + parse of the organizer's public Limitless profile page. Upserts `first_tournament_date`/`detected_at` as a side effect. 404 if not found on Limitless |

### `WaitEstimateOut`

```json
{
  "organizer_id": 2720,
  "slope": 0.5,
  "r_squared": 0.95,
  "projected_active_date": "2026-08-01",
  "sample_size": 468,
  "frontier_size": 55,
  "total_points": 468,
  "fitted_line": [
    {"organizer_id": 1500, "projected_date": "2025-01-01"},
    {"organizer_id": 2720, "projected_date": "2026-08-01"}
  ],
  "points": [
    {"organizer_id": 1500, "first_tournament_date": "2025-01-01", "is_frontier": false}
  ]
}
```

`points` is capped at 200 entries (all frontier points plus a sampled subset
of the rest) to keep the dashboard chart responsive; `sample_size`/
`total_points` reflect the true (uncapped) count.

### `OrganizerProfileOut`

`organizer_id`, `name`, `upcoming_tournaments`/`recent_tournaments`
(`list[TournamentEntryOut]`: `tournament_id`, `name`, `date`, `game`,
`players`), `onboarded_at`, `first_tournament_date`, `detected_at`,
`estimated_onboard_date` (only populated when `onboarded_at` is still
unknown — see the [Architecture](architecture.md#data-flow-organizer-onboarding)
onboarding-signals note).

## Task triggers

`backend/app/api/routers/tasks.py` — manual, on-demand equivalents of every
Celery-beat-scheduled task (see [Configuration](configuration.md) for the
schedules). Every task listed here is also discoverable via
`GET /api/admin/tasks` (see [Admin](#admin) below).

| Method | Path | Description | Returns |
|--------|------|--------------|---------|
| `POST` | `/api/tasks/ingest-tournaments` | Fetch recent tournaments from Limitless across all games | `TaskResultOut` (synchronous, 120s timeout) |
| `POST` | `/api/tasks/full-backfill` | Discover all tournament pages, dispatch one task per page | `TaskResultOut` (fire-and-forget — monitor via event log) |
| `POST` | `/api/tasks/scan-organizers` | Runs `audit_organizer_scan_task` directly — the same task the beat-scheduled `scan_new_organizers_task` dispatches to. Audits organizer IDs from the current watermark forward, dispatches per-ID scans | `TaskResultOut` (fire-and-forget) |
| `POST` | `/api/tasks/backfill-organizers` | One-time: create `Organizer` rows for every orphan `organizer_id` in `tournaments` | `TaskResultOut` (fire-and-forget) |
| `POST` | `/api/tasks/historical-organizer-scan` | One-time: probe organizer IDs 1–watermark, queue scans for each `200` | `TaskResultOut` (fire-and-forget) |
| `POST` | `/api/tasks/verify-frontier-regression` | One-time: count `Organizer` rows, run the regression, log slope/R²/sizes | `TaskResultOut` (fire-and-forget) |
| `POST` | `/api/tasks/resubmit-application` | Resubmit the organizer application via Playwright, Discord-notify | `ResubmissionEventOut` (synchronous, 120s timeout) |

`TaskResultOut`: `task_id`, `status` (`"completed"` or `"started"`),
`result` (human-readable summary or progress note).

## Admin

`backend/app/api/routers/admin.py` (FR20–FR23) — operational visibility and
runtime config, all under `/api/admin`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/admin/event-log` | Paginated event log. Query: `limit` (default 50, max 200), `offset`, `event_type`, `severity`, `source` |
| `GET` | `/api/admin/diagnostics` | System health snapshot |
| `GET` | `/api/admin/config` | Current *effective* (DB-merged) config — see [Configuration](configuration.md#resolution-order) |
| `PUT` | `/api/admin/config` | Partial update of admin-editable keys; rebuilds the Celery beat schedule on success |
| `GET` | `/api/admin/tasks` | List of all manually-triggerable tasks (name, endpoint, method, description, component) — drives the Admin tab's Task Triggers panel |

### `DiagnosticsOut`

`db_ok`, `redis_ok` (bool health checks), `celery_workers` (list of worker
hostnames that responded to a `control.ping`), `beat_ok` (whether any
`task.completed` event has ever been logged), `last_success_per_task`
(task name → ISO timestamp of its most recent `task.completed` event).

### `AdminConfigOut` / `AdminConfigUpdate`

Mirrors the nine admin-editable keys documented in
[Configuration](configuration.md): `application_status_check_interval_hours`,
`resubmit_times_utc`, `tournament_ingest_interval_hours`,
`tournament_ingest_limit`, `tournament_backfill_months`,
`organizer_scan_interval_hours`, `organizer_scan_limit`,
`organizer_scan_start_id`, `display_timezone`. `PUT` accepts any subset
(all fields optional) and returns `422` if none are provided.

## Health check

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Liveness/readiness probe — `{"status": "ok"}`. No API key required; used by the Helm chart's probes (see [Helm Reference](deployment/helm.md)) |
