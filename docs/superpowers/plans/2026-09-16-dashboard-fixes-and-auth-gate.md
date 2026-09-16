# Dashboard Fixes + Admin/Application Auth Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Wait Time Estimator's regression actually respect the date-window filter, default both charts to a 90-day window, put a real clickable link in the resubmission reminder, and gate the Admin + My Application tabs behind a simple username/password session while keeping the Organizers tab public.

**Architecture:** Four independent, PR-sized changes built on the existing FastAPI + React/Vite/React Query stack. Parts 1-2 change how `GET /api/organizers/wait-estimate` computes its regression (adds an optional `days` filter applied before the frontier/regression calculation) and how the frontend consumes it. Part 3 adds a `dashboard_base_url` setting and threads it into the existing Discord reminder message. Part 4 adds a second, independent auth layer (HttpOnly session cookie, stdlib-`hmac`-signed) on top of the existing `X-API-Key` gate, enforced only on the routers backing the Admin and My Application tabs.

**Tech Stack:** FastAPI, SQLAlchemy, pytest + respx (backend); React, TanStack Query, Vitest + MSW + Testing Library (frontend). No new dependencies in any task.

## Global Constraints

- No hardcoded secrets — `admin_username`, `admin_password`, `session_secret_key`, `dashboard_base_url` are all new env-var-backed settings in `app/config.py` (`Settings`), never committed with real values.
- Every new/changed backend setting that gates behavior (`admin_username`/`admin_password`/`session_secret_key`) must be a no-op (route stays open) when unset — this exactly mirrors the existing `require_api_key` behavior in `app/api/auth.py` (`if not valid_keys: return None`) and is required so the ~50 existing integration tests for `admin.py`/`tasks.py`/`status.py` keep passing without modification.
- TDD (red → green → refactor) for every step below — write the failing test first, confirm it fails, then implement.
- Stage files by name when committing — never `git add -A`/`.`.
- Each task below is exactly one PR. Stop after each task, push, open the PR, run `/review`, get owner merge approval — never self-merge (`~/.claude/CLAUDE.md`).
- Branch per task off `main` (not off each other) using `git checkout -b <type>/<slug>`, per `~/.claude/CLAUDE.md`'s "no exceptions" rule — each task's Step 1 says exactly which branch name to use.

---

### Task 1: Wait-estimate regression respects the date window + 90-day defaults

**Files:**
- Modify: `backend/app/analytics/frontier.py` (`build_frontier_regression`)
- Modify: `backend/app/api/routers/organizers.py` (`get_wait_estimate`, `~line 60-65`)
- Test: `backend/tests/unit/test_build_frontier_regression.py`
- Test: `backend/tests/integration/test_organizers_api.py`
- Modify: `frontend/src/api/client.ts` (`getWaitEstimate`, line 107)
- Modify: `frontend/src/components/WaitTimeEstimator.tsx`
- Modify: `frontend/src/components/OrganizerActivityChart.tsx` (line 20 only)
- Test: `frontend/src/components/WaitTimeEstimator.test.tsx`
- Test: `frontend/src/components/OrganizerActivityChart.test.tsx`
- Test: `frontend/src/test/handlers.ts` (wait-estimate handler)

**Interfaces:**
- Produces: `build_frontier_regression(session: Session, days: int | None = None) -> tuple[points, frontier_points, result]` — same return shape as today, just computed over a date-filtered subset when `days` is set.
- Produces: `GET /api/organizers/wait-estimate?days=<int>` — existing `WaitEstimateOut` shape, values reflect the filtered set.
- Produces: `getWaitEstimate(organizerId?: number, days?: number): Promise<WaitEstimate>` in `frontend/src/api/client.ts`.

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull --ff-only
git checkout -b fix/wait-estimate-date-window
```

- [ ] **Step 2: Write the failing backend unit test — date filter excludes points before frontier calc**

Add to `backend/tests/unit/test_build_frontier_regression.py`:

```python
from datetime import timedelta


def test_days_filter_excludes_points_outside_window(db_session, monkeypatch):
    """When days is set, points outside the window are excluded BEFORE frontier/regression,
    not just from the final result — a stale organizer with a very early date must not
    pull the regression toward it even indirectly."""
    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "app.analytics.frontier.datetime",
        type("_FixedDatetime", (), {"now": staticmethod(lambda tz=None: now)}),
    )
    _add_activity(db_session, 100, now - timedelta(days=200))  # outside 90-day window
    _add_activity(db_session, 200, now - timedelta(days=10))
    _add_activity(db_session, 300, now - timedelta(days=5))
    db_session.commit()

    points, frontier_points, result = build_frontier_regression(db_session, days=90)

    ids = {int(oid) for oid, _ in points}
    assert ids == {200, 300}
    assert 100 not in ids


def test_days_none_behaves_exactly_as_before(db_session):
    """days=None (the default) must not change existing all-time behavior."""
    _add_activity(db_session, 100, datetime(2025, 1, 1, tzinfo=timezone.utc))
    _add_activity(db_session, 200, datetime(2025, 6, 1, tzinfo=timezone.utc))
    db_session.commit()

    with_none = build_frontier_regression(db_session, days=None)
    without_arg = build_frontier_regression(db_session)

    assert [p for p in with_none[0]] == [p for p in without_arg[0]]
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/unit/test_build_frontier_regression.py -v -k "days"`
Expected: FAIL — `build_frontier_regression() got an unexpected keyword argument 'days'`

- [ ] **Step 4: Implement the `days` filter in `build_frontier_regression`**

Replace the full contents of `backend/app/analytics/frontier.py` with:

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.regression import fit_linear_regression
from app.db.models import OrganizerActivity

TOP_N_ORGANIZERS = 1000


def build_frontier_regression(session: Session, days: int | None = None):
    stmt = (
        select(
            OrganizerActivity.organizer_id,
            func.min(OrganizerActivity.first_tournament_date).label("first_tournament_date"),
        )
        .group_by(OrganizerActivity.organizer_id)
    )
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.having(func.min(OrganizerActivity.first_tournament_date) >= cutoff)

    rows = session.execute(
        stmt.order_by(OrganizerActivity.organizer_id.desc()).limit(TOP_N_ORGANIZERS)
    ).all()
    if len(rows) < 2:
        return None, None, None

    points = [(float(oid), float(first_date.date().toordinal())) for oid, first_date in reversed(rows)]
    frontier_points = compute_frontier(points)
    regression_points = frontier_points if len(frontier_points) >= 2 else points
    result = fit_linear_regression(regression_points)
    return points, frontier_points, result


def compute_frontier(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return the Pareto-optimal (lower-envelope) subset of (organizer_id, date_ordinal) points.

    A point is on the frontier iff no other point with an equal-or-higher organizer_id
    has a strictly earlier date — i.e., it represents the fastest observed
    onboarding-to-first-event lag for its ID range.

    Input may be in any order. Output is sorted ascending by organizer_id.
    """
    if not points:
        return []

    frontier: list[tuple[float, float]] = []
    running_min = float("inf")

    for organizer_id, date_ordinal in sorted(points, key=lambda p: p[0], reverse=True):
        if date_ordinal <= running_min:
            frontier.append((organizer_id, date_ordinal))
            running_min = date_ordinal

    frontier.reverse()
    return frontier
```

