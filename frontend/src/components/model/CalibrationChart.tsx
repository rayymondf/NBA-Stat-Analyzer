import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { ChartTooltip } from "../charts";
import { pct } from "../../lib/format";

const AXIS = {
  stroke: "var(--baseline)",
  tick: { fill: "var(--ink-muted)", fontSize: 11 },
  tickLine: false as const,
  axisLine: { stroke: "var(--baseline)" },
};

/** Predicted vs actual make rate per distance bucket, on held-out test shots. */
export default function CalibrationChart({ rows }: {
  rows: { bucket: string; predicted: number; actual: number; shots: number }[];
}) {
  if (!rows?.length) return null;
  return (
    <div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: -18 }} barCategoryGap="28%" barGap={2}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="bucket" {...AXIS} />
          <YAxis
            {...AXIS}
            width={44}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            domain={[0, 0.75]}
          />
          <Tooltip
            content={<ChartTooltip formatter={(v: number) => pct(v)} />}
            cursor={{ fill: "var(--surface-2)", opacity: 0.5 }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, color: "var(--ink-muted)" }}
            iconType="circle"
            iconSize={8}
          />
          <Bar dataKey="predicted" name="Model predicted" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={24} />
          <Bar dataKey="actual" name="Actually made" fill="var(--series-6)" radius={[4, 4, 0, 0]} maxBarSize={24} />
        </BarChart>
      </ResponsiveContainer>
      <p className="text-[11px] text-ink-muted mt-1">
        Graded on shots the model never saw during training. When the two bars
        match, the model is honest: if it says 44%, players really make about
        44% from there.
      </p>
    </div>
  );
}
