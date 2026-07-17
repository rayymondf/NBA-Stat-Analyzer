import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { num, pct, signed } from "../../lib/format";
import { Card, CardTitle, ErrorState, PercentileBar, SkeletonCard, StatTile } from "../ui";
import type { ProfileFilters } from "./FilterBar";

export default function EfficiencySection({ playerId, filters }: {
  playerId: number;
  filters: ProfileFilters;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["efficiency", playerId, filters.season, filters.season_type],
    queryFn: () => api.efficiency(playerId, {
      season: filters.season, season_type: filters.season_type,
    }),
  });

  if (isLoading) return <SkeletonCard lines={8} />;
  if (error) return <ErrorState message={(error as Error).message} />;
  const m = data?.metrics;
  if (!m || !data.games) return <ErrorState message="No efficiency data for this selection." />;
  const p = data.percentiles ?? {};

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatTile label="True shooting" value={pct(m.ts_pct)} tip="TS_PCT" />
        <StatTile label="Effective FG" value={pct(m.efg_pct)} tip="EFG_PCT" />
        <StatTile label="Usage" value={pct(m.usg_pct)} tip="USG_PCT" />
        <StatTile label="AST / TO" value={num(m.ast_to, 2)} tip="AST_TO" />
        <StatTile label="Turnover rate" value={pct(m.tov_pct)} tip="TOV_PCT" />
        <StatTile label="FT rate" value={num(m.ft_rate, 2)} tip="FT_RATE" />
        <StatTile label="Pts / possession" value={num(m.pts_per_poss, 2)} tip="PTS_PER_POSS" />
        <StatTile label="Off. rating" value={num(m.off_rating)} tip="OFF_RATING" />
        <StatTile label="Def. rating" value={num(m.def_rating)} tip="DEF_RATING" />
        <StatTile label="Net rating" value={signed(m.net_rating)} tip="NET_RATING" />
      </div>

      <Card>
        <CardTitle tip="PERCENTILE">Efficiency vs position</CardTitle>
        {[
          { key: "TS_PCT", label: "True shooting", fmt: pct },
          { key: "EFG_PCT", label: "Effective FG", fmt: pct },
          { key: "USG_PCT", label: "Usage", fmt: pct },
          { key: "AST_TO", label: "AST / TO", fmt: (v: number) => num(v, 2) },
          { key: "TM_TOV_PCT", label: "Turnover rate", fmt: pct },
          { key: "OFF_RATING", label: "Off. rating", fmt: (v: number) => num(v) },
          { key: "DEF_RATING", label: "Def. rating", fmt: (v: number) => num(v) },
          { key: "NET_RATING", label: "Net rating", fmt: (v: number) => signed(v) },
          { key: "PIE", label: "Impact (PIE)", fmt: pct },
        ].map((row) => {
          const item = p[row.key];
          if (!item) return null;
          return (
            <PercentileBar
              key={row.key}
              label={row.label}
              format={row.key}
              value={row.fmt(item.value) as string}
              percentile={item.percentile}
            />
          );
        })}
      </Card>
    </div>
  );
}
