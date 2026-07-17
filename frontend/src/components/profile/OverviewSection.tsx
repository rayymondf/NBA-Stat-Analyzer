import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { num, pct, signed } from "../../lib/format";
import { Card, CardTitle, ErrorState, PercentileBar, SkeletonCard, StatTile } from "../ui";
import type { ProfileFilters } from "./FilterBar";

const PCT_ROWS: { key: string; label: string; fmt?: (v: number) => string; tip?: string }[] = [
  { key: "PTS", label: "Points" },
  { key: "REB", label: "Rebounds" },
  { key: "AST", label: "Assists" },
  { key: "STL", label: "Steals" },
  { key: "BLK", label: "Blocks" },
  { key: "TOV", label: "Turnovers" },
  { key: "PF", label: "Fouls" },
  { key: "MIN", label: "Minutes" },
  { key: "PLUS_MINUS", label: "Plus-minus" },
  { key: "TS_PCT", label: "True shooting", fmt: (v) => pct(v), tip: "TS_PCT" },
  { key: "USG_PCT", label: "Usage", fmt: (v) => pct(v), tip: "USG_PCT" },
];

const POS_LABEL: Record<string, string> = { G: "guards", F: "forwards", C: "centers" };

export default function OverviewSection({ playerId, filters }: {
  playerId: number;
  filters: ProfileFilters;
}) {
  const { perMode, ...apiFilters } = filters;
  const { data, isLoading, error } = useQuery({
    queryKey: ["overview", playerId, apiFilters],
    queryFn: () => api.overview(playerId, apiFilters),
  });

  if (isLoading) return <div className="grid md:grid-cols-2 gap-4"><SkeletonCard lines={6} /><SkeletonCard lines={6} /></div>;
  if (error) return <ErrorState message={(error as Error).message} />;
  const stats = data?.stats;
  if (!stats || !stats.games) return <ErrorState message="No games match these filters." />;

  const rates = stats[perMode] ?? stats.per_game;
  const sh = stats.shooting ?? {};
  const pcts = data.percentiles ?? {};
  const posGroup = Object.values(pcts)[0] as any;
  const poolNote = posGroup
    ? `vs ${POS_LABEL[posGroup.position_group] ?? "peers"} (${posGroup.pool_size} qualified)`
    : "";

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatTile label="Games" value={stats.games} sub={stats.starts != null ? `${stats.starts} starts` : undefined} />
        <StatTile label="Record" value={`${stats.wins ?? "—"}-${stats.losses ?? "—"}`} />
        <StatTile label="Minutes" value={num(rates?.MIN)} tip="PER_36" />
        <StatTile label="Points" value={num(rates?.PTS)} />
        <StatTile label="Rebounds" value={num(rates?.REB)} />
        <StatTile label="Assists" value={num(rates?.AST)} />
        <StatTile label="Steals" value={num(rates?.STL)} />
        <StatTile label="Blocks" value={num(rates?.BLK)} />
        <StatTile label="Turnovers" value={num(rates?.TOV)} />
        <StatTile label="Fouls" value={num(rates?.PF)} />
        <StatTile label="Plus-minus" value={signed(rates?.PLUS_MINUS)} tip="PLUS_MINUS" />
        <StatTile label="True shooting" value={pct(sh.TS_PCT)} tip="TS_PCT" />
      </div>

      <Card>
        <CardTitle tip="PERCENTILE">Percentile vs position {poolNote && <span className="normal-case font-normal text-ink-muted tracking-normal">· {poolNote}</span>}</CardTitle>
        <div>
          {PCT_ROWS.map((row) => {
            const p = pcts[row.key];
            if (!p) return null;
            return (
              <PercentileBar
                key={row.key}
                label={row.label}
                format={row.tip}
                value={row.fmt ? row.fmt(p.value) : num(p.value)}
                percentile={p.percentile}
                poolLabel={`Better than ${p.percentile}% of ${POS_LABEL[p.position_group] ?? "peers"}`}
              />
            );
          })}
        </div>
        <p className="text-[11px] text-ink-muted mt-3">
          Percentiles always compare full-season per-game numbers against players at the
          same position (min. 10 games, 15 MPG) — they don't change with the filters above.
        </p>
      </Card>
    </div>
  );
}