Note: using `.having()` on the aggregated `MIN(first_tournament_date)` (not a plain `.where()`) is required — the filter must apply to each organizer's *earliest* date across games, matching how the un-filtered query already dedupes via `MIN`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/unit/test_build_frontier_regression.py -v`
Expected: PASS (all tests, including the two new ones and the five pre-existing ones)

- [ ] **Step 6: Write the failing integration test — endpoint accepts and applies `days`**

Add to `backend/tests/integration/test_organizers_api.py`:

```python
def test_get_wait_estimate_with_days_filters_before_regression(client, monkeypatch):
    import app.analytics.frontier as frontier_module

    fixed_now = _dt(2026, 6, 25)
    monkeypatch.setattr(
        frontier_module, "datetime",
        type("_FixedDatetime", (), {"now": staticmethod(lambda tz=None: fixed_now)}),
    )

    test_client, session_factory = client
    with session_factory() as session:
        session.add_all(
            [
                OrganizerActivity(**_activity(100, "PTCG", _dt(2025, 1, 1))),  # outside 90d
                OrganizerActivity(**_activity(200, "PTCG", _dt(2026, 5, 1))),  # within 90d
                OrganizerActivity(**_activity(300, "PTCG", _dt(2026, 6, 1))),  # within 90d
            ]
        )
        session.commit()

    response = test_client.get("/api/organizers/wait-estimate", params={"days": 90})

    assert response.status_code == 200
    body = response.json()
    assert body["sample_size"] == 2
    ids = {p["organizer_id"] for p in body["points"]}
    assert ids == {200, 300}


def test_get_wait_estimate_without_days_is_unchanged(client):
    test_client, session_factory = client
    with session_factory() as session:
        session.add_all(
            [
                OrganizerActivity(**_activity(100, "PTCG", _dt(2025, 1, 1))),
                OrganizerActivity(**_activity(200, "PTCG", _dt(2026, 5, 1))),
            ]
        )
        session.commit()

    response = test_client.get("/api/organizers/wait-estimate")

    assert response.status_code == 200
    assert response.json()["sample_size"] == 2
```

- [ ] **Step 7: Run to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/integration/test_organizers_api.py -v -k days`
Expected: FAIL — `days` query param is silently ignored (422 is NOT expected since FastAPI ignores unknown query params by default; instead the first assertion `sample_size == 2` fails because both organizers are still returned)

- [ ] **Step 8: Wire `days` through the endpoint**

In `backend/app/api/routers/organizers.py`, change the `get_wait_estimate` signature and call (around line 60-65):

```python
@router.get("/organizers/wait-estimate", response_model=WaitEstimateOut)
def get_wait_estimate(
    organizer_id: int | None = Query(None),
    days: int | None = Query(None),
    db: Session = Depends(get_db),
) -> WaitEstimateOut:
    points, frontier_points, result = build_frontier_regression(db, days=days)
```

(Only the signature and the `build_frontier_regression` call change — everything below stays as-is.)

- [ ] **Step 9: Run to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/integration/test_organizers_api.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 10: Run the full backend suite**

Run: `cd backend && .venv/bin/pytest`
Expected: PASS, no regressions

- [ ] **Step 11: Commit the backend change**

```bash
git add backend/app/analytics/frontier.py backend/app/api/routers/organizers.py \
  backend/tests/unit/test_build_frontier_regression.py backend/tests/integration/test_organizers_api.py
git commit -m "$(cat <<'EOF'
fix(backend): wait-estimate regression respects date-window filter

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 12: Update the MSW wait-estimate handler to honor `days`**

In `frontend/src/test/handlers.ts`, replace the `*/api/organizers/wait-estimate` handler (around line 208-222) with:

```ts
export const waitEstimate90d = {
  organizer_id: 400,
  slope: 0.2,
  r_squared: 0.8,
  projected_active_date: "2026-05-01",
  sample_size: 2,
  frontier_size: 2,
  total_points: 2,
  fitted_line: [
    { organizer_id: 300, projected_date: "2026-03-03" },
    { organizer_id: 400, projected_date: "2026-05-01" },
  ],
  points: [
    { organizer_id: 300, first_tournament_date: "2026-03-03", is_frontier: true },
    { organizer_id: 380, first_tournament_date: "2026-06-20", is_frontier: true },
  ],
};

// (keep the existing `waitEstimate` export as-is — used as the all-time/no-days-param response)
```

And the handler itself:

```ts
  http.get("*/api/organizers/wait-estimate", ({ request }) => {
    const url = new URL(request.url);
    const organizerId = url.searchParams.get("organizer_id");
    const days = url.searchParams.get("days");
    const base = days === "90" ? waitEstimate90d : waitEstimate;
    const response = organizerId
      ? { ...base, organizer_id: Number(organizerId) }
      : {
          ...base,
          organizer_id: null,
          projected_active_date: null,
        };
    return HttpResponse.json(response);
  }),
```

- [ ] **Step 13: Write the failing frontend test — dropdown change re-queries with `days` and updates stats**

In `frontend/src/components/WaitTimeEstimator.test.tsx`, **replace** the existing `it("keeps stats unchanged when date window is changed", ...)` test (this test currently asserts the bug — that stats stay the same across window changes — which is exactly the behavior being fixed) with:

```ts
  it("defaults to a 90-day window and requests days=90 on load", async () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    // waitEstimate90d's stats (slope 0.2, R² 0.8, sample_size 2) prove days=90 was sent
    expect(await screen.findByText(/0\.2000/)).toBeInTheDocument();
    expect(screen.getByText(/0\.800/)).toBeInTheDocument();
    const dateSelect = screen.getByLabelText(/date range/i);
    expect(dateSelect).toHaveDisplayValue("Last 90 days");
  });

  it("recalculates the regression when the date window changes", async () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    await screen.findByText(/0\.2000/); // initial 90-day default

    const dateSelect = screen.getByLabelText(/date range/i);
    fireEvent.change(dateSelect, { target: { value: "" } }); // switch to All time

    // waitEstimate's stats (slope 0.5, R² 0.95, sample_size 5) prove the query re-ran without days
    expect(await screen.findByText(/0\.5000/)).toBeInTheDocument();
    expect(screen.getByText(/0\.950/)).toBeInTheDocument();
  });
```

