import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { signed, num, pct } from "../lib/format";
import { Card, CardTitle, ErrorState, GlossaryTip, HowItsMade, PageHeader, Skeleton } from "../components/ui";

const TEAMS = ["","ATL","BOS","BKN","CHA","CHI","CLE","DAL","DEN","DET","GSW","HOU","IND","LAC","LAL","MEM","MIA","MIL","MIN","NOP","NYK","OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS"];

const PAGE = 50;
const selectCls = "bg-surface border border-edge rounded-lg px-2.5 py-1.5 text-xs outline-none";

export default function GamesPage() {
  const [params] = useSearchParams();
  const [season, setSeason] = useState<string>("");
  const [team, setTeam] = useState("");
  const [seasonType, setSeasonType] = useState("Regular Season");
  const [dateFilter, setDateFilter] = useState("");
  const [visible, setVisible] = useState(PAGE);
  const [selected, setSelected] = useState<string | null>(params.get("game"));

  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const activeSeason = season || meta?.current_season || "";

  // One cached backend call returns the whole season schedule; filter + page
  // entirely client-side (no extra API requests when the user changes filters).
  const { data: games, isLoading } = useQuery({
    queryKey: ["games", activeSeason, seasonType, team],
    queryFn: () =>
      api.games({
        season: activeSeason || undefined,
        team: team || undefined,
        season_type: seasonType,
        limit: 1500,
      }),
    enabled: !!activeSeason,
  });

  const filtered = useMemo(() => {
    let list = games ?? [];
    if (dateFilter) list = list.filter((g) => String(g.date).slice(0, 10) === dateFilter);
    return list;
  }, [games, dateFilter]);

  const shown = filtered.slice(0, visible);

  const resetPaging = () => setVisible(PAGE);

  return (
    <div>
      <PageHeader
        kicker="Every game, investigated"
        title="Games"
        dek="Pick any completed game and get a ranked, evidence-based explanation of why it was won and lost."
      />
      <div className="grid lg:grid-cols-[340px_1fr] gap-4 items-start">
      <Card className="!p-0 overflow-hidden">
        <div className="p-3 border-b border-edge space-y-2">
          <div className="flex gap-2">
            <select
              className={`${selectCls} flex-1`}
              value={activeSeason}
              onChange={(e) => { setSeason(e.target.value); resetPaging(); }}
            >
              {(meta?.seasons ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <select
              className={selectCls}
              value={seasonType}
              onChange={(e) => { setSeasonType(e.target.value); resetPaging(); }}
            >
              <option>Regular Season</option>
              <option>Playoffs</option>
            </select>
          </div>
          <div className="flex gap-2">
            <select
              className={`${selectCls} flex-1`}
              value={team}
              onChange={(e) => { setTeam(e.target.value); resetPaging(); }}
            >
              <option value="">All teams</option>
              {TEAMS.filter(Boolean).map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input
              type="date"
              className={selectCls}
              value={dateFilter}
              onChange={(e) => { setDateFilter(e.target.value); resetPaging(); }}
              title="Jump to a date"
            />
          </div>
          {dateFilter && (
            <button
              className="text-[11px] text-ink-muted hover:text-ink underline underline-offset-2"
              onClick={() => { setDateFilter(""); resetPaging(); }}
            >
              Clear date
            </button>
          )}
        </div>

        <div className="px-3 py-2 border-b border-edge text-[11px] text-ink-muted">
          {isLoading ? "Loading games…" : (
            <>
              {activeSeason} {seasonType} · newest first
              <br />
              showing {shown.length} of {filtered.length} game{filtered.length === 1 ? "" : "s"}
              {team && ` · ${team}`}{dateFilter && ` · ${dateFilter}`}
            </>
          )}
        </div>

        <div className="max-h-[62vh] overflow-y-auto">
          {isLoading && Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="p-3 border-b border-edge"><Skeleton className="h-9" /></div>
          ))}
          {!isLoading && filtered.length === 0 && (
            <p className="p-4 text-xs text-ink-muted">No games match these filters.</p>
          )}
          {shown.map((g) => (
            <button
              key={g.game_id}
              onClick={() => setSelected(g.game_id)}
              className={`w-full p-3 text-left border-b border-edge last:border-0 transition-colors ${
                selected === g.game_id ? "bg-surface-2" : "hover:bg-surface-2"
              }`}
            >
              <div className="text-[11px] text-ink-muted">{String(g.date).slice(0, 10)}</div>
              <div className="text-sm tnum mt-0.5 flex justify-between">
                <span className={g.away.wl === "W" ? "font-semibold" : "text-ink-2"}>
                  {g.away.abbr} {g.away.pts}
                </span>
                <span className="text-ink-muted text-xs">@</span>
                <span className={g.home.wl === "W" ? "font-semibold" : "text-ink-2"}>
                  {g.home.pts} {g.home.abbr}
                </span>
              </div>
            </button>
          ))}
          {shown.length < filtered.length && (
            <button
              onClick={() => setVisible((v) => v + PAGE)}
              className="w-full p-3 text-xs text-center text-ink-2 hover:text-ink hover:bg-surface-2 transition-colors"
            >
              Show more ({filtered.length - shown.length} remaining)
            </button>
          )}
        </div>
      </Card>

      {selected ? (
        <Investigation gameId={selected} />
      ) : (
        <Card className="text-center py-16 text-ink-muted text-sm">
          Pick a completed game to see why it was won and lost:
          shooting, turnovers, runs, stars and fourth-quarter execution, ranked by evidence.
        </Card>
      )}
      </div>
      <HowItsMade>
        Game investigations are pure statistics, no AI. The app pulls the
        official box score and play-by-play from NBA.com, computes the four
        factors, star performances vs season averages, scoring runs and
        fourth-quarter execution, then ranks the strongest explanations with
        evidence for and against each one.
      </HowItsMade>
    </div>
  );
}

function Investigation({ gameId }: { gameId: string }) {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["investigate", gameId],
    queryFn: () => api.investigate(gameId),
  });

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-16 rounded-xl" />
        <Skeleton className="h-40 rounded-xl" />
        <Skeleton className="h-40 rounded-xl" />
      </div>
    );
  }
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data) return null;

  const maxScore = Math.max(0.01, ...data.explanations.map((e: any) => e.score));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-bold">Final: {data.final}</h2>
        <button
          onClick={() => navigate("/ai", {
            state: {
              question: `Why did ${data.teams.find((t: any) => !t.winner)?.name} lose this game?`,
              context: { game_id: gameId },
            },
          })}
          className="text-xs px-3 py-1.5 rounded-lg border border-edge text-ink-2 hover:text-ink transition-colors"
        >
          <span style={{ color: "var(--series-7)" }}>✦</span> Ask AI to explain
        </button>
      </div>

      <Card>
        <CardTitle>Why it happened, strongest explanations first</CardTitle>
        <div className="space-y-3">
          {data.explanations.map((e: any) => (
            <div key={e.key} className="border border-edge rounded-lg p-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium">{e.title}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-2 text-ink-2">
                  favored {e.favored}
                </span>
                <div className="ml-auto w-24 h-1.5 rounded-full bg-surface-2 overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${(e.score / maxScore) * 100}%`, background: "var(--series-1)" }} />
                </div>
              </div>
              <p className="text-xs text-ink-2 mt-1.5">{e.summary}</p>
              {e.evidence_for?.length > 0 && (
                <div className="mt-2 grid sm:grid-cols-2 gap-x-4 gap-y-0.5">
                  {e.evidence_for.map((ev: any, i: number) => (
                    <div key={i} className="text-[11px] text-ink-muted flex justify-between gap-2">
                      <span>{ev.label}</span><span className="tnum text-ink-2">{String(ev.value)}</span>
                    </div>
                  ))}
                </div>
              )}
              {e.evidence_against?.length > 0 && (
                <div className="mt-1.5">
                  {e.evidence_against.map((ev: any, i: number) => (
                    <div key={i} className="text-[11px] flex gap-1.5 items-center" style={{ color: "var(--serious)" }}>
                      <span>⚠</span><span>{ev.label}: {String(ev.value)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardTitle tip="FOUR_FACTORS">Four factors</CardTitle>
          <table className="w-full text-xs tnum">
            <thead>
              <tr className="text-ink-muted text-left">
                <th className="py-1 font-medium">Team</th>
                <th className="text-right font-medium">
                  <span className="inline-flex items-center gap-1">
                    Eff. FG% <GlossaryTip term="EFG_PCT" />
                  </span>
                </th>
                <th className="text-right font-medium">TOV%</th>
                <th className="text-right font-medium">ORB%</th>
                <th className="text-right font-medium">FT rate</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.four_factors).map(([abbr, ff]: [string, any]) => (
                <tr key={abbr} className="border-t border-edge">
                  <td className="py-1.5 font-medium">{abbr}</td>
                  <td className="text-right">{pct(ff.efg)}</td>
                  <td className="text-right">{pct(ff.tov)}</td>
                  <td className="text-right">{pct(ff.orb)}</td>
                  <td className="text-right">{num(ff.ft, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card>
          <CardTitle>Star lines vs season average</CardTitle>
          <div className="space-y-1">
            {data.star_lines.map((l: any) => (
              <div key={`${l.player_id}`} className="text-xs flex items-center gap-2">
                <span className="w-10 text-ink-muted">{l.team}</span>
                <span className="flex-1 truncate">{l.name}</span>
                <span className="tnum">{l.pts} pts</span>
                <span className={`tnum w-12 text-right ${l.delta >= 0 ? "text-delta-up" : "text-delta-down"}`}>
                  {signed(l.delta)}
                </span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-ink-muted mt-2">Delta vs the player's season scoring average.</p>
        </Card>
      </div>
      <p className="text-[11px] text-ink-muted">{data.method}</p>
    </div>
  );
}
