import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { num, pct, signed } from "../../lib/format";
import SearchPalette from "../SearchPalette";
import ShotChart from "../ShotChart";
import { Card, CardTitle, ErrorState, GlossaryTip, Skeleton } from "../ui";

const A_COLOR = "var(--series-1)";
const B_COLOR = "var(--series-6)";

const ROWS: { key: string[]; label: string; fmt: (v: any) => string; tip?: string; from: "per" | "shoot" | "eff" }[] = [
  { key: ["PTS"], label: "Points", fmt: (v) => num(v), from: "per" },
  { key: ["REB"], label: "Rebounds", fmt: (v) => num(v), from: "per" },
  { key: ["AST"], label: "Assists", fmt: (v) => num(v), from: "per" },
  { key: ["STL"], label: "Steals", fmt: (v) => num(v), from: "per" },
  { key: ["BLK"], label: "Blocks", fmt: (v) => num(v), from: "per" },
  { key: ["TOV"], label: "Turnovers", fmt: (v) => num(v), from: "per" },
  { key: ["PF"], label: "Fouls", fmt: (v) => num(v), from: "per" },
  { key: ["MIN"], label: "Minutes", fmt: (v) => num(v), from: "per" },
  { key: ["TS_PCT"], label: "True shooting", fmt: pct, tip: "TS_PCT", from: "shoot" },
  { key: ["EFG_PCT"], label: "Effective FG", fmt: pct, tip: "EFG_PCT", from: "shoot" },
  { key: ["FG3_PCT"], label: "3PT %", fmt: pct, from: "shoot" },
  { key: ["FT_RATE"], label: "FT rate", fmt: (v) => num(v, 2), tip: "FT_RATE", from: "shoot" },
  { key: ["AST_TO"], label: "AST/TO", fmt: (v) => num(v, 2), tip: "AST_TO", from: "shoot" },
  { key: ["usg_pct"], label: "Usage", fmt: pct, tip: "USG_PCT", from: "eff" },
  { key: ["off_rating"], label: "Off. rating", fmt: (v) => num(v), tip: "OFF_RATING", from: "eff" },
  { key: ["def_rating"], label: "Def. rating", fmt: (v) => num(v), tip: "DEF_RATING", from: "eff" },
  { key: ["net_rating"], label: "Net rating", fmt: (v) => signed(v), tip: "NET_RATING", from: "eff" },
];

function valueOf(block: any, row: (typeof ROWS)[number], perMode: string) {
  const src =
    row.from === "per" ? block?.stats?.[perMode] :
    row.from === "shoot" ? block?.stats?.shooting :
    block?.efficiency;
  return src?.[row.key[0]] ?? null;
}