Also update the earlier `it("renders a date window selector defaulting to All time", ...)` test — rename and change its expectation:

```ts
  it("renders a date window selector defaulting to Last 90 days", async () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    await screen.findByText(/0\.2000/);
    const dateSelect = screen.getByLabelText(/date range/i);
    expect(dateSelect).toHaveDisplayValue("Last 90 days");
  });
```

And every other existing test in this file that currently asserts on `waitEstimate`'s all-time values (`0.5000`, `0.950`, frontier `3`, sample size text, etc.) on initial render must instead expect the 90-day default values (`waitEstimate90d`: slope `0.2000`, R² `0.800`, `frontier_size: 2`) OR explicitly switch the dropdown to `""` first before asserting the old values. Go through the file's remaining `it(...)` blocks (`renders the scatter chart on load...`, `does not show projected active date...`, `clears the projected date...`, `shows projected active date after submitting...`, `shows the frontier size stat on load`, and both 404/500 error tests, which are unaffected) and add `fireEvent.change(screen.getByLabelText(/date range/i), { target: { value: "" } });` right after the initial render/first `findByText` wait in each one that currently asserts `0.5000`/`0.950`/frontier `3`, so they keep testing the all-time dataset's values deliberately rather than by accident.

- [ ] **Step 14: Run to verify the new/changed tests fail**

Run: `cd frontend && npm test -- --run WaitTimeEstimator`
Expected: FAIL — component doesn't send `days` yet, default window is still `""`

- [ ] **Step 15: Update `getWaitEstimate` in the API client**

In `frontend/src/api/client.ts`, replace (line 107-112):

```ts
export function getWaitEstimate(organizerId?: number, days?: number): Promise<WaitEstimate> {
  const params = new URLSearchParams();
  if (organizerId !== undefined) params.set("organizer_id", String(organizerId));
  if (days !== undefined) params.set("days", String(days));
  const qs = params.toString();
  return getJson<WaitEstimate>(`/api/organizers/wait-estimate${qs ? `?${qs}` : ""}`);
}
```

- [ ] **Step 16: Update `WaitTimeEstimator.tsx`**

In `frontend/src/components/WaitTimeEstimator.tsx`:

1. Change the default: `const [dateWindow, setDateWindow] = useState<DateWindow>("90");`
2. Replace the `estimateQuery` block and remove the client-side filtering:

```tsx
  const days = dateWindow === "" ? undefined : Number(dateWindow);

  const estimateQuery = useQuery<WaitEstimate, Error>({
    queryKey: ["wait-estimate", targetOrganizerId, dateWindow],
    queryFn: () => getWaitEstimate(targetOrganizerId, days),
  });
```

3. Remove the `filteredEstimate` block entirely (the `const filteredEstimate: WaitEstimate | undefined = ...` block).
4. In the JSX, replace `toScatterData(filteredEstimate!)` and `toFrontierScatterData(filteredEstimate!)` with `toScatterData(estimateQuery.data!)` and `toFrontierScatterData(estimateQuery.data!)`.
5. Remove the now-unused `filterByDateWindow` import (keep the `DateWindow` type import).

- [ ] **Step 17: Change `OrganizerActivityChart.tsx`'s default**

In `frontend/src/components/OrganizerActivityChart.tsx`, line 20:

```tsx
  const [dateWindow, setDateWindow] = useState<DateWindow>("90");
```

- [ ] **Step 18: Update `OrganizerActivityChart.test.tsx` for the new default**

Replace the `it("renders a date window selector defaulting to All time", ...)` test (line 47-54):

```ts
  it("renders a date window selector defaulting to Last 90 days", async () => {
    renderWithQueryClient(<OrganizerActivityChart />);

    await screen.findByText("Jun 1: 2");

    const dateSelect = screen.getByLabelText(/date range/i);
    expect(dateSelect).toHaveDisplayValue("Last 90 days");
  });
```

And update `it("shows all buckets when All time is selected", ...)` (line 91-98) to explicitly select "All time" first, since it's no longer the default:

```ts
  it("shows all buckets when All time is selected", async () => {
    renderWithQueryClient(<OrganizerActivityChart />);

    await screen.findByText("Jun 1: 2");
    fireEvent.change(screen.getByLabelText(/date range/i), { target: { value: "" } });

    await waitFor(() => {
      expect(screen.getByText("Dec 1: 3")).toBeInTheDocument();
    });
    expect(screen.getByText("Jan 5: 4")).toBeInTheDocument();
    expect(screen.getByText("Mar 1: 2")).toBeInTheDocument();
  });
```

The `it("filters activity to last 90 days when selected", ...)` test (line 73-89) already explicitly sets the dropdown to `"90"` itself, so it keeps passing unchanged — but note it's now testing a no-op transition (90 → 90) at the mocked system time; leave it as-is, it still validates the filtering logic.

- [ ] **Step 19: Run the frontend tests to verify they pass**

Run: `cd frontend && npm test -- --run`
Expected: PASS, full suite

- [ ] **Step 20: Commit the frontend change**

```bash
git add frontend/src/api/client.ts frontend/src/components/WaitTimeEstimator.tsx \
  frontend/src/components/OrganizerActivityChart.tsx frontend/src/components/WaitTimeEstimator.test.tsx \
  frontend/src/components/OrganizerActivityChart.test.tsx frontend/src/test/handlers.ts
git commit -m "$(cat <<'EOF'
fix(frontend): wait-estimate window drives regression, default both charts to 90 days

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 21: Push and open the PR**

```bash
git push -u origin fix/wait-estimate-date-window
gh pr create --title "fix: wait-estimate regression follows date window, default 90 days" --body "$(cat <<'EOF'
## Summary
- `GET /api/organizers/wait-estimate` gains an optional `days` param; when set, organizers outside the window are excluded **before** the frontier/regression calculation, not just from the chart dots. Fixes slope/R²/fitted-line not respecting the date-window dropdown.
- The X-axis resize issue reported alongside this is a side effect of the same root cause — fixed for free once the fitted line and points share the same filtered range, no separate domain-clipping code needed.
- Both the Organizer Activity chart and Wait Time Estimator now default to "Last 90 days" instead of "All time".

