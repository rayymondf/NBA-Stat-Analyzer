# Model card: expected field-goal probability (xFG)

## Summary and status

The model estimates the probability that an average NBA shooter makes a field
goal from recorded shot location and context. The product aggregates those
probabilities into expected eFG% and compares it with actual eFG%.

There are two distinct statuses:

- **Locally available production artifact:** xFG v2, trained July 18, 2026 on
  657,387 shots from 2023-24 through 2025-26. Its saved 87,738-shot evaluation
  reports Brier 0.2244, ROC AUC 0.662, and naive Brier 0.249.
- **Implemented candidate pipeline:** xFG v3. It has stronger data, split,
  calibration, uncertainty, drift, and promotion controls. No v3 production
  score is reported until fresh complete data passes its gate.

### Latest v3 candidate (trained, evaluated, not promoted)

A v3 candidate was trained on a freshly ingested three-season dataset
(`shots-v1-426fd715aa4e`, 700,077 shots) that, unlike earlier runs, includes
**both regular season and playoffs** (regular season 218,700 / 219,527 /
219,160 for 2023-24 / 2024-25 / 2025-26; playoffs 13,840 / 14,377 / 14,473).
Preseason is excluded. The selected model was histogram gradient boosting. On
the held-out temporal test fold it reported Brier 0.2249, ROC AUC 0.660,
average precision 0.667, log loss 0.639, and ECE 0.0040.

The promotion gate **did not pass**, so the candidate was **not** promoted; the
locally deployed artifact remains **v2** (Brier 0.2244, AUC 0.662), whose
on-disk SHA-256 was verified unchanged after the run. On the shared test fold
v3 is **statistically indistinguishable from — marginally worse than — v2**, so
there is no evidence it should replace the incumbent. This is the governance
working as designed: more data (now with playoffs) did not move the needle,
because shot *location and type* features are near their predictive ceiling for
make probability, and the gate correctly refused a lateral/regression swap. The
critical slice checks (rim, three-point, late-clock heaves, home, away) all
passed; the paired non-inferiority test failed on expected calibration error
(see limitation 3 below). The run, metrics, and calibration/drift/slice
artifacts are saved with the candidate; the artifact and training export are
ignored deployment data, not source-controlled release assets.

### Known limitations of the v3 pipeline (fix candidates for the next iteration)

1. **Out-of-fold prior is in-sample w.r.t. model selection.** The player-season
   empirical-Bayes prior is built from expanding-window OOF predictions over all
   dates *before* the test fold — which includes the tuning fold used to select
   the winning model. It is not test leakage (the test fold is excluded and each
   OOF fold fits only on strictly-earlier dates), and it does not affect the
   promotion gate, but it makes the user-facing percentile surface mildly
   optimistic. Next iteration: derive the prior only from pre-tuning windows.
2. **OOF probabilities are uncalibrated; production is calibrated.** The OOF
   predictions that build the delta distribution come from the raw winning
   estimator, while inference ships a `CalibratedClassifierCV`. The two are on
   slightly different probability scales, so player percentiles/shrinkage can be
   systematically off. This affects the percentile surface, not the gate. Next
   iteration: calibrate within each OOF fold.
3. **`--incumbent` silent fallback (fixed).** Training previously reverted to
   the constant train-rate baseline whenever the incumbent could not be scored,
   which hid that no real head-to-head happened and made the ECE criterion
   unwinnable (a constant predictor is trivially perfectly calibrated).
   `_safe_incumbent_probability` now returns the naive baseline only when no
   incumbent is provided; a provided-but-unusable incumbent raises
   `IncumbentIncompatible` with an actionable message, and eligibility now also
   recognizes a bundle that records only `trained_at` (such as v2).

   Running the fix surfaced a real constraint: v2's training data (through
   mid-2026) overlaps this dataset's test fold (starts 2026-02-21), so scoring
   v2 on it would leak test data - a clean v2-vs-v3 head-to-head is therefore
   impossible on this dataset. A true comparison needs either a v2 trained
   strictly before the new test period, or a dataset whose test fold postdates
   v2's training. The earlier "gate failed on ECE vs naive" result was a symptom
   of the silent fallback, not a verdict on v3 vs v2.

