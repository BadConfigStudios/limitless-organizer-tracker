# Dashboard Fixes + Admin/Application Auth Gate — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:writing-plans to turn this spec into an implementation plan, then superpowers:subagent-driven-development (preferred) or superpowers:executing-plans to execute it task-by-task. This spec bundles four related but independently-shippable pieces of work — the implementation plan MUST size them as separate PR-scoped tasks per `~/.claude/CLAUDE.md`'s PR guardrails, not one large PR.

## Goal

Four fixes/enhancements to the dashboard, bundled into one planning cycle because they were raised together in the same session:

1. **Wait-time estimator regression doesn't respect the date-window filter.** The dropdown only filters the scatter dots client-side; slope/R²/fitted-line/frontier always reflect the full top-1000-organizer-ID dataset regardless of the selected window.
2. **Default date window should be 90 days**, not "All time," on both the Organizer Activity chart and the Wait Time Estimator.
3. **Resubmission Discord reminder has no clickable link.** It currently just says "Use the Resubmit Now button on the dashboard's My Application tab" with no URL.
4. **Admin + My Application tabs need a password gate.** Per the 2026-07-19 single-tenant pivot decision, the reporting/Organizers tab should stay publicly viewable, but Admin and My Application should require login.

## Current State (confirmed during brainstorming)