See docs/superpowers/specs/2026-09-16-dashboard-fixes-and-auth-gate-design.md (Parts 1-2).

## Test plan
- [x] `backend/tests/unit/test_build_frontier_regression.py` — new `days` filter tests
- [x] `backend/tests/integration/test_organizers_api.py` — new `?days=` endpoint tests
- [x] `frontend/src/components/WaitTimeEstimator.test.tsx` — updated for 90-day default + recalculation
- [x] `frontend/src/components/OrganizerActivityChart.test.tsx` — updated for 90-day default
- [ ] Manual: load Organizers tab, confirm Wait Time Estimator shows "Last 90 days" and the stats/axis change when switching to "All time"

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Then run `/review`, fix any Critical/High or low-LOE findings, do manual verification (per `~/.claude/CLAUDE.md`'s mandatory pre-merge gate — load the app, switch the date window on both charts, confirm the Wait Time Estimator's stats and axis actually change), and get owner merge approval. **Stop here — do not start Task 2 until this PR is merged and the owner has checked in**, per the PR-boundary rule in `~/.claude/CLAUDE.md`.

---

### Task 2: Resubmission reminder gets a real Discord link

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/notifications/discord.py`
- Modify: `backend/app/tasks/resubmit_tasks.py`
- Test: `backend/tests/integration/test_discord_webhook.py`
- Test: `backend/tests/integration/test_resubmit_reminder_task.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `settings.dashboard_base_url: str` (new config field, default `""`).
- Produces: `build_reminder_message(timestamp: datetime, link: str = "") -> str` and `post_reminder_notice(webhook_url: str, timestamp: datetime, link: str = "") -> httpx.Response` — both backward compatible (existing 2-arg calls still work).

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull --ff-only
git checkout -b feat/resubmit-reminder-link
```

- [ ] **Step 2: Write the failing test — reminder message includes the link when provided**

Add to `backend/tests/integration/test_discord_webhook.py`:

```python
@respx.mock
def test_post_reminder_notice_includes_link_when_provided():
    route = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))
    timestamp = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)

    response = post_reminder_notice(WEBHOOK_URL, timestamp, link="https://limitless-org-dashboard.badconfig.com")

    assert response.status_code == 204
    payload = route.calls.last.request.content.decode()
    assert "https://limitless-org-dashboard.badconfig.com" in payload


@respx.mock
def test_post_reminder_notice_omits_link_when_not_provided():
    route = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))
    timestamp = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)

    post_reminder_notice(WEBHOOK_URL, timestamp)

    payload = route.calls.last.request.content.decode()
    assert "http" not in payload.lower()
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/integration/test_discord_webhook.py -v -k link`
Expected: FAIL — `post_reminder_notice() got an unexpected keyword argument 'link'`

- [ ] **Step 4: Add `dashboard_base_url` setting**

In `backend/app/config.py`, add after `discord_webhook_url: str = ""` (line 17):

```python
    dashboard_base_url: str = ""
```

- [ ] **Step 5: Update `build_reminder_message`/`post_reminder_notice`**

In `backend/app/notifications/discord.py`, replace:

```python
def build_reminder_message(timestamp: datetime, link: str = "") -> str:
    """Build the Discord message content for a resubmission reminder."""
    message = _REMINDER_TEMPLATE.format(timestamp=timestamp.isoformat())
    if link:
        message = f"{message}\n{link}"
    return message


def post_reminder_notice(webhook_url: str, timestamp: datetime, link: str = "") -> httpx.Response:
    """Post a Discord notification reminding the user to resubmit manually."""
    message = build_reminder_message(timestamp, link)
    return httpx.post(webhook_url, json={"content": message})
```

- [ ] **Step 6: Run to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/integration/test_discord_webhook.py -v`
Expected: PASS

- [ ] **Step 7: Write the failing test — the Celery task passes the configured link through**

Add to `backend/tests/integration/test_resubmit_reminder_task.py`:

```python
@respx.mock
def test_resubmit_reminder_task_includes_dashboard_link_when_configured(monkeypatch, db_session_factory):
    monkeypatch.setattr("app.db.session.SessionLocal", db_session_factory)
    monkeypatch.setattr(resubmit_tasks.settings, "discord_webhook_url", WEBHOOK_URL)
    monkeypatch.setattr(resubmit_tasks.settings, "dashboard_base_url", "https://limitless-org-dashboard.badconfig.com")

    route = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    resubmit_tasks.resubmit_reminder_task.delay()

    payload = route.calls.last.request.content.decode()
    assert "https://limitless-org-dashboard.badconfig.com" in payload
```

- [ ] **Step 8: Run to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/integration/test_resubmit_reminder_task.py -v -k link`
Expected: FAIL — link not in payload (task doesn't pass it yet)

- [ ] **Step 9: Wire the link into `resubmit_reminder_task`**

In `backend/app/tasks/resubmit_tasks.py`, in `resubmit_reminder_task` (currently `response = post_reminder_notice(settings.discord_webhook_url, reminded_at)`), change to:

```python
    response = post_reminder_notice(settings.discord_webhook_url, reminded_at, link=settings.dashboard_base_url)
```

Note: `Dashboard.tsx`'s `TABS[0].id` is `"application"` and its `activeTab` state already initializes to `TABS[0].id` — the My Application tab is already the default view, so the bare `dashboard_base_url` lands there with no query-param deep-linking needed.

- [ ] **Step 10: Run to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/integration/test_resubmit_reminder_task.py -v`
Expected: PASS

- [ ] **Step 11: Run the full backend suite**

Run: `cd backend && .venv/bin/pytest`
Expected: PASS, no regressions

- [ ] **Step 12: Commit**

```bash
git add backend/app/config.py backend/app/notifications/discord.py backend/app/tasks/resubmit_tasks.py \
  backend/tests/integration/test_discord_webhook.py backend/tests/integration/test_resubmit_reminder_task.py
git commit -m "$(cat <<'EOF'
feat(backend): add clickable dashboard link to resubmission reminder

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 13: Push and open the PR**

```bash
git push -u origin feat/resubmit-reminder-link
gh pr create --title "feat: clickable dashboard link in resubmission reminder" --body "$(cat <<'EOF'
## Summary
- New `dashboard_base_url` setting; when set, the Discord resubmission reminder includes it as a clickable link (Discord auto-embeds bare URLs). Empty by default, so local/dev behavior is unchanged.
- No auto-resubmission behavior change — confirmed during brainstorming that auto-resubmit was already fully decommissioned in #152/Phase 54; this PR only adds the missing link to the existing manual-trigger reminder.

See docs/superpowers/specs/2026-09-16-dashboard-fixes-and-auth-gate-design.md (Part 3).

