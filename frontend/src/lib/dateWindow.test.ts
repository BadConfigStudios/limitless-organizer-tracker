import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { dateWindowToDays, filterByDateWindow } from "./dateWindow";

describe("dateWindowToDays", () => {
  it("returns undefined for the empty (All time) window", () => {
    expect(dateWindowToDays("")).toBeUndefined();
  });

  it("returns a number for 30/90/180", () => {
    expect(dateWindowToDays("30")).toBe(30);
    expect(dateWindowToDays("90")).toBe(90);
    expect(dateWindowToDays("180")).toBe(180);
  });
});

describe("filterByDateWindow", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-06-25T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const items = [
    { date: "2025-10-01", value: "old" },
    { date: "2026-01-15", value: "mid" },
    { date: "2026-04-01", value: "recent-ish" },
    { date: "2026-06-10", value: "recent" },
    { date: "2026-06-20", value: "very-recent" },
  ];

  it("returns all items when window is empty (All time)", () => {
    const result = filterByDateWindow(items, (i) => i.date, "");
    expect(result).toEqual(items);
  });

  it("filters to last 30 days", () => {
    const result = filterByDateWindow(items, (i) => i.date, "30");
    expect(result.map((i) => i.value)).toEqual(["recent", "very-recent"]);
  });

  it("filters to last 90 days", () => {
    const result = filterByDateWindow(items, (i) => i.date, "90");
    expect(result.map((i) => i.value)).toEqual(["recent-ish", "recent", "very-recent"]);
  });

  it("filters to last 180 days", () => {
    const result = filterByDateWindow(items, (i) => i.date, "180");
    expect(result.map((i) => i.value)).toEqual(["mid", "recent-ish", "recent", "very-recent"]);
  });

  it("returns empty array when no items match the window", () => {
    const oldItems = [{ date: "2020-01-01", value: "ancient" }];
    const result = filterByDateWindow(oldItems, (i) => i.date, "30");
    expect(result).toEqual([]);
  });
});
