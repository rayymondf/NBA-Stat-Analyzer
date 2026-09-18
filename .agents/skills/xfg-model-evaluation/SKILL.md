---
name: xfg-model-evaluation
description: Train, evaluate, review, or promote the NBA expected-field-goal model. Use for xFG features, temporal splits, calibration, uncertainty, drift, experiments, model cards, and model-registry decisions; not for general player-stat UI changes.
---

# xFG model evaluation

Use the versioned data manifest as the experiment input and keep all comparisons on the same untouched temporal test fold.

1. Confirm `dataset_version`, seasons, row count, target definition, and time/game split boundaries.
2. Check that a whole game/date group appears in only one fold. Reject random shot-level splitting or preprocessing fitted across folds.
3. Compare the calibrated candidate against the recorded incumbent on Brier score, log loss, ROC AUC, average precision, and expected calibration error.
4. Inspect clustered 95% bootstrap intervals, calibration rows, feature importance, and slices for rim, midrange, threes, heaves, home/away, and season.
5. Treat player deltas as estimates: require empirical-Bayes shrinkage, sample size, and a confidence interval. Do not describe xFG delta as pure shooting talent or causal impact.
6. Save the candidate and evaluation report before promotion. Use `nba-pipeline promote` only when the recorded gate passes. Do not use `--force` without explicit user authorization and a written reason.
7. Run focused training tests, then the backend gate. If optional MLflow is enabled, log dataset version, candidate parameters, test metrics, and evaluation JSON.

Return a ship/no-ship verdict, metric deltas with uncertainty, failed slices or limitations, candidate/report paths, and the exact promotion command if it is eligible.
