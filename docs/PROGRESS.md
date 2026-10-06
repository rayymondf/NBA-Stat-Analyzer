# Progress log

A running record of the revamp/optimization effort: what was completed (with
evidence), what remains, and what the next iteration should pick up. Each slice
was verified against the local gate (backend: ruff, mypy, pytest, OpenAPI
export; frontend: oxlint, vitest, build) before commit.

## Honest status at a glance

- **Deployed xFG model:** v2 (657,387 shots; held-out Brier 0.2244, AUC 0.662).
  A v3 candidate trained on a newer 700k dataset did **not** beat v2 and was
  **not** promoted. See [MODEL_CARD](MODEL_CARD.md).
- **Current dataset:** `shots-v1-426fd715aa4e` — 700,077 shots, 2023-24 through
  2025-26, **regular season + playoffs** (no preseason). See [DATA_CARD](DATA_CARD.md).
- **CI/CD:** backend and frontend gates pass locally. `pipeline.yml` is
  dispatch/schedule-only and depends on live ingestion + optional secrets.
- **Container:** Dockerfile/compose statically reviewed and sound (multi-stage,
  non-root, model-less health check). Not executed here — Docker is not installed
  on the dev machine; run `docker compose up --build` where Docker is available.
- **Agents/skills:** task-focused agents in `.kiro/agents/`, coordinated by the
  `.kiro/skills/nba-agent-workflow` skill.

## Completed slices

### Slice 1 — CI/CD green + commit the in-flight work
- Reproduced both CI gates locally. Root cause of CI failure: the committed
  `openapi.json` and `schema.d.ts` were stale (code added `"Pre Season"` to the
  `SeasonType` enum but the generated contract was not regenerated).
- Committed the regenerated contract so the drift checks pass; grouped and
  committed the rest of the in-flight changes.
- `pipeline.yml` assessed as code-correct (every CLI subcommand/flag validated
  against `nba-pipeline --help`); its failures are environmental, not code.
- Evidence: backend 124 passed / 80.1% coverage; frontend 35 passed; both drift
  gates exit 0 against the committed tree.

### Slice 2 — bug and efficiency sweep
Read-only review across backend + frontend; fixed the confirmed, high-impact
defects (three of them worsen Ask AI responsiveness):
- **AI budget lockout:** the global rate-limit reservation was never released on
  a failed Gemini call, so a burst of upstream errors locked out Ask AI for a
  minute. Now refunded on failure.
- **Serial request pile-up:** the per-question single-flight lock was held across
  the full ~25s call with no timeout; identical questions stacked up. Now a
  bounded wait + fast-fail/cache fall-through.
- **Silent wrong data:** a starter/bench filter was silently ignored when start
  data was unavailable, returning all games as if filtered. Now raises a clear
  error.
- **AiMode wrong-turn render:** turns were keyed by array index; a resolved
  report could attach to the wrong turn. Now keyed by stable turn id.
- Evidence: +2 offline tests; backend 126 passed.

### Slice 3 — performance + scraping/output efficiency (measured)
- **Percentile hot path:** the position map was rebuilt twice per request.
  Computed once and reused. Measured: `player_index` upstream calls 4 → 2
  (−50%); assembly latency 13.62 → 7.95 ms/call (−42%).
- **Ingestion memory:** `combine_raw` concatenated every partition into one
  in-memory frame. Now streams one partition at a time via a pyarrow
  `ParquetWriter` (or append-CSV), bounding peak memory to a single partition.
- **Resume cost:** partitions record size + mtime; resume trusts a
  size+mtime+rows fingerprint and only full-hashes on mismatch, so a resume no
  longer re-hashes the whole corpus.
- **Frontend bundle:** measured and intentionally left unchanged — recharts
  (371 kB) is already isolated and lazy-loaded via the code-split GameDetail
  route, so it never hits initial load.
- Evidence: backend 126 passed; functional combine check (parquet + csv).

### Slice 4 — add 2025-26 + 2024-25 + 2023-24 (regular season + playoffs)
- Closed a real gap: ingestion previously fetched Regular Season only. It now
  fetches **both Regular Season and Playoffs** per team-season, tags each shot
  with `SEASON_TYPE`, and partitions them distinctly.
- Live ingestion result: **700,077 shots, 180 partitions, 0 failures** (42 empty
  = non-playoff teams). Built dataset `shots-v1-426fd715aa4e`.
- Evidence: 14 pipeline tests updated and passing; mixed reg+playoff build
  verified; backend 126 passed.

### Slice 5 — xFG retrain + validate (v2 kept)
- Trained a v3 candidate on the 700k dataset against the recorded promotion gate.
- Result: Brier 0.2249, AUC 0.660, ECE 0.0040 — statistically indistinguishable
  from / marginally worse than v2. **Gate did not pass; v2 kept.** Active
  `xfg.joblib` SHA-256 verified unchanged (no promotion).
