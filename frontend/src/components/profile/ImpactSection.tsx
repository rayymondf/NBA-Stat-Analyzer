import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { num, signed } from "../../lib/format";
import { Card, CardTitle, ErrorState, SkeletonCard, StatTile } from "../ui";
import type { ProfileFilters } from "./FilterBar";

export default function ImpactSection({ playerId, filters }: {
  playerId: number;
  filters: ProfileFilters;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["impact", playerId, filters.season, filters.season_type],
    queryFn: () => api.impact(playerId, {
      season: filters.season, season_type: filters.season_type,
    }),
  });

  if (isLoading) return <SkeletonCard lines={6} />;
  if (error) return <ErrorState message={(error as Error).message} />;
  const cur = data?.current;
  if (!cur) return <ErrorState message="No on/off data available for this player and season." />;

  const rows = [cur, ...(data.history ?? [])];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatTile label="On/off net swing" value={signed(cur.net_diff)} tip="ON_OFF" sub="per 100 possessions" />
        <StatTile label="Net rating on court" value={signed(cur.on_court?.net_rating)} tip="NET_RATING" />
        <StatTile label="Net rating off court" value={signed(cur.off_court?.net_rating)} />
        <StatTile label="Offense / defense swing" value={`${signed(cur.off_diff)} / ${signed(cur.def_diff)}`} sub="on-court minus off-court" />
      </div>

      <Card>
        <CardTitle tip="ON_OFF">On court vs off court, by season</CardTitle>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-ink-muted text-left">
              <th className="py-1.5 font-medium">Season</th>
              <th className="text-right font-medium">On min</th>
              <th className="text-right font-medium">On net</th>
              <th className="text-right font-medium">Off net</th>
              <th className="text-right font-medium">Swing</th>
            </tr>
          </thead>
          <tbody className="tnum">
            {rows.map((r: any) => (
              <tr key={r.season} className="border-t border-edge">
                <td className="py-1.5">{r.season}</td>
                <td className="text-right">{num(r.on_court?.min, 0)}</td>
                <td className="text-right">{signed(r.on_court?.net_rating)}</td>
                <td className="text-right">{signed(r.off_court?.net_rating)}</td>
                <td className={`text-right font-semibold ${r.net_diff > 0 ? "text-delta-up" : "text-delta-down"}`}>
                  {signed(r.net_diff)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div className="card p-4 text-xs text-ink-2 leading-relaxed border-l-2" style={{ borderLeftColor: "var(--series-4)" }}>
        <span className="font-semibold">These are estimates, not box-score facts. </span>
        {data.disclaimer} History rows only cover seasons with the player's current team.
      </div>
    </div>
  );
}
