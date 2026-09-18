import { useQuery } from "@tanstack/react-query";
import { api, DATASET_URL } from "../../lib/api";
import { Card, ErrorState, SkeletonCard } from "../ui";

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <div className="font-display text-2xl text-ink-muted leading-none pt-0.5 w-7 shrink-0 text-right">
        {n}
      </div>
      <div>
        <div className="text-sm font-semibold">{title}</div>
        <p className="text-xs text-ink-2 leading-relaxed mt-1">{children}</p>
      </div>
    </div>
  );
}

/** Plain-English "how this model was built", driven by live model metadata. */
export default function ModelExplainer() {
  const { data: info, isLoading, error, refetch } = useQuery({
    queryKey: ["modelInfo"],
    queryFn: api.modelInfo,
    staleTime: 30 * 60 * 1000,
  });

  if (isLoading) return <SkeletonCard lines={6} />;
  if (error) return <ErrorState message={(error as Error).message} onRetry={() => void refetch()} />;
  if (!info) return null;
  if (info.available === false) return <Card><p className="text-sm text-ink-2">Model unavailable: {info.reason}</p></Card>;

  const nShots = info.n_shots?.toLocaleString() ?? "hundreds of thousands of";
  const seasons = (info.seasons ?? []).join(", ");
  const m = info.metrics;
  const base = info.baseline;
  const sizeMb = info.dataset?.size_bytes
    ? Math.round(info.dataset.size_bytes / 1024 / 1024)
    : null;
  const brierInterval = info.confidence_intervals_95?.brier;
  const importanceMax = Math.max(
    ...(info.feature_importance ?? []).map((item) => Math.abs(item.importance)),
    0.0001,
  );

  return (
    <Card className="section-in">
      <div className="eyebrow mb-4">How this model was built</div>
      <div className="grid md:grid-cols-2 gap-x-8 gap-y-5">
        <Step n={1} title="Real shots, straight from NBA.com">
          Every shot attempted in the {seasons} seasons was pulled from
          NBA.com's official stats feed: {nShots} shots in total, each with its
          court location, distance, shot type, quarter, clock and result. No
          outside datasets, and no video. The model only ever sees where and
          how a shot was taken, never footage of it.
        </Step>
        <Step n={2} title={`Each shot becomes ${info.feature_count ?? 36} numbers`}>
          Distance, court position and angle, zone, shot type (dunk, pull-up,
          floater and so on), seconds left in the quarter, home or away. These
          numbers are the only inputs; the make-or-miss result is the answer
          the model learns to predict.
        </Step>
        <Step n={3} title="Multiple models compete on future games">
          Logistic regression and gradient-boosted candidates are compared on
          a later validation window; this artifact selected <strong>{info.selected_model ?? "the best calibrated candidate"}</strong>.
          The finished model can estimate, for any
          shot, the chance an average NBA player makes it. Averaged across a
          player's real shots, that becomes the expected effective field goal
          percentage: what an average NBA player would be expected to shoot
          from those same shots.
        </Step>
        <Step n={4} title="Then it is graded honestly">
          {m.n_test?.toLocaleString() ?? "Tens of thousands of"} shots were
          hidden from the model during training and used as a blind exam.
          Score: Brier {m.brier} against {m.brier_naive} for a naive
          always-guess-the-average baseline (lower is better), AUC {m.auc}.
          {brierInterval && <> Clustered 95% Brier interval: {brierInterval.lower.toFixed(4)} to {brierInterval.upper.toFixed(4)}.</>}
          {base && (
            <> This version also beat the previous design ({base.brier} Brier)
            on the exact same test shots before it was allowed to ship.</>
          )}
        </Step>
      </div>
      <div className="rule mt-6 pt-5 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          ["Log loss", m.log_loss?.toFixed(4) ?? "-"],
          ["Average precision", m.average_precision?.toFixed(3) ?? "-"],
          ["Calibration error", m.ece?.toFixed(4) ?? "-"],
          ["Dataset version", info.dataset_version ?? "legacy"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg bg-surface-2 px-3 py-2">
            <div className="text-[10px] uppercase tracking-wider text-ink-muted">{label}</div>
            <div className="text-sm font-semibold tnum mt-0.5 break-all">{value}</div>
          </div>
        ))}
      </div>
      {(info.feature_importance?.length ?? 0) > 0 && (
        <div className="rule mt-5 pt-4 grid md:grid-cols-2 gap-6">
          <div>
            <div className="eyebrow mb-3">Permutation importance</div>
            <div className="space-y-2">
              {info.feature_importance!.slice(0, 6).map((item) => (
                <div key={item.feature} className="grid grid-cols-[9rem_1fr] gap-2 items-center text-xs">
                  <span className="text-ink-2 truncate" title={item.feature}>{item.feature}</span>
                  <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
                    <div className="h-full bg-[var(--series-1)]" style={{ width: `${Math.max(2, Math.abs(item.importance) / importanceMax * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="eyebrow mb-3">Temporal drift check</div>
            <div className="flex flex-wrap gap-2">
              {(info.drift ?? []).map((item) => (
                <span key={item.feature} className="rounded-full border border-edge px-2.5 py-1 text-xs">
                  {item.feature}: <strong>{item.status}</strong> <span className="text-ink-muted">({item.psi.toFixed(3)} PSI)</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
      {info.dataset?.available && (
        <div className="rule mt-5 pt-4 flex flex-wrap items-center gap-x-2 text-xs">
          <a
            href={DATASET_URL}
            download
            className="font-medium underline underline-offset-2 hover:text-ink transition-colors"
            style={{ color: "var(--series-1)" }}
          >
            Download the training dataset
          </a>
          <span className="text-ink-muted">
            CSV, {nShots} shots, seasons {seasons}
            {sizeMb ? `, about ${sizeMb} MB` : ""}. Opens in Excel.
          </span>
          {info.dataset.usage_note && (
            <span className="basis-full text-[10px] text-ink-muted mt-1">{info.dataset.usage_note}</span>
          )}
        </div>
      )}
    </Card>
  );
}
