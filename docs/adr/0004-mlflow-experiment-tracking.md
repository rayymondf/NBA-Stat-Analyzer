# ADR 0004: File-backed MLflow experiment tracking and registry

- Status: accepted
- Date: 2026-09-18

## Decision

Record each xFG training run to a local, file-backed MLflow store via
`nba-pipeline train --mlflow`. Log run parameters, per-candidate tuning metrics,
final calibrated test metrics, the baseline comparison, clustered-bootstrap
interval widths, and calibration/drift/slice/promotion artifacts. Register a
candidate as a versioned model in the local MLflow model registry only when the
recorded promotion gate passes.

## Rationale

The pipeline already produced a rich JSON evaluation report and an atomic,
SHA-pinned promotion gate. Adding MLflow makes runs browsable and comparable
over time without standing up a server: `mlflow-skinny` with the default file
store needs no database or tracking service, so it preserves the one-command,
local-first posture of the project. Gating registration on the same promotion
rule keeps a single source of truth for "is this candidate shippable" and avoids
a registry that disagrees with the artifact gate.

## Consequences

- `mlflow ui` shows every run with metrics, artifacts, and tags; a reviewer can
  compare candidates and see the gate decision at a glance.
- The registry only ever contains gate-passing models, so it is safe to treat a
  registered version as promotable, but the atomic file artifact + SHA pin
  remains the authoritative deployment source (see ADR 0003).
- Tracking is optional: without the `ml` extra installed, `log_mlflow` is a
  no-op and training still succeeds, so the default offline test suite is
  unaffected.
- A hosted tracking backend (database + artifact store) is a future step if the
  project needs shared, multi-user run history.
