import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { Card, CardTitle, ErrorState, SkeletonCard } from "../ui";

export default function ShotDifficultyExplainer({ playerId, filters }: { playerId: number; filters: { season?: string; season_type?: string } }) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["shotExplainer", playerId, filters.season, filters.season_type],
    queryFn: () => api.shotExplainer(playerId, filters), staleTime: 30 * 60 * 1000,
  });
  if (isLoading) return <SkeletonCard lines={5} />;
  if (error) return <ErrorState message={error.message} onRetry={() => void refetch()} />;
  if (!data || !data.available) return <Card><CardTitle>Feature explanation unavailable</CardTitle><p className="text-sm text-ink-muted">{data?.reason ?? "The optional feature explainer is not available for this model."}</p><p className="text-xs text-ink-muted mt-2">Shot-quality estimates can still be available without this explanation.</p></Card>;
  const contributions = data.contributions ?? [];
  const max = Math.max(...contributions.map((contribution) => contribution.mean_abs_impact), 0.0001);
  return (
    <Card>
      <CardTitle>Feature attribution magnitude (SHAP)</CardTitle>
      <p className="text-xs text-ink-2 mb-4">Mean absolute attribution across {data.shots_explained} shots, in model-output units. Larger values indicate greater influence on the model output; these magnitudes do not show a positive or negative direction.</p>
      {contributions.length ? <div className="space-y-3">{contributions.map((contribution) => <div key={contribution.feature} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_3rem] items-center gap-2 text-xs">
        <span className="text-ink-2 break-words">{contribution.label}</span>
        <div aria-hidden="true" className="h-2 rounded-full bg-surface-2 overflow-hidden"><div className="h-full rounded-full bg-[var(--series-1)]" style={{ width: `${contribution.mean_abs_impact / max * 100}%` }} /></div>
        <span className="tnum text-right">{contribution.mean_abs_impact.toFixed(3)}</span>
      </div>)}</div> : <p className="text-sm text-ink-muted">No feature attributions available.</p>}
      <p className="text-xs text-ink-muted mt-4">These values describe the model, not causal effects or pure shooting talent. Unmeasured defensive pressure and other context can affect results. Values are not percentage-point changes in make probability.</p>
    </Card>
  );
}
