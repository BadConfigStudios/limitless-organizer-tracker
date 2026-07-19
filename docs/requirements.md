# Requirements & MVP Traceability

This document tracks the Business Requirements (BR), Functional Requirements
(FR), and Non-Functional Requirements (NFR) for the Limitless Organizer
Tracker, and maps them to the MVPs and build phases that implement them.

## Business Requirements (BR)

- **BR1**: Provide visibility into organizer-application throughput
  (status-check history, outcomes) that Limitless does not report on.
- **BR2**: Maximize approval likelihood by automating frequent, scheduled
  resubmission per Limitless's LIFO-favoring review process, with a Discord
  notification per resubmission sent to the user's own server (for manual
  copy/paste into the organizer Discord, matching the existing manual habit).
- **BR3**: Provide visibility into platform-wide organizer growth — how many
  new organizers (across all games) become active each week/month, based on
  each organizer's first tournament date — and estimate how long a new
  applicant should expect to wait before their organizer ID becomes active,
  based on the current onboarding rate. Also capture actual organizer
  onboarding dates (when the organizer profile page first goes live) for
  forward-looking daily onboarding-rate analytics and delta measurement
  (time from onboarding to first tournament).

## Functional Requirements (FR)

| ID | Requirement | Serves | Status / Phase |
|----|-------------|--------|-----------------|
| FR1 | Log into play.limitlesstcg.com via Playwright using stored username/password, persisting session for reuse | BR1, BR2 | **Done — Phase 5** (`app/scraper/browser.py`) |
| FR2 | Check organizer/organization application status on a configurable schedule; record each check as a timestamped datapoint (status enum + raw text) | BR1 | **Done — Phase 6** (`app/tasks/status_tasks.py`, `check_application_status_task`, beat schedule via `application_status_check_interval_hours`) |
| FR3 | Resubmit the organization application 1-2x/day on a configurable schedule | BR2 | **Done — Phase 6** (`app/tasks/resubmit_tasks.py`, `resubmit_application_task`, beat schedule via `resubmit_times_utc`) |
| FR4 | Post a Discord notification (to the user's own server, via `DISCORD_WEBHOOK_URL`) when a resubmission occurs, for manual copy/paste into the organizer Discord | BR2 | **Done — Phase 5/6** (`app/notifications/discord.py`; wired into `resubmit_application_task`. Phase 6 also adds a status-change notice for FR2.) |
| FR5 | Log each resubmission as a timestamped datapoint (success flag, discord-notified flag) | BR1, BR2 | **Done — Phase 6** (`record_resubmission` in `app/tasks/resubmit_tasks.py`) |
| FR6 | Ingest tournament data from `GET /api/tournaments` across all games | BR3 | **Done — Phase 3/10**: recent ingestion (Phase 3) plus paginated historical backfill (`TOURNAMENT_BACKFILL_MONTHS`, default 3 months) on a Celery beat schedule (`app/tasks/tournament_tasks.py`) |
| FR7 | Determine each organizer's ID and first-tournament date per game from ingested data | BR3 | **Done — Phase 3** (`OrganizerActivity`) |
| FR8 | Compute counts of newly-active organizers per week/month, overall and filterable by game | BR3 | **Done — Phase 11** (`GET /api/organizers/activity`, `app/api/routers/organizers.py`) |
| FR9 | Dashboard displays application status-check history (timeline) | BR1 | **Done — Phase 7/8** (`GET /api/status-history`; `frontend/src/components/StatusTimeline.tsx`) |
| FR10 | Dashboard displays resubmission log | BR1, BR2 | **Done — Phase 7/8** (`GET /api/resubmissions`; `frontend/src/components/ResubmissionLog.tsx`) |
| FR11 | Dashboard displays newly-active-organizer counts per week/month, filterable by game | BR3 | **Done — Phase 12** (`frontend/src/components/OrganizerActivityChart.tsx`) |
| FR12 | Identify the top 1000 highest `organizer_id`s globally (one point per organizer using `MIN(first_tournament_date)` across games), compute the Pareto frontier (lower-envelope — points not dominated by any other point with a higher ID and earlier date), fit OLS regression on the frontier to estimate the onboarding rate (slope), and optionally project when a target organizer ID will become active | BR3 | **Done — Phase 12.5** ([#41](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/41), `GET /api/organizers/wait-estimate`, `app/analytics/frontier.py`, `app/analytics/regression.py`) |
| FR13 | Dashboard displays the onboarding-rate scatter (general + frontier series) with fitted line and R²; optionally shows a projected active date for a user-supplied target organizer ID | BR3 | **Done — Phase 12.5** ([#41](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/41), `frontend/src/components/WaitTimeEstimator.tsx`) |
| FR14 | Provide an API endpoint to trigger an on-demand application-status check (extends FR2), running synchronously and returning the recorded result | BR1 | **Done** — [#23](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/23) (`POST /api/status-check`, `app/api/routers/status.py`) |
| FR15 | Given an organizer ID, scrape `play.limitlesstcg.com/organizer/{id}` via the FR18 endpoint and display the organizer's name, upcoming/recent tournaments, and highest known organizer ID stat card on the dashboard | BR3 | **Done — Phase 17** ([#45](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/45), `frontend/src/components/OrganizerProfile.tsx`) |
| FR16 | Dashboard stat card showing the highest organizer ID currently in the `Organizer` table (populated by FR17 scanner) | BR3 | **Done — Phase 16** (API) / **Phase 17** (UI: `frontend/src/components/HighestOrganizerIdCard.tsx`) — [#45](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/45) |
| FR17 | Detect and record actual organizer onboarding dates: daily Celery task scans `play.limitlesstcg.com/organizer/{id}` (public page, httpx, no auth) starting from `MAX(organizer_id) + 1` across `Organizer` + `OrganizerActivity` tables, increments until the first 404; each 200 records the organizer in the new `Organizer` table with `onboarded_at = today`. Tournament ingestion also upserts `Organizer.first_tournament_date` (MIN across games) so the onboarding-to-first-tournament delta is always fresh | BR3 | **Done — Phase 14** ([#51](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/51)) |
| FR18 | `GET /api/organizers/{id}/scrape` — httpx fetch of the public `play.limitlesstcg.com/organizer/{id}` page, parsed via BeautifulSoup 4, returning organizer name and tournament list as JSON; no DB storage (data lives on the source page). Tested against fixture HTML | BR3 | **Done — Phase 16** ([#45](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/45)) |
| FR19 | Centralized event log: all significant application operations (task lifecycle, scraper actions, data ingestion, notifications, API triggers) are recorded in a partitioned `event_log` table with event type, severity, source, message, and JSON metadata. Provides an `app/events.py` service callable from any module | BR1 | **Done — Phase 21a** (`app/events.py`, `app/db/models.py`) |
| FR20 | Admin event-log API: `GET /api/admin/event-log` returns paginated, filterable event log entries (by event type, severity, source, date range) | BR1 | **Done — Phase 21a** (API), **Phase 21b** (frontend: `EventLogViewer.tsx`) |
| FR21 | Admin diagnostics API: `GET /api/admin/diagnostics` returns system health (DB status, Redis connectivity, Celery worker/beat status, last successful run per task) | BR1 | **Done — Phase 21a** (API), **Phase 21b** (frontend: `Diagnostics.tsx`) |
| FR22 | Admin config API: `GET /api/admin/config` returns current non-sensitive configuration (scan intervals, backfill months, ingest limits) via hardcoded allowlist | BR1 | **Done — Phase 21a** (API), **Phase 21b** (frontend: `AdminConfig.tsx`) |
| FR23 | Admin tasks API: `GET /api/admin/tasks` returns available task trigger endpoints for frontend task-trigger buttons. All Celery beat tasks must have a corresponding manual trigger endpoint | BR1 | **Done — Phase 21a** (API), **Phase 21b** (frontend: `TaskTriggers.tsx`). Gap: `scan_new_organizers_task` missing — [#83](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/83) |
| FR24 | Log a `scraper.session_refreshed` event in the event log when `authenticated_page()` detects and recovers from an expired session, so the recovery is visible in the admin Event Log viewer (not just Celery worker logs) | BR1 | **Done — Phase 31** ([#96](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/96)) |
| FR25 | When `SCRAPER_DEBUG` is enabled, capture full page HTML (`page.content()[:20000]`) on every scrape attempt (not just failures) and include it in the `log_event()` details, providing on-demand diagnostic visibility without a code change or redeploy | BR1 | **Done — Phase 33** ([#91](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/91)) |
| FR26 | Runtime configuration database: `config_entries` table stores key/value pairs that override env-var defaults at runtime. `config_db.py` module provides `get_config_value()`, `set_config_value()`, and an `EDITABLE_CONFIG_KEYS` allowlist restricting which settings are admin-editable. Sensitive config (DB URL, credentials, API keys) is never stored in the DB | BR1 | **Done — Phase 34** ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100)) |
| FR27 | Config resolution layer: `get_effective_config()` merges DB overrides over env-var defaults for all editable keys; `get_effective_value()` resolves a single key with type coercion. `GET /api/admin/config` returns effective (DB-merged) config. Runtime task config reads (`tournament_ingest_limit`, `tournament_backfill_months`, `organizer_scan_start_id`, `organizer_scan_limit`) use `get_effective_value()` instead of raw `settings.*` | BR1 | **Done — Phase 35** ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100)) |
| FR28 | Admin config edit API + frontend: `PUT /api/admin/config` accepts partial updates validated against the editable-keys allowlist, persists via `set_config_value()`, and returns the updated effective config. Frontend `AdminConfig.tsx` supports inline editing with per-row edit/save controls via `useMutation` | BR1 | **Done — Phase 36** ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100)) |
| FR29 | Dynamic Celery beat schedule via `celery-redbeat`: replaces the static import-time beat schedule with Redis-backed `RedBeatSchedulerEntry` objects. `build_beat_schedule()` reads effective config (DB-merged) and writes schedule entries to Redis. Schedule is rebuilt on app startup and after `PUT /api/admin/config` writes, so config changes take effect without redeploying | BR1 | **Done — Phase 37** ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100)) |
| FR30 | Surface `detected_at` with full datetime in organizer API responses; `GET /api/organizers/recently-onboarded?limit=N` returns the N most recently detected organizers ordered by `detected_at` desc; `display_timezone` admin-editable setting (default `America/Chicago`) | BR3 | **Done — Phase 40** ([#101](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/101), [#102](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/102), [#126](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/126)) |
| FR31 | Recently onboarded organizers table: `RecentlyOnboarded.tsx` displays recently onboarded organizers with datetime timestamps and clickable IDs linking to Organizer Profile section | BR3 | **Done — Phase 41** ([#92](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/92)) |
| FR32 | Date window selector on Organizer Activity chart and Wait Time Estimator (30/90/180 days, all time) enabling users to focus on recent trends vs historical data | BR3 | **Done — Phase 41** ([#125](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/125)) |
| FR33 | Onboarding analytics overlay + delta: onboarding counts as a Line series on the Organizer Activity chart alongside the existing Bar (first tournament activity); `GET /api/organizers/onboarding-delta` returning avg/median days from `onboarded_at` to `first_tournament_date` for organizers with both fields (excludes negative deltas); `OnboardingDelta` dashboard card displaying the stats with ID ≥ 2723 threshold note | BR3 | **Done — Phase 42** ([#85](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/85)) |
| FR34 | Dashboard stat cards: "My Application" tab shows at-a-glance stat cards (current status badge, last check time, total resubmissions, last resubmission time) sourced from existing `/api/status-history` and `/api/resubmissions` endpoints; "Organizers" tab shows scanner status card (last scan time, scanner watermark/highest ID, organizers found in last scan) sourced from existing `/api/organizers/highest-id` and `/api/admin/event-log` endpoints | BR1, BR3 | **Done — Phase 43** ([#103](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/103)) |
| FR35 | One-time admin-triggered backfill task (`backfill_organizers_from_tournaments_task`) that creates `Organizer` rows for every `organizer_id` present in `tournaments` but missing from `Organizer`, reusing `sync_organizer_first_tournament_dates()` (FR17) so `detected_at` is set per FR-fix in Phase 46. Trigger endpoint `POST /api/tasks/backfill-organizers`, admin UI button | BR3 | **Done — Phase 47** ([#136](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/136)) |
| FR36 | One-time admin-triggered historical scan (`historical_organizer_scan_task`) that probes organizer IDs 1 through the scanner watermark (`organizer_scan_start_id`) via httpx 200/404, skipping IDs that already have an `Organizer` row. Unlike the frontier scanner (FR17), does not stop at the first 404 — historical IDs have gaps. Dispatches `scan_single_organizer_task` per 200 with `set_onboarded=False` so historical organizers don't get a misleading `onboarded_at`. Trigger endpoint `POST /api/tasks/historical-organizer-scan`, admin UI button | BR3 | **Done — Phase 48** ([#137](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/137)) |
| FR37 | Frontier regression logic extracted from the organizers router into a shared `app/analytics/frontier.py` module (`build_frontier_regression(session)`), used by both `GET /api/organizers/wait-estimate` (FR12) and a new one-time admin-triggered verification task (`verify_frontier_regression_task`) that counts `Organizer` rows and logs slope/R²/frontier_size/sample_size as an event. Trigger endpoint `POST /api/tasks/verify-frontier-regression`, admin UI button | BR3 | **Done — Phase 49** ([#139](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/139)) |
| FR38 | MkDocs + mkdocs-material documentation site covering project overview/architecture, development setup/workflow/configuration/API reference, deployment (local/staging/production/Helm), and metrics methodology (frontier regression, organizer activity, organizer lifecycle); built via `mkdocs build --strict` in CI | BR1 | **Done — Phase 50/51** ([#140](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/140)) |
| FR39 | Documentation site served from the cube cluster at `/manual` via a dedicated `docs` image (MkDocs static build + nginx), Helm Deployment/Service mirroring the `frontend` pattern, and an independent Ingress resource (`/manual(/\|$)(.*)` rewrite) that does not couple docs deploys to the frontend image | BR1 | **Done — Phase 52** ([#147](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/147)) |

## Non-Functional Requirements (NFR)

| ID | Requirement | Status |
|----|-------------|--------|
| NFR1 | TDD (red→green→refactor) for all code, with unit/integration/acceptance coverage | **Established — Phases 1-4** (18 tests, ongoing each phase) |
| NFR2 | API-first backend, written in Python (FastAPI), decoupled from frontend | **Established — Phases 1-2** |
| NFR3 | Always-running architecture via Celery worker + beat scheduler | **Done — Phases 6/10** (`app/celery_app.py`): MVP1 status-check/resubmit tasks plus MVP2 tournament-ingestion task |
| NFR4 | Monorepo, public on GitHub, with GitHub Actions CI | **Established — Phase 1** |
| NFR5 | Scraper logic decoupled from live site; tested via fixture HTML, no live calls in CI (`@pytest.mark.live` reserved for future) | **Established — Phases 4-5** |
| NFR6 | Configuration via environment variables (`.env`), no secrets committed | **Established — Phases 1-2** |

## MVP Breakdown

### MVP1 — Application Status & Resubmission Tracker
Serves BR1, BR2 / FR1-5, FR9-10, partial NFR3. Phases 5-9.

**Acceptance**: `docker compose up` runs backend + celery worker/beat +
postgres/redis + frontend; status checks and resubmissions are logged on
schedule; Discord notified on resubmission; dashboard shows status timeline
and resubmission log.

**Verified — Phase 9 (2026-06-13)**: `docker compose up --build` brings up all
six services; `backend` applies migrations on startup and serves `/healthz`
(200); `celery-worker`/`celery-beat` connect to Redis and start without
error; `frontend` serves the dashboard at `:5173`. Full test suites pass in
containers: `docker compose run --rm backend pytest` (68/68) and
`docker compose run --rm frontend npm test -- --run` (5/5).

### MVP2 — Organizer Activity Analytics
Serves BR3 / FR6-8, FR11-18, remaining NFR3. Phases 10-13, 15, 18.

**Acceptance**: tournament ingestion runs on schedule, including a paginated
historical backfill (default 3 months); `/api/organizers/activity` returns
correct weekly/monthly counts, filterable by game; `/api/organizers/wait-estimate`
returns a global Pareto-frontier regression (top-1,000 organizer IDs) with
slope/R²/frontier_size and an optional projected active date for a supplied
organizer ID; dashboard organizer-activity chart renders filterable by game;
wait-time estimator renders the scatter + fitted line on load;
`scan_new_organizers_task` runs daily and records `Organizer.onboarded_at`;
`/api/organizers/onboarding-history` returns daily/weekly counts.

**Verified — Phase 13 (2026-06-18)**: `docker compose up --build` brings up all
six services cleanly; `celery-worker` registers all 3 tasks and connects to
Redis; `celery-beat` starts. Full test suites pass in containers:
`docker compose run --rm backend pytest` (121/121) and
`docker compose run --rm frontend npm test -- --run` (30/30). Live checks:
`GET /api/games` → 12 games; `GET /api/organizers/activity?interval=week` →
weekly counts; `GET /api/organizers/wait-estimate?organizer_id=2720` →
slope/R²/projected_date (sample_size=468, frontier_size=55).

**Phase 14 extension (2026-06-18)**: FR17 (`scan_new_organizers_task` + `Organizer`
table + `GET /api/organizers/onboarding-history`) implemented and merged (PR #53).
Backend test suite extended to 121 tests; all pass.

### MVP3 — Documentation & Traceability
Project hygiene / final NFR coverage. Phase 15.

**Acceptance**: README fully documents setup/env/scheduling/scraper-selector
caveat; this traceability table shows all FR/NFR as Done with final phase
references.

**Verified — Phase 15 (2026-06-18)**: `docs/dev_guide.md` covers all env vars
(including `LIMITLESS_APPLICATION_ID`, `CORS_ALLOWED_ORIGINS`,
`TOURNAMENT_BACKFILL_MONTHS`, `ORGANIZER_SCAN_INTERVAL_HOURS`,
`ORGANIZER_SCAN_LIMIT`) and the scraper-selector caveat. FR/NFR traceability
table is complete through Phase 14. README placeholder stub removed.

**Release — v0.3.0 (2026-06-23)**: Phases 15–29 shipped. Includes Helm/Fleet
deployment, DaisyUI theme, admin API + frontend, event logging, backend
refactors, frontend cleanup, performance fixes, historical backfill,
error-state tests, wait-estimate API shape cleanup (#37), and expired session
detection/recovery (#16). CHANGELOG cut to `[0.3.0]`.

### MVP4 — Runtime Configuration & Polish

Runtime config editing from the admin UI (including cronjob schedules) without
redeploying, session lifecycle improvements, debug tooling, UI polish, and
onboarding analytics. Phases 30–45.

**Acceptance**: `docker compose up` runs backend + celery worker/beat +
postgres/redis + frontend; admin UI edits to config are persisted to DB and
override env-var defaults; Celery beat schedule rebuilds automatically after
config edits (via celery-redbeat); onboarding dashboard shows recently
onboarded organizers, activity overlay with onboarding counts, and
onboarding-to-first-tournament delta; dashboard stat cards show at-a-glance
application status and scanner status; DaisyUI dim theme with visible zebra
striping and wider layout. Full test suites pass in containers.

**Verified — Phase 45 (2026-06-25)**: Full test suites pass in containers.
Staging verification confirms admin config editing, dynamic beat schedule
reload, onboarding dashboard, stat cards, and UI polish. CHANGELOG cut to
`[0.4.0]`.

**Release — v0.4.0 (2026-06-25)**: Phases 30–44 shipped. Includes resubmit
bug triage (#86), session refresh event logging (#96), configurable session
validation timeout (#97), SCRAPER_DEBUG flag (#91), config-in-database with
admin editing (#100), celery-redbeat for dynamic beat schedules (#100), UI
styling rework + dim theme (#79), UI layout + table polish (#122–#124, #116),
recently onboarded API + display_timezone (#101, #102, #126), onboarding
dashboard + date windows (#92, #125), onboarding analytics overlay + delta
(#85), dashboard stat cards (#103), and bug fixes (#106, #109, #113, #119).

### MVP5 — Organizer Data Completeness & Metrics Docs

Close organizer data gaps (ingestion upsert fix, backfill from tournaments,
historical ID scan 1–2722), verify frontier regression improvement, and add a
metrics documentation site served from the cluster at `/manual`. Phases 46–53.

**Acceptance**: All organizer_ids present in the `tournaments` table have a
corresponding `Organizer` row with `detected_at` set; historical IDs 1–2722
probed for existence; frontier regression metrics logged after backfill;
MkDocs site builds cleanly with project, development, deployment, and metrics
documentation and is reachable at `/manual` in staging/production. Full test
suites pass in containers, `ruff` clean, `mkdocs build --strict` succeeds.

**Verified — Phase 53 (2026-06-30)**: Full backend test suite passes in
containers (393/393), `ruff` clean. `mkdocs build --strict` succeeds.
CHANGELOG cut to `[0.5.0]`. Staging verification (backfill tasks increase the
Organizer count, regression metrics in the event log, new admin trigger
buttons, `/manual` reachability) pending — see follow-up after this PR merges.

**Release — v0.5.0 (2026-06-30)**: Phases 46–53 shipped. Includes ingestion
organizer upsert fix (#138), Organizer backfill from tournament data (#136),
historical organizer ID scan 1–2722 (#137), frontier regression verification +
refactor (#139), MkDocs documentation site with project/dev/deployment/metrics
content (#140), and docs site deployment via dedicated Helm Deployment +
Ingress at `/manual` (#147).

## Build Order

Tracked via [GitHub milestones](https://github.com/badconfigstudios/limitless-organizer-tracker/milestones)
(one per MVP) and one issue per phase.

| Phase | Description | MVP | Issue |
|-------|-------------|-----|-------|
| 1 | Repo scaffold + CI | — | — |
| 2 | Backend foundation (config, FastAPI healthz, models, Alembic) | — | — |
| 3 | Tournament ingestion + organizer activity aggregation | MVP2 | — |
| 4 | Application-status scraper (fixture-based HTML parsing) | MVP1 | — |
| 4.5 | Requirements traceability doc (this file) | — | [#1](https://github.com/badconfigstudios/limitless-organizer-tracker/pull/1) |
| 5 | Resubmit scraper + Discord notifier | MVP1 | [#2](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/2) |
| 6 | Celery app + beat schedule for status-check/resubmit tasks | MVP1 | [#3](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/3) |
| 7 | FastAPI routers: status history, resubmissions | MVP1 | [#4](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/4) |
| 8 | Frontend scaffold + MVP1 dashboard (status timeline, resubmission log) | MVP1 | [#5](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/5) |
| 9 | MVP1 docker-compose verification (acceptance checkpoint) — **Done** | MVP1 | [#6](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/6) |
| 10 | Tournament ingestion Celery task + beat schedule, including paginated historical backfill (default 3 months) — **Done** | MVP2 | [#7](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/7) |
| 11 | FastAPI routers: organizer activity, games, onboarding-rate regression/wait estimate (FR12) — **Done** | MVP2 | [#8](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/8) |
| 12 | Frontend organizer-activity chart + wait-time estimator (FR11, FR13) — **Done** | MVP2 | [#9](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/9) |
| 12.5 | Redesign wait-estimate: global top-1000 Pareto-frontier regression (FR12, FR13) — **Done** | MVP2 | [#41](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/41) |
| 13 | MVP2 docker-compose verification (acceptance checkpoint) — **Done** | MVP2 | [#10](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/10) |
| 14 | Organizer onboarding scanner: `Organizer` table (organizer_id, onboarded_at, first_tournament_date, detected_at), daily `scan_new_organizers_task` Celery task, `first_tournament_date` sync in tournament ingestion, `GET /api/organizers/onboarding-history` (FR17) — **Done** | MVP2 | [#51](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/51) |
| 15 | README + traceability finalization — **Done** | MVP3 | [#11](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/11) |
| 16 | Organizer profile backend: `GET /api/organizers/{id}/scrape` (httpx + BS4, FR18) + `GET /api/organizers/highest-id` (FR16 API) — **Done** | MVP2 | [#45](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/45) |
| 17 | Organizer profile frontend: `OrganizerProfile` component + `HighestOrganizerIdCard` stat card + Dashboard wiring (FR15, FR16 UI) — **Done** | MVP2 | [#45](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/45) |
| 18 | Cyberpunk theme via DaisyUI | MVP3 | [#46](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/46) |
| 19 | Helm chart + Rancher Fleet GitOps deployment to local k3s/MicroOS cluster — **Done** | MVP3 | [#47](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/47) |
| 20 | Separate Celery worker image with Playwright; expose all tasks as API endpoints — **Done** | MVP3 | [#69](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/69), [#71](https://github.com/badconfigstudios/limitless-organizer-tracker/pull/71) |
| 21a | Admin API backend: EventLog model (partitioned), event logging service, Celery signal handlers, instrumented business logic, admin router (event-log, diagnostics, config, tasks) (FR19-FR23) | MVP3 | [#70](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/70) |
| 21b | Admin frontend: Admin tab with EventLog, Diagnostics, TaskTriggers, Config components — **Done** | MVP3 | [#70](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/70) |
| 22 | Backend refactors: shared test fixtures ([#57](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/57), [#32](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/32)), `task_session()` context manager ([#56](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/56), [#17](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/17)), dedupe test helpers ([#18](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/18)), merge bucket functions ([#55](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/55)) — **Done** | — | [#57](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/57), [#56](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/56), [#55](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/55), [#32](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/32), [#18](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/18), [#17](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/17) |
| 23 | Frontend cleanup: restore tab/table styling ([#77](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/77)), date-formatting helper ([#40](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/40)), query-string standardization ([#39](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/39)), remove unreachable branch ([#38](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/38)) — **Done** | MVP3 | [#77](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/77), [#40](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/40), [#39](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/39), [#38](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/38) |
| 24 | Performance: fix N+1 queries in tournament ingestion ([#54](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/54)), add index on `OrganizerActivity.game` ([#31](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/31)) — **Done** | — | [#54](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/54), [#31](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/31) |
| 25 | Scrape endpoint syncs `first_tournament_date` + returns `estimated_onboard_date` from regression ([#62](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/62)) — **Done** | MVP3 | [#62](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/62) |
| 26 | Historical tournament backfill: full-history ingestion task with admin trigger ([#68](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/68)) — **Done** | MVP3 | [#68](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/68) |
| 27 | Error-state tests for admin + data components ([#75](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/75)) | MVP3 | [#75](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/75) |
| 28 | Wait-estimate response shape cleanup: remove `intercept`, add `fitted_line` endpoints + `total_points`, cap `points` at 200 (FR12, FR13) ([#37](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/37)) | MVP3 | [#37](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/37) |
| 29 | Expired session detection and recovery: `authenticated_page()` validates stored sessions, auto-refreshes on expiry ([#16](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/16)) | MVP3 | [#16](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/16) |
| 30 | Triage resubmit bug: verified fix from PR #88, added missing `post_request_failed` test (FR3) ([#86](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/86)) | MVP4 | [#86](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/86) |
| 31 | Log `scraper.session_refreshed` event on expired session recovery (FR24) ([#96](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/96)) — **Done** | MVP4 | [#96](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/96) |
| 32 | Configurable session validation timeout: `SESSION_VALIDATION_TIMEOUT_MS` setting controls `page.goto()` timeout during session validation; `PlaywrightTimeoutError` treated as expired session ([#97](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/97)) — **Done** | MVP4 | [#97](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/97) |
| 33 | `SCRAPER_DEBUG` config flag: when enabled, capture full page HTML on every scrape attempt in event log details (FR25) ([#91](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/91)) | MVP4 | [#91](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/91) |
| 34 | Config DB table + model + migration: `ConfigEntry` model, `config_db.py` module with `get_config_value()`, `set_config_value()`, `EDITABLE_CONFIG_KEYS` allowlist (FR26) ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100)) — **Done** | MVP4 | [#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100) |
| 35 | Config resolution: DB overrides env (FR27) ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100)) — **Done** | MVP4 | [#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100) |
| 36 | Admin config edit API + frontend: `PUT /api/admin/config` with allowlist validation, `AdminConfig.tsx` inline editing (FR28) ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100)) — **Done** | MVP4 | [#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100) |
| 37 | Dynamic Celery beat schedule via `celery-redbeat`: Redis-backed beat entries rebuilt on startup and after config edits (FR29) ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100)) — **Done** | MVP4 | [#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100) |
| 38 | UI styling rework: DaisyUI dim theme, table zebra, pagination on all lists, task trigger table with component badges, error message standardization, auto-refresh, keepPreviousData ([#79](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/79)) — **Done** | MVP4 | [#79](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/79) |
| 39 | UI layout + table polish: widen page layout (#122), fix zebra striping contrast in dim theme (#123), reorganize dashboard tabs (#124), fix MSW PUT handler type mismatch (#116) — **Done** | MVP4 | [#122](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/122), [#123](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/123), [#124](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/124), [#116](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/116) |
| 40 | Surface `detected_at` with full datetime in organizer API responses, new `GET /api/organizers/recently-onboarded` endpoint, `display_timezone` admin-editable setting (FR30) ([#101](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/101), [#102](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/102), [#126](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/126)) | MVP4 | [#101](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/101), [#102](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/102), [#126](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/126) |
| 41 | Organizer onboarding dashboard: `RecentlyOnboarded.tsx` table, date window selector on activity chart and wait-time estimator (FR31, FR32) ([#92](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/92), [#125](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/125)) — **Done** | MVP4 | [#92](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/92), [#125](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/125) |
| 42 | Onboarding analytics overlay + delta: onboarding line series on activity chart, `GET /api/organizers/onboarding-delta`, `OnboardingDelta` card (FR33) ([#85](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/85)) — **Done** | MVP4 | [#85](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/85) |
| 43 | Dashboard stat cards: application stat cards on "My Application" tab, scanner status card on "Organizers" tab (FR34) ([#103](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/103)) — **Done** | MVP4 | [#103](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/103) |
| 44 | Bug fixes + cleanup: centralize `session_refreshed` event logging (#106), eliminate redundant `page.content()` calls (#109), fix `config_db` bool type coercion (#113), make `build_beat_schedule` atomic (#119) — **Done** | MVP4 | [#106](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/106), [#109](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/109), [#113](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/113), [#119](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/119) |
| 45 | MVP4 verification + release cut (v0.4.0): update requirements traceability, record remaining technical decisions, CHANGELOG cut, full test suite, manual staging verification — **Done** | MVP4 | — |
| 46 | Ingestion organizer upsert fix: set `detected_at` on new Organizer rows created by `sync_organizer_first_tournament_dates()` (FR17) — **Done** | MVP5 | [#138](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/138) |
| 47 | Backfill Organizer rows from tournament data: one-time admin-triggered Celery task that creates Organizer rows for all orphan `organizer_id`s in tournaments table, with trigger endpoint and admin UI entry (FR35) — **Done** | MVP5 | [#136](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/136) |
| 48 | Historical organizer ID scan 1–watermark: one-time admin-triggered Celery task that probes existence via httpx without stopping at the first 404, dispatching `scan_single_organizer_task` for each 200 (FR36) — **Done** | MVP5 | [#137](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/137) |
| 49 | Verify frontier regression + refactor: extract `build_frontier_regression()` into `app/analytics/frontier.py`, add a verification task that logs slope/R²/frontier_size/sample_size after backfill (FR37) — **Done** | MVP5 | [#139](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/139) |
| 50 | Documentation site scaffold: MkDocs + mkdocs-material, project/development/deployment pages, `docs-build` CI job (FR38) — **Done** | MVP5 | [#140](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/140) |
| 51 | Documentation site: metrics pages (overview, frontier regression, organizer activity, organizer lifecycle) (FR38) — **Done** | MVP5 | [#140](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/140) |
| 52 | Deploy docs site via Helm + Ingress: dedicated `docs` image (MkDocs build + nginx), Deployment/Service mirroring `frontend`, independent Ingress at `/manual` (FR39) — **Done** | MVP5 | [#147](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/147) |
| 53 | MVP5 verification + release cut (v0.5.0): update requirements traceability, CHANGELOG cut, full test suite, manual staging verification, `mkdocs build --strict` — **Done** | MVP5 | — |
