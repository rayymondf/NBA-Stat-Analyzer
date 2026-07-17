import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type ShotPoint } from "../../lib/api";
import { num, pct } from "../../lib/format";
import ShotChart from "../ShotChart";
import { Card, CardTitle, ErrorState, SkeletonCard, StatTile } from "../ui";
import type { ProfileFilters } from "./FilterBar";

export default function ShootingSection({ playerId, filters }: {
  playerId: number;
  filters: ProfileFilters;
}) {
  const [quarter, setQuarter] = useState<number | null>(null);
  const [result, setResult] = useState<"all" | "made" | "missed">("all");

  const { data, isLoading, error } = useQuery({
    queryKey: ["shooting", playerId, filters.season, filters.season_type],
    queryFn: () => api.shooting(playerId, {
      season: filters.season,
      season_type: filters.season_type,
    }),
  });

  const points: ShotPoint[] = useMemo(() => {
    let pts = data?.points ?? [];
    if (quarter) pts = pts.filter((p: ShotPoint) => p.period === quarter);
    if (result !== "all") pts = pts.filter((p: ShotPoint) => p.made === (result === "made"));
    return pts;
  }, [data, quarter, result]);

  if (isLoading) return <div className="grid md:grid-cols-2 gap-4"><SkeletonCard lines={8} /><SkeletonCard lines={8} /></div>;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data?.points?.length) return <ErrorState message="No shot data for this season." />;

  const t = data.totals ?? {};
  const sb = data.scoring_breakdown ?? {};

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatTile label="FG" value={pct(t.fg_pct)} sub={`${t.fgm}/${t.fga}`} />
        <StatTile label="3PT" value={t.fg3a ? pct(t.fg3m / t.fg3a) : "—"} sub={`${t.fg3m}/${t.fg3a}`} />
        <StatTile label="2PT" value={t.fga - t.fg3a ? pct((t.fgm - t.fg3m) / (t.fga - t.fg3a)) : "—"} sub={`${t.fgm - t.fg3m}/${t.fga - t.fg3a}`} />
        <StatTile label="Pts / shot" value={num(t.pts_per_shot, 2)} tip="PTS_PER_SHOT" />
        <StatTile label="Avg distance" value={`${num(t.avg_distance)} ft`} />
        <StatTile label="Attempts" value={t.fga} sub="field goals" />
      </div>

      <div className="grid lg:grid-cols-[1fr_320px] gap-4">
        <Card>
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <select
              className="bg-surface border border-edge rounded-lg px-2.5 py-1.5 text-xs outline-none"
              value={quarter ?? ""}
              onChange={(e) => setQuarter(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">All quarters</option>
              {[1, 2, 3, 4].map((q) => <option key={q} value={q}>Q{q}</option>)}
              <option value="5">OT</option>
            </select>
            <select
              className="bg-surface border border-edge rounded-lg px-2.5 py-1.5 text-xs outline-none"
              value={result}
              onChange={(e) => setResult(e.target.value as any)}
            >
              <option value="all">Makes + misses</option>
              <option value="made">Makes only</option>
              <option value="missed">Misses only</option>
            </select>
            <span className="text-xs text-ink-muted ml-auto tnum">{points.length} shots shown</span>
          </div>
          <ShotChart points={points} zones={data.zones ?? []} />
        </Card>

        <div className="space-y-4">
          <Card>
            <CardTitle>Shooting by distance</CardTitle>
            <div className="space-y-2">
              {(data.by_distance ?? []).map((d: any) => (
                <div key={d.range} className="text-xs">
                  <div className="flex justify-between mb-1">
                    <span className="text-ink-2">{d.range}</span>
                    <span className="tnum">{pct(d.pct)} <span className="text-ink-muted">({d.fgm}/{d.fga})</span></span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
                    <div className="bar-fill h-full rounded-full" style={{ width: `${d.freq * 100}%`, background: "var(--series-1)" }} />
                  </div>
                </div>
              ))}
              <p className="text-[10px] text-ink-muted pt-1">Bar length = share of total attempts.</p>
            </div>
          </Card>

          {sb.pct_ast_fgm != null && (
            <Card>
              <CardTitle>Assisted vs created</CardTitle>
              <div className="space-y-2 text-xs">
                <Row label="Assisted makes" value={pct(sb.pct_ast_fgm)} />
                <Row label="Unassisted makes" value={pct(sb.pct_uast_fgm)} />
                <Row label="2PT assisted" value={pct(sb.pct_ast_2pm)} />
                <Row label="3PT assisted" value={pct(sb.pct_ast_3pm)} />
                {sb.pct_pts_paint != null && <Row label="Points in paint" value={pct(sb.pct_pts_paint)} />}
                {sb.pct_pts_fastbreak != null && <Row label="Fast-break points" value={pct(sb.pct_pts_fastbreak)} />}
              </div>
            </Card>
          )}
        </div>
      </div>
      <p className="text-[11px] text-ink-muted">
        Shot chart covers the selected season {filters.season} ({filters.season_type?.toLowerCase()}).
        Quarter and make/miss filters apply on the chart; zones compare against the league average from each zone.
      </p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-ink-2">{label}</span>
      <span className="tnum font-medium">{value}</span>
    </div>
  );
}
