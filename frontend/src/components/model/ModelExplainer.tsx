import { useQuery } from "@tanstack/react-query";
import { api, DATASET_URL } from "../../lib/api";
import { Card } from "../ui";

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
  const { data: info } = useQuery({
    queryKey: ["modelInfo"],
    queryFn: api.modelInfo,
    staleTime: 30 * 60 * 1000,
  });

  if (!info?.available) return null;

  const nShots = info.n_shots?.toLocaleString() ?? "hundreds of thousands of";
  const seasons = (info.seasons ?? []).join(", ");
  const m = info.metrics ?? {};
  const base = info.baseline;
  const sizeMb = info.dataset?.size_bytes
    ? Math.round(info.dataset.size_bytes / 1024 / 1024)
    : null;

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
        <Step n={3} title="A gradient-boosted model learns the patterns">
          Using scikit-learn (free, runs on this PC), hundreds of small
          decision trees are built in sequence, each correcting the mistakes
          of the ones before it. The finished model can estimate, for any
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
          {base && (
            <> This version also beat the previous design ({base.brier} Brier)
            on the exact same test shots before it was allowed to ship.</>
          )}
        </Step>
      </div>
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
        </div>
      )}
    </Card>
  );
}
