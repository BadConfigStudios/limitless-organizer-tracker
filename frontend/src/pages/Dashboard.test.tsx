import { fireEvent, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import { server } from "../test/server";
import { Dashboard } from "./Dashboard";

describe("Dashboard", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-06-25T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the tab navigation with three tabs", () => {
    renderWithQueryClient(<Dashboard />);

    expect(screen.getByRole("tab", { name: /my application/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /organizers/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /admin/i })).toBeInTheDocument();
  });

  it("uses a wide page layout", () => {
    const { container } = renderWithQueryClient(<Dashboard />);
    const main = container.querySelector("main");
    expect(main?.className).toMatch(/max-w-6xl/);
  });

  it("shows the application tab by default with stat cards, status history, resubmit action, and resubmission log", async () => {
    renderWithQueryClient(<Dashboard />);

    // The session check settles asynchronously (loading → authenticated), so the gated content
    // isn't present on the very first render.
    expect(await screen.findByRole("heading", { name: /application overview/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /status history/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /resubmit application/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /resubmit now/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /resubmission log/i })).toBeInTheDocument();

    expect(await screen.findByText("Pending")).toBeInTheDocument();
    expect(await screen.findAllByText("Success")).toHaveLength(1);
  });

  it("switches to organizers tab and shows growth + lookup sections", async () => {
    renderWithQueryClient(<Dashboard />);

    fireEvent.click(screen.getByRole("tab", { name: /organizers/i }));

    expect(screen.getByRole("heading", { name: /organizer activity/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /recently onboarded/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /wait time estimator/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /scanner status/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /organizer profile/i })).toBeInTheDocument();

    expect(await screen.findByText("Jun 1: 2")).toBeInTheDocument();
    expect((await screen.findAllByText("2720")).length).toBeGreaterThan(0);
  });

  it("switches to admin tab and shows diagnostics, task triggers, config, and event log", async () => {
    renderWithQueryClient(<Dashboard />);

    fireEvent.click(screen.getByRole("tab", { name: /admin/i }));

    // Same async session-check settling as above.
    expect(await screen.findByRole("heading", { name: /system diagnostics/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /task triggers/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /configuration/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /event log/i })).toBeInTheDocument();

    expect(await screen.findByText("Database")).toBeInTheDocument();
    expect(await screen.findByText("ingest_tournaments completed")).toBeInTheDocument();
  });

  it("hides other tabs' content when switching", async () => {
    renderWithQueryClient(<Dashboard />);

    await screen.findByText("Pending");

    fireEvent.click(screen.getByRole("tab", { name: /organizers/i }));

    expect(screen.queryByRole("heading", { name: /status history/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /resubmit application/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /resubmission log/i })).not.toBeInTheDocument();
  });
});

describe("Dashboard auth gate", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-06-25T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

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

  it("shows a neutral loading state on the application tab while the session check is pending", () => {
    renderWithQueryClient(<Dashboard />);

    // Asserted synchronously, before the session check settles: neither the gated content nor
    // the login form should render yet.
    expect(screen.getByText(/checking session/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /application overview/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/username/i)).not.toBeInTheDocument();
  });

  it("falls back to the login form on the application tab when the session check errors", async () => {
    server.use(http.get("*/api/auth/session", () => HttpResponse.json({ detail: "boom" }, { status: 500 })));

    renderWithQueryClient(<Dashboard />);

    expect(await screen.findByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /application overview/i })).not.toBeInTheDocument();
  });

  it("falls back to the login form on the admin tab when the session check errors", async () => {
    server.use(http.get("*/api/auth/session", () => HttpResponse.json({ detail: "boom" }, { status: 500 })));

    renderWithQueryClient(<Dashboard />);
    fireEvent.click(screen.getByRole("tab", { name: /admin/i }));

    expect(await screen.findByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /system diagnostics/i })).not.toBeInTheDocument();
  });

  it("shows a Log out button when authenticated and re-gates the application tab on click", async () => {
    let authenticated = true;
    server.use(
      http.get("*/api/auth/session", () => HttpResponse.json({ authenticated })),
      http.post("*/api/auth/logout", () => {
        authenticated = false;
        return HttpResponse.json({ authenticated: false });
      }),
    );

    renderWithQueryClient(<Dashboard />);

    const logoutButton = await screen.findByRole("button", { name: /log out/i });
    fireEvent.click(logoutButton);

    expect(await screen.findByLabelText(/username/i)).toBeInTheDocument();
  });
});
