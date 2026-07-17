import {
  Bar, CartesianGrid, ComposedChart, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const AXIS = {
  stroke: "var(--baseline)",
  tick: { fill: "var(--ink-muted)", fontSize: 11 },
  tickLine: false as const,
  axisLine: { stroke: "var(--baseline)" },
};

export function ChartTooltip({ active, payload, label, formatter }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-xl" style={{ background: "var(--surface-2)" }}>
      <div className="text-ink-muted mb-1">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.stroke ?? p.fill }} />
          <span className="text-ink-2">{p.name}:</span>
          <span className="tnum font-medium">
            {formatter ? formatter(p.value, p.dataKey) : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export interface Series {
  key: string;
  name: string;
  color: string;
  dashed?: boolean;
}

/** Themed multi-series line chart (2px lines, recessive grid, crosshair tooltip). */
export function TrendChart({
  data, series, height = 240, yDomain, formatter, xKey = "date",
}: {
  data: any[];
  series: Series[];
  height?: number;
  yDomain?: [number | string, number | string];
  formatter?: (v: any, key: string) => string;
  xKey?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey={xKey} {...AXIS} minTickGap={40} tickFormatter={(d) => String(d).slice(5)} />
        <YAxis {...AXIS} domain={yDomain as any} width={46} />
        <Tooltip content={<ChartTooltip formatter={formatter} />} cursor={{ stroke: "var(--ink-muted)", strokeDasharray: "3 3" }} />
        {series.map((s) => (
          <Line
            key={s.key}
            dataKey={s.key}
            name={s.name}
            stroke={s.color}
            strokeWidth={2}
            strokeDasharray={s.dashed ? "5 4" : undefined}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Minutes bars + points line, game by game. */
export function MinutesProductionChart({ data, height = 260 }: { data: any[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -14 }} barCategoryGap="20%">
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="date" {...AXIS} minTickGap={40} tickFormatter={(d) => String(d).slice(5)} />
        <YAxis {...AXIS} width={40} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--surface-2)", opacity: 0.5 }} />
        <Bar dataKey="min" name="Minutes" fill="var(--series-5)" radius={[4, 4, 0, 0]} maxBarSize={10} />
        <Line dataKey="pts" name="Points" stroke="var(--series-1)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/** Score-margin worm for a single game (positive = home leads). */
export function GameFlowChart({ data, homeAbbr, awayAbbr, height = 220 }: {
  data: any[]; homeAbbr: string; awayAbbr: string; height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -20 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis
          dataKey="t" type="number" domain={[0, "dataMax"]} {...AXIS}
          tickFormatter={(t) => `Q${Math.min(4, Math.floor(t / 12) + 1)}`}
          ticks={[0, 12, 24, 36, 48]}
        />
        <YAxis {...AXIS} width={44} />
        <Tooltip
          content={<ChartTooltip formatter={(v: number) => `${v > 0 ? homeAbbr : awayAbbr} +${Math.abs(v)}`} />}
          cursor={{ stroke: "var(--ink-muted)", strokeDasharray: "3 3" }}
        />
        <Line dataKey="margin" name="Lead" stroke="var(--series-1)" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
