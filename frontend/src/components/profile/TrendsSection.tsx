import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { num, pct, signed } from "../../lib/format";
import { TrendChart } from "../charts";
import { Card, CardTitle, ErrorState, SkeletonCard, StatTile } from "../ui";
import type { ProfileFilters } from "./FilterBar";

export default function TrendsSection({ playerId, filters }: {
  playerId: number;
  filters: ProfileFilters;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["trends", playerId, filters.season, filters.season_type],
    queryFn: () => api.trends(playerId, {
      season: filters.season, season_type: filters.season_type,
    }),
  });
  const { data: career } = useQuery({
    queryKey: ["career", playerId],
    queryFn: () => api.career(playerId),
  });

  if (isLoading) return <SkeletonCard lines={8} />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data?.series?.length) return <ErrorState message="Not enough games to chart trends yet." />;

  const form = data.recent_form ?? {};
  const formDelta = (form.last_10_pts ?? 0) - (form.season_pts ?? 0);
  const unusual = Math.abs(form.pts_z_score ?? 0) >= 1.5;

  const careerRows = career?.regular_season ?? [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatTile label="Last 10: points" value={num(form.last_10_pts)} sub={`season ${num(form.season_pts)}`} />
        <StatTile label="Last 10: TS%" value={pct(form.last_10_ts)} sub={`season ${pct(form.season_ts)}`} tip="TS_PCT" />
        <StatTile label="Form vs season" value={signed(formDelta)} sub="points per game" />
        <StatTile
          label="Statistically unusual?"
          value={unusual ? "Yes" : "No"}
          sub={`z-score ${signed(form.pts_z_score, 2)}`}
        />
      </div>

      <Card>
        <CardTitle>Rolling scoring & efficiency ({data.window}-game window)</CardTitle>
        <TrendChart
          data={data.series}
          series={[
            { key: "pts", name: "Points (game)", color: "var(--grid)" },
            { key: "pts_roll", name: "Points (rolling)", color: "var(--series-1)" },
          ]}
        />
        <TrendChart
          data={data.series}
          height={170}
          series={[{ key: "ts_roll", name: "TS% (rolling)", color: "var(--series-5)" }]}
          formatter={(v) => pct(v as number)}
        />
      </Card>

      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardTitle>Minutes & shot volume trend</CardTitle>
          <TrendChart
            data={data.series}
            height={190}
            series={[
              { key: "min_roll", name: "Minutes (rolling)", color: "var(--series-5)" },
              { key: "fga_roll", name: "FGA (rolling)", color: "var(--series-4)" },
            ]}
          />
        </Card>
        <Card>
          <CardTitle tip="FG3A_RATE">Usage & 3-point rate trend</CardTitle>
          <TrendChart
            data={data.series}
            height={190}
            series={[
              ...(data.series.some((s: any) => s.usg_roll != null)
                ? [{ key: "usg_roll", name: "Usage (rolling)", color: "var(--series-7)" }]
                : []),
              { key: "fg3a_rate_roll", name: "3PA rate (rolling)", color: "var(--series-1)" },
            ]}
            formatter={(v) => pct(v as number)}
          />
        </Card>
      </div>

      {careerRows.length > 1 && (
        <Card>
          <CardTitle>Career development (per game, regular season)</CardTitle>
          <TrendChart
            data={careerRows}
            xKey="season"
            height={220}
            series={[
              { key: "pts", name: "Points", color: "var(--series-1)" },
              { key: "reb", name: "Rebounds", color: "var(--series-5)" },
              { key: "ast", name: "Assists", color: "var(--series-4)" },
            ]}
          />
          <TrendChart
            data={careerRows}
            xKey="season"
            height={160}
            series={[{ key: "ts_pct", name: "True shooting", color: "var(--series-7)" }]}
            formatter={(v) => pct(v as number)}
          />
        </Card>
      )}
    </div>
  );
}
