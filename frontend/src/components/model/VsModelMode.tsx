import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import SearchPalette from "../SearchPalette";
import { AnimatedNumber, Card, CardTitle, ErrorState, GlossaryTip, Skeleton } from "../ui";
import DeltaHistogram from "./DeltaHistogram";
import CalibrationChart from "./CalibrationChart";
import ZoneDeltaBars from "./ZoneDeltaBars";

/** Pick one player; the model plays the "average NBA player" taking the same shots. */
export default function VsModelMode() {
  const [params, setParams] = useSearchParams();
  const playerId = params.get("player") ? Number(params.get("player")) : null;
  const [picking, setPicking] = useState(false);

  const { data: summary } = useQuery({
    queryKey: ["summary", playerId],
    queryFn: () => api.summary(playerId!),
    enabled: !!playerId,
  });
  const { data: quality, isLoading, error } = useQuery({
    queryKey: ["shotQuality", playerId],
    queryFn: () => api.shotQuality(playerId!),
    enabled: !!playerId,
    staleTime: 30 * 60 * 1000,
  });
  const { data: info } = useQuery({
    queryKey: ["modelInfo"],
    queryFn: api.modelInfo,
    staleTime: 30 * 60 * 1000,
  });

  const bio = summary; // summary endpoint returns bio fields at the top level
  const name: string | undefined = bio?.name;

  const pickPlayer = (id: number) => {
    const next = new URLSearchParams(params);
    next.set("player", String(id));
    setParams(next);
  };

  return (
    <div className="space-y-4">
      <button
        onClick={() => setPicking(true)}
        className="card p-4 flex items-center gap-3 hover:border-ink-muted transition-colors text-left w-full sm:w-auto sm:min-w-80"
      >
        {bio ? (
          <>
            <img src={bio.headshot} alt="" className="w-14 h-14 rounded-full object-cover bg-surface-2" />
            <div>
              <div className="text-sm font-semibold">{bio.name}</div>
              <div className="text-xs text-ink-muted">
                {bio.team ?? "-"} · {bio.position ?? "-"}
              </div>
              <div className="text-[10px] text-ink-muted mt-0.5 underline underline-offset-2">
                Change player
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="w-14 h-14 rounded-full bg-surface-2 grid place-items-center text-ink-muted text-xl">+</div>
            <div className="text-sm text-ink-muted">Pick a player to test against the model</div>
          </>
        )}
      </button>

      {!playerId ? (
        <Card className="text-center py-12 text-ink-muted text-sm">
          Choose any player. The model then plays the part of an average NBA
          player taking that player's exact shots, and we see who shoots better.
        </Card>
      ) : isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-40 rounded-lg" />
          <Skeleton className="h-64 rounded-lg" />
        </div>
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : quality && !quality.available ? (
        <Card className="text-center py-10 text-ink-muted text-sm">{quality.reason}</Card>
      ) : quality ? (
        <>
          <Card className="section-in">
            <CardTitle tip="XFG">
              {name ?? "Player"} vs the model · {quality.season}
            </CardTitle>
            <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
              <div>
                <div className="text-3xl font-semibold tnum">
                  <AnimatedNumber value={quality.actual_efg * 100} format={(n) => `${n.toFixed(1)}%`} />
                </div>
                <div className="text-[11px] uppercase tracking-wider text-ink-muted mt-1">
                  {name ? `${name}'s actual eFG%` : "Actual eFG%"}
                </div>
              </div>
              <div>
                <div className="text-3xl font-semibold tnum text-ink-2">
                  <AnimatedNumber value={quality.expected_efg * 100} format={(n) => `${n.toFixed(1)}%`} />
                </div>
                <div className="text-[11px] uppercase tracking-wider text-ink-muted mt-1 flex items-center gap-1">
                  Average player, same shots <GlossaryTip term="XFG" />
                </div>
              </div>
              <div>
                <span
                  className="text-sm font-semibold tnum px-2.5 py-1 rounded-full text-white"
                  style={{
                    background:
                      quality.delta >= 0.005 ? "var(--good)" :
                      quality.delta <= -0.005 ? "var(--critical)" : "var(--ink-muted)",
                  }}
                >
                  {quality.delta > 0 ? "+" : ""}{(quality.delta * 100).toFixed(1)} pts
                </span>
                <div className="text-[11px] text-ink-muted mt-1.5">
                  {quality.delta_per_100_shots > 0 ? "+" : ""}
                  {quality.delta_per_100_shots} points per 100 shots
                </div>
              </div>
              <div className="text-xs text-ink-2 max-w-56 leading-relaxed">
                {quality.percentile != null ? (
                  <>Shot-making better than <strong>{quality.percentile}%</strong> of
                  qualified NBA players, on {quality.shots.toLocaleString()} shots.</>
                ) : (
                  <>{quality.shots.toLocaleString()} shots analyzed.</>
                )}
              </div>
            </div>
          </Card>

          <div className="grid lg:grid-cols-2 gap-4">
            <Card className="section-in">
              <CardTitle>Where they land in the league</CardTitle>
              <DeltaHistogram
                distribution={info?.delta_distribution ?? []}
                playerDelta={quality.delta}
                playerName={name}
              />
            </Card>
            <Card className="section-in">
              <CardTitle>Zone by zone: actual vs expected</CardTitle>
              <ZoneDeltaBars zones={quality.zones ?? []} />
            </Card>
          </div>

          {(info?.calibration_by_distance?.length ?? 0) > 0 && (
            <Card className="section-in">
              <CardTitle>Can you trust the model? Predicted vs real make rates</CardTitle>
              <CalibrationChart rows={info.calibration_by_distance} />
            </Card>
          )}
        </>
      ) : null}

      <SearchPalette open={picking} onClose={() => setPicking(false)} onPick={pickPlayer} />
    </div>
  );
}
