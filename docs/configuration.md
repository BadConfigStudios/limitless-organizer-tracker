# Configuration

## Environment variables

Copy `.env.example` to `.env` and fill in real values. `.env` is gitignored
— never commit real credentials or webhook URLs.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis URLs for Celery |
| `LIMITLESS_BASE_URL` | Base URL for play.limitlesstcg.com |
| `LIMITLESS_USERNAME` / `LIMITLESS_PASSWORD` | Scraper login credentials |
| `LIMITLESS_APPLICATION_ID` | Your organizer application's numeric ID — from the URL `…/user/application/<id>` |
| `DISCORD_WEBHOOK_URL` | Webhook for a channel on **your own** Discord server; the tracker posts a notice here that you copy/paste into the organizer Discord |
| `DASHBOARD_BASE_URL` | Public URL of this dashboard; included as a clickable link in the resubmission reminder (default: none) |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins allowed to call the API (default: `http://localhost:5173`) |
| `APPLICATION_STATUS_CHECK_INTERVAL_HOURS` | How often to run the application-status check, in hours (default: 4) |
| `RESUBMIT_TIMES_UTC` | Comma-separated `HH:MM` UTC times for resubmission; provide 1 or 2 (e.g. `09:00,21:00`) |
| `TOURNAMENT_INGEST_INTERVAL_HOURS` | How often to ingest tournament data, in hours (default: 1) |
| `TOURNAMENT_INGEST_LIMIT` | Number of most-recent tournaments pulled per ingestion run (default: 1000) |
| `TOURNAMENT_BACKFILL_MONTHS` | Months of historical tournament data to keep backfilled per run (default: 3) |
| `ORGANIZER_SCAN_INTERVAL_HOURS` | How often the organizer onboarding scanner runs, in hours (default: 24) |
| `ORGANIZER_SCAN_LIMIT` | Max new organizer IDs probed per scan run (default: 50) |
| `ORGANIZER_SCAN_START_ID` | Organizer ID the daily scanner starts probing from when no rows exist yet (default: 2722) |
| `DISPLAY_TIMEZONE` | Timezone used to render `detected_at`/`onboarded_at` in the dashboard (default: `America/Chicago`) |
| `API_KEYS` | Comma-separated list of valid secrets protecting `/api/*` endpoints (any one of them satisfies `X-API-Key`); at least one must match `VITE_API_KEY` |
| `VITE_API_BASE_URL` | Frontend's base URL for the backend API |
| `VITE_API_KEY` | API key baked into the frontend build; sent as `X-API-Key` header on every request |

## Runtime configuration database

Most of the intervals/limits above can also be edited live from the Admin
tab's config editor (`PUT /api/admin/config`), without a redeploy.

- `app/db/models.py` — `ConfigEntry` table stores key/value overrides.
- `app/config_db.py` — `EDITABLE_CONFIG_KEYS` is the hardcoded allowlist of
  which settings are admin-editable. Sensitive config (DB URL, credentials,
  API keys) is **never** stored in the DB and never admin-editable.

**Admin-editable keys**: `application_status_check_interval_hours`,
`resubmit_times_utc`, `tournament_ingest_interval_hours`,
`tournament_ingest_limit`, `tournament_backfill_months`,
`organizer_scan_interval_hours`, `organizer_scan_limit`,
`organizer_scan_start_id`, `display_timezone`.

### Resolution order

For each editable key, `get_effective_value()` resolves in this order:

1. **DB entry** in `ConfigEntry`, if one exists — type-coerced to match the
   default's type (bool/int/str).
2. **Environment variable**, via `Settings` (`app/config.py`) — the
   out-of-the-box default for an unconfigured deployment.
3. **Hardcoded default** in the `Settings` class, if neither of the above
   is set.

`GET /api/admin/config` returns this effective (DB-merged) config — what
the system is actually using right now, not just the env-var values.

### Beat schedule reload

Changing an interval via `PUT /api/admin/config` does **not** require a
restart. The endpoint persists the new value to `ConfigEntry`, then calls
`build_beat_schedule()`, which writes new `RedBeatSchedulerEntry` objects to
Redis (creating the new entries before deleting the stale ones) using
`celery-redbeat`. Celery beat reads its schedule from Redis on every poll
cycle, so the new interval takes effect within one poll. If the rebuild
fails, the config write still succeeds but a `WARNING`-severity event is
logged — check the Admin event log if a schedule change doesn't seem to
take effect.

See [Architecture](architecture.md) for how beat/worker/Redis fit together,
and [API Reference](api.md#admin) for the full admin endpoint list.
