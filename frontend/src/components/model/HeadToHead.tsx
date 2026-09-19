import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { ComparisonBlock, PlayerBio, PlayerSummary } from "../../lib/types";
import { num, pct, signed } from "../../lib/format";
import SearchPalette from "../SearchPalette";
import ShotChart from "../ShotChart";
import { Card, CardTitle, ErrorState, GlossaryTip, Segmented, Skeleton } from "../ui";
import AnalysisPeriod from "./AnalysisPeriod";
import { useAnalysisPeriod } from "./useAnalysisPeriod";

const A_COLOR = "var(--series-1)";
const B_COLOR = "var(--series-6)";

const ROWS: { key: string; label: string; fmt: (v: number | null | undefined) => string; tip?: string; from: "per" | "shoot" | "eff" }[] = [
  { key: "PTS", label: "Points", fmt: (v) => num(v), from: "per" },
  { key: "REB", label: "Rebounds", fmt: (v) => num(v), from: "per" },
  { key: "AST", label: "Assists", fmt: (v) => num(v), from: "per" },
  { key: "STL", label: "Steals", fmt: (v) => num(v), from: "per" },
  { key: "BLK", label: "Blocks", fmt: (v) => num(v), from: "per" },
  { key: "TOV", label: "Turnovers", fmt: (v) => num(v), from: "per" },
  { key: "PF", label: "Fouls", fmt: (v) => num(v), from: "per" },
  { key: "MIN", label: "Minutes", fmt: (v) => num(v), from: "per" },
  { key: "TS_PCT", label: "True shooting", fmt: pct, tip: "TS_PCT", from: "shoot" },
  { key: "EFG_PCT", label: "Effective FG", fmt: pct, tip: "EFG_PCT", from: "shoot" },
  { key: "FG3_PCT", label: "3PT %", fmt: pct, from: "shoot" },
  { key: "FT_RATE", label: "FT rate", fmt: (v) => num(v, 2), tip: "FT_RATE", from: "shoot" },
  { key: "AST_TO", label: "AST/TO", fmt: (v) => num(v, 2), tip: "AST_TO", from: "shoot" },
  { key: "usg_pct", label: "Usage", fmt: pct, tip: "USG_PCT", from: "eff" },
  { key: "off_rating", label: "Off. rating", fmt: (v) => num(v), tip: "OFF_RATING", from: "eff" },
  { key: "def_rating", label: "Def. rating", fmt: (v) => num(v), tip: "DEF_RATING", from: "eff" },
  { key: "net_rating", label: "Net rating", fmt: (v) => signed(v), tip: "NET_RATING", from: "eff" },
];

function valueOf(block: ComparisonBlock, row: (typeof ROWS)[number], perMode: "per_game" | "per_75") {
  const src =
    row.from === "per" ? block?.stats?.[perMode] :
    row.from === "shoot" ? block?.stats?.shooting :
    block?.efficiency;
  return src?.[row.key] ?? null;
}

function StatsTable({ data, rows, perMode }: { data: { a: ComparisonBlock; b: ComparisonBlock }; rows: typeof ROWS; perMode: "per_game" | "per_75" }) {
  return (
    <table className="w-full table-fixed text-xs sm:text-sm">
      <caption className="sr-only">Player comparison statistics</caption>
      <thead><tr className="border-b border-edge"><th scope="col" className="text-left py-3 w-[38%]">Metric</th><th scope="col" className="px-1 py-3 break-words" style={{ color: A_COLOR }}>{data.a.info.name ?? "Player A"}</th><th scope="col" className="px-1 py-3 break-words" style={{ color: B_COLOR }}>{data.b.info.name ?? "Player B"}</th></tr></thead>
      <tbody>{rows.map((row) => {
        const va = valueOf(data.a, row, perMode);
        const vb = valueOf(data.b, row, perMode);
        const lowerBetter = ["TOV", "PF", "def_rating"].includes(row.key);
        const comparable = va !== null && vb !== null && va !== vb;
        const aBetter = comparable && (lowerBetter ? va < vb : va > vb);
        const bBetter = comparable && !aBetter;
        const total = Math.abs(va ?? 0) + Math.abs(vb ?? 0) || 1;
        return <tr key={row.key} className="border-b border-edge last:border-0">
          <th scope="row" className="text-left font-normal text-ink-2 py-3 pr-2"><span>{row.label}</span>{row.tip && <GlossaryTip term={row.tip} />}</th>
          {([{ value: va, better: aBetter, color: A_COLOR }, { value: vb, better: bBetter, color: B_COLOR }]).map((cell, index) => <td key={index} className={`text-center px-2 py-3 tnum ${cell.better ? "font-bold" : "text-ink-2"}`}>
            {row.fmt(cell.value)}<div aria-hidden="true" className="h-1 mt-2 rounded-full bg-surface-2 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${Math.abs(cell.value ?? 0) / total * 100}%`, background: cell.color }} /></div>
          </td>)}
        </tr>;
      })}</tbody>
    </table>
  );
}

