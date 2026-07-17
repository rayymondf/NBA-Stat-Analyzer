import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { pct, signed } from "../../lib/format";
import { Card, ErrorState, SkeletonCard } from "../ui";
import type { ProfileFilters } from "./FilterBar";

type SortKey = "date" | "pts" | "reb" | "ast" | "min" | "plus_minus" | "ts_pct";

export default function GameLogSection({ playerId, filters }: {
  playerId: number;
  filters: ProfileFilters;
}) {
  const { perMode, ...apiFilters } = filters;
  const [sort, setSort] = useState<SortKey>("date");
  const [desc, setDesc] = useState(true);

  const { data, isLoading, error } = useQuery({
    queryKey: ["gamelog", playerId, apiFilters],
    queryFn: () => api.gamelog(playerId, apiFilters),
  });

  if (isLoading) return <SkeletonCard lines={10} />;
  if (error) return <ErrorState message={(error as Error).message} />;
  const rows = data?.rows ?? [];
  if (!rows.length) return <ErrorState message="No games match these filters." />;

  const sorted = [...rows].sort((a, b) => {
    if (sort === "date") return desc ? (a.date < b.date ? 1 : -1) : (a.date > b.date ? 1 : -1);
    const av = a[sort] ?? -999, bv = b[sort] ?? -999;
    return desc ? bv - av : av - bv;
  });

  const TH = ({ k, children, align = "right" }: { k?: SortKey; children: any; align?: string }) => (
    <th
      className={`py-2 px-2 font-medium text-${align} ${k ? "cursor-pointer hover:text-ink select-none" : ""}`}
      onClick={k ? () => { sort === k ? setDesc(!desc) : (setSort(k), setDesc(true)); } : undefined}
    >
      {children}{sort === k ? (desc ? " ↓" : " ↑") : ""}
    </th>
  );

  return (
    <Card className="overflow-x-auto !p-0">
      <table className="w-full text-xs min-w-[760px]">
        <thead>
          <tr className="text-ink-muted border-b border-edge">
            <TH k="date" align="left">Date</TH>
            <th className="py-2 px-2 font-medium text-left">Matchup</th>
            <th className="py-2 px-2 font-medium">W/L</th>
            <TH k="min">MIN</TH>
            <TH k="pts">PTS</TH>
            <TH k="reb">REB</TH>
            <TH k="ast">AST</TH>
            <th className="py-2 px-2 font-medium text-right">FG</th>
            <th className="py-2 px-2 font-medium text-right">3PT</th>
            <th className="py-2 px-2 font-medium text-right">FT</th>
            <th className="py-2 px-2 font-medium text-right">TOV</th>
            <th className="py-2 px-2 font-medium text-right">PF</th>
            <TH k="plus_minus">+/-</TH>
            <TH k="ts_pct">TS%</TH>
          </tr>
        </thead>
        <tbody className="tnum">
          {sorted.map((r) => (
            <tr key={r.game_id} className="border-b border-edge last:border-0 hover:bg-surface-2 transition-colors">
              <td className="py-1.5 px-2 whitespace-nowrap">
                <Link to={`/player/${playerId}/game/${r.game_id}`}
                  className="hover:underline underline-offset-2" style={{ color: "var(--series-1)" }}>
                  {r.date}
                </Link>
              </td>
              <td className="px-2 text-ink-2 whitespace-nowrap">{r.matchup}{r.started === false ? " · bench" : ""}</td>
              <td className={`px-2 text-center font-medium ${r.wl === "W" ? "text-delta-up" : "text-delta-down"}`}>{r.wl}</td>
              <td className="px-2 text-right">{r.min}</td>
              <td className="px-2 text-right font-semibold">{r.pts}</td>
              <td className="px-2 text-right">{r.reb}</td>
              <td className="px-2 text-right">{r.ast}</td>
              <td className="px-2 text-right text-ink-2">{r.fgm}-{r.fga}</td>
              <td className="px-2 text-right text-ink-2">{r.fg3m}-{r.fg3a}</td>
              <td className="px-2 text-right text-ink-2">{r.ftm}-{r.fta}</td>
              <td className="px-2 text-right">{r.tov}</td>
              <td className="px-2 text-right">{r.pf}</td>
              <td className="px-2 text-right">{signed(r.plus_minus, 0)}</td>
              <td className="px-2 text-right">{pct(r.ts_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11px] text-ink-muted p-3">
        Click a date to open the full game view — shot chart, scoring timeline and boxscore line.
      </p>
    </Card>
  );
}
