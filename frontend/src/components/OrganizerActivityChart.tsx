import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getGames, getOnboardingHistory, getOrganizerActivity } from "../api/client";
import { mergeOnboardingOverlay, toActivityChartData } from "../lib/activityChartData";
import { filterByDateWindow, type DateWindow } from "../lib/dateWindow";
import { DateWindowSelect } from "./DateWindowSelect";

export function OrganizerActivityChart() {
  const [game, setGame] = useState<string | null>(null);
  const [dateWindow, setDateWindow] = useState<DateWindow>("90");

  const gamesQuery = useQuery({ queryKey: ["games"], queryFn: getGames });
  const activityQuery = useQuery({
    queryKey: ["organizer-activity", game],
    queryFn: () => getOrganizerActivity(game),
  });
  const onboardingQuery = useQuery({
    queryKey: ["onboarding-history"],
    queryFn: () => getOnboardingHistory("week"),
  });

  const filteredActivity = filterByDateWindow(activityQuery.data ?? [], (b) => b.period, dateWindow);
  const activityChartData = toActivityChartData(filteredActivity);

  const filteredOnboarding = filterByDateWindow(
    onboardingQuery.data ?? [],
    (b) => b.period,
    dateWindow,
  );
  const chartData = mergeOnboardingOverlay(activityChartData, filteredOnboarding);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-4">
        <div className="form-control w-fit">
          <label htmlFor="activity-game-filter" className="label">
            <span className="label-text">Game</span>
          </label>
          <select
            id="activity-game-filter"
            value={game ?? ""}
            onChange={(event) => setGame(event.target.value || null)}
            className="select select-bordered select-sm"
          >
            <option value="">All</option>
            {(gamesQuery.data ?? []).map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </div>
        <DateWindowSelect id="activity-date-range" value={dateWindow} onChange={setDateWindow} />
      </div>

      {activityQuery.isLoading && <p>Loading organizer activity…</p>}
      {activityQuery.isError && <p className="text-error">Failed to load organizer activity</p>}
      {activityQuery.data && chartData.length === 0 && (
        <p>{dateWindow ? "No activity in the selected date range" : "No organizer activity yet"}</p>
      )}

      {!activityQuery.isLoading && !activityQuery.isError && chartData.length > 0 && (
        <>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="label" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" name="First tournament" fill="#75d1f0" />
              <Line
                dataKey="onboarded"
                name="Onboarded"
                type="monotone"
                stroke="#a78bfa"
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
          <ul className="sr-only">
            {chartData.map((datum) => (
              <li key={datum.period}>
                <span>{datum.label}: {datum.count}</span>
                {datum.onboarded != null && datum.onboarded > 0 && (
                  <span>, onboarded: {datum.onboarded}</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