export default function HeadToHead() {
  const [params, setParams] = useSearchParams();
  const validId = (value: string | null) => { const id = Number(value); return Number.isSafeInteger(id) && id > 0 ? id : null; };
  const a = validId(params.get("a"));
  const b = validId(params.get("b"));
  const [picking, setPicking] = useState<"a" | "b" | null>(null);
  const [perMode, setPerMode] = useState<"per_game" | "per_75">("per_game");
  const { filters } = useAnalysisPeriod();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["compare", a, b, filters.season, filters.season_type],
    queryFn: () => api.compare(a!, b!, filters), enabled: !!a && !!b,
  });
  const summaryA = useQuery({ queryKey: ["summary", a, filters.season, filters.season_type], queryFn: () => api.summary(a!, filters), enabled: !!a });
  const summaryB = useQuery({ queryKey: ["summary", b, filters.season, filters.season_type], queryFn: () => api.summary(b!, filters), enabled: !!b });
  const setPlayer = (slot: "a" | "b", id: number) => {
    const next = new URLSearchParams(params);
    next.set(slot, String(id));
    setParams(next);
  };
  return (
    <div className="space-y-5 min-w-0">
      <AnalysisPeriod />
      <div className="grid grid-cols-2 gap-3 sm:gap-4">
        <PlayerSlot color={A_COLOR} info={data?.a.info ?? summaryA.data} label="Player A" onPick={() => setPicking("a")} />
        <PlayerSlot color={B_COLOR} info={data?.b.info ?? summaryB.data} label="Player B" onPick={() => setPicking("b")} />
      </div>
      {(summaryA.isError || summaryB.isError) && <ErrorState message="Some player details are unavailable." onRetry={() => { void summaryA.refetch(); void summaryB.refetch(); }} />}
      {!a || !b ? <Card className="text-center py-12"><h2 className="font-display font-bold text-xl">Choose your matchup</h2><p className="text-sm text-ink-muted mt-2">Pick two players to compare their stats, efficiency and shot profiles.</p></Card>
        : isLoading ? <div className="space-y-3"><Skeleton className="h-64 rounded-lg" /><Skeleton className="h-64 rounded-lg" /></div>
        : error ? <ErrorState message={error.message} onRetry={() => void refetch()} />
        : data ? <>
          <Card className="min-w-0">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <CardTitle>{data.season} · {data.season_type}</CardTitle>
              <div className="flex items-center gap-1"><Segmented options={[{ value: "per_game", label: "Per game" }, { value: "per_75", label: "Per 75" }]} value={perMode} onChange={setPerMode} /><GlossaryTip term="PER_75" /></div>
            </div>
            <p className="text-xs text-ink-muted">Games: {data.a.info.name ?? "Player A"} {data.a.stats.games} · {data.b.info.name ?? "Player B"} {data.b.stats.games}</p>
            {data.a.stats.games === 0 && data.b.stats.games === 0 && <p className="text-sm text-ink-muted mt-3">No games available for either player in this period.</p>}
            <StatsTable data={data} rows={ROWS.slice(0, 3)} perMode={perMode} />
            <details className="border-t border-edge mt-3 pt-3"><summary className="cursor-pointer font-semibold text-sm py-2">Advanced stats & efficiency</summary><StatsTable data={data} rows={ROWS.slice(3)} perMode={perMode} /></details>
            <p className="text-xs text-ink-muted mt-4">Bold indicates a category edge when both values are available. Lower is favored for turnovers, fouls and defensive rating. Role, volume and team context still matter.</p>
          </Card>
          <div className="grid md:grid-cols-2 gap-4 min-w-0">{(["a", "b"] as const).map((slot) => <Card key={slot} className="min-w-0">
            <CardTitle>{slot === "a" ? "Player A" : "Player B"} · {data[slot].info.name}: shot chart</CardTitle>
            {data[slot].shot_points.length ? <ShotChart points={data[slot].shot_points} zones={data[slot].zones ?? []} defaultView="zones" height={360} /> : <p className="text-sm text-ink-muted py-10">No shot data for this player and period.</p>}
          </Card>)}</div>
        </> : null}
      <SearchPalette open={picking !== null} onClose={() => setPicking(null)} onPick={(id) => { if (picking) setPlayer(picking, id); }} />
    </div>
  );
}

function PlayerSlot({ info, label, color, onPick }: { info?: PlayerBio | PlayerSummary; label: string; color: string; onPick: () => void }) {
  return (
    <button onClick={onPick} aria-label={`${label}: ${info?.name ?? "choose player"}`} className="card min-w-0 p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center gap-3 hover:border-ink-muted transition-colors text-left">
      {info ? <img src={info.headshot} alt="" className="w-12 h-12 rounded-full object-cover bg-surface-2" /> : <span className="w-12 h-12 rounded-full bg-surface-2 grid place-items-center text-xl">+</span>}
      <span className="min-w-0"><span className="block text-xs text-ink-muted mb-1">{label}</span><span className="block text-sm font-bold break-words" style={{ color }}>{info?.name ?? "Choose player"}</span>{info && <span className="block text-xs text-ink-muted mt-1">{info.team ?? "?"} · {info.position ?? "?"}</span>}<span className="block text-xs underline underline-offset-2 mt-2">{info ? "Change player" : "Search players"}</span></span>
    </button>
  );
}
