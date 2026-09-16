import { http, HttpResponse } from "msw";

export const statusHistoryPage = {
  items: [
    {
      id: 3,
      checked_at: "2026-06-12T12:00:00Z",
      status: "rejected",
      raw_text: "check 3",
      review_note: "Your application was rejected. Please join the Discord.",
    },
    { id: 2, checked_at: "2026-06-12T10:00:00Z", status: "pending", raw_text: "check 2", review_note: null },
    { id: 1, checked_at: "2026-06-12T06:00:00Z", status: "approved", raw_text: "check 1", review_note: null },
  ],
  total: 3,
  limit: 50,
  offset: 0,
};

export const resubmissionsPage = {
  items: [
    { id: 2, submitted_at: "2026-06-12T09:00:00Z", success: true, discord_notified: true },
    { id: 1, submitted_at: "2026-06-12T08:00:00Z", success: false, discord_notified: false },
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

export const games = ["POCKET", "PTCG"];

export const organizerActivityByWeek = [
  { period: "2025-12-01", count: 3 },
  { period: "2026-01-05", count: 4 },
  { period: "2026-03-01", count: 2 },
  { period: "2026-06-01", count: 2 },
  { period: "2026-06-08", count: 1 },
];

export const organizerActivityForPTCG = [{ period: "2026-06-01", count: 1 }];

export const waitEstimate = {
  organizer_id: 400,
  slope: 0.5,
  r_squared: 0.95,
  projected_active_date: "2026-04-01",
  sample_size: 5,
  frontier_size: 3,
  total_points: 5,
  fitted_line: [
    { organizer_id: 100, projected_date: "2026-01-01" },
    { organizer_id: 400, projected_date: "2026-04-01" },
  ],
  points: [
    { organizer_id: 100, first_tournament_date: "2025-10-01", is_frontier: true },
    { organizer_id: 200, first_tournament_date: "2026-02-01", is_frontier: false },
    { organizer_id: 300, first_tournament_date: "2026-03-03", is_frontier: true },
    { organizer_id: 350, first_tournament_date: "2026-06-10", is_frontier: false },
    { organizer_id: 380, first_tournament_date: "2026-06-20", is_frontier: true },
  ],
};

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

export const organizerProfile = {
  organizer_id: 42,
  name: "Test Organizer",
  upcoming_tournaments: [
    { tournament_id: "t1", name: "Upcoming Cup", date: "2026-07-01", game: "POCKET", players: 0 },
  ],
  recent_tournaments: [
    { tournament_id: "t2", name: "Recent League", date: "2026-06-01", game: "PTCG", players: 16 },
    { tournament_id: "t3", name: "Spring Open", date: "2026-05-15", game: "POCKET", players: 32 },
  ],
  onboarded_at: "2026-05-01",
  first_tournament_date: "2026-05-15",
};

export const recentlyOnboarded = [
  {
    organizer_id: 2720,
    onboarded_at: "2026-06-20",
    detected_at: "2026-06-20T14:30:00Z",
    first_tournament_date: null,
  },
  {
    organizer_id: 2719,
    onboarded_at: "2026-06-19",
    detected_at: "2026-06-19T14:30:00Z",
    first_tournament_date: "2026-06-25",
  },
  {
    organizer_id: 2718,
    onboarded_at: "2026-06-18",
    detected_at: "2026-06-18T14:30:00Z",
    first_tournament_date: null,
  },
];

export const highestOrganizerId = { organizer_id: 2720 };

export const onboardingDelta = {
  avg_days: 13.3,
  median_days: 10.0,
  count: 3,
};

export const onboardingHistoryByWeek = [
  { period: "2026-06-01", count: 2 },
  { period: "2026-06-08", count: 1 },
];

export const adminEventLog = {
  items: [
    {
      id: 3,
      timestamp: "2026-06-22T12:00:00Z",
      event_type: "task.completed",
      severity: "info",
      source: "celery",
      message: "ingest_tournaments completed",
      details: { duration_ms: 1234 },
      correlation_id: "abc-123",
    },
    {
      id: 2,
      timestamp: "2026-06-22T11:00:00Z",
      event_type: "task.started",
      severity: "info",
      source: "celery",
      message: "ingest_tournaments started",
      details: null,
      correlation_id: "abc-123",
    },
    {
      id: 1,
      timestamp: "2026-06-22T10:00:00Z",
      event_type: "scraper.error",
      severity: "error",
      source: "resubmit",
      message: "Resubmit button not found",
      details: { url: "/organizer/settings" },
      correlation_id: null,
    },
  ],
  total: 3,
  limit: 50,
  offset: 0,
};

export const adminDiagnostics = {
  db_ok: true,
  redis_ok: true,
  celery_workers: ["celery@worker1"],
  beat_ok: true,
  last_success_per_task: {
    ingest_tournaments: "2026-06-22T11:30:00Z",
    scan_new_organizers: "2026-06-22T10:00:00Z",
  },
};

export const adminConfig = {
  application_status_check_interval_hours: 4,
  resubmit_times_utc: "09:00,21:00",
  tournament_ingest_interval_hours: 6,
  tournament_ingest_limit: 200,
  tournament_backfill_months: 3,
  organizer_scan_interval_hours: 24,
  organizer_scan_limit: 100,
  organizer_scan_start_id: 1,
  display_timezone: "America/Chicago",
};

export const adminTasks = [
  {
    name: "ingest_tournaments",
    endpoint: "/api/tasks/ingest-tournaments",
    method: "POST",
    description: "Fetch recent tournaments from Limitless API",
    component: "Tournaments",
  },
  {
    name: "scan_organizers",
    endpoint: "/api/tasks/scan-organizers",
    method: "POST",
    description: "Scan for newly onboarded organizers",
    component: "Organizers",
  },
];

export const handlers = [
  http.get("*/api/status-history", ({ request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit") ?? 50);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const sliced = statusHistoryPage.items.slice(offset, offset + limit);
    return HttpResponse.json({
      items: sliced,
      total: statusHistoryPage.items.length,
      limit,
      offset,
    });
  }),
  http.get("*/api/resubmissions", () => HttpResponse.json(resubmissionsPage)),
  http.get("*/api/games", () => HttpResponse.json(games)),
  http.get("*/api/organizers/activity", ({ request }) => {
    const game = new URL(request.url).searchParams.get("game");
    return HttpResponse.json(game === "PTCG" ? organizerActivityForPTCG : organizerActivityByWeek);
  }),
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
  http.get("*/api/organizers/onboarding-delta", () => HttpResponse.json(onboardingDelta)),
  http.get("*/api/organizers/onboarding-history", () => HttpResponse.json(onboardingHistoryByWeek)),
  http.get("*/api/organizers/recently-onboarded", ({ request }) => {
    const limit = Number(new URL(request.url).searchParams.get("limit") ?? 10);
    return HttpResponse.json(recentlyOnboarded.slice(0, limit));
  }),
  http.get("*/api/organizers/highest-id", () => HttpResponse.json(highestOrganizerId)),
  http.get("*/api/organizers/:organizerId/scrape", ({ params }) => {
    const id = Number(params.organizerId);
    if (id === 9999) {
      return HttpResponse.json({ detail: "organizer not found on Limitless" }, { status: 404 });
    }
    return HttpResponse.json({ ...organizerProfile, organizer_id: id });
  }),
  http.get("*/api/admin/event-log", () => HttpResponse.json(adminEventLog)),
  http.get("*/api/admin/diagnostics", () => HttpResponse.json(adminDiagnostics)),
  http.get("*/api/admin/config", () => HttpResponse.json(adminConfig)),
  http.put("*/api/admin/config", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const coerced: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(body)) {
      const original = adminConfig[key as keyof typeof adminConfig];
      if (typeof original === "number" && typeof value === "string") {
        coerced[key] = Number(value);
      } else {
        coerced[key] = value;
      }
    }
    return HttpResponse.json({ ...adminConfig, ...coerced });
  }),
  http.get("*/api/admin/tasks", () => HttpResponse.json(adminTasks)),
  http.post("*/api/tasks/*", () => HttpResponse.json({ status: "triggered" })),
  http.get("*/api/auth/session", () => HttpResponse.json({ authenticated: true })),
  http.post("*/api/auth/login", () => HttpResponse.json({ authenticated: true })),
  http.post("*/api/auth/logout", () => HttpResponse.json({ authenticated: false })),
];
