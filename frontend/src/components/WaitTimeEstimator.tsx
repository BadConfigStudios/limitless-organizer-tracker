import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ApiError, getWaitEstimate, type WaitEstimate } from "../api/client";
import { formatEpochDate } from "../lib/formatDate";
import { toFittedLineData, toFrontierScatterData, toScatterData } from "../lib/waitEstimateChartData";
import { type DateWindow } from "../lib/dateWindow";
import { DateWindowSelect } from "./DateWindowSelect";

export function WaitTimeEstimator() {
  const [organizerIdInput, setOrganizerIdInput] = useState("");
  const [targetOrganizerId, setTargetOrganizerId] = useState<number | undefined>(undefined);
  const [dateWindow, setDateWindow] = useState<DateWindow>("90");

  const days = dateWindow === "" ? undefined : Number(dateWindow);

  const estimateQuery = useQuery<WaitEstimate, Error>({
    queryKey: ["wait-estimate", targetOrganizerId, dateWindow],
    queryFn: () => getWaitEstimate(targetOrganizerId, days),
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = organizerIdInput.trim();
    if (trimmed === "") {
      setTargetOrganizerId(undefined);
      return;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
      return;
    }
    setTargetOrganizerId(parsed);
  };

  return (
    <div>
      <form onSubmit={handleSubmit} className="mb-4 flex flex-wrap items-end gap-2">
        <div className="form-control">
          <label htmlFor="wait-estimate-organizer-id" className="label">
            <span className="label-text">Organizer ID (optional — enter yours for a projected date)</span>
          </label>
          <input
            id="wait-estimate-organizer-id"
            type="number"
            value={organizerIdInput}
            onChange={(event) => setOrganizerIdInput(event.target.value)}
            className="input input-bordered input-sm w-32"
          />
        </div>
        <button type="submit" className="btn btn-primary btn-sm">
          Estimate
        </button>
        <DateWindowSelect id="wait-estimate-date-range" value={dateWindow} onChange={setDateWindow} />
      </form>

      {estimateQuery.isLoading && <p>Calculating wait estimate…</p>}
      {estimateQuery.isError && (
        <p className="text-error">
          {estimateQuery.error instanceof ApiError && estimateQuery.error.status === 404
            ? "Not enough data to estimate an onboarding trend"
            : "Failed to load wait estimate"}
        </p>
      )}

      {estimateQuery.data && (
        <div>
          <div className="stats stats-horizontal mb-4 shadow">
            <div className="stat">
              <div className="stat-title">Slope (days / ID)</div>
              <div className="stat-value text-sm">{estimateQuery.data.slope.toFixed(4)}</div>
            </div>
            <div className="stat">
              <div className="stat-title">R²</div>
              <div className="stat-value text-sm">{estimateQuery.data.r_squared.toFixed(3)}</div>
            </div>
            <div className="stat">
              <div className="stat-title">Sample size</div>
              <div className="stat-value text-sm">{estimateQuery.data.sample_size}</div>
            </div>
            <div className="stat">
              <div className="stat-title">Frontier organizers</div>
              <div className="stat-value text-sm">{estimateQuery.data.frontier_size}</div>
            </div>
          </div>

          {estimateQuery.data.organizer_id !== null &&
            estimateQuery.data.projected_active_date !== null && (
              <div className="stats mb-4 shadow">
                <div className="stat">
                  <div className="stat-title">Projected active date</div>
                  <div className="stat-value text-sm text-accent">{estimateQuery.data.projected_active_date}</div>
                </div>
              </div>
            )}

          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="timestamp"
                type="number"
                name="First tournament date"
                domain={["auto", "auto"]}
                tickFormatter={formatEpochDate}
              />
              <YAxis dataKey="organizerId" type="number" name="Organizer ID" domain={["auto", "auto"]} />
              <Tooltip />
              <Scatter
                name="All organizers"
                data={toScatterData(estimateQuery.data!)}
                dataKey="organizerId"
                fill="#75d1f0"
              />
              <Scatter
                name="Frontier (fastest onboarding)"
                data={toFrontierScatterData(estimateQuery.data!)}
                dataKey="organizerId"
                fill="#ff7598"
              />
              <Line
                name="Fitted line"
                data={toFittedLineData(estimateQuery.data)}
                dataKey="organizerId"
                stroke="#c8ff00"
                dot={false}
                type="linear"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
