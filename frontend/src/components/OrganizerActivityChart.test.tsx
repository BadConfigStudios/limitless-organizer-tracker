import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import { OrganizerActivityChart } from "./OrganizerActivityChart";

describe("OrganizerActivityChart", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-06-25T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a loading state before activity data loads", () => {
    renderWithQueryClient(<OrganizerActivityChart />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders activity buckets and a game filter populated from /api/games", async () => {
    renderWithQueryClient(<OrganizerActivityChart />);

    expect(await screen.findByText("Jun 1: 2")).toBeInTheDocument();
    expect(screen.getByText("Jun 8: 1")).toBeInTheDocument();

    const select = screen.getByLabelText(/game/i);
    expect(select).toHaveDisplayValue("All");
    expect(await screen.findByRole("option", { name: "PTCG" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "POCKET" })).toBeInTheDocument();
  });

  it("refetches activity filtered by the selected game", async () => {
    renderWithQueryClient(<OrganizerActivityChart />);

    const select = await screen.findByLabelText(/game/i);
    await screen.findByRole("option", { name: "PTCG" });
    fireEvent.change(select, { target: { value: "PTCG" } });

    await waitFor(() => {
      expect(screen.getByText("Jun 1: 1")).toBeInTheDocument();
    });
    expect(screen.queryByText("Jun 8: 1")).not.toBeInTheDocument();
  });

  it("renders a date window selector defaulting to Last 90 days", async () => {
    renderWithQueryClient(<OrganizerActivityChart />);

    await screen.findByText("Jun 1: 2");

    const dateSelect = screen.getByLabelText(/date range/i);
    expect(dateSelect).toHaveDisplayValue("Last 90 days");
  });

  it("filters activity to last 30 days when selected", async () => {
    renderWithQueryClient(<OrganizerActivityChart />);

    await screen.findByText("Jun 1: 2");

    const dateSelect = screen.getByLabelText(/date range/i);
    fireEvent.change(dateSelect, { target: { value: "30" } });

    await waitFor(() => {
      expect(screen.getByText("Jun 1: 2")).toBeInTheDocument();
      expect(screen.getByText("Jun 8: 1")).toBeInTheDocument();
    });
    expect(screen.queryByText("Dec 1: 3")).not.toBeInTheDocument();
    expect(screen.queryByText("Jan 5: 4")).not.toBeInTheDocument();
    expect(screen.queryByText("Mar 1: 2")).not.toBeInTheDocument();
  });

  it("filters activity to last 90 days when selected", async () => {
    renderWithQueryClient(<OrganizerActivityChart />);

    await screen.findByText("Jun 1: 2");

    const dateSelect = screen.getByLabelText(/date range/i);
    fireEvent.change(dateSelect, { target: { value: "90" } });

    await waitFor(() => {
      expect(screen.getByText("Jun 1: 2")).toBeInTheDocument();
      expect(screen.getByText("Jun 8: 1")).toBeInTheDocument();
    });
    // Mar 1 is ~116 days before Jun 25, outside the 90-day window
    expect(screen.queryByText("Mar 1: 2")).not.toBeInTheDocument();
    expect(screen.queryByText("Dec 1: 3")).not.toBeInTheDocument();
    expect(screen.queryByText("Jan 5: 4")).not.toBeInTheDocument();
  });

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

  it("shows a contextual empty message when date filter removes all data", async () => {
    renderWithQueryClient(<OrganizerActivityChart />);

    await screen.findByText("Jun 1: 2");

    // Move system time far enough ahead that all mock data is older than 30 days
    vi.setSystemTime(new Date("2027-01-01T12:00:00Z"));
    const dateSelect = screen.getByLabelText(/date range/i);
    fireEvent.change(dateSelect, { target: { value: "30" } });

    await waitFor(() => {
      expect(screen.getByText("No activity in the selected date range")).toBeInTheDocument();
    });
    expect(screen.queryByText("No organizer activity yet")).not.toBeInTheDocument();
  });

  it("renders onboarding overlay data in the accessible list", async () => {
    renderWithQueryClient(<OrganizerActivityChart />);

    await screen.findByText("Jun 1: 2");

    // Onboarding data from MSW handler should show as "onboarded: N" in the sr-only list
    expect(await screen.findByText(/onboarded: 2/i)).toBeInTheDocument();
    expect(screen.getByText(/onboarded: 1/i)).toBeInTheDocument();
  });
});
