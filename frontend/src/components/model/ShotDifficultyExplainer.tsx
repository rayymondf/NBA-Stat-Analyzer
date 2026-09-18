import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { Card, CardTitle, ErrorState, SkeletonCard } from "../ui";

/**
 * SHAP-based shot-difficulty explainer: which shot-context features most drive
 * the model's per-shot make-probability estimate. This attributes the MODEL's
 * estimate to its inputs; it is not a causal or pure-talent measure.
 */
export default function ShotDifficultyExplainer({
  playerId, filters,
}: {
  playerId: number;
  filters: { season?: string; season_type?: string };
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["shotExplainer", playerId, filters.season, filters.season_type],
    queryFn: () => api.shotExplainer(playerId, {
      season: filters.season,
      season_type: filters.season_type,
    }),
    staleTime: 30 * 60 * 1000,
  });

  if (isLoading) return <SkeletonCard lines={5} />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data || data.available === false) return null;

  const contributions = data.contributions ?? [];
  if (!contributions.length) return null;
  const max = Math.max(...contributions.map((c) => c.mean_abs_impact), 0.0001);

  return (
    <Card>
      <CardTitle tip="XFG">What drives the difficulty (SHAP)</CardTitle>
      <p className="text-xs text-ink-2 mb-3">
        Average impact of each shot-context feature on the model's make-probability
        estimate, over {data.shots_explained} shots.
      </p>
      <div className="space-y-2">
        {contributions.map((c) => {
          const up = c.mean_signed_impact >= 0;
          return (
            <div key={c.feature} className="flex items-center gap-2">
              <div className="w-32 shrink-0 text-xs text-ink-2 truncate" title={c.label}>
                {c.label}
              </div>
              <div className="flex-1 h-2 rounded-full bg-surface-2 overflow-hidden">
                <div
                  className="bar-fill h-full rounded-full"
                  style={{
                    width: `${(c.mean_abs_impact / max) * 100}%`,
                    background: up ? "var(--delta-up)" : "var(--delta-down)",
                  }}
                />
              </div>
              <div
                className="w-16 shrink-0 text-[10px] tnum text-right"
                style={{ color: up ? "var(--delta-up)" : "var(--delta-down)" }}
                title={c.direction}
              >
                {up ? "+" : "−"}{c.mean_abs_impact.toFixed(3)}
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-ink-muted mt-3 leading-relaxed">
        Attributes the model's estimate to its inputs. Not a causal or pure-talent
        measure; the model never sees defenders, contest quality, or video.
      </p>
    </Card>
  );
}
