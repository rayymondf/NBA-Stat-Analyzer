import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";

/** Shared season / season-type selection backed by URL search params. */
export function useAnalysisPeriod() {
  const [params, setParams] = useSearchParams();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const season = params.get("season") || meta.data?.current_season;
  const season_type = params.get("season_type") || "Regular Season";
  const update = (key: "season" | "season_type", value: string) => {
    const next = new URLSearchParams(params);
    next.set(key, value);
    setParams(next);
  };
  return { filters: { season, season_type }, meta, update };
}
