import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { num, pct } from "../../lib/format";
import { Card, CardTitle, ErrorState, SkeletonCard, StatTile } from "../ui";
import type { ProfileFilters } from "./FilterBar";

const TYPE_LABELS: Record<string, string> = {
  personal: "Personal",
  shooting: "Shooting",
  offensive: "Offensive",
  technical: "Technical",
  loose_ball: "Loose ball",
  other: "Other",
};

export default function FoulsSection({ playerId, filters }: {
  playerId: number;
  filters: ProfileFilters;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["fouls", playerId, filters.season, filters.season_type],
    queryFn: () => api.fouls(playerId, {
      season: filters.season, season_type: filters.season_type,
    }),
    staleTime: Infinity,
  });

  if (isLoading) {
    return (
      <div className="space-y-3">
        <SkeletonCard lines={5} />
        <p className="text-xs text-ink-muted text-center">
          First load parses recent play-by-play for foul types — can take ~15 seconds.
        </p>
      </div>
    );
  }
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data?.games) return <ErrorState message="No games for this selection." />;

  const types = data.foul_types_recent?.counts ?? {};
  const typeTotal = Object.values(types).reduce((a: number, b: any) => a + b, 0);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatTile label="Fouls / game" value={num(data.pf_per_game, 2)} />
        <StatTile label="Fouls / 36 min" value={num(data.pf_per_36, 2)} />
        <StatTile label="Total fouls" value={data.pf_total} />
        <StatTile label="Fouls drawn / g" value={num(data.fouls_drawn_per_game, 2)} />
        <StatTile label="5-foul games" value={data.games_5_fouls} />
        <StatTile label="Fouled out" value={data.games_6_fouls} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardTitle>Foul types (recent games)</CardTitle>
          {typeTotal === 0 ? (
            <p className="text-xs text-ink-muted">No fouls recorded in the analyzed games.</p>
          ) : (
            <div className="space-y-2">
              {Object.entries(TYPE_LABELS).map(([key, label]) => {
                const n = types[key] ?? 0;
                if (!n) return null;
                return (
                  <div key={key} className="text-xs">
                    <div className="flex justify-between mb-1">
                      <span className="text-ink-2">{label}</span>
                      <span className="tnum">{n}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
                      <div className="bar-fill h-full rounded-full"
                        style={{ width: `${(n / typeTotal) * 100}%`, background: "var(--series-6)" }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <p className="text-[11px] text-ink-muted mt-3">{data.note}</p>
          {data.foul_types_recent?.opponent_fta_from_shooting_fouls_estimate > 0 && (
            <p className="text-[11px] text-ink-muted mt-1">
              ≈{data.foul_types_recent.opponent_fta_from_shooting_fouls_estimate} opponent free throws
              from shooting fouls in those games (estimate).
            </p>
          )}
        </Card>

        <Card>
          <CardTitle>Foul trouble</CardTitle>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-ink-2">Foul-trouble rate (5+ fouls)</span>
              <span className="tnum font-medium">{pct(data.foul_trouble_rate)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-2">Minutes in foul-trouble games</span>
              <span className="tnum font-medium">{num(data.avg_min_foul_trouble)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-2">Minutes otherwise</span>
              <span className="tnum font-medium">{num(data.avg_min_normal)}</span>
            </div>
          </div>
          <CardTitle>Fouls per game (season)</CardTitle>
          <div className="flex items-end gap-[2px] h-16">
            {(data.series ?? []).map((s: any, i: number) => (
              <div
                key={i}
                title={`${s.date}: ${s.pf} fouls`}
                className="flex-1 rounded-t"
                style={{
                  height: `${Math.max(6, (s.pf / 6) * 100)}%`,
                  background: s.pf >= 5 ? "var(--series-8)" : "var(--series-6)",
                  opacity: s.pf === 0 ? 0.25 : 0.9,
                }}
              />
            ))}
          </div>
          <p className="text-[10px] text-ink-muted mt-1.5">Red bars = 5+ foul games.</p>
        </Card>
      </div>
    </div>
  );
}