## Test plan
- [x] `backend/tests/integration/test_discord_webhook.py` — link included/omitted based on param
- [x] `backend/tests/integration/test_resubmit_reminder_task.py` — task passes configured `dashboard_base_url` through
- [ ] Manual: set `DASHBOARD_BASE_URL` locally, trigger the reminder task, confirm the Discord message contains a clickable link

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Then `/review`, fix findings, manual verification (trigger the reminder task against a real or test webhook, confirm the link appears and is clickable), owner merge approval. **Stop here — do not start Task 3 until merged.**

---

### Task 3: Admin + application auth — backend

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/api/auth.py`
- Create: `backend/app/api/routers/auth.py`
- Modify: `backend/app/api/routers/admin.py` (dependencies list only)
- Modify: `backend/app/api/routers/tasks.py` (dependencies list only)
- Modify: `backend/app/api/routers/status.py` (dependencies list only)
- Modify: `backend/app/main.py` (CORS + router registration)
- Test: `backend/tests/unit/test_session_auth.py` (new)
- Test: `backend/tests/integration/test_auth_api.py` (new)

**Interfaces:**
- Consumes: nothing from Tasks 1-2.
- Produces: `create_session_token() -> str`, `verify_session_token(token: str) -> bool`, `require_session(session_token: str | None = Cookie(None)) -> None` in `app/api/auth.py` — consumed by Task 4 indirectly (frontend calls the endpoints this task exposes, not these functions directly).
- Produces: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/session` — consumed directly by Task 4's frontend code.

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull --ff-only
git checkout -b feat/admin-auth-backend
```

- [ ] **Step 2: Write the failing unit tests for token creation/verification**

Create `backend/tests/unit/test_session_auth.py`:

```python
import time

from app.api.auth import create_session_token, verify_session_token
from app.config import Settings
import app.config


def _with_secret(monkeypatch, secret="test-secret-key"):
    monkeypatch.setattr(app.config.settings, "session_secret_key", secret)


def test_create_and_verify_round_trip(monkeypatch):
    _with_secret(monkeypatch)
    token = create_session_token()
    assert verify_session_token(token) is True


def test_verify_rejects_tampered_signature(monkeypatch):
    _with_secret(monkeypatch)
    token = create_session_token()
    payload, _sig = token.split(".", 1)
    tampered = f"{payload}.deadbeef"
    assert verify_session_token(tampered) is False


def test_verify_rejects_malformed_token(monkeypatch):
    _with_secret(monkeypatch)
    assert verify_session_token("not-a-valid-token") is False


def test_verify_rejects_expired_token(monkeypatch):
    _with_secret(monkeypatch)
    monkeypatch.setattr("app.api.auth.SESSION_MAX_AGE_SECONDS", -1)
    token = create_session_token()
    assert verify_session_token(token) is False


def test_verify_rejects_token_signed_with_different_secret(monkeypatch):
    _with_secret(monkeypatch, secret="secret-a")
    token = create_session_token()
    _with_secret(monkeypatch, secret="secret-b")
    assert verify_session_token(token) is False
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/unit/test_session_auth.py -v`
Expected: FAIL — `create_session_token`/`verify_session_token` don't exist yet

- [ ] **Step 4: Add settings**

In `backend/app/config.py`, add after `api_keys: str = ""` (before the closing of the class):

```python
    admin_username: str = ""
    admin_password: str = ""
    session_secret_key: str = ""
    session_cookie_secure: bool = True
```

- [ ] **Step 5: Implement session token sign/verify + `require_session` in `app/api/auth.py`**

Replace the full contents of `backend/app/api/auth.py` with:

```python
import hashlib
import hmac
import time

from fastapi import Cookie, HTTPException, Security
from fastapi.security import APIKeyHeader

import app.config

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

SESSION_MAX_AGE_SECONDS = 12 * 60 * 60  # 12 hours


def _parse_keys() -> set[str]:
    return {k.strip() for k in app.config.settings.api_keys.split(",") if k.strip()}


async def require_api_key(key: str | None = Security(_api_key_header)) -> str | None:
    valid_keys = _parse_keys()
    if not valid_keys:
        return None
    if key is None or key not in valid_keys:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return key


def session_gate_configured() -> bool:
    settings = app.config.settings
    return bool(settings.admin_username and settings.admin_password and settings.session_secret_key)


