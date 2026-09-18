# Portfolio and interview guide

## Honest positioning

Lead with this as an end-to-end ML systems project, not merely an NBA UI. The
strongest evidence is the contract and failure design connecting data lineage,
leakage-resistant evaluation, artifact trust, resilient online inference, and a
usable typed client.

Do not call xFG v3 deployed until a saved v3 evaluation passes and the hosted
model-info endpoint reports version 3. Current production evidence is v2; v3 is
the implemented MLOps upgrade path.

## Resume bullets

Use or adapt only after the final CI run remains green:

- Built a FastAPI/React NBA analytics platform with a versioned API, typed
  parameters/errors, and strict TypeScript domain models,
  resilient upstream access (SQLite/LRU cache, single-flight, bounded retries,
  stale fallback, circuit breaker), request correlation, rate limits, health
  probes, and Prometheus metrics.
- Engineered a resumable Parquet data pipeline with team-season checkpoints,
  schema/domain validation, content-addressed manifests, atomic dataset swaps,
  read-only DuckDB exploration, and SHA-256-verified S3-compatible artifacts.
- Implemented an xFG model lifecycle using chronological game-date folds,
  isolated tuning/calibration/test periods, grouped bootstrap intervals,
  calibration/drift/slice reporting, out-of-fold empirical-Bayes shrinkage, and
  gated atomic promotion.
- Reduced the local runtime cache from 451 MB to 54 MB by separating offline
  training payloads, and cut the player-profile entry chunk about 50% through
  tab-level code splitting while preserving strict types and accessibility.
- Automated locked backend/frontend tests, API contract drift, container builds,
  scheduled retraining, gated artifact publication, and attested GHCR releases.
- Added file-backed MLflow experiment tracking and a model registry to the
  training pipeline: runs log parameters, per-candidate tuning metrics, test
  metrics, baseline deltas, and calibration/drift/slice artifacts, and only a
  gate-passing candidate is registered — mirroring the atomic promotion gate.
- Hardened the public contract with explicit, discriminated-union Pydantic DTOs
  (model-info, shot explainer) and derived the strict TypeScript client types
  directly from the generated OpenAPI, making server/client drift a compile
  error.
- Shipped a SHAP-based shot-difficulty explainer (endpoint + UI panel) that
  attributes the model's per-shot make-probability to its inputs, labeled as
  model attribution rather than causal or pure-talent measurement.

## Five-minute demo

1. Open a player profile and change season/splits; call out explicit
   loading/error/stale behavior and lazy analytics tabs.
2. Open Shooting and explain recorded context, xFG limitations, sample size,
   shrinkage, and intervals without calling it causal talent.
3. Show `/docs`, `/health/ready`, and `/metrics`; trigger or describe request ID
   and cache freshness headers.
4. Show a raw partition sidecar and processed manifest, then run a read-only
   DuckDB query.
5. Open a saved evaluation report and walk through temporal boundaries,
   calibration, paired confidence intervals, slices, drift, and the gate.
6. End on CI/workflows, Docker non-root runtime, and rollback via immutable
   artifact URL/SHA.

## Interview discussion points

- Why one FastAPI process is a good portfolio/local trade-off and what changes
  before horizontal scaling.
- Why a random shot split is optimistic and why same-date games stay together.
- Why calibration has its own fold and why final test labels cannot construct a
  production shrinkage prior.
- Why a checksum must be checked before joblib load, and why a trusted producer
  is still required.
- Why stale data can improve availability but must be bounded and observable.
- Why generic OpenAPI JSON response roots are an interim contract and explicit
  DTOs are the next API-hardening increment.

## Next depth, in priority order

Done in the latest iteration:

- Ran a fresh, ID-complete three-season v3 ingestion and trained/evaluated a
  candidate with full MLflow tracking. The gate correctly withheld promotion
  (calibration non-inferiority against a constant baseline), so v3 remains an
  honest candidate rather than a deployed claim.
- Replaced the model-info and shot-explainer JSON roots with explicit DTOs and
  derived frontend domain types directly from OpenAPI.
- Added a SHAP shot-difficulty explainer endpoint and UI panel.
- Navigation/IA overhaul and visual refresh, verified live with a browser
  accessibility/UX pass.

Deferred (future improvements):

1. Promote the first v3 candidate that passes against a temporally eligible
   incumbent (not just the constant baseline).
2. Replace the remaining generic analytics response roots with explicit DTOs.
3. Capture a public warm-cache Locust report to accompany the browser audit.
4. Move coordination to Redis and demonstrate two replicas if scale is part of
   the target role.
5. Add OpenTelemetry traces, SBOM/container scanning, and hosted MLflow/metrics
   dashboards.
6. Track the large training CSV with git-lfs (or drop it from history) since it
   is a ~93 MB file in the repository.
7. Add a tracking-data provider only if licensing and reproducibility are clear;
   it would materially improve contest/context modeling.

These are deliberate next increments, not hidden claims about the current repo.
