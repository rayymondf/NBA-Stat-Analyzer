import { useAnalysisPeriod } from "./useAnalysisPeriod";

export default function AnalysisPeriod() {
  const { filters, meta, update } = useAnalysisPeriod();
  const seasons = [...new Set([filters.season, ...(meta.data?.seasons ?? [])].filter((value): value is string => !!value))];
  const types = [...new Set([filters.season_type, ...(meta.data?.season_types ?? ["Regular Season", "Playoffs"])])];
  return (
    <fieldset className="flex flex-wrap gap-3">
      <legend className="sr-only">Analysis period</legend>
      <label className="text-xs text-ink-muted flex flex-col gap-1.5">
        Season
        <select className="rounded-lg border border-outline-variant bg-surface-container px-3 py-2 text-sm text-ink min-h-11" value={filters.season ?? ""} onChange={(event) => update("season", event.target.value)}>
          {!filters.season && <option value="">Current season</option>}
          {seasons.map((season) => <option key={season} value={season}>{season}</option>)}
        </select>
      </label>
      <label className="text-xs text-ink-muted flex flex-col gap-1.5">
        Season type
        <select className="rounded-lg border border-outline-variant bg-surface-container px-3 py-2 text-sm text-ink min-h-11" value={filters.season_type} onChange={(event) => update("season_type", event.target.value)}>
          {types.map((type) => <option key={type} value={type}>{type}</option>)}
        </select>
      </label>
      {meta.isError && <button className="text-xs underline self-end py-3" onClick={() => void meta.refetch()}>Retry season options</button>}
    </fieldset>
  );
}
