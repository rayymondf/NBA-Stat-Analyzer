import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { num, pct, signed } from "../../lib/format";
import { MinutesProductionChart } from "../charts";
import { Card, CardTitle, ErrorState, SkeletonCard, StatTile } from "../ui";
import type { ProfileFilters } from "./FilterBar";

export default function PlaytimeSection({ playerId, filters }: {
  playerId: number;
  filters: ProfileFilters;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["playtime", playerId, filters.season, filters.season_type],
    queryFn: () => api.playtime(playerId, {
      season: filters.season, season_type: filters.season_type,
    }),
  });

  if (isLoading) return <SkeletonCard lines={8} />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data?.games) return <ErrorState message="No games for this selection." />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatTile label="Minutes / game" value={num(data.min_per_game)} />
        <StatTile label="Total minutes" value={Math.round(data.min_total)} />
        <StatTile label="Games played" value={data.games} sub={data.team_games ? `of ${data.team_games} team games` : undefined} />
        <StatTile label="Games missed" value={data.games_missed ?? "—"} />
        <StatTile label="Starts" value={data.starts ?? "—"} sub={data.bench_games != null ? `${data.bench_games} off bench` : undefined} />
        <StatTile label="Q4 minutes" value={data.q4 ? num(data.q4.min_per_game) : "—"} sub="per game" />
      </div>

      <Card>
        <CardTitle>Minutes & production, game by game</CardTitle>
        <MinutesProductionChart data={data.timeline ?? []} />
      </Card>

      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardTitle>Performance by minutes played</CardTitle>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-ink-muted text-left">
                <th className="py-1.5 font-medium">Minutes</th>
                <th className="text-right font-medium">Games</th>
                <th className="text-right font-medium">PTS</th>
                <th className="text-right font-medium">REB</th>
                <th className="text-right font-medium">AST</th>
                <th className="text-right font-medium">TS%</th>
              </tr>
            </thead>
            <tbody className="tnum">
              {(data.by_minutes ?? []).map((b: any) => (
                <tr key={b.bucket} className="border-t border-edge">
                  <td className="py-1.5 text-ink-2">{b.bucket}</td>
                  <td className="text-right">{b.games}</td>
                  <td className="text-right">{num(b.pts)}</td>
                  <td className="text-right">{num(b.reb)}</td>
                  <td className="text-right">{num(b.ast)}</td>
                  <td className="text-right">{pct(b.ts_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardTitle>Foul trouble impact</CardTitle>
            <div className="space-y-1.5 text-xs">
              <Row label="Games with 5+ fouls" value={String(data.foul_impact?.games_5plus_fouls ?? 0)} />
              <Row label="Avg minutes in those games" value={num(data.foul_impact?.avg_min_foul_trouble)} />
              <Row label="Avg minutes otherwise" value={num(data.foul_impact?.avg_min_normal)} />
            </div>
          </Card>
          <Card>
            <CardTitle tip="CLUTCH">Clutch time</CardTitle>
            {data.clutch ? (
              <div className="space-y-1.5 text-xs">
                <Row label="Clutch games" value={`${data.clutch.games} (${data.clutch.record})`} />
                <Row label="Clutch minutes / game" value={num(data.clutch.min_per_game)} />
                <Row label="Clutch points / game" value={num(data.clutch.pts_per_game)} />
                <Row label="Clutch FG%" value={pct(data.clutch.fg_pct)} />
                <Row label="Clutch plus-minus" value={signed(data.clutch.plus_minus, 0)} />
              </div>
            ) : (
              <p className="text-xs text-ink-muted">No clutch-time data.</p>
            )}
          </Card>
        </div>
      </div>
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
