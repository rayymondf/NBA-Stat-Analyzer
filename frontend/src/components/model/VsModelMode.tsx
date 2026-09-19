import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Filters } from "../../lib/api";
import SearchPalette from "../SearchPalette";
import ShotChart from "../ShotChart";
import { AnimatedNumber, Card, CardTitle, ErrorState, Segmented, Skeleton } from "../ui";
import DeltaHistogram from "./DeltaHistogram";
import ZoneDeltaBars from "./ZoneDeltaBars";
import AnalysisPeriod from "./AnalysisPeriod";
import { useAnalysisPeriod } from "./useAnalysisPeriod";
import ShotDifficultyExplainer from "./ShotDifficultyExplainer";

function ShotSelectionCard({ playerId, name, filters }: { playerId: number; name?: string; filters: Filters }) {
  const [result, setResult] = useState<"all" | "made" | "missed">("all");
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["shooting", playerId, filters.season, filters.season_type],
    queryFn: () => api.shooting(playerId, { ...filters }),
    staleTime: 30 * 60 * 1000,
  });
  const points = useMemo(() => (data?.points ?? []).filter((point) => result === "all" || point.made === (result === "made")), [data, result]);
  if (isLoading) return <Skeleton className="h-80 rounded-lg" />;
  if (error) return <ErrorState message={error.message} onRetry={() => void refetch()} />;
  return (
    <Card className="min-w-0">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <CardTitle>{name ? `${name}'s shot selection` : "Shot selection"}</CardTitle>
        <Segmented options={[{ value: "all", label: "All shots" }, { value: "made", label: "Makes" }, { value: "missed", label: "Misses" }]} value={result} onChange={setResult} />
      </div>
      {points.length ? <ShotChart points={points} zones={data?.zones ?? []} defaultView="dots" height={420} /> : <p className="text-sm text-ink-muted py-8">No shots match this view.</p>}
      <p className="text-xs text-ink-muted mt-2">Shots from the selected period. Zone colors compare actual field-goal percentage with the league average.</p>
    </Card>
  );
}

