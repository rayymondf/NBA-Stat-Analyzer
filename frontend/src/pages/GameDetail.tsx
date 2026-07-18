import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { num, pct } from "../lib/format";
import ShotChart from "../components/ShotChart";
import { GameFlowChart } from "../components/charts";
import { Card, CardTitle, ErrorState, SkeletonCard, StatTile } from "../components/ui";

export default function GameDetailPage() {
  const { id, gameId } = useParams();
  const playerId = Number(id);
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ["gameDetail", playerId, gameId],
    queryFn: () => api.gameDetail(playerId, gameId!),
  });

  if (isLoading) return <div className="space-y-4"><SkeletonCard lines={4} /><SkeletonCard lines={10} /></div>;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data) return null;

  const line = data.player_line;
  const ts =
    line && line.fga + 0.44 * line.fta > 0
      ? line.pts / (2 * (line.fga + 0.44 * line.fta))
      : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <Link to={`/player/${playerId}`} className="text-xs text-ink-muted hover:text-ink">← Back to profile</Link>
          <h1 className="text-xl font-bold mt-1">
            {data.away?.abbr} {data.away?.pts} @ {data.home?.abbr} {data.home?.pts}
            <span className="text-ink-muted font-normal text-sm ml-2">{data.season} {data.season_type}</span>
          </h1>
        </div>
        <button
          onClick={() => navigate("/ai", {
            state: {
              question: `Why did ${((data.home?.pts ?? 0) > (data.away?.pts ?? 0) ? data.away?.name : data.home?.name)} lose this game?`,
              context: { game_id: gameId },
            },
          })}
          className="text-xs px-3 py-1.5 rounded-lg border border-edge text-ink-2 hover:text-ink hover:border-ink-muted transition-colors"
        >
          <span style={{ color: "var(--series-7)" }}>✦</span> Investigate this game with AI
        </button>
      </div>

      {line && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
          <StatTile label="Minutes" value={num(line.min)} />
          <StatTile label="Points" value={line.pts} />
          <StatTile label="Rebounds" value={line.reb} />
          <StatTile label="Assists" value={line.ast} />
          <StatTile label="FG" value={`${line.fgm}-${line.fga}`} />
          <StatTile label="3PT" value={`${line.fg3m}-${line.fg3a}`} />
          <StatTile label="TS%" value={pct(ts)} tip="TS_PCT" />
          <StatTile label="+/-" value={line.plus_minus ?? "–"} />
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <CardTitle>Shot chart for this game</CardTitle>
          {data.shots?.points?.length ? (
            <ShotChart points={data.shots.points} zones={data.shots.zones ?? []} height={400} />
          ) : (
            <p className="text-xs text-ink-muted">No shots recorded.</p>
          )}
        </Card>

        <div className="space-y-4">
          <Card>
            <CardTitle>Game flow (lead margin)</CardTitle>
            {data.timeline?.length ? (
              <GameFlowChart data={data.timeline} homeAbbr={data.home?.abbr} awayAbbr={data.away?.abbr} />
            ) : (
              <p className="text-xs text-ink-muted">No play-by-play available.</p>
            )}
          </Card>
          <Card>
            <CardTitle>Scoring plays ({data.scoring_events?.length ?? 0})</CardTitle>
            <div className="max-h-64 overflow-y-auto space-y-1.5 pr-1">
              {(data.scoring_events ?? []).map((e: any, i: number) => (
                <div key={i} className="text-xs flex gap-2">
                  <span className="text-ink-muted tnum shrink-0 w-16">
                    Q{e.period} {String(e.clock).replace("PT", "").replace("M", ":").split(".")[0]}
                  </span>
                  <span className="text-ink-2">{e.desc}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
