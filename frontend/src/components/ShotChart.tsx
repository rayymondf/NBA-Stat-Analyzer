import { useMemo, useState } from "react";
import type { ShotPoint, Zone } from "../lib/api";
import { pct } from "../lib/format";
import { Segmented } from "./ui";

/*
 * NBA shot coordinates: units are tenths of feet, hoop at (0, 0),
 * x ∈ [-250, 250] (sideline to sideline), y up-court from the hoop,
 * baseline at y = -52. We render the half court with the hoop at the bottom.
 */
const X_MIN = -250, X_MAX = 250, Y_MIN = -52, Y_MAX = 440;

export type ShotView = "dots" | "heat" | "zones";

const ZONE_SHORT: Record<string, string> = {
  "Restricted Area": "Rim",
  "In The Paint (Non-RA)": "Paint",
  "Mid-Range": "Mid-range",
  "Left Corner 3": "Left corner 3",
  "Right Corner 3": "Right corner 3",
  "Above the Break 3": "Above-break 3",
  Backcourt: "Backcourt",
};

function CourtLines() {
  const s = "var(--baseline)";
  const w = 2.5;
  return (
    <g stroke={s} strokeWidth={w} fill="none">
      {/* boundary */}
      <rect x={X_MIN} y={Y_MIN} width={X_MAX - X_MIN} height={Y_MAX - Y_MIN} />
      {/* hoop + backboard */}
      <circle cx={0} cy={0} r={7.5} />
      <line x1={-30} y1={-7.5} x2={30} y2={-7.5} strokeWidth={w * 1.4} />
      {/* restricted area */}
      <path d="M -40 0 A 40 40 0 0 0 40 0" />
      {/* paint */}
      <rect x={-80} y={Y_MIN} width={160} height={190 + 52} />
      <rect x={-60} y={Y_MIN} width={120} height={190 + 52} />
      {/* free-throw circle */}
      <path d="M -60 190 A 60 60 0 0 0 60 190" />
      <path d="M -60 190 A 60 60 0 0 1 60 190" strokeDasharray="12 10" />
      {/* three-point line: corners + arc (r = 237.5) */}
      <line x1={-220} y1={Y_MIN} x2={-220} y2={89} />
      <line x1={220} y1={Y_MIN} x2={220} y2={89} />
      <path d="M -220 89 A 237.5 237.5 0 0 0 220 89" />
      {/* half-court */}
      <path d={`M -60 ${Y_MAX} A 60 60 0 0 1 60 ${Y_MAX}`} />
    </g>
  );
}

/** Sequential blue ramp (dataviz palette steps 150→650). */
const HEAT_RAMP = ["#b7d3f6", "#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"];

function heatColor(count: number, max: number) {
  const idx = Math.min(
    HEAT_RAMP.length - 1,
    Math.floor((count / max) * HEAT_RAMP.length),
  );
  return HEAT_RAMP[idx];
}

/** Diverging color for zone efficiency vs league (blue = better, red = worse). */
function diffColor(diff: number | null) {
  if (diff === null) return "var(--surface-2)";
  if (diff > 0.06) return "#1c5cab";
  if (diff > 0.02) return "#3987e5";
  if (diff >= -0.02) return "#898781";
  if (diff >= -0.06) return "#e34948";
  return "#b52625";
}