/** Classic two-player head-to-head comparison. */
export default function HeadToHead() {
  const [params, setParams] = useSearchParams();
  const a = params.get("a") ? Number(params.get("a")) : null;
  const b = params.get("b") ? Number(params.get("b")) : null;
  const [picking, setPicking] = useState<"a" | "b" | null>(null);
  const [perMode, setPerMode] = useState<"per_game" | "per_75">("per_game");

  const { data, isLoading, error } = useQuery({
    queryKey: ["compare", a, b],
    queryFn: () => api.compare(a!, b!),
    enabled: !!a && !!b,
  });

  const setPlayer = (slot: "a" | "b", id: number) => {
    const next = new URLSearchParams(params);
    next.set(slot, String(id));
    setParams(next);
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <PlayerSlot color={A_COLOR} info={data?.a?.info} label="Player A" onPick={() => setPicking("a")} />
        <PlayerSlot color={B_COLOR} info={data?.b?.info} label="Player B" onPick={() => setPicking("b")} />
      </div>

      {!a || !b ? (
        <Card className="text-center py-12 text-ink-muted text-sm">
          Pick two players to compare their stats, efficiency and shot profiles side by side.
        </Card>
      ) : isLoading ? (
        <div className="space-y-3"><Skeleton className="h-64 rounded-lg" /><Skeleton className="h-64 rounded-lg" /></div>
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : data ? (
        <>
          <Card>
            <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
              <CardTitle>Head to head · {data.season}</CardTitle>
              <div className="flex gap-1 text-xs">
                {(["per_game", "per_75"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setPerMode(m)}
                    className={`px-2.5 py-1 rounded-md border transition-colors ${
                      perMode === m ? "border-ink-muted text-ink font-medium" : "border-edge text-ink-muted"
                    }`}
                  >
                    {m === "per_game" ? "Per game" : "Per 75"}
                  </button>
                ))}
                <GlossaryTip term="PER_75" />
              </div>
            </div>
            <div className="space-y-1.5">
              {ROWS.map((row) => {
                const va = valueOf(data.a, row, perMode);
                const vb = valueOf(data.b, row, perMode);
                if (va === null && vb === null) return null;
                const lowerBetter = ["Turnovers", "Fouls", "Def. rating"].includes(row.label);
                const total = Math.abs(va ?? 0) + Math.abs(vb ?? 0) || 1;
                const aBetter = lowerBetter ? (va ?? 0) < (vb ?? 0) : (va ?? 0) > (vb ?? 0);
                return (
                  <div key={row.label} className="grid grid-cols-[70px_1fr_130px_1fr_70px] items-center gap-2 text-xs">
                    <span className={`tnum text-right ${aBetter ? "font-bold" : "text-ink-2"}`}>{row.fmt(va)}</span>
                    <div className="h-2 rounded-full bg-surface-2 overflow-hidden flex justify-end">
                      <div className="bar-fill h-full rounded-full" style={{ width: `${(Math.abs(va ?? 0) / total) * 100}%`, background: A_COLOR }} />
                    </div>
                    <span className="text-center text-ink-muted flex items-center justify-center gap-1">
                      {row.label}{row.tip && <GlossaryTip term={row.tip} />}
                    </span>
                    <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
                      <div className="bar-fill h-full rounded-full" style={{ width: `${(Math.abs(vb ?? 0) / total) * 100}%`, background: B_COLOR }} />
                    </div>
                    <span className={`tnum ${!aBetter ? "font-bold" : "text-ink-2"}`}>{row.fmt(vb)}</span>
                  </div>
                );
              })}
            </div>
          </Card>

          <div className="grid md:grid-cols-2 gap-4">
            {(["a", "b"] as const).map((slot) => (
              <Card key={slot}>
                <CardTitle>
                  <span style={{ color: slot === "a" ? A_COLOR : B_COLOR }}>●</span>{" "}
                  {data[slot].info?.name}: shot zones vs league
                </CardTitle>
                <ShotChart points={data[slot].shot_points ?? []} zones={data[slot].zones ?? []} view="zones" onViewChange={() => {}} height={360} />
              </Card>
            ))}
          </div>
          <p className="text-[11px] text-ink-muted">
            Bold value = better in that category (turnovers, fouls and defensive rating: lower is better).
            A category edge doesn't make a player universally better; check volume, role and position context.
          </p>
        </>
      ) : null}

      <SearchPalette
        open={picking !== null}
        onClose={() => setPicking(null)}
        onPick={(pid) => picking && setPlayer(picking, pid)}
      />
    </div>
  );
}

function PlayerSlot({ info, label, color, onPick }: any) {
  return (
    <button onClick={onPick} className="card p-4 flex items-center gap-3 hover:border-ink-muted transition-colors text-left">
      {info ? (
        <>
          <img src={info.headshot} alt="" className="w-14 h-14 rounded-full object-cover bg-surface-2" />
          <div>
            <div className="text-sm font-semibold" style={{ color }}>{info.name}</div>
            <div className="text-xs text-ink-muted">{info.team ?? "-"} · {info.position ?? "-"}</div>
            <div className="text-[10px] text-ink-muted mt-0.5 underline underline-offset-2">Change player</div>
          </div>
        </>
      ) : (
        <>
          <div className="w-14 h-14 rounded-full bg-surface-2 grid place-items-center text-ink-muted text-xl">+</div>
          <div className="text-sm text-ink-muted">{label}: click to choose</div>
        </>
      )}
    </button>
  );
}
