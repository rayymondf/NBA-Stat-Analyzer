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

The local joblib artifact and training export are ignored deployment data, not
source-controlled release assets.

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
- A weekly in-season workflow rebuilds data and a candidate but publishes only
  a passing release.
- Alert candidates at PSI >= 0.25; review at PSI >= 0.10.
- Roll back by restoring the preceding immutable artifact URL/SHA pair.

## Reproducibility

Python dependencies and RNG seed are pinned/recorded. Every processed dataset
has a content-derived version and manifest; every artifact has an index,
declared size, metadata, and SHA-256. See [DATA_CARD.md](DATA_CARD.md) and
[DEPLOYMENT.md](DEPLOYMENT.md).