export default function ShotChart({
  points, zones, view, onViewChange, height = 460,
}: {
  points: ShotPoint[];
  zones: Zone[];
  view?: ShotView;
  onViewChange?: (v: ShotView) => void;
  height?: number;
}) {
  const [internalView, setInternalView] = useState<ShotView>("dots");
  const v = view ?? internalView;
  const setV = onViewChange ?? setInternalView;
  const [hover, setHover] = useState<{ px: number; py: number; p: ShotPoint } | null>(null);

  const bins = useMemo(() => {
    if (v !== "heat") return { cells: [] as { x: number; y: number; n: number }[], max: 1 };
    const size = 25;
    const map = new Map<string, { x: number; y: number; n: number }>();
    for (const p of points) {
      const bx = Math.floor(p.x / size) * size;
      const by = Math.floor(p.y / size) * size;
      const key = `${bx},${by}`;
      const cell = map.get(key) ?? { x: bx, y: by, n: 0 };
      cell.n++;
      map.set(key, cell);
    }
    const cells = [...map.values()];
    return { cells, max: Math.max(1, ...cells.map((c) => c.n)) };
  }, [points, v]);

  const zoneCentroids = useMemo(() => {
    if (v !== "zones") return [];
    const groups = new Map<string, { sx: number; sy: number; n: number }>();
    for (const p of points) {
      const g = groups.get(p.zone) ?? { sx: 0, sy: 0, n: 0 };
      g.sx += p.x; g.sy += p.y; g.n++;
      groups.set(p.zone, g);
    }
    return zones
      .filter((z) => z.zone !== "Backcourt" && groups.has(z.zone))
      .map((z) => {
        const g = groups.get(z.zone)!;
        return { ...z, cx: g.sx / g.n, cy: g.sy / g.n };
      });
  }, [points, zones, v]);

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <Segmented
          options={[
            { value: "dots" as ShotView, label: "Shots" },
            { value: "heat" as ShotView, label: "Heatmap" },
            { value: "zones" as ShotView, label: "Zones vs league" },
          ]}
          value={v}
          onChange={setV}
        />
        {v === "dots" && (
          <div className="flex items-center gap-4 text-xs text-ink-muted">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--series-1)" }} />
              Made
            </span>
            <span className="flex items-center gap-1.5">
              <svg width="10" height="10" viewBox="0 0 10 10">
                <path d="M1.5 1.5l7 7M8.5 1.5l-7 7" stroke="var(--ink-muted)" strokeWidth="1.8" />
              </svg>
              Missed
            </span>
          </div>
        )}
        {v === "zones" && (
          <div className="flex items-center gap-3 text-xs text-ink-muted">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full" style={{ background: "#3987e5" }} /> Above league</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full" style={{ background: "#898781" }} /> Even</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full" style={{ background: "#e34948" }} /> Below</span>
          </div>
        )}
      </div>

      <svg
        viewBox={`${X_MIN} ${Y_MIN} ${X_MAX - X_MIN} ${Y_MAX - Y_MIN}`}
        style={{ width: "100%", maxHeight: height, background: "var(--surface)" }}
        className="rounded-xl border border-edge"
        onMouseLeave={() => setHover(null)}
      >
        {/* flip so the hoop is at the bottom */}
        <g transform={`translate(0 ${Y_MAX + Y_MIN}) scale(1 -1)`}>
          {v === "heat" &&
            bins.cells.map((c) => (
              <rect
                key={`${c.x},${c.y}`}
                x={c.x} y={c.y} width={25} height={25} rx={5}
                fill={heatColor(c.n, bins.max)}
                opacity={0.9}
              />
            ))}

          <CourtLines />

          {v === "dots" &&
            points.map((p, i) =>
              p.made ? (
                <circle
                  key={i}
                  cx={p.x} cy={p.y} r={5}
                  fill="var(--series-1)"
                  opacity={0.85}
                  onMouseEnter={(e) => {
                    const r = (e.target as SVGElement).closest("svg")!.getBoundingClientRect();
                    setHover({ px: e.clientX - r.left, py: e.clientY - r.top, p });
                  }}
                />
              ) : (
                <g key={i} opacity={0.6}
                  onMouseEnter={(e) => {
                    const r = (e.target as SVGElement).closest("svg")!.getBoundingClientRect();
                    setHover({ px: e.clientX - r.left, py: e.clientY - r.top, p });
                  }}>
                  <path
                    d={`M ${p.x - 4} ${p.y - 4} l 8 8 M ${p.x + 4} ${p.y - 4} l -8 8`}
                    stroke="var(--ink-muted)" strokeWidth={2}
                  />
                  {/* invisible hover target bigger than the mark */}
                  <circle cx={p.x} cy={p.y} r={8} fill="transparent" />
                </g>
              ),
            )}

          {v === "zones" &&
            zoneCentroids.map((z) => (
              <g key={z.zone}>
                <circle
                  cx={z.cx} cy={z.cy}
                  r={Math.max(24, Math.min(52, Math.sqrt(z.fga) * 3.2))}
                  fill={diffColor(z.diff)}
                  opacity={0.92}
                  stroke="var(--surface)"
                  strokeWidth={2}
                />
                <text
                  x={z.cx} y={-z.cy + 4} transform="scale(1 -1)"
                  textAnchor="middle" fontSize={15} fontWeight={700}
                  fill="#ffffff"
                >
                  {z.pct !== null ? `${Math.round(z.pct * 100)}%` : "–"}
                </text>
              </g>
            ))}
        </g>
      </svg>

      {hover && (
        <div
          className="absolute z-10 pointer-events-none card px-3 py-2 text-xs shadow-xl"
          style={{
            left: Math.min(hover.px + 12, 340),
            top: hover.py - 10,
            background: "var(--surface-2)",
          }}
        >
          <div className="font-medium">
            {hover.p.made ? "Made" : "Missed"} {hover.p.value === 3 ? "3PT" : "2PT"} · {hover.p.dist} ft
          </div>
          <div className="text-ink-muted mt-0.5">{hover.p.action}</div>
          <div className="text-ink-muted">{hover.p.vs} · Q{hover.p.period} · {hover.p.date?.slice(0, 10)}</div>
        </div>
      )}

      {v === "zones" && (
        <div className="mt-3 space-y-1">
          {zones.filter((z) => z.zone !== "Backcourt").map((z) => (
            <div key={z.zone} className="flex items-center gap-2 text-xs">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: diffColor(z.diff) }} />
              <span className="w-32 text-ink-2">{ZONE_SHORT[z.zone] ?? z.zone}</span>
              <span className="tnum">{z.fgm}/{z.fga}</span>
              <span className="tnum font-medium">{pct(z.pct)}</span>
              <span className="text-ink-muted tnum">
                league {pct(z.league_pct)}
                {z.diff !== null && ` (${z.diff > 0 ? "+" : ""}${(z.diff * 100).toFixed(1)})`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