export default function VsModelMode() {
  const [params, setParams] = useSearchParams();
  const rawId = Number(params.get("player"));
  const playerId = Number.isSafeInteger(rawId) && rawId > 0 ? rawId : null;
  const [picking, setPicking] = useState(false);
  const { filters } = useAnalysisPeriod();
  const summary = useQuery({
    queryKey: ["summary", playerId, filters.season, filters.season_type],
    queryFn: () => api.summary(playerId!, filters), enabled: !!playerId,
  });
  const { data: quality, isLoading, error, refetch } = useQuery({
    queryKey: ["shotQuality", playerId, filters.season, filters.season_type],
    queryFn: () => api.shotQuality(playerId!, filters), enabled: !!playerId, staleTime: 30 * 60 * 1000,
  });
  const model = useQuery({ queryKey: ["modelInfo"], queryFn: api.modelInfo, staleTime: 30 * 60 * 1000 });
  const modelInfo = model.data?.available ? model.data : null;
  const bio = summary.data;
  const name = bio?.name ?? undefined;
  const pickPlayer = (id: number) => {
    const next = new URLSearchParams(params);
    next.set("player", String(id));
    setParams(next);
  };
  return (
    <div className="space-y-5 min-w-0">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <button onClick={() => setPicking(true)} className="card p-4 flex items-center gap-3 hover:border-ink-muted transition-colors text-left w-full sm:w-auto sm:min-w-80" aria-label={playerId ? "Change player" : "Choose player"}>
          {bio ? <img src={bio.headshot} alt="" className="w-14 h-14 rounded-full object-cover bg-surface-2" /> : <span className="w-14 h-14 rounded-full bg-surface-2 grid place-items-center text-xl">+</span>}
          <div><div className="text-base font-semibold">{name ?? (playerId ? `Player ${playerId}` : "Choose a player")}</div><div className="text-xs text-ink-muted mt-1">{bio ? `${bio.team ?? "—"} · ${bio.position ?? "—"}` : "Explore actual and expected shooting"}</div>{playerId && <span className="text-xs underline underline-offset-2">Change player</span>}</div>
        </button>
        <AnalysisPeriod />
      </div>
      {summary.isError && <ErrorState message="Player details are unavailable." onRetry={() => void summary.refetch()} />}
      {!playerId ? <Card className="py-12 text-center"><h2 className="font-display text-xl font-bold">Start with a player's shots</h2><p className="text-sm text-ink-muted mt-2">Choose a player and period to see actual shooting, the model estimate and the difference.</p></Card>
        : isLoading ? <div className="space-y-3"><Skeleton className="h-40 rounded-lg" /><Skeleton className="h-64 rounded-lg" /></div>
        : error ? <ErrorState message={error.message} onRetry={() => void refetch()} />
        : quality && !quality.available ? <Card><h2 className="font-semibold">Shot quality unavailable</h2><p className="text-sm text-ink-muted mt-2">{quality.reason}</p></Card>
        : quality ? <>
          <Card>
            <CardTitle tip="XFG">Actual vs expected · {quality.season} · {quality.season_type}</CardTitle>
            <div className="grid sm:grid-cols-3 gap-5">
              <div><div className="text-xs text-ink-muted mb-2">Actual effective FG%</div><div className="text-4xl font-display font-bold"><AnimatedNumber value={quality.actual_efg * 100} format={(n) => `${n.toFixed(1)}%`} /></div></div>
              <div><div className="text-xs text-ink-muted mb-2">Model expected effective FG%</div><div className="text-4xl font-display font-bold text-ink-2"><AnimatedNumber value={quality.expected_efg * 100} format={(n) => `${n.toFixed(1)}%`} /></div></div>
              <div><div className="text-xs text-ink-muted mb-2">Estimated adjusted difference</div><div className="text-3xl font-display font-bold tnum" style={{ color: quality.delta >= 0 ? "var(--good)" : "var(--critical)" }}>{quality.delta > 0 ? "+" : ""}{(quality.delta * 100).toFixed(1)} <span className="text-sm">pp</span></div><p className="text-xs text-ink-muted mt-2">{quality.delta_per_100_shots > 0 ? "+" : ""}{quality.delta_per_100_shots} points per 100 shots</p></div>
            </div>
            <div className="border-t border-edge mt-5 pt-4 text-sm flex flex-wrap gap-x-6 gap-y-2">
              <span><strong className="tnum">{quality.shots.toLocaleString()}</strong> shots analyzed</span>
              {quality.confidence_interval_95 ? <span>95% interval: <strong className="tnum">{(quality.confidence_interval_95[0] * 100).toFixed(1)} to {(quality.confidence_interval_95[1] * 100).toFixed(1)} pp</strong></span> : <span className="text-ink-muted">Confidence interval unavailable</span>}
              {quality.percentile != null && <span>Model residual percentile: {quality.percentile}</span>}
            </div>
            <p className="text-xs text-ink-muted leading-relaxed mt-3">{quality.uncertainty_note ?? "The adjusted difference may be shrunk toward the average to account for sample size."} This estimate includes unmeasured context and uncertainty; it does not isolate shooting skill.</p>
            <p className="text-xs text-ink-muted mt-2">Model {quality.model.model_version ?? "version unavailable"} · Dataset {quality.model.dataset_version ?? "version unavailable"}</p>
          </Card>
          <Card><CardTitle>Zone by zone: actual vs expected</CardTitle>{quality.zones.length ? <ZoneDeltaBars zones={quality.zones} /> : <p className="text-sm text-ink-muted">Zone estimates unavailable for this period.</p>}</Card>
          <ShotSelectionCard playerId={playerId} name={name} filters={filters} />
          <Card><CardTitle>League reference distribution</CardTitle>
            {model.isLoading ? <Skeleton className="h-48" /> : model.error ? <ErrorState message={model.error.message} onRetry={() => void model.refetch()} /> : modelInfo?.delta_distribution?.length ? <DeltaHistogram distribution={modelInfo.delta_distribution} playerDelta={quality.delta} playerName={name} /> : <p className="text-sm text-ink-muted">League reference distribution unavailable.</p>}
            <p className="text-xs text-ink-muted mt-2">Reference seasons: {modelInfo?.seasons?.join(", ") || "unavailable"}. The reference population can differ from your selected period.</p>
          </Card>
          <details className="card p-5"><summary className="cursor-pointer font-semibold">What drives the model estimate?</summary><div className="mt-4"><ShotDifficultyExplainer playerId={playerId} filters={filters} /></div></details>
        </> : null}
      <SearchPalette open={picking} onClose={() => setPicking(false)} onPick={pickPlayer} />
    </div>
  );
}