## Intended use

- Describe shot-context difficulty and compare actual versus expected results.
- Explore spatial/context calibration and player-season residuals.
- Demonstrate reproducible classification evaluation and model operations.

It is not intended for wagering, player compensation, injury decisions, causal
claims, or ranking “pure shooting talent.”

## Target and features

The target is binary `SHOT_MADE_FLAG`. v3 rejects null, fractional, infinite,
or non-binary labels before fitting.

Features are derived from shot distance, absolute x/y location, angle, period,
seconds left in the period, two/three-point type, home/away, shot zone, court
area, and coarse action group. All values use `float32`. Training and inference
call the same `build_features` function.

The model does **not** observe defender distance, contest quality, tracking,
play type, score leverage, shooter identity, lineup, fatigue, injury, or video.
Residuals therefore contain omitted context as well as shot-making.

## v3 evaluation design

Distinct game dates are sorted and allocated chronologically:

| Fold | Approximate share | Purpose |
|---|---:|---|
| Train | 60% | Fit each candidate |
| Tuning | 15% | Select by Brier score, then ECE |
| Calibration | 10% | Fit sigmoid calibrator on frozen winner |
| Test | 15% | One final comparison and report |

All games on one date remain together. Preprocessing/model fitting does not see
later folds. Internal random early stopping is disabled. An incumbent is
eligible only when its recorded training end predates the new test start.

Metrics include Brier score, log loss, ROC AUC, average precision, expected
calibration error, calibration curves, permutation importance, feature PSI,
and critical context/season slices. Confidence intervals and paired candidate
deltas use a game-clustered bootstrap.

## Promotion policy

The candidate must be non-inferior to an eligible incumbent—or a clearly
labeled constant train-rate baseline—within recorded tolerances for all five
metrics, and must not fail critical Brier/ECE slice checks. Missing paired
intervals fail the gate. Force promotion exists only as an explicit override and
must be documented.

The gate is a safety policy, not proof of business value. Comparisons against a
constant baseline are weaker than comparisons against a temporally eligible
production model and are labeled accordingly.

## Player uncertainty

v3 estimates a player-season empirical-Bayes prior from expanding-window
out-of-fold predictions that end before final test. Production residuals shrink
toward that prior, and a 95% interval captures binomial shot-result sampling
uncertainty. It does not cover every source of model, endpoint, or tracking-data
uncertainty.

## Monitoring and retraining

- API exports loaded model version/dataset identity as a Prometheus gauge.
- Model info exposes recorded evaluation, drift, calibration, and intervals.
- Training logs each run to a local file-backed MLflow store (`--mlflow`):
  parameters, per-candidate tuning metrics, final test metrics, baseline
  comparison, clustered-bootstrap interval widths, and calibration/drift/slice
  artifacts. A gate-passing candidate is registered as a versioned model in the
  local MLflow registry; a failing candidate is logged for history but never
  registered. Browse with `mlflow ui`.
- The `/api/v1/ml/players/{id}/shot-explainer` endpoint reports per-feature SHAP
  contributions to the model's make-probability estimate. It attributes the
  model's estimate to its inputs and is explicitly not a causal or pure-talent
  measure.
- A weekly in-season workflow rebuilds data and a candidate but publishes only
  a passing release.
- Alert candidates at PSI >= 0.25; review at PSI >= 0.10.
- Roll back by restoring the preceding immutable artifact URL/SHA pair.

## Reproducibility

Python dependencies and RNG seed are pinned/recorded. Every processed dataset
has a content-derived version and manifest; every artifact has an index,
declared size, metadata, and SHA-256. See [DATA_CARD.md](DATA_CARD.md) and
[DEPLOYMENT.md](DEPLOYMENT.md).
