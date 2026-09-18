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

1. Run fresh v3 ingestion and publish the first passing candidate/report.
2. Replace remaining generic response roots with explicit domain DTOs and derive
   frontend domain types directly from OpenAPI.
3. Capture a public warm-cache Locust report and browser accessibility audit.
4. Move coordination to Redis and demonstrate two replicas if scale is part of
   the target role.
5. Add OpenTelemetry traces, SBOM/container scanning, and hosted dashboards.
6. Add a tracking-data provider only if licensing and reproducibility are clear;
   it would materially improve contest/context modeling.

These are deliberate next increments, not hidden claims about the current repo.