- Auto-resubmission is **already fully decommissioned** (Phase 54 / #152) — `resubmit_application_task` only runs via the manual `POST /api/tasks/resubmit-application` trigger; the Celery beat schedule only wires `resubmit_reminder_task`, which performs no scraping or submission. This is not a regression; item 3 above is purely "add a link to the existing reminder text."
- All API routers currently share one flat gate: `require_api_key` (`X-API-Key` header, checked in `app/api/auth.py`) applied uniformly to `organizers.py`, `admin.py`, `tasks.py`, and `status.py`. There is no per-tab/per-user auth today.
- Frontend is a single `Dashboard.tsx` with three tabs (`application`, `organizers`, `admin`) toggled by local `activeTab` state — no routing library, no auth state.

---

## Part 1: Wait-estimate regression follows the date window

**Backend** (`backend/app/analytics/frontier.py`, `backend/app/api/routers/organizers.py`):

- `build_frontier_regression(session, days: int | None = None)` gains a `days` parameter. When set, the query filters to `first_tournament_date >= today - days` **before** computing the Pareto frontier and fitting the regression — not as a post-hoc filter on an already-frontier-computed set. This means slope/R²/frontier_size/sample_size all reflect only the selected window when one is chosen.
- `TOP_N_ORGANIZERS = 1000` stays as a safety cap in both cases (irrelevant in practice for a date-filtered query, since a 30/90/180-day window will almost always return far fewer than 1000 organizers).
- `GET /api/organizers/wait-estimate` gains `days: int | None = Query(None)`, passed straight through to `build_frontier_regression`. Response shape (`WaitEstimateOut`) is unchanged — the values inside it just reflect the filtered set.

**Frontend** (`frontend/src/components/WaitTimeEstimator.tsx`, `frontend/src/api/client.ts`):

- `getWaitEstimate(organizerId?: number, days?: number)` appends `days` to the query string when provided.
- `dateWindow` becomes part of the React Query key: `["wait-estimate", targetOrganizerId, dateWindow]`, converted from the `DateWindow` string type (`"" | "30" | "90" | "180"`) to a numeric `days` value (or `undefined` for `""`) passed to `getWaitEstimate`.
- The client-side `filterByDateWindow`/`filteredEstimate` logic in this component is removed — `estimateQuery.data` is now already scoped to the selected window, so `toScatterData`/`toFrontierScatterData` read it directly.
- `XAxis` keeps `domain={["auto", "auto"]}` — no manual domain clipping needed. Since the fitted line's own endpoints now come from the same filtered regression, the axis naturally shrinks to match the selected window. This resolves the "chart doesn't resize" complaint as a side effect of computing the regression correctly, rather than as a separate visual-clipping hack.

**Note on `OrganizerActivityChart.tsx`:** this component already resizes correctly today — it passes a single shared `data` array to `ComposedChart`, so both the Bar and Line series shrink together when `filterByDateWindow` trims the array. No backend change needed there; it only gets the Part 2 default-value change.

---

## Part 2: Default date window = 90 days

- `OrganizerActivityChart.tsx`: `useState<DateWindow>("")` → `useState<DateWindow>("90")`.
- `WaitTimeEstimator.tsx`: same change, `useState<DateWindow>("")` → `useState<DateWindow>("90")`.
- `DateWindowSelect.tsx` options list/order is unchanged — "All time" stays first in the dropdown, it's just no longer the initial selection.

---

## Part 3: Resubmission reminder gets a real link

**Backend:**

- `backend/app/config.py`: new setting `dashboard_base_url: str = ""` (e.g. `https://limitless-org-dashboard.badconfig.com`; empty by default so local/dev environments without a public URL don't break).
- `backend/app/notifications/discord.py`: `build_reminder_message(timestamp, link: str | None)` — when `link` is non-empty, appends it as a distinct line so Discord auto-embeds it as a clickable URL (e.g. `f"{base_text}\n{link}"`); when empty, message text is unchanged from today (keeps local/dev behavior sane without the config set).
- `backend/app/tasks/resubmit_tasks.py`: `resubmit_reminder_task` builds the link as `f"{settings.dashboard_base_url}/?tab=application"` (or just the bare base URL if query-param tab-selection isn't worth adding — see Part 4's note on whether tab state becomes a URL param) and passes it to `post_reminder_notice`.

This value naturally gets set as part of the prod-cutover ArgoCD `Application`'s `helm.parameters` (alongside the other carried-over secrets in that plan's Task 5) once the production URL is finalized.

---

## Part 4: Admin + My Application password gate

Per owner decision during brainstorming: **app-level login page** with a signed session cookie (not ingress Basic Auth, not a localStorage shared-secret header). Session signing uses **stdlib `hmac`/`hashlib`**, not a new dependency — appropriate here since there's exactly one shared credential and no per-user claims to encode.

**Backend:**

- `backend/app/config.py`: new settings `admin_username: str = ""`, `admin_password: str = ""`, `session_secret_key: str = ""`. All three must be set via env var in any environment where the gate should actually work (never committed).
- `backend/app/api/auth.py`: add
  - `create_session_token() -> str` — builds a payload `f"{expiry_unix_ts}"`, HMAC-signs it with `session_secret_key` (sha256), returns `f"{payload}.{signature_hex}"`.
  - `verify_session_token(token: str) -> bool` — splits payload/signature, recomputes HMAC with `hmac.compare_digest` (constant-time), checks the signature matches AND `expiry_unix_ts` hasn't passed.
  - `require_session(session_token: str | None = Cookie(None)) -> None` — FastAPI dependency; raises `401` if the cookie is missing or `verify_session_token` fails.
  - Session length: 12 hours (re-login required after that — no refresh/remember-me for a v1).
- New `backend/app/api/routers/auth.py`:
  - `POST /api/auth/login` — body `{username, password}`; compares against `settings.admin_username`/`admin_password` with `hmac.compare_digest`; on success sets an `HttpOnly`, `SameSite=Lax`, `Secure` (when not on `localhost`) cookie named `session_token` via `create_session_token()`; on failure returns `401`.
  - `POST /api/auth/logout` — clears the cookie.
  - `GET /api/auth/session` — returns `{"authenticated": bool}` by checking the cookie; used by the frontend on load to decide whether to show the login form or the protected tab content, without needing a real protected call to probe.
- Wire `Depends(require_session)` into the existing `dependencies=[...]` list on `admin.py`, `tasks.py`, and `status.py` routers (alongside the existing `require_api_key`) — both checks must pass. `organizers.py` (reporting/Organizers tab) is **not** changed; it stays `require_api_key`-only, i.e. publicly viewable the way it is today.

**Frontend:**

- New `frontend/src/components/LoginForm.tsx` — username/password fields, posts to `/api/auth/login`, shows an error on `401`.
- New `frontend/src/lib/auth.ts` (or a small hook `useAuthSession()`) — wraps a `useQuery` against `GET /api/auth/session` on mount.
- `Dashboard.tsx`: the `application` and `admin` tab bodies render `<LoginForm>` instead of their real content when `useAuthSession()` reports `authenticated: false`; a small "Log out" control appears somewhere on those tabs when authenticated (calls `POST /api/auth/logout`, then invalidates the session query). The `organizers` tab is unwrapped/unchanged.
- API client requests already need `credentials: "include"` (or equivalent fetch option) so the `HttpOnly` cookie is sent — confirm current `fetch` wrapper in `frontend/src/api/client.ts` does this; add if missing.

**Testing (all four parts):**

- Backend unit: `build_frontier_regression` with `days` set excludes out-of-window points *before* frontier computation (not after); `create_session_token`/`verify_session_token` round-trip, and expiry/tamper rejection; `build_reminder_message` with/without a link.
- Backend integration: `GET /api/organizers/wait-estimate?days=90` against seeded fixture data returns the narrower point/slope set; hitting `/api/admin/*`, `/api/tasks/*`, `/api/status-history` without a session cookie returns `401`; `/api/organizers/activity` without a session cookie still succeeds (API-key only); full login → protected-call → logout flow.
- Frontend: dropdown change on `WaitTimeEstimator` re-queries with the right `days` value and updated chart; both charts default to "Last 90 days" on mount; `Dashboard` renders `LoginForm` for `application`/`admin` tabs when unauthenticated and the real content when authenticated; `organizers` tab renders regardless of auth state.

---

## Requirements Traceability

This spec's implementation plan should add new FR entries to `docs/requirements.md` (per `~/.claude/CLAUDE.md`'s "confirm work traces to requirements-doc entry — add one if missing") for:

- Wait-estimate date-window regression filtering (extends FR12/FR13).
- Default date-window value (minor UX note under FR32, probably not its own FR).
- Reminder message link (extends FR4).
- Admin/application password gate (new FR, serves BR1/BR2 per the single-tenant pivot's auth-model decision) — closes out GitHub issue [#157](https://github.com/badconfigstudios/limitless-organizer-tracker/issues/157).

## Out of Scope

- Multi-tenant accounts, RBAC, OAuth/SSO — explicitly ruled out by the 2026-07-19 single-tenant pivot.
- "Remember me" / refresh tokens / password reset flow for the admin login — single shared credential, rotate manually via env var if needed.
- Changing the API-key (`X-API-Key`) layer itself — the session cookie is an additional, separate gate on top of it for the two protected routers.
- Deep-linking a specific tab via URL query param (`?tab=application`) for the Discord reminder link — Part 3 uses the bare `dashboard_base_url` unless the implementer finds the query-param approach trivial to add alongside existing `Dashboard.tsx` tab state; not required for this spec to be considered complete.
