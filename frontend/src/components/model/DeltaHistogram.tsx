import {
  Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { ChartTooltip } from "../charts";

const AXIS = {
  stroke: "var(--baseline)",
  tick: { fill: "var(--ink-muted)", fontSize: 11 },
  tickLine: false as const,
  axisLine: { stroke: "var(--baseline)" },
};

/** League distribution of shot-making deltas with this player's position marked. */
export default function DeltaHistogram({ distribution, playerDelta, playerName }: {
  distribution: number[];
  playerDelta: number | null;
  playerName?: string;
}) {
  if (!distribution?.length) return null;

  const values = distribution.map((d) => d * 100); // percentage points
  const lo = Math.floor(Math.min(...values));
  const hi = Math.ceil(Math.max(...values));
  const binCount = 24;
  const width = (hi - lo) / binCount || 1;
  const bins = Array.from({ length: binCount }, (_, i) => ({
    x: lo + i * width,
    label: `${(lo + i * width).toFixed(1)} to ${(lo + (i + 1) * width).toFixed(1)}`,
    players: 0,
  }));
  for (const v of values) {
    const i = Math.min(binCount - 1, Math.max(0, Math.floor((v - lo) / width)));
    bins[i].players += 1;
  }
  const markerBin = playerDelta === null || playerDelta === undefined
    ? null
    : bins[Math.min(binCount - 1,
                    Math.max(0, Math.floor((playerDelta * 100 - lo) / width)))];

  return (
    <div>
      <ResponsiveContainer width="100%" height={190}>
        <BarChart data={bins} margin={{ top: 18, right: 8, bottom: 0, left: -22 }} barCategoryGap={1}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis
            dataKey="x"
            {...AXIS}
            interval={5}
            tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${Number(v).toFixed(0)}`}
          />
          <YAxis {...AXIS} allowDecimals={false} width={40} />
          <Tooltip
            content={<ChartTooltip formatter={(v: number) => `${v} players`} />}
            cursor={{ fill: "var(--surface-2)", opacity: 0.5 }}
            labelFormatter={(l: any) => l}
          />
          <Bar dataKey="players" name="Players" fill="var(--series-1)" radius={[4, 4, 0, 0]} />
          {markerBin && (
            <ReferenceLine
              x={markerBin.x}
              stroke="var(--ink)"
              strokeWidth={2}
              label={{
                value: playerName ? `${playerName} sits here` : "This player",
                position: "top",
                fill: "var(--ink)",
                fontSize: 11,
                fontWeight: 600,
              }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
      <p className="text-[11px] text-ink-muted mt-1">
        Every qualified NBA player (200+ shots over the training seasons),
        placed by how far their actual shooting sits above or below the
        model's expectation, in effective field goal percentage points. Zero means exactly
        as expected.
      </p>
    </div>
  );
}
