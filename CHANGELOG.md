# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/). Per
[DECISIONS.md](DECISIONS.md), each MVP milestone bumps the minor version
(0.1.0, 0.2.0, ...) until a 1.0.0 release is determined.

## [Unreleased]

### Changed

- **Phase 54 — Replace automated resubmission with reminder-based manual
  trigger ([#152](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/152),
  FR3, FR4)**: The beat schedule no longer auto-dispatches resubmission.
  Instead it posts a Discord reminder (`resubmit_reminder_task`) on the
  existing `resubmit_times_utc` schedule, and resubmission is now performed
  only via an explicit "Resubmit Now" button on the My Application dashboard
  tab, reusing the existing `resubmit_application_task` and
  `POST /api/tasks/resubmit-application` endpoint. Walked back after 4 weeks
  of staging data showed no measurable benefit from full automation.

## [0.5.0] - 2026-06-30

### Added

- **Phase 52 — Deploy docs site via Helm + Ingress
  ([#147](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/147),
  FR39)**: Documentation site served from the cube cluster at `/manual` via a
  dedicated `docs` image (MkDocs static build + nginx), Helm Deployment/Service
  mirroring the existing `frontend` pattern, and an independent Ingress
  resource so docs deploys aren't coupled to a frontend image rebuild.

- **Phase 50/51 — Documentation site
  ([#140](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/140),
  FR38)**: MkDocs + mkdocs-material site with project overview/architecture,
  development setup/workflow/configuration/API reference, deployment
  (local/staging/production/Helm), and metrics methodology (frontier
  regression, organizer activity, organizer lifecycle) documentation.
  `docs-build` CI job runs `mkdocs build --strict`.

- **Phase 49 — Verify frontier regression + refactor
  ([#139](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/139),
  FR37)**: Extracted `build_frontier_regression()` from the organizers router
  into `app/analytics/frontier.py`, shared by `GET /api/organizers/wait-estimate`
  and a new one-time admin-triggered `verify_frontier_regression_task` that
  logs slope/R²/frontier_size/sample_size as an event after backfill.

- **Phase 48 — Historical organizer ID scan
  ([#137](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/137),
  FR36)**: One-time admin-triggered `historical_organizer_scan_task` that
  probes organizer IDs 1 through the scanner watermark via httpx, continuing
  past 404/500 (unlike the frontier scanner) since historical IDs have gaps,
  dispatching `scan_single_organizer_task` for each 200.

- **Phase 47 — Backfill Organizer rows from tournament data
  ([#136](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/136),
  FR35)**: One-time admin-triggered `backfill_organizers_from_tournaments_task`
  that creates `Organizer` rows for every orphan `organizer_id` present in
  `tournaments`, reusing `sync_organizer_first_tournament_dates()`.

### Fixed

- **Phase 46 — Ingestion organizer upsert fix
  ([#138](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/138),
  FR17)**: `sync_organizer_first_tournament_dates()` now sets `detected_at` on
  newly created `Organizer` rows, so ingestion-discovered organizers are
  visible in "recently detected" queries.

## [0.4.0] - 2026-06-25

### Added

- **Phase 43 — Dashboard stat cards + activity summary
  ([#103](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/103),
  FR34)**: At-a-glance stat cards on "My Application" tab (current status badge,
  last check time, total resubmissions, last resubmission time) and "Organizers"
  tab (scanner status card with last scan time, scanner watermark/highest ID,
  organizers found in last scan). Data sourced from existing endpoints
  (`/api/status-history`, `/api/resubmissions`, `/api/organizers/highest-id`,
  `/api/admin/event-log`).

- **Phase 42 — Onboarding analytics overlay + delta
  ([#85](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/85),
  FR33)**: Onboarding counts displayed as a `Line` series on the Organizer
  Activity chart alongside the existing `Bar` (first tournament activity).
  New `GET /api/organizers/onboarding-delta` endpoint returning
  `{avg_days, median_days, count}` — average/median time from `onboarded_at`
  to `first_tournament_date` for organizers with both fields (excludes negative
  deltas). `OnboardingDelta` dashboard card with ID ≥ 2723 threshold note.

- **Phase 41 — Organizer onboarding dashboard + date windows
  ([#92](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/92),
  [#125](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/125),
  FR31, FR32)**: `RecentlyOnboarded.tsx` table of recently onboarded organizers
  with datetime timestamps and clickable IDs linking to Organizer Profile.
  Date window selector (30/90/180 days, all time) on `OrganizerActivityChart`
  and `WaitTimeEstimator` for focusing on recent trends vs historical data.

- **Phase 40 — Surface detected_at + recently onboarded API + timezone
  ([#101](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/101),
  [#102](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/102),
  [#126](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/126),
  FR30)**: `detected_at` surfaced with full datetime in organizer API responses.
  New `GET /api/organizers/recently-onboarded?limit=N` endpoint returning the N
  most recently detected organizers ordered by `detected_at` desc.
  `display_timezone` admin-editable setting (default `America/Chicago`).

- **Phase 37 — Dynamic Celery beat schedule via celery-redbeat
  ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100),
  FR29)**: Replaced static import-time beat schedule with Redis-backed
  `RedBeatSchedulerEntry` objects via `celery-redbeat`. `build_beat_schedule()`
  reads effective config (DB-merged) and writes schedule entries to Redis.
  Schedule is rebuilt on app startup and after `PUT /api/admin/config` writes,
  so config changes take effect without redeploying. New dependency:
  `celery-redbeat`.

- **Phase 36 — Admin config edit API + frontend
  ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100),
  FR28)**: `PUT /api/admin/config` accepts partial updates validated against the
  editable-keys allowlist, persists via `set_config_value()`, and returns the
  updated effective config. Frontend `AdminConfig.tsx` supports inline editing
  with per-row edit/save controls via `useMutation`.

- **Phase 35 — Config resolution: DB overrides env
  ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100),
  FR27)**: `get_effective_config()` merges DB overrides over env-var defaults for
  all editable keys; `get_effective_value()` resolves a single key with type
  coercion. `GET /api/admin/config` returns effective (DB-merged) config.
  Runtime task config reads use `get_effective_value()` instead of raw
  `settings.*`.

- **Phase 34 — Config DB table + model + migration
  ([#100](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/100),
  FR26)**: New `ConfigEntry` model (`key`, `value`, `updated_at`) with Alembic
  migration. New `config_db.py` module providing `get_config_value()`,
  `set_config_value()`, and `EDITABLE_CONFIG_KEYS` allowlist (the 8
  non-sensitive fields from `AdminConfigOut`). Sensitive config (DB URL,
  credentials, API keys) is never stored in the DB. Data layer only — no API
  changes yet (part 1/4 of #100).

- **Phase 33 — SCRAPER_DEBUG config flag
  ([#91](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/91),
  FR25)**: New `SCRAPER_DEBUG` setting (default `false`). When enabled, captures
  `page.content()[:20000]` on every scrape attempt (status checks and
  resubmissions) and includes the HTML in the `log_event()` details, providing
  on-demand diagnostic visibility without a code change or redeploy.

- **Phase 32 — Configurable session validation timeout
  ([#97](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/97))**:
  New `SESSION_VALIDATION_TIMEOUT_MS` setting (default 10000) controls the
  timeout for the `page.goto()` call that validates stored sessions.
  `PlaywrightTimeoutError` is now caught and treated as an expired session
  (triggers re-authentication), logged distinctly from redirect-based expiry.

- **Phase 31 — Log session refresh event
  ([#96](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/96),
  FR24)**: `authenticated_page()` now yields an `AuthenticatedPageContext`
  dataclass with `page` and `session_refreshed` fields. When an expired session
  is detected and recovered, the calling task (`status_tasks`,
  `resubmit_tasks`) logs a `scraper.session_refreshed` event (severity WARNING)
  to the event log, making the recovery visible in the admin Event Log viewer
  instead of only in Celery worker logs.

### Changed

- **Phase 39 — UI layout + table polish
  ([#122](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/122),
  [#123](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/123),
  [#124](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/124),
  [#116](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/116))**:
  Widened page layout from `max-w-3xl` to `max-w-5xl` (#122). Fixed zebra
  striping contrast in dim theme with explicit `even:bg-base-200` (#123).
  Reorganized dashboard tabs for better information architecture (#124). Fixed
  MSW PUT handler type mismatch (#116).

- **Phase 38 — UI styling rework
  ([#79](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/79))**:
  Switched DaisyUI theme from `dark` to `dim` for better base color contrast.
  Added table zebra striping, pagination on all list views, task trigger table
  with component badges, standardized error messages, auto-refresh on data
  queries, and `keepPreviousData` for smooth pagination transitions.

### Fixed

- **Phase 44 — Bug fixes + cleanup
  ([#106](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/106),
  [#109](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/109),
  [#113](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/113),
  [#119](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/119))**:
  - Centralized `session_refreshed` event logging into `authenticated_page()`
    so every caller gets it automatically (#106)
  - Eliminated redundant `page.content()` calls on resubmit failure paths when
    `SCRAPER_DEBUG` is enabled — reuses `result.page_html` instead (#109)
  - Fixed `config_db` type coercion for bool keys (`bool` subclasses `int`);
    extracted `_coerce_value()` helper to eliminate duplication (#113)
  - Made `build_beat_schedule` atomic: creates new entries before deleting stale
    ones, uses a Redis pipeline for the tracking set update (#119)

### Tests

- **Phase 30 — Triage resubmit bug
  ([#86](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/86))**:
  verified resubmit flow is working after PR #88 fix (in-browser `fetch()`).
  Added missing `post_request_failed` failure-stage unit test. All 6 resubmit
  unit tests + 2 acceptance tests pass. Closes #86.

## [0.3.0] - 2026-06-23

### Fixed

- **Phase 29 — Expired session detection and recovery
  ([#16](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/16))**:
  `authenticated_page()` now validates stored sessions by navigating to an
  auth-required page after loading the context. If the server redirects to
  `/login` (indicating the session cookie has expired), the stale
  `storage_state.json` is deleted and a fresh login is performed
  automatically. Previously, an expired session caused `parse_status_html` to
  fall back to `UNKNOWN` (firing false Discord alerts) and
  `parse_resubmit_result` to report `success=False` on every run, with no
  automatic recovery.

### Changed

- **Phase 28 — Wait-estimate response shape cleanup
  ([#37](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/37))**:
  `GET /api/organizers/wait-estimate` no longer exposes the regression
  `intercept` (Python ordinal-day units). The backend now computes the fitted
  line's two endpoints as `{organizer_id, projected_date}` pairs and returns
  them in a new `fitted_line` field, so the frontend consumes dates directly
  without reimplementing ordinal-to-timestamp math. `points` is capped at
  `MAX_CHART_POINTS` (200) with frontier points always preserved; a new
  `total_points` field reports the pre-cap count. Frontend
  `waitEstimateChartData.ts` simplified: `EPOCH_ORDINAL`, `MIN_ORDINAL`,
  `MAX_ORDINAL` constants and ordinal conversion logic removed entirely.
  References FR12, FR13.

### Added

- **Phase 27 — Error-state tests
  ([#75](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/75))**:
  added API error-state tests (500 responses via MSW `server.use()`) to all 6
  data components: EventLogViewer, Diagnostics, TaskTriggers, AdminConfig,
  StatusTimeline, ResubmissionLog. 74 frontend tests total.
- **Phase 26 — Historical tournament backfill
  ([#68](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/68))**:
  `full_tournament_backfill_task` Celery task pages through the entire Limitless
  tournament API history with no date cutoff, upserting all tournaments and
  recomputing organizer activity/first-tournament-date data. Admin trigger at
  `POST /api/tasks/full-backfill` (10-minute timeout for the long-running
  operation). Registered in the Task Triggers panel.
- **Phase 25 — Scrape endpoint sync + estimated onboard date
  ([#62](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/62))**:
  `GET /api/organizers/{id}/scrape` now upserts an `Organizer` row on lookup,
  parsing `first_tournament_date` from the scraped tournament list (updating if
  earlier than the DB value). For organizers without a scanner-observed
  `onboarded_at`, the response includes `estimated_onboard_date` computed from
  the Pareto frontier regression. `onboarded_at` is only set by the daily
  scanner (organizer IDs >= 2723); the estimate fills in the gap for older IDs.

### Changed

- **Phase 24 — Performance
  ([#54](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/54),
  [#31](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/31))**:
  - `sync_organizer_first_tournament_dates` rewritten from O(N) per-organizer
    queries to 2 bulk queries (one `GROUP BY` aggregate + one `IN` fetch),
    eliminating the N+1 pattern during tournament ingestion (#54).
  - Added standalone index on `OrganizerActivity.game` (Alembic migration
    `d7c22892b275`) to support `WHERE game = :game` filters in activity and
    wait-estimate endpoints without a full table scan (#31).
- **Phase 23 — Frontend cleanup
  ([#77](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/77),
  [#40](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/40),
  [#39](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/39))**:
  - Tabs switched from `tabs-bordered` to DaisyUI v5 `tabs-border` with
    `text-primary font-semibold` on the active tab for clear visual distinction;
    all dashboard sections wrapped in `card bg-base-200` containers for visual
    separation from the page background (#77).
  - Shared date-formatting helpers (`formatTimestamp`, `formatDateShort`,
    `formatEpochDate`) in `src/lib/formatDate.ts` replace ad-hoc
    `new Date(x).toLocaleString()` calls across 5 components (#40).
  - All API client functions standardized on `URLSearchParams` for query-string
    building, replacing inconsistent `encodeURIComponent` template literals (#39).
  - #38 was already resolved during the Phase 12.5 redesign (the unreachable
    `fetchEstimate` null branch no longer exists).
- **Phase 22 — Backend refactors
  ([#57](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/57),
  [#56](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/56),
  [#55](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/55),
  [#32](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/32),
  [#18](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/18),
  [#17](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/17))**:
  - `task_session()` context manager in `app/db/session.py` replaces the
    duplicated `SessionLocal()` / try / finally pattern across all 4 Celery
    task modules (#56, #17). Adds rollback-on-exception to all task paths.
  - Shared test fixtures in `tests/conftest.py` (`db_session_factory`,
    `db_session`) and `tests/integration/conftest.py` (`client`) eliminate
    ~30 copies of the SQLite engine/session/TestClient boilerplate across
    unit, integration, and acceptance tests (#57, #32).
  - `fake_authenticated_page` helper moved to `tests/conftest.py`; the two
    duplicated acceptance tests consolidated into a single end-to-end beat-cycle
    test exercising both status-check and resubmission tasks in sequence (#18).
  - `bucket_activity` and `bucket_onboarding` merged into a single
    `bucket_dates` function accepting `date | datetime` and supporting all
    three intervals (`day`, `week`, `month`) (#55).

### Added

- **Phase 21b — Admin frontend tab
  ([#70](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/70))**:
  new "Admin" tab in the dashboard with four components consuming the Phase 21a
  admin API: `EventLogViewer` (paginated event log table with severity badges),
  `Diagnostics` (DB/Redis/Celery/Beat health cards + worker list + last success
  per task), `TaskTriggers` (trigger buttons for all registered Celery tasks),
  `AdminConfig` (current configuration display). Admin API client functions and
  MSW test handlers added. 16 new frontend tests (68 total). References FR20-FR23.
- **Phase 20 — Separate Celery worker image with Playwright**: new
  `Dockerfile.worker` based on `mcr.microsoft.com/playwright/python:v1.60.0-noble`
  so the Celery worker container has Chromium available for application-status
  checks and resubmission tasks (FR1-FR3). API server stays on `python:3.13-slim`
  (`Dockerfile.prod`); celery-beat stays on the backend image (scheduling only).
  CI builds and pushes `ghcr.io/.../worker` alongside backend/frontend. Helm chart
  updated: celery-worker deployment now references `worker.image`.
- **Phase 19 — Helm chart + Rancher Fleet GitOps
  ([#47](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/47))**:
  production Dockerfiles (`Dockerfile.prod` for backend + frontend with nginx),
  GitHub Actions workflow to build + push images to GHCR on main push.
  Helm chart (`charts/limitless-organizer-tracker/`) with deployments for
  backend, frontend, celery-worker, celery-beat; services; NGINX ingress for
  `limitless-org-dashboard.badconfig.com`; Percona PG Operator CRD for
  PostgreSQL; Bitnami Redis subchart. `fleet.yaml` targets the Rancher `local`
  cluster for GitOps deployment.
- **Phase 18 — Dark theme via DaisyUI
  ([#46](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/46))**:
  installed DaisyUI v5 plugin with `dark` theme. All components migrated from
  hardcoded Tailwind color utilities to DaisyUI semantic classes (`btn`,
  `badge`, `stats`, `tabs`, `input`, `select`, `form-control`). Recharts chart
  colors updated for dark background readability. 51/51 frontend tests pass.
- **Phase 17 — Organizer profile frontend + dashboard overhaul (FR15, FR16 UI,
  [#45](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/45))**:
  `OrganizerProfile` component — form to look up an organizer by ID via
  `GET /api/organizers/{id}/scrape`, displays organizer name, onboarded/first-
  tournament dates (from `Organizer` DB table), and upcoming/recent tournament
  lists with game and player count; handles 404 and empty-list states.
  `HighestOrganizerIdCard` stat card — renders the highest known organizer ID
  from `GET /api/organizers/highest-id`. Three-tab dashboard layout: "My
  Application" (status history + resubmission log), "Organizer Growth" (activity
  chart + wait-time estimator), "Organizer Lookup" (highest ID + profile).
  Status history paginated (20/page) with scrollable container. Wait-time
  estimator scatter chart axes flipped (time→X, organizer ID→Y) for readability.
  Scrape endpoint enriched with `onboarded_at` and `first_tournament_date` from
  the `Organizer` table. 51/51 frontend, 171/171 backend tests pass.
- **Phase 16 — Organizer profile backend (FR16 API, FR18)**:
  `GET /api/organizers/{id}/scrape` — httpx-fetches the public
  `play.limitlesstcg.com/organizer/{id}` page, parses with BeautifulSoup 4,
  returns organizer name + upcoming/recent tournament list as JSON (no DB
  storage). 404 from Limitless passes through as 404. Tested against fixture
  HTML. `GET /api/organizers/highest-id` — returns `MAX(organizer_id)` from
  `Organizer` table (falls back to `OrganizerActivity`; 404 if both empty).
  New schemas: `OrganizerProfileOut`, `TournamentEntryOut`,
  `HighestOrganizerIdOut`. 165/165 backend tests pass.
- **Phase 15 — README + traceability finalization (MVP3, closes [#11](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/11))**:
  expanded `docs/dev_guide.md` env-var table to cover all settings added since
  Phase 8 (`LIMITLESS_APPLICATION_ID`, `CORS_ALLOWED_ORIGINS`,
  `TOURNAMENT_BACKFILL_MONTHS`, `ORGANIZER_SCAN_INTERVAL_HOURS`,
  `ORGANIZER_SCAN_LIMIT`); added a "Scraper selectors" subsection explaining
  the `@pytest.mark.live` gate and the httpx-only nature of the onboarding
  scanner. `docs/requirements.md` FR17 status updated to Done (Phase 14);
  Phase 14 and 15 rows in the build-order table marked Done; MVP2 extended
  with a Phase 14 verification note; MVP3 marked Verified. README placeholder
  stub removed.
- **Phase 14 — Organizer onboarding scanner (FR17)**: new `Organizer` table
  (`organizer_id`, `onboarded_at`, `first_tournament_date`, `detected_at`) with Alembic
  migration. Daily `scan_new_organizers_task` Celery beat task scans public
  `play.limitlesstcg.com/organizer/{id}` pages (httpx, no auth) starting from
  `MAX(organizer_id) + 1` across `Organizer` + `OrganizerActivity`, records a row for each
  200 response (`onboarded_at = today`), and stops at the first 404. Configurable via
  `ORGANIZER_SCAN_INTERVAL_HOURS` (default 24) and `ORGANIZER_SCAN_LIMIT` (default 50).
  Tournament ingestion (`ingest_tournaments`) now also upserts
  `Organizer.first_tournament_date` = MIN across games from `OrganizerActivity`, keeping
  the onboarding-to-first-tournament delta always fresh. New `GET /api/organizers/onboarding-
  history?interval=day|week` endpoint returns `[{period, count}]` bucketed from
  `Organizer.onboarded_at` (null rows excluded). Closes [#51](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/51).
- Phase numbering shift: organizer onboarding scanner is now Phase 14; former phases 14→18
  shift to 15→18 (`docs/requirements.md` and GitHub issues updated).

## [0.2.0] - 2026-06-18

### Added

- **MVP2 acceptance (Phase 13)**: verified via `docker compose up --build` — all 6 services
  (postgres, redis, backend, celery-worker, celery-beat, frontend) start cleanly. `backend`
  serves `/healthz` (200); `celery-worker` registers all 3 tasks and connects to Redis;
  `celery-beat` starts. `docker compose run --rm backend pytest` (121/121) and
  `docker compose run --rm frontend npm test -- --run` (30/30) both pass inside the
  containers. Live checks: `GET /api/games` → 12 games; `GET /api/organizers/activity?
  interval=week` → weekly counts; `GET /api/organizers/wait-estimate?organizer_id=2720` →
  slope/R²/projected_date (sample_size=468, frontier_size=55). Closes the MVP2 acceptance
  checkpoint in `docs/requirements.md`.
- `review_note` on `ApplicationStatusCheck` (PR #49): the scraper now parses
  `.organizer-application .response` and stores any reviewer note in a new nullable
  `review_note` column (Alembic migration `ff32d370af50`). Surfaced in `StatusCheckOut`
  and displayed in `StatusTimeline` when non-null.
- `app/analytics/frontier.py` (FR12, Phase 12.5): `compute_frontier` extracts the Pareto
  lower-envelope from a sequence of `(organizer_id, ordinal_date)` pairs — retaining only
  points not dominated by any point with a higher-or-equal ID and a strictly earlier date
  (tied dates are kept).
  Unit-tested in `backend/tests/unit/test_frontier.py` (9 tests).
- `GET /api/organizers/wait-estimate` redesigned (FR12/FR13, Phase 12.5): now queries the
  global top-1,000 highest `organizer_id`s (one point per organizer,
  `MIN(first_tournament_date)` across all their games), computes the Pareto frontier, and
  fits OLS regression on frontier points only (falls back to all top-N if frontier size
  < 2). `game` parameter dropped; `organizer_id` is now optional (projection only shown
  when supplied). Response gains `frontier_size` and a per-point `is_frontier` flag.
  See `DECISIONS.md` for the design rationale.
- `WaitTimeEstimator` redesigned (FR13, Phase 12.5): chart loads on mount without requiring
  a form submission. Renders two scatter series (general population + Pareto frontier) with
  the fitted regression line. Projected active date shown only after the user submits an
  organizer ID.
- Frontend (FR11, FR13, Phase 12): the dashboard now has "Organizer Activity"
  and "Wait Time Estimator" sections.
  - `OrganizerActivityChart` fetches `GET /api/organizers/activity` (weekly
    buckets) and `GET /api/games`, with a game filter `<select>`. It renders
    a Recharts `ComposedChart` combining a bar and a line over the same
    weekly counts, plus an `sr-only` accessible list of `{label}: {count}`
    for screen readers and tests.
  - `WaitTimeEstimator` takes an organizer ID + game, fetches
    `GET /api/organizers/wait-estimate`, and renders the slope, R²,
    projected active date, and sample size, plus a `ComposedChart` scatter
    of each organizer's first-tournament date (`points`) with the fitted
    regression line.
  - `src/lib/activityChartData.ts` and `src/lib/waitEstimateChartData.ts` are
    pure, unit-tested transforms from API responses to chart-ready data
    (including converting the regression's ordinal-day units to JS epoch
    timestamps).
  - `recharts` added as a new frontend dependency.
- `GET /api/organizers/wait-estimate` (FR13, Phase 12): response now also
  includes `intercept` and a `points` array (each organizer's `organizer_id`
  and `first_tournament_date`) so the frontend can render a scatter plot and
  fitted line alongside the regression stats.
- `app/api/routers/organizers.py` (FR8, FR12): three new read-only endpoints
  over `OrganizerActivity`:
  - `GET /api/games` returns the distinct `game` values, sorted.
  - `GET /api/organizers/activity?game=&interval=week|month` (default
    `week`) buckets `first_tournament_date` into week-start (Monday) or
    month-start (1st) periods, optionally filtered by `game`, returning
    `[{"period": "YYYY-MM-DD", "count": N}, ...]`. Bucketing is a pure
    function (`app/analytics/buckets.py`, unit-tested).
  - `GET /api/organizers/wait-estimate?organizer_id=&game=` fits an
    ordinary-least-squares line of `organizer_id` vs. `first_tournament_date`
    (`app/analytics/regression.py`, pure stdlib, unit-tested) over that
    game's `OrganizerActivity` rows and returns the slope, R², a projected
    active date for `organizer_id`, and the sample size. Returns `404` if
    the game has fewer than 2 rows. See `DECISIONS.md` for the design
    choices (no new regression dependency, bucket label format, 404 on
    insufficient data).
- `app/tasks/tournament_tasks.py` (FR6, FR7, NFR3): `ingest_tournaments_task`
  runs on the `tournament_ingest_interval_hours` beat schedule (default
  hourly). It pages through `GET /api/tournaments` (`app/limitless_client/
  tournaments_api.py` now accepts a `page` param) newest-first and ingests
  each page via the existing `ingest_tournaments`, stopping once a page is
  empty or its oldest tournament is older than `TOURNAMENT_BACKFILL_MONTHS`
  (new setting, default 3 months). Re-walking the full backfill window on
  every run is idempotent (upsert) and self-heals retroactive edits within
  the window — see `DECISIONS.md` for the alternatives considered.
- `LIMITLESS_APPLICATION_ID` (`.env.example`, `app/config.py`): the
  organizer application's ID, taken from the URL of the application page
  (`https://play.limitlesstcg.com/user/application/<id>`) or the Discord
  resubmission message's link. Used by FR2's status check to build the
  application page URL.
- `POST /api/status-check` (FR14, `app/api/routers/status.py`): runs an
  on-demand application-status check synchronously (login, scrape, record
  datapoint, post a Discord notice if the status changed) and returns the
  recorded `StatusCheckOut`. Lets you verify scraper selectors / check status
  immediately instead of waiting for the next
  `application_status_check_interval_hours` tick. No auth, matching the rest
  of the API. `app/tasks/status_tasks.py` now exposes
  `run_application_status_check(session)`, shared by both the Celery task and
  this endpoint.

### Changed

- `CONTRIBUTING.md`: per-phase workflow now includes a "Manual verification"
  step between `/code-review`/`/security-review` and merge — bring up the
  stack with `docker compose up --build` and walk through new/changed
  behavior (UI happy path + an edge case, or `curl` against new/changed
  endpoints) before merging.
- Clarified FR4/BR2 (`.env.example`, `README.md`, `docs/requirements.md`):
  `DISCORD_WEBHOOK_URL` points to a webhook on the user's own server, not the
  Limitless organizer Discord. The tracker posts a notification there for the
  user to manually copy/paste into the organizer Discord. No code change —
  `app/notifications/discord.py` already just posts to whatever webhook URL
  is configured. See `DECISIONS.md`.

### Fixed

- `app/scraper/resubmit.py` (Phase 12.5): now waits for `.page2` to become visible after
  clicking Continue (ensures the JavaScript transition completes) and waits for `.page3`
  visibility instead of `networkidle`, so the resubmit wizard works reliably for
  JS-driven page reveals. Returns `False` on `PlaywrightTimeoutError` so a server-side
  rejection is treated as failure rather than raising.
- `app/scraper/resubmit.py` (PR #49): the `.page2` `wait_for_selector` is now wrapped in
  `try/except PlaywrightTimeoutError` so a JS failure preventing `.page2` from appearing
  returns `False` (no `ResubmissionEvent` recorded) rather than raising through the Celery
  task.
- `frontend/src/components/StatusTimeline.tsx` (Phase 12.5): removed `raw_text` from the
  rendered output; now shows only the capitalized status enum with a per-status color
  indicator (green/yellow/red/gray by status value).
- `frontend/src/components/StatusTimeline.tsx` (PR #49): `STATUS_COLORS` now includes
  `expired` mapped to `text-orange-500`; previously `expired` rendered identically to
  `unknown` (`text-gray-500`).
- `app/main.py`: `CORSMiddleware` now allows `POST` (in addition to `GET`), so
  the new `POST /api/status-check` (FR14) can be called cross-origin from the
  dashboard's configured origin. Previously only `GET` was allowed, which
  would fail the browser's preflight check for any `POST` request.
- `backend/Dockerfile` / `backend/pyproject.toml`: pin `playwright==1.60.0`
  and bump the base image to `mcr.microsoft.com/playwright/python:v1.60.0-noble`
  so the installed `playwright` package matches the browsers bundled in the
  image. Previously `playwright>=1.45` resolved to `1.60.0` at build time
  while the `v1.48.0-noble` base image only bundled `1.48.0`'s browsers,
  causing every `authenticated_page()` call (FR2/FR3/FR14) to fail with
  `BrowserType.launch: Executable doesn't exist at
  /ms-playwright/chromium_headless_shell-1223/...` (500 from
  `POST /api/status-check`).
- FR2 (`app/scraper/selectors.py`, `app/scraper/application_status.py`): the
  status check now navigates to the organizer's own application page
  (`/user/application/<LIMITLESS_APPLICATION_ID>`) and reads the status from
  `.organizer-application .status .code`, both verified against a live,
  authenticated session. Previously it navigated to
  `/account/settings/orgs` (a placeholder that returns no content for this
  account) and looked for a non-existent `.application-status` element, so
  `POST /api/status-check` returned 200 with `status: "unknown"` and an
  empty `raw_text` instead of the real status. The "pending" wording is
  verified live; "approved"/"rejected"/"expired" fixtures
  (`tests/fixtures/html/application_*.html`) are best-guess based on the same
  structure — if a real status doesn't match, `parse_status_html` falls back
  to `UNKNOWN` and preserves `raw_text` for manual reading.
- FR3 (`app/scraper/selectors.py`, `app/scraper/resubmit.py`,
  `app/scraper/parsing.py`): resubmit now navigates to
  `/user/application/<LIMITLESS_APPLICATION_ID>` (same as FR2) and walks the
  on-page wizard — clicking `.page1 button.continue` (verified live as a
  pure client-side reveal of `.page2`, no network request) and then
  `.page2 button.submit` (the actual resubmit). `parse_resubmit_result` now
  checks whether `.page3` has been revealed with its `success` class intact.
  Previously resubmit navigated to `/account/settings/orgs` and clicked a
  non-existent `button.resubmit`/`a.resubmit`, the same placeholder bug as
  FR2. The success path (`.page3.success`) is verified structurally; the
  failure path (an error in `.response`) is best-guess, per the same
  `UNKNOWN`-fallback philosophy as FR2 — see
  `tests/fixtures/html/application_resubmit_*.html`.

## [0.1.0] - 2026-06-13

### Added

- **MVP1 acceptance (Phase 9)**: verified via `docker compose up --build` —
  `postgres`/`redis` report healthy, `backend` serves `/healthz` (200) after
  applying migrations on startup, `celery-worker`/`celery-beat` connect to
  Redis and start without error, and `frontend` serves the dashboard at
  `:5173`. `docker compose run --rm backend pytest` (68/68) and
  `docker compose run --rm frontend npm test -- --run` (5/5) both pass inside
  the containers. Closes the MVP1 acceptance checkpoint in
  `docs/requirements.md`.
- `backend/entrypoint.sh`: runs `alembic upgrade head` before exec'ing the
  container command. Set as the `backend` image's `ENTRYPOINT`
  (`backend/Dockerfile`), so the `backend` service applies pending migrations
  on every `docker compose up` instead of requiring a manual
  `docker compose exec backend alembic upgrade head`.
- `frontend/`: Vite + React + TypeScript dashboard scaffold. `src/api/client.ts`
  fetches `/api/status-history` and `/api/resubmissions` (typed `Page<T>`
  envelope matching `app/api/schemas.py`) via `VITE_API_BASE_URL`.
  `src/components/StatusTimeline.tsx` and `src/components/ResubmissionLog.tsx`
  render the two feeds via TanStack Query; `src/pages/Dashboard.tsx` renders
  both. Styled with Tailwind CSS. Covers FR9/FR10 (dashboard UI).
- `app/main.py`: `CORSMiddleware` allowing cross-origin requests from the
  frontend dev server, configurable via the new `CORS_ALLOWED_ORIGINS`
  setting (default `http://localhost:5173`), so the dashboard can call the
  API directly from the browser.
- `app/api/routers/status.py`: `GET /api/status-history` and
  `GET /api/resubmissions`, returning `ApplicationStatusCheck` /
  `ResubmissionEvent` rows ordered by timestamp descending, paginated via
  `?limit=&offset=` (default `limit=50`, max `200`) in a
  `{items, total, limit, offset}` envelope (`app/api/schemas.py`). The
  count+paginate query logic is shared via `app/api/pagination.py`
  (`paginate()`), for reuse by future routers (e.g. Phase 11). Wired into
  `app/main.py`. Covers FR9/FR10 (API support for the Phase 8 dashboard).
- `app/scraper/session.py`: `authenticated_page()` context manager launches a
  Playwright browser, reuses `storage_state.json` if present, otherwise logs
  in with the configured credentials and persists the session.
- `app/celery_app.py`: Celery app bound to `celery_broker_url` /
  `celery_result_backend`, with a beat schedule built from
  `application_status_check_interval_hours` (status-check task) and
  `resubmit_times_utc` (one resubmit-task entry per configured time, via
  `parse_resubmit_times`).
- `app/tasks/status_tasks.py`: `check_application_status_task` checks the
  application status via an authenticated page, records each check as a
  timestamped datapoint (`record_status_check`, FR2), and posts a Discord
  status-change notice (`post_status_update_notice`,
  `app/notifications/discord.py`) only when the status differs from the
  previous check.
- `app/tasks/resubmit_tasks.py`: `resubmit_application_task` resubmits the
  application via an authenticated page, records the outcome
  (`record_resubmission`, FR5), and always posts a Discord resubmission
  notice (FR4).
- `docs/requirements.md`: FR2/FR3/FR5 marked done, FR4 extended to cover the
  Phase 6 status-change notice, and NFR3 marked done for MVP1 tasks.
- `DECISIONS.md`: new technical-decisions log (newest-first), with a
  "Technical decisions" section in `CONTRIBUTING.md` requiring owner sign-off
  before any non-trivial technical decision.
- `app/scraper/browser.py`: `login(page, username, password, storage_state_path=...)`
  authenticates against the play.limitlesstcg.com password login form and
  persists the session to `storage_state.json` for reuse (FR1).
- `app/scraper/resubmit.py`: `resubmit_application(page) -> bool` clicks the
  resubmit button and reports success/failure based on the resulting page
  state (FR3). `app/scraper/parsing.py` gains `parse_resubmit_result` plus a
  `RESUBMIT_RESULT_SELECTOR` and new fixtures
  (`org_settings_resubmit_success.html`, `org_settings_resubmit_failure.html`).
- `app/notifications/discord.py`: `post_resubmission_notice(webhook_url,
  timestamp, success)` posts a resubmission-outcome message to a Discord
  webhook via `httpx` (FR4).
- `docs/requirements.md`: FR1 marked done; FR2/FR3/FR4/FR5 updated to reflect
  login/resubmit/notifier logic landing in Phase 5, with scheduled-task
  wiring and persistence remaining in Phase 6. NFR5 now covers Phases 4-5.
- `docs/requirements.md`: BR3 expanded to cover wait-time estimation, and two
  new functional requirements for MVP2: FR12 (linear regression of
  `organizer_id` vs. `first_tournament_date` to estimate the onboarding rate
  and project a target organizer ID's active date) and FR13 (dashboard
  regression chart + wait-time estimator). FR6 now also covers a paginated
  historical backfill (`TOURNAMENT_BACKFILL_MONTHS`, default 3 months) needed
  to seed the FR12 regression, scoped to Phase 10. Phases 10-12 build-order
  descriptions updated accordingly.
- `docs/requirements.md`: Business/Functional/Non-Functional requirements
  (BR1-3, FR1-11, NFR1-6) with an MVP breakdown (MVP1: application status &
  resubmission tracker, MVP2: organizer activity analytics, MVP3:
  documentation & traceability) and a per-phase build order through Phase 14.
  Phases 1-4 are retroactively tagged: FR6/FR7/NFR1/NFR2/NFR4/NFR6 are done
  (Phases 1-3), and application-status HTML parsing (part of FR2) and NFR5
  are done (Phase 4). README links to this doc under a new "Requirements &
  MVPs" section.
- GitHub milestones for MVP1-MVP3 and one tracking issue per remaining phase
  (#2-#11), linked from the `docs/requirements.md` build-order table.
- `docs/dev_guide.md`: local backend setup, test layout (unit/integration/
  acceptance/fixtures), `@pytest.mark.live` usage, environment variable
  reference, running the full stack via `docker compose`, CI overview, and
  Alembic migration workflow.
- `CONTRIBUTING.md`: per-phase contribution workflow (branch → TDD → docs →
  CHANGELOG → commit → PR → `/code-review` + `/security-review` → merge),
  commit message conventions, and general repo rules. README links to both
  new docs.
- Monorepo scaffold: `.gitignore`, `.env.example`, `docker-compose.yml`
  (postgres, redis, backend, celery-worker, celery-beat, frontend),
  `backend/Dockerfile`, `frontend/Dockerfile`, `backend/pyproject.toml`,
  and GitHub Actions CI workflow (`.github/workflows/ci.yml`) covering
  backend lint/test, frontend lint/test, and docker builds.
- Backend foundation: pydantic-settings config (`app/config.py`), FastAPI
  app with `/healthz`, SQLAlchemy models (`ApplicationStatusCheck`,
  `ResubmissionEvent`, `Tournament`, `OrganizerActivity`), DB session
  helper, and an initial Alembic migration creating all four tables.

- `UTCDateTime` SQLAlchemy type decorator so all timestamp columns
  round-trip as UTC-aware datetimes on both SQLite (tests) and Postgres.
- Limitless tournaments API client (`app/limitless_client/tournaments_api.py`)
  and `TournamentDTO` schema for `GET /api/tournaments`.
- Tournament ingestion (`app/limitless_client/ingestion.py`): upserts
  tournament rows and maintains an `OrganizerActivity` row per
  (organizer_id, game) tracking first/last-seen tournament dates.

- Application-status scraper (`app/scraper/`): `parse_status_html` extracts
  the organizer application status (pending/approved/rejected/expired/unknown)
  from the `/account/settings/orgs` page HTML, and `check_application_status`
  is a thin Playwright wrapper around it. CSS selectors are isolated in
  `app/scraper/selectors.py` as best-guess placeholders pending a live
  verification pass against an authenticated session.

### Fixed

- `docker-compose.yml`: `celery-worker` and `celery-beat` now set
  `entrypoint: []` to skip the `backend` image's migration-running
  entrypoint. Running `alembic upgrade head` concurrently in all three
  backend-image services against a fresh database raced on
  `CREATE TABLE alembic_version`, crashing two of the three containers with
  `psycopg.errors.UniqueViolation`. Only `backend` now applies migrations on
  startup.
- `backend/Dockerfile`: `COPY . .` now runs before
  `pip install -e ".[dev]"`, so the editable install's generated package
  finder includes the `app` source mapping. Previously, `docker compose run
  --rm backend pytest` failed all 24 test files with
  `ModuleNotFoundError: No module named 'app'` (the editable install was
  performed against an empty source tree); `uvicorn`/`celery` masked this
  because both prepend `cwd` to `sys.path` when resolving import strings.
- `app/tasks/resubmit_tasks.py` / `app/tasks/status_tasks.py`: Discord
  notification failures (e.g. `discord_webhook_url` unset, the default) no
  longer crash the task or prevent the FR2/FR5 datapoint from being recorded
  — `httpx.HTTPError` is caught around each notification call and
  `discord_notified` is recorded as `False`.
- `app/celery_app.py`: `parse_resubmit_times` now skips blank entries instead
  of raising on an empty `resubmit_times_utc`, and a new
  `_status_check_schedule` helper treats a non-positive
  `application_status_check_interval_hours` as hourly instead of raising
  `ValueError` from `crontab(hour="*/0")` — both previously crashed
  `app.celery_app` at import time on misconfiguration.
- `app/scraper/session.py`: `authenticated_page()` now closes the browser even
  if `login()` raises, preventing a leaked Chromium process on login failure.
- `app/tasks/status_tasks.py`: `record_status_check`'s previous-check lookup
  now breaks `checked_at` ties with `id desc`, making status-change detection
  deterministic.

### Tests

- `frontend`: Vitest + React Testing Library + MSW component tests for
  `StatusTimeline`, `ResubmissionLog`, and `Dashboard` covering loading
  states and rendering of mocked `/api/status-history` /
  `/api/resubmissions` responses.
- Integration tests for `CORSMiddleware`: a simple cross-origin `GET` and a
  preflight `OPTIONS` request from `http://localhost:5173` both receive
  `Access-Control-Allow-Origin`.
- Integration tests for `GET /api/status-history` and `GET /api/resubmissions`
  via `TestClient` against an in-memory SQLite DB (overriding `get_db`):
  envelope shape, descending-timestamp ordering, `limit`/`offset` pagination,
  the `limit<=200` validation boundary, and the empty-table case.
- Unit tests for `authenticated_page` (mocked Playwright, both with and
  without an existing `storage_state.json`), `parse_resubmit_times` and the
  beat schedule contents, `record_status_check` (first-check and
  status-change detection), `record_resubmission`, and the new
  `build_status_update_message`/`post_status_update_notice` Discord helpers.
  Integration tests run `check_application_status_task` and
  `resubmit_application_task` in Celery eager mode against an in-memory
  SQLite DB with mocked Playwright/Discord. Acceptance tests in
  `tests/acceptance/` cover the scheduled status-change and resubmission
  flows end-to-end (FR2, FR5). Additional unit/integration tests cover the
  code-review fixes above: `parse_resubmit_times` with empty/blank entries,
  `_status_check_schedule` with a non-positive interval,
  `authenticated_page` closing the browser when `login()` raises, and both
  scheduled tasks recording their datapoint when `discord_webhook_url` is
  unset.
- Unit tests for `parse_resubmit_result`, the `login` browser helper, and
  `resubmit_application` (mocked Playwright `Page`), plus Discord message
  templating. Integration test for `post_resubmission_notice` (respx-mocked).
  Acceptance tests in `tests/acceptance/` cover the login flow (FR1) and the
  resubmit-then-notify flow for both success and failure outcomes (FR3, FR4).
- Unit tests for the `ApplicationStatus` enum, model table names, the
  `TournamentDTO` schema, tournament ingestion/activity aggregation
  (first-seen tracking, per-game separation, re-ingestion updates, upserts),
  and application-status HTML parsing against hand-authored fixtures for
  each status plus the "no application yet" case.
- Integration tests for `/healthz`, DB model round-trips, and the
  tournaments API client (mocked via `respx` using real sample payloads).
