import { fireEvent, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import { server } from "../test/server";
import { WaitTimeEstimator } from "./WaitTimeEstimator";

describe("WaitTimeEstimator", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-06-25T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders an organizer ID input and a submit button on load", () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    expect(screen.getByLabelText(/organizer id/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /estimate/i })).toBeInTheDocument();
  });

  it("does not render a game selector", () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    expect(screen.queryByLabelText(/game/i)).not.toBeInTheDocument();
  });

  it("renders the scatter chart on load without requiring organizer ID input", async () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    fireEvent.change(screen.getByLabelText(/date range/i), { target: { value: "" } });

    // slope and R² are rendered without user submitting a form
    expect(await screen.findByText(/0\.5000/)).toBeInTheDocument();
    expect(screen.getByText(/0\.950/)).toBeInTheDocument();
    expect(screen.getByText(/frontier/i)).toBeInTheDocument();
  });

  it("does not show projected active date until an organizer ID is submitted", async () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    fireEvent.change(screen.getByLabelText(/date range/i), { target: { value: "" } });

    // Wait for initial chart to render
    await screen.findByText(/0\.5000/);
    expect(screen.queryByText(/projected active date/i)).not.toBeInTheDocument();
  });

  it("clears the projected date when the input is cleared and re-submitted", async () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    fireEvent.change(screen.getByLabelText(/date range/i), { target: { value: "" } });
    await screen.findByText(/0\.5000/);

    // Submit an organizer ID to show the projection
    fireEvent.change(screen.getByLabelText(/organizer id/i), { target: { value: "400" } });
    fireEvent.click(screen.getByRole("button", { name: /estimate/i }));
    expect(await screen.findByText(/projected active date/i)).toBeInTheDocument();

    // Clear the input and re-submit — projection should disappear
    fireEvent.change(screen.getByLabelText(/organizer id/i), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /estimate/i }));
    expect(await screen.findByText(/0\.5000/)).toBeInTheDocument();
    expect(screen.queryByText(/projected active date/i)).not.toBeInTheDocument();
  });

  it("shows projected active date after submitting an organizer ID", async () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    fireEvent.change(screen.getByLabelText(/date range/i), { target: { value: "" } });
    await screen.findByText(/0\.5000/);

    fireEvent.change(screen.getByLabelText(/organizer id/i), { target: { value: "400" } });
    fireEvent.click(screen.getByRole("button", { name: /estimate/i }));

    expect(await screen.findByText(/projected active date/i)).toBeInTheDocument();
    expect(screen.getByText("2026-04-01")).toBeInTheDocument();
  });

  it("shows the frontier size stat on load", async () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    fireEvent.change(screen.getByLabelText(/date range/i), { target: { value: "" } });

    expect(await screen.findByText(/frontier organizers/i)).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows a message when there isn't enough data to estimate", async () => {
    server.use(
      http.get("*/api/organizers/wait-estimate", () =>
        HttpResponse.json({ detail: "not enough activity data to estimate" }, { status: 404 }),
      ),
    );

    renderWithQueryClient(<WaitTimeEstimator />);

    expect(await screen.findByText(/not enough data/i)).toBeInTheDocument();
  });

  it("shows a generic failure message for a non-404 error", async () => {
    server.use(
      http.get("*/api/organizers/wait-estimate", () =>
        HttpResponse.json({ detail: "internal error" }, { status: 500 }),
      ),
    );

    renderWithQueryClient(<WaitTimeEstimator />);

    expect(await screen.findByText(/failed to load/i)).toBeInTheDocument();
    expect(screen.queryByText(/not enough data/i)).not.toBeInTheDocument();
  });

  it("renders a date window selector defaulting to Last 90 days", async () => {
    renderWithQueryClient(<WaitTimeEstimator />);

    await screen.findByText(/0\.2000/);
    const dateSelect = screen.getByLabelText(/date range/i);
    expect(dateSelect).toHaveDisplayValue("Last 90 days");
  });

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
});