- Decision and known limitations documented in [MODEL_CARD](MODEL_CARD.md).

### Slice 6 — Ask AI latency (token-neutral)
- Added a non-blocking background cache warm: when the page context pins a
  player or game, `_generate_report` pre-warms the most-likely first tool so it
  races the model's opening round-trip and is cache-warm when the SDK calls it.
- Verified non-blocking (returns ~0.3 ms even when the underlying fetch takes
  3 s), never extends the 25s deadline, and adds **zero** Gemini tokens (output
  and remote-call caps unchanged).
- Evidence: +3 offline tests; backend 132 passed.

### Slice 7 — documentation
- Updated MODEL_CARD (honest v2, v3 gate result, known limitations), DATA_CARD
  (700k dataset, playoffs, `SEASON_TYPE`, new partition layout), README and
  AGENTS.md (removed the retired Codex roster references; current `.kiro` agents
  and skill), and added this progress log.

## What remains / known gaps

- **xFG model is at a feature ceiling.** Location+type features cap make-
  probability prediction near Brier ~0.225 / AUC ~0.66. Beating v2 needs new
  signal, not more rows (see next iteration).
- **`--incumbent` silent fallback ? FIXED.** Training no longer silently
  reverts to the naive baseline: a provided-but-unusable incumbent now raises
  `IncumbentIncompatible` with an actionable message, and eligibility recognizes
  v2's `trained_at`. This surfaced that v2's training overlaps this dataset's
  test fold, so a clean v2-vs-v3 head-to-head needs a non-overlapping dataset or
  an earlier-trained v2 (see MODEL_CARD limitation 3).
- **OOF prior / calibration mismatch** in the player-percentile surface
  (MODEL_CARD limitations 1–2) — cosmetic to users, not a gate issue.
- **`pipeline.yml`** cannot pass in ordinary CI (needs live ingestion + secrets);
  it is a scheduled/dispatch job by design.

## Post-revamp checks

### Docker image check (static)

Docker is not installed on the development machine, so the image could not be
built or run here. A full static review of `Dockerfile`, `docker-compose.yml`,
and `.dockerignore` against the CI container job passed on every point:

- Multi-stage build: Node 24 frontend build -> `python:3.12-slim` runtime, uv
  0.8.22 pinned, `uv sync --locked --no-dev --extra inference`.
- Runs **non-root** (`useradd app` + `USER app`; `data/` chowned to `app`).
- `HEALTHCHECK` hits `/health/live`, which returns `{"status":"ok"}` with no
  dependencies or model. `/health/ready` passes without a model because
  `require_model` defaults to False.
- Runtime imports are inference-safe: no top-level `shap`/`mlflow`/`optuna`, and
  `boto3` is imported lazily inside a function, so `app.main:app` starts with
  only base deps + the `inference` extra (xgboost).
- No baked model or secrets: `.dockerignore` excludes `backend/.env`,
  `data/models`, raw/processed/manifests, and the sqlite cache.

**To verify live where Docker is available:**

```bash
docker compose up --build         # or: docker build -t nba:ci .
curl -f http://127.0.0.1:8000/health/live
curl -f http://127.0.0.1:8000/health/ready
```

This mirrors the `container` job in `.github/workflows/ci.yml`. A deployed
container has no model baked in by design; configure the SHA-pinned artifact
bootstrap (see DEPLOYMENT.md) or it serves without the xFG model (readiness
still passes).

## Next iteration

1. **Fix the incumbent comparison** so v3-vs-v2 is a true shared-test-fold
   head-to-head (re-featurize/evaluate v2) or fails loudly — never silent naive
   fallback.
2. **Add predictive signal** the model lacks (defender distance / contest /
   shot-clock). RESEARCHED - not feasible at shot level from public data (see
   docs/RESEARCH_SHOT_CONTEXT.md): the public NBA API exposes these only as
   per-player aggregate buckets with no GAME_ID to join to shots; the one
   public shot-level set is a stale 2014-15 leak; current tracking (Second
   Spectrum / Sportradar) is licensed/paid. Options: keep the honest
   location+type model; add a descriptive (non-model) contested-shooting view
   from the aggregate buckets; or license a paid feed for shot-level contest.
3. **Calibrate within each OOF fold** and derive the player prior only from
   pre-tuning windows, so the percentile surface matches production probabilities.
4. **Season-type as a modeling or reporting dimension** now that playoffs are in
   the dataset (e.g. playoff vs regular-season shot-quality splits).
5. Optional: a small frontend pass (lazy the GameDetail chart within the page
   shell) only if measurement shows it helps.