def create_session_token() -> str:
    expiry = int(time.time()) + SESSION_MAX_AGE_SECONDS
    payload = str(expiry)
    signature = hmac.new(
        app.config.settings.session_secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_session_token(token: str) -> bool:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return False
    expected = hmac.new(
        app.config.settings.session_secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        expiry = int(payload)
    except ValueError:
        return False
    return time.time() < expiry


async def require_session(session_token: str | None = Cookie(None)) -> None:
    if not session_gate_configured():
        return None
    if session_token is None or not verify_session_token(session_token):
        raise HTTPException(status_code=401, detail="Login required")
```

Note: `SESSION_MAX_AGE_SECONDS` is read fresh at call time inside `create_session_token` (module-level name looked up at call time, not bound at import), so Step 2's `monkeypatch.setattr("app.api.auth.SESSION_MAX_AGE_SECONDS", -1)` works correctly for the expiry test.

- [ ] **Step 6: Run to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/unit/test_session_auth.py -v`
Expected: PASS

- [ ] **Step 7: Write the failing integration tests for the auth endpoints**

Create `backend/tests/integration/test_auth_api.py`:

```python
import os

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.config
from app.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(bind=engine)

    def override_get_db():
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    return TestClient(fastapi_app)


class TestAuthConfigured:
    def setup_method(self):
        os.environ["ADMIN_USERNAME"] = "owner"
        os.environ["ADMIN_PASSWORD"] = "correct-horse"
        os.environ["SESSION_SECRET_KEY"] = "test-signing-key"
        app.config.settings = Settings()
        self.client = _make_client()

    def teardown_method(self):
        fastapi_app.dependency_overrides.clear()
        for k in ("ADMIN_USERNAME", "ADMIN_PASSWORD", "SESSION_SECRET_KEY"):
            os.environ.pop(k, None)
        app.config.settings = Settings()

    def test_admin_route_returns_401_without_session(self):
        resp = self.client.get("/api/admin/config")
        assert resp.status_code == 401

    def test_status_route_returns_401_without_session(self):
        resp = self.client.get("/api/status-history")
        assert resp.status_code == 401

    def test_organizers_route_does_not_require_session(self):
        resp = self.client.get("/api/games")
        assert resp.status_code == 200

    def test_login_with_wrong_credentials_returns_401(self):
        resp = self.client.post("/api/auth/login", json={"username": "owner", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_then_protected_route_succeeds(self):
        login_resp = self.client.post(
            "/api/auth/login", json={"username": "owner", "password": "correct-horse"}
        )
        assert login_resp.status_code == 200
        assert login_resp.json() == {"authenticated": True}

        resp = self.client.get("/api/admin/config")
        assert resp.status_code == 200

    def test_session_endpoint_reports_authenticated_after_login(self):
        self.client.post("/api/auth/login", json={"username": "owner", "password": "correct-horse"})
        resp = self.client.get("/api/auth/session")
        assert resp.json() == {"authenticated": True}

    def test_session_endpoint_reports_unauthenticated_before_login(self):
        resp = self.client.get("/api/auth/session")
        assert resp.json() == {"authenticated": False}

    def test_logout_clears_session(self):
        self.client.post("/api/auth/login", json={"username": "owner", "password": "correct-horse"})
        logout_resp = self.client.post("/api/auth/logout")
        assert logout_resp.status_code == 200

        resp = self.client.get("/api/admin/config")
        assert resp.status_code == 401


class TestAuthNotConfigured:
    def setup_method(self):
        for k in ("ADMIN_USERNAME", "ADMIN_PASSWORD", "SESSION_SECRET_KEY"):
            os.environ.pop(k, None)
        app.config.settings = Settings()
        self.client = _make_client()

    def teardown_method(self):
        fastapi_app.dependency_overrides.clear()
        app.config.settings = Settings()

    def test_admin_route_accessible_without_login_when_gate_disabled(self):
        resp = self.client.get("/api/admin/config")
        assert resp.status_code == 200

    def test_session_endpoint_reports_authenticated_when_gate_disabled(self):
        resp = self.client.get("/api/auth/session")
        assert resp.json() == {"authenticated": True}
```

- [ ] **Step 8: Run to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/integration/test_auth_api.py -v`
Expected: FAIL — `/api/auth/*` routes don't exist (404), `require_session` not wired into `admin.py`/`status.py` yet

- [ ] **Step 9: Create the auth router**

Create `backend/app/api/routers/auth.py`:

```python
import hmac

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

from app.api.auth import (
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
    require_api_key,
    verify_session_token,
    session_gate_configured,
)
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(require_api_key)])


class LoginIn(BaseModel):
    username: str
    password: str


class SessionOut(BaseModel):
    authenticated: bool


def _credentials_valid(username: str, password: str) -> bool:
    if not settings.admin_username or not settings.admin_password:
        return False
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(
        password, settings.admin_password
    )


@router.post("/login", response_model=SessionOut)
def login(body: LoginIn, response: Response) -> SessionOut:
    if not _credentials_valid(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_session_token()
    response.set_cookie(
        "session_token",
        token,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        max_age=SESSION_MAX_AGE_SECONDS,
    )
    return SessionOut(authenticated=True)


@router.post("/logout", response_model=SessionOut)
def logout(response: Response) -> SessionOut:
    response.delete_cookie("session_token")
    return SessionOut(authenticated=False)


@router.get("/session", response_model=SessionOut)
def get_session(session_token: str | None = Cookie(None)) -> SessionOut:
    if not session_gate_configured():
        return SessionOut(authenticated=True)
    authenticated = session_token is not None and verify_session_token(session_token)
    return SessionOut(authenticated=authenticated)
```

- [ ] **Step 10: Wire `require_session` into the protected routers**

In `backend/app/api/routers/admin.py`, find the `router = APIRouter(...)` block (around line 27-30) and add the import + dependency:

```python
from app.api.auth import require_api_key, require_session
...
router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_api_key), Depends(require_session)],
)
```

Do the same in `backend/app/api/routers/tasks.py` (around line 17-20) and `backend/app/api/routers/status.py` (line 11) — same pattern, add `require_session` to the existing `require_api_key` import and to the router's `dependencies` list. **Do not touch `backend/app/api/routers/organizers.py`** — it stays `require_api_key`-only.

- [ ] **Step 11: Register the auth router and enable CORS credentials in `main.py`**

In `backend/app/main.py`:

```python
from app.api.routers import admin as admin_router
from app.api.routers import auth as auth_router
from app.api.routers import organizers as organizers_router
from app.api.routers import status as status_router
from app.api.routers import tasks as tasks_router
from app.config import settings


def parse_cors_origins(value: str) -> list[str]:
    """Parse a comma-separated list of origins, trimming surrounding whitespace."""
    return [origin.strip() for origin in value.split(",") if origin.strip()]


app = FastAPI(title="Limitless Organizer Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)
app.include_router(admin_router.router)
app.include_router(auth_router.router)
app.include_router(status_router.router)
app.include_router(organizers_router.router)
app.include_router(tasks_router.router)
```

(Only the `auth_router` import/include and the `allow_credentials=True` line are new — everything else in the file is unchanged.)

- [ ] **Step 12: Run to verify the new tests pass**

Run: `cd backend && .venv/bin/pytest tests/integration/test_auth_api.py -v`
Expected: PASS

- [ ] **Step 13: Run the FULL backend suite — this is the step that proves existing admin/tasks/status tests still pass unmodified**

Run: `cd backend && .venv/bin/pytest`
Expected: PASS, 0 regressions. If any pre-existing `test_admin_api.py`/`test_status_api.py`/`test_task_trigger_api.py` test fails with a 401, it means `session_gate_configured()` is returning `True` when it shouldn't — check that no test in the suite leaves `ADMIN_USERNAME`/`ADMIN_PASSWORD`/`SESSION_SECRET_KEY` set in the environment (this is why `TestAuthConfigured`/`TestAuthNotConfigured` above scrupulously `pop` them in `teardown_method`).

- [ ] **Step 14: Commit**

```bash
git add backend/app/config.py backend/app/api/auth.py backend/app/api/routers/auth.py \
  backend/app/api/routers/admin.py backend/app/api/routers/tasks.py backend/app/api/routers/status.py \
  backend/app/main.py backend/tests/unit/test_session_auth.py backend/tests/integration/test_auth_api.py
git commit -m "$(cat <<'EOF'
feat(backend): session-cookie auth gate for admin and application routers

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 15: Push and open the PR**

```bash
git push -u origin feat/admin-auth-backend
gh pr create --title "feat: session-cookie auth gate for admin + application routers (backend)" --body "$(cat <<'EOF'
## Summary
- New `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/session`. Session is a signed, HttpOnly cookie using stdlib hmac (no new dependency) — appropriate for a single shared credential with no per-user claims.
- `require_session` added alongside the existing `require_api_key` on the `admin`, `tasks`, and `status` routers (My Application + Admin tabs). `organizers` (reporting/Organizers tab) is unchanged — stays publicly viewable per the 2026-07-19 single-tenant pivot decision.
- The gate is a no-op (routes stay open) when `ADMIN_USERNAME`/`ADMIN_PASSWORD`/`SESSION_SECRET_KEY` aren't all set — mirrors the existing `require_api_key` pattern, so no existing test needed to change.
- Part 1 of closing #157. Frontend login UI is Task 4 — this PR is backend-only and doesn't change any user-visible behavior in an unconfigured (local/dev) environment.

See docs/superpowers/specs/2026-09-16-dashboard-fixes-and-auth-gate-design.md (Part 4).

## Test plan
- [x] `backend/tests/unit/test_session_auth.py` — token sign/verify/expiry/tamper
- [x] `backend/tests/integration/test_auth_api.py` — login/logout/session, gate-configured vs gate-disabled
- [x] Full backend suite — 0 regressions in pre-existing admin/tasks/status tests
- [ ] Manual: `curl` login with correct/incorrect credentials, confirm cookie is set, confirm `/api/admin/config` returns 401 without it and 200 with it

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Then `/review`, fix findings. **This PR touches auth/RBAC-adjacent code — run `/security-review` per `~/.claude/CLAUDE.md`'s Security section before merge**, in addition to the regular review. Manual verification, owner merge approval. **Stop here — do not start Task 4 until merged.**

---

### Task 4: Admin + application auth — frontend

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/lib/useAuthSession.ts`
- Create: `frontend/src/components/LoginForm.tsx`
- Test: `frontend/src/components/LoginForm.test.tsx` (new)
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/test/handlers.ts` (add `/api/auth/*` handlers)
- Test: `frontend/src/pages/Dashboard.test.tsx`

**Interfaces:**
- Consumes: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/session` from Task 3.
- Produces: `useAuthSession()` hook returning a React Query result over `{authenticated: boolean}`, consumed by `Dashboard.tsx`.

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull --ff-only
git checkout -b feat/admin-auth-frontend
```

- [ ] **Step 2: Add default MSW handlers for the auth endpoints — authenticated by default**

In `frontend/src/test/handlers.ts`, add to the `handlers` array (this default keeps every existing Dashboard/admin/application-tab test passing unchanged, matching how the backend gate defaults to open):

```ts
  http.get("*/api/auth/session", () => HttpResponse.json({ authenticated: true })),
  http.post("*/api/auth/login", () => HttpResponse.json({ authenticated: true })),
  http.post("*/api/auth/logout", () => HttpResponse.json({ authenticated: false })),
```

- [ ] **Step 3: Add `credentials: "include"` to the API client's fetch calls + auth functions**

In `frontend/src/api/client.ts`:

1. In `getJson`, `postJson`, `putJson`, add `credentials: "include"` to each `fetch(...)` call's options object (alongside the existing `headers`).
2. Add a new helper and the three auth functions, near the bottom of the file:

```ts
async function postJsonBody<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed with status ${response.status}`, response.status);
  }
  return (await response.json()) as T;
}

export interface SessionStatus {
  authenticated: boolean;
}

export function getSession(): Promise<SessionStatus> {
  return getJson<SessionStatus>("/api/auth/session");
}

export function login(username: string, password: string): Promise<SessionStatus> {
  return postJsonBody<SessionStatus>("/api/auth/login", { username, password });
}

export function logout(): Promise<SessionStatus> {
  return postJson<SessionStatus>("/api/auth/logout");
}
```

- [ ] **Step 4: Write the failing hook + LoginForm tests**

Create `frontend/src/components/LoginForm.test.tsx`:

```tsx
import { fireEvent, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import { server } from "../test/server";
import { LoginForm } from "./LoginForm";

describe("LoginForm", () => {
  it("renders username and password fields and a submit button", () => {
    renderWithQueryClient(<LoginForm />);

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log in/i })).toBeInTheDocument();
  });

  it("shows an error message on invalid credentials", async () => {
    server.use(
      http.post("*/api/auth/login", () =>
        HttpResponse.json({ detail: "Invalid username or password" }, { status: 401 }),
      ),
    );

    renderWithQueryClient(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "owner" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    expect(await screen.findByText(/invalid username or password/i)).toBeInTheDocument();
  });

  it("calls onSuccess after a successful login", async () => {
    let called = false;
    renderWithQueryClient(<LoginForm onSuccess={() => (called = true)} />);

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "owner" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "correct-horse" } });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    await screen.findByRole("button", { name: /log in/i }); // wait a tick for the async submit
    expect(called).toBe(true);
  });
});
```

- [ ] **Step 5: Run to verify it fails**

Run: `cd frontend && npm test -- --run LoginForm`
Expected: FAIL — `LoginForm` module doesn't exist

- [ ] **Step 6: Implement `useAuthSession`**

Create `frontend/src/lib/useAuthSession.ts`:

```ts
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSession, logout as logoutRequest } from "../api/client";

export function useAuthSession() {
  return useQuery({ queryKey: ["auth-session"], queryFn: getSession });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return async () => {
    await logoutRequest();
    await queryClient.invalidateQueries({ queryKey: ["auth-session"] });
  };
}
```

- [ ] **Step 7: Implement `LoginForm`**

Create `frontend/src/components/LoginForm.tsx`:

```tsx
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, login } from "../api/client";

interface LoginFormProps {
  onSuccess?: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const queryClient = useQueryClient();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      await queryClient.invalidateQueries({ queryKey: ["auth-session"] });
      onSuccess?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex max-w-xs flex-col gap-2">
      <div className="form-control">
        <label htmlFor="login-username" className="label">
          <span className="label-text">Username</span>
        </label>
        <input
          id="login-username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="input input-bordered input-sm"
        />
      </div>
      <div className="form-control">
        <label htmlFor="login-password" className="label">
          <span className="label-text">Password</span>
        </label>
        <input
          id="login-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input input-bordered input-sm"
        />
      </div>
      {error && <p className="text-error text-sm">{error}</p>}
      <button type="submit" className="btn btn-primary btn-sm" disabled={submitting}>
        Log in
      </button>
    </form>
  );
}
```

Note: `ApiError`'s `.message` is `Request to /api/auth/login failed with status 401` by default (see `getJson`'s error construction) — **not** the backend's `detail` text. To surface `"Invalid username or password"` as asserted in Step 4's test, `postJsonBody` (Step 3) needs the same error-detail parsing `putJson` already does. Update `postJsonBody` from Step 3 to match `putJson`'s error handling:

```ts
async function postJsonBody<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = `Request to ${path} failed with status ${response.status}`;
    try {
      const err = (await response.json()) as { detail?: string | unknown[] };
      if (typeof err.detail === "string") {
        detail = err.detail;
      } else if (Array.isArray(err.detail) && err.detail.length > 0) {
        const first = err.detail[0] as { msg?: string };
        if (first.msg) detail = first.msg;
      }
    } catch {
      // response body not JSON — keep generic message
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}
```

- [ ] **Step 8: Run to verify it passes**

Run: `cd frontend && npm test -- --run LoginForm`
Expected: PASS

- [ ] **Step 9: Write the failing Dashboard tests for the unauthenticated case**

Add to `frontend/src/pages/Dashboard.test.tsx`:

```tsx
import { HttpResponse, http } from "msw";
import { server } from "../test/server";

describe("Dashboard auth gate", () => {
  it("shows a login form on the application tab when unauthenticated", async () => {
    server.use(http.get("*/api/auth/session", () => HttpResponse.json({ authenticated: false })));

    renderWithQueryClient(<Dashboard />);

    expect(await screen.findByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /application overview/i })).not.toBeInTheDocument();
  });

  it("shows a login form on the admin tab when unauthenticated", async () => {
    server.use(http.get("*/api/auth/session", () => HttpResponse.json({ authenticated: false })));

    renderWithQueryClient(<Dashboard />);
    fireEvent.click(screen.getByRole("tab", { name: /admin/i }));

    expect(await screen.findByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /system diagnostics/i })).not.toBeInTheDocument();
  });

  it("does not show a login form on the organizers tab when unauthenticated", async () => {
    server.use(http.get("*/api/auth/session", () => HttpResponse.json({ authenticated: false })));

    renderWithQueryClient(<Dashboard />);
    fireEvent.click(screen.getByRole("tab", { name: /organizers/i }));

    expect(screen.queryByLabelText(/username/i)).not.toBeInTheDocument();
    expect(await screen.findByText("Jun 1: 2")).toBeInTheDocument();
  });
});
```

(Add this as a second `describe` block in the same file, after the existing one — keep the existing `import` lines at the top and add `HttpResponse, http` and `server` to them rather than re-importing.)

- [ ] **Step 10: Run to verify it fails**

Run: `cd frontend && npm test -- --run Dashboard`
Expected: FAIL — application/admin tabs render their real content regardless of auth state today

- [ ] **Step 11: Wire the gate into `Dashboard.tsx`**

Read the full current file first (`frontend/src/pages/Dashboard.tsx`) to get exact context, then:

1. Add imports: `import { useAuthSession, useLogout } from "../lib/useAuthSession";` and `import { LoginForm } from "../components/LoginForm";`
2. Inside the `Dashboard` component function, add: `const authQuery = useAuthSession(); const logout = useLogout();`
3. Wrap the existing `{activeTab === "application" && ( ... )}` block's inner content: if `authQuery.data?.authenticated` is falsy, render `<LoginForm onSuccess={() => authQuery.refetch()} />` instead of the existing content. Same for the `{activeTab === "admin" && ( ... )}` block. The `{activeTab === "organizers" && ( ... )}` block is untouched.
4. Add a small logout control, shown only when authenticated, e.g. next to `<TabNavigation ... />`:

```tsx
        {authQuery.data?.authenticated && (
          <button type="button" onClick={() => logout()} className="btn btn-ghost btn-sm">
            Log out
          </button>
        )}
```

Exact placement/JSX structure depends on the current file layout — preserve all existing content and structure for the `organizers` tab and for the authenticated branches of `application`/`admin`; only add the conditional wrapping and the logout control.

- [ ] **Step 12: Run to verify it passes**

Run: `cd frontend && npm test -- --run Dashboard`
Expected: PASS

- [ ] **Step 13: Run the full frontend suite**

Run: `cd frontend && npm test -- --run`
Expected: PASS, 0 regressions (the default `authenticated: true` MSW handler from Step 2 is what keeps every pre-existing Dashboard/admin/application test passing without modification)

- [ ] **Step 14: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/lib/useAuthSession.ts frontend/src/components/LoginForm.tsx \
  frontend/src/components/LoginForm.test.tsx frontend/src/pages/Dashboard.tsx frontend/src/pages/Dashboard.test.tsx \
  frontend/src/test/handlers.ts
git commit -m "$(cat <<'EOF'
feat(frontend): login form gates admin and application tabs

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 15: Push and open the PR**

```bash
git push -u origin feat/admin-auth-frontend
gh pr create --title "feat: session-cookie auth gate for admin + application tabs (frontend)" --body "$(cat <<'EOF'
## Summary
- New `LoginForm` + `useAuthSession`/`useLogout` hook, backed by `/api/auth/*` (Task 3, already merged).
- Dashboard's My Application and Admin tabs render a login form instead of their content when unauthenticated; Organizers tab is unchanged and stays public.
- Closes #157.

See docs/superpowers/specs/2026-09-16-dashboard-fixes-and-auth-gate-design.md (Part 4).

## Test plan
- [x] `frontend/src/components/LoginForm.test.tsx` — renders, error on bad credentials, success callback
- [x] `frontend/src/pages/Dashboard.test.tsx` — login form shown/hidden per tab based on auth state
- [x] Full frontend suite — 0 regressions
- [ ] Manual: with `ADMIN_USERNAME`/`ADMIN_PASSWORD`/`SESSION_SECRET_KEY` set on the backend, load the dashboard, confirm My Application + Admin show a login form, Organizers doesn't, log in, confirm both unlock and "Log out" works

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Then `/review` (and `/security-review` again if the reviewer flags anything credential/session-related beyond what Task 3's security review already covered), manual verification (the actual browser walk-through — load the app, confirm the login wall on the two gated tabs, log in, confirm access, log out, confirm re-gated), owner merge approval.

---

## Requirements Traceability Follow-Up

After Task 4 merges, add entries to `docs/requirements.md`:
- Extend FR12/FR13's "Done" note to mention the `days` param (Task 1).
- Extend FR4's "Done" note to mention the reminder link (Task 2).
- New FR (next available number) for the admin/application password gate, serving BR1/BR2, closing #157 (Tasks 3-4).
- A new Build Order row/phase number for this work, per `~/.claude/CLAUDE.md`'s "confirm work traces to requirements-doc entry" rule — this can be its own small follow-up PR or folded into Task 4's PR at the implementer's discretion, since it's docs-only and low-LOE.
