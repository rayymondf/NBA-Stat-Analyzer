import { useQuery } from "@tanstack/react-query";
import { api, type Filters } from "../../lib/api";
import { Segmented } from "../ui";

export type PerMode = "per_game" | "per_36" | "per_75" | "per_100";

export interface ProfileFilters extends Filters {
  perMode: PerMode;
}

const TEAMS = ["ATL","BOS","BKN","CHA","CHI","CLE","DAL","DEN","DET","GSW","HOU","IND","LAC","LAL","MEM","MIA","MIL","MIN","NOP","NYK","OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS"];

const selectCls =
  "bg-surface border border-edge rounded-lg px-2.5 py-1.5 text-xs text-ink outline-none hover:border-ink-muted transition-colors";

export default function FilterBar({ filters, onChange }: {
  filters: ProfileFilters;
  onChange: (f: ProfileFilters) => void;
}) {
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const set = (patch: Partial<ProfileFilters>) => onChange({ ...filters, ...patch });

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        className={selectCls}
        value={filters.season ?? ""}
        onChange={(e) => set({ season: e.target.value })}
      >
        {(meta?.seasons ?? [filters.season]).map((s) => (
          <option key={s} value={s ?? ""}>{s}</option>
        ))}
      </select>

      <Segmented
        options={[
          { value: "Regular Season", label: "Regular" },
          { value: "Playoffs", label: "Playoffs" },
        ]}
        value={(filters.season_type ?? "Regular Season") as string}
        onChange={(v) => set({ season_type: v })}
      />

      <Segmented
        options={[
          { value: "per_game" as PerMode, label: "Per game" },
          { value: "per_36" as PerMode, label: "Per 36" },
          { value: "per_75" as PerMode, label: "Per 75" },
          { value: "per_100" as PerMode, label: "Per 100" },
        ]}
        value={filters.perMode}
        onChange={(v) => set({ perMode: v })}
      />

      <select
        className={selectCls}
        value={filters.location ?? ""}
        onChange={(e) => set({ location: e.target.value || undefined })}
      >
        <option value="">Home + away</option>
        <option value="home">Home only</option>
        <option value="away">Away only</option>
      </select>

      <select
        className={selectCls}
        value={filters.outcome ?? ""}
        onChange={(e) => set({ outcome: e.target.value || undefined })}
      >
        <option value="">Wins + losses</option>
        <option value="W">Wins only</option>
        <option value="L">Losses only</option>
      </select>

      <select
        className={selectCls}
        value={filters.starter === undefined ? "" : String(filters.starter)}
        onChange={(e) => set({ starter: e.target.value === "" ? undefined : e.target.value === "true" })}
      >
        <option value="">Starter + bench</option>
        <option value="true">As starter</option>
        <option value="false">Off the bench</option>
      </select>

      <select
        className={selectCls}
        value={filters.last_n ?? ""}
        onChange={(e) => set({ last_n: e.target.value ? Number(e.target.value) : undefined })}
      >
        <option value="">Full season</option>
        <option value="5">Last 5 games</option>
        <option value="10">Last 10 games</option>
        <option value="20">Last 20 games</option>
      </select>

      <select
        className={selectCls}
        value={filters.opponent ?? ""}
        onChange={(e) => set({ opponent: e.target.value || undefined })}
      >
        <option value="">All opponents</option>
        {TEAMS.map((t) => <option key={t} value={t}>vs {t}</option>)}
      </select>

      <div className="flex items-center gap-1">
        <input
          type="date"
          className={selectCls}
          value={filters.date_from ?? ""}
          onChange={(e) => set({ date_from: e.target.value || undefined })}
          title="From date"
        />
        <span className="text-ink-muted text-xs">–</span>
        <input
          type="date"
          className={selectCls}
          value={filters.date_to ?? ""}
          onChange={(e) => set({ date_to: e.target.value || undefined })}
          title="To date"
        />
      </div>

      {(filters.location || filters.outcome || filters.starter !== undefined ||
        filters.last_n || filters.opponent || filters.date_from || filters.date_to) && (
        <button
          className="text-xs text-ink-muted hover:text-ink underline underline-offset-2"
          onClick={() => set({
            location: undefined, outcome: undefined, starter: undefined,
            last_n: undefined, opponent: undefined, date_from: undefined,
            date_to: undefined,
          })}
        >
          Reset filters
        </button>
      )}
    </div>
  );
}
