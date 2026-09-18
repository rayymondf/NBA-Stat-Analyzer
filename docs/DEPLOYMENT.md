# Deployment and operations

## Local production build

```powershell
docker compose up --build
```

Smoke checks:

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
Invoke-WebRequest http://localhost:8000/api/v1/ml/model-info
```

The image serves the compiled frontend and API from one non-root, single-worker
process. SQLite data uses the `nba-data` Compose volume.

## Required configuration

| Variable | Purpose | Production guidance |
|---|---|---|
| `APP_ENV` | Runtime label | `production` |
| `TRUSTED_HOSTS` | Host-header allowlist | Exact service/custom domains |
| `CORS_ORIGINS` | Browser origins | Exact origins; no wildcard |
| `NBA_DATA_DIR` | Cache/model directory | Writable absolute path |
| `REQUIRE_MODEL` | Fail readiness/startup without xFG | Enable after artifact setup |
| `ARTIFACT_BASE_URL` | Release prefix containing index/model | Trusted HTTPS/object store |
| `ARTIFACT_EXPECTED_SHA256` | Artifact pin | Required with the URL |
| `DATASET_PUBLIC_URL` | Optional large CSV object | HTTPS URL with suitable policy |
| `GEMINI_API_KEY` | Optional AI Mode | Secret manager only |

Rate/cache variables are documented in `backend/.env.example`. Never pass
secrets as Docker build arguments or commit `.env`.

## Verified model bootstrap

Publish creates `<prefix>/<version>/index.json` and a model file. Configure the
release prefix and the exact digest from the index:

```text
ARTIFACT_BASE_URL=https://objects.example/models/v3-12345
ARTIFACT_EXPECTED_SHA256=<64 lowercase hex characters>
REQUIRE_MODEL=true
```

Startup validates index schema, safe filename, declared/max size, streamed byte
count, and SHA-256 before joblib load. The artifact producer must still be
trusted because pickle-family formats can execute code when deserialized.

## Render

`render.yaml` defines a Docker web service and readiness health check. Create a
Blueprint from the repo, then:

1. Confirm `TRUSTED_HOSTS` matches the assigned/custom domain.
2. Add model URL/SHA and Gemini key in the dashboard if used.
3. Set `REQUIRE_MODEL=true` only after a verified artifact is reachable.
4. Understand that the included free service has ephemeral cache storage and
   can cold-start. A paid persistent disk or external cache is needed for
   durable warm data.

The blueprint follows Render's documented Docker, environment, and
`healthCheckPath` fields. Validate it with `render blueprints validate
render.yaml` when the Render CLI is installed.

## CI/CD

- `ci.yml`: locked backend lint/types/tests/coverage, OpenAPI drift, frontend
  generated contract/lint/tests/build, and container build.
- `pipeline.yml`: resumable weekly in-season ingestion, dataset build, candidate
  evaluation, gate check, optional R2/S3-compatible release, retained evidence.
- `release.yml`: tagged/manual multi-stage image publish to GHCR plus build
  provenance attestation.

Configure repository secrets only for the optional services: artifact URL/SHA,
R2 endpoint/bucket/access keys. A candidate that fails its recorded gate is
uploaded as run evidence but not published as a release.

## Runbook

### Readiness fails

Check `/health/ready`. Cache failures indicate a non-writable/corrupt data path.
Model failures include a safe status string; verify URL, digest, object size,
and bundle contract. Temporarily set `REQUIRE_MODEL=false` to restore non-ML
analytics while correcting the artifact.

### NBA.com is slow or failing

Look at `nba_upstream_calls_total`, `nba_upstream_circuit_open`, request latency,
and `X-Data-Cache`. The service retries only transient failures, deduplicates
identical misses, opens its circuit, and can serve bounded stale entries. Avoid
restarting repeatedly because that discards circuit state and decoded LRU.

### Cache growth

Inspect the performance skill or `cache.stats()`. General pruning enforces the
configured logical limit. Training-only team-shot payloads have a narrower safe
preview/apply command. Back up the SQLite file before unrelated manual SQL.

### Rollback

Restore the previous container tag and previous immutable artifact URL/SHA pair.
Do not overwrite an artifact version. Confirm `/health/ready`, model identity,
one player summary, and one shot-quality response.

### Scaling beyond one process

Before multiple workers/replicas, move cache/rate-limit/circuit/single-flight
coordination to shared infrastructure. SQLite WAL and process-local controls do
not provide cluster-wide limits or deduplication.
