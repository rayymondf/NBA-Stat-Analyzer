# ADR 0002: Date-grouped temporal xFG evaluation

- Status: accepted
- Date: 2026-08-24

## Decision

Split xFG data chronologically by distinct game date into train, tuning,
calibration, and final test folds. Keep every game on a date in one fold and
derive production player priors only from pre-test expanding-window predictions.

## Rationale

Random shot splits leak evolving season/player/context information and make
evaluation unrealistically easy. Reusing tuning or test labels for calibration
or shrinkage similarly contaminates claims.

## Consequences

Training is slower and early periods have less data. Scores better represent
forward-time behavior. A model without a recorded pre-test training boundary is
not an eligible incumbent for paired promotion.
