# Progress log

A running record of the revamp/optimization effort: what was completed (with
evidence), what remains, and what the next iteration should pick up. Each slice
was verified against the local gate (backend: ruff, mypy, pytest, OpenAPI
export; frontend: oxlint, vitest, build) before commit.

## Honest status at a glance (as of 2026-10-06)

- **Deployed xFG model:** v2 (657,387 shots; held-out Brier 0.2244, AUC 0.662).
  A v3 candidate on the newer 700k dataset did **not** beat v2 and was **not**
  promoted (gate working as designed). See [MODEL_CARD](MODEL_CARD.md).
- **Current dataset:** `shots-v1-426fd715aa4e` — 700,077 shots, 2023-24 through
  2025-26, **regular season + playoffs** (no preseason). See [DATA_CARD](DATA_CARD.md).
- **Backend + frontend gates:** green locally (backend ruff/mypy/pytest 142
  passed; frontend oxlint 0 warnings, 35 tests, build OK). All work pushed to
  `origin/main`.
- **Ask AI (Gemini):** works when Google's API is healthy; failures now surface
  an actionable "overloaded, try again" message instead of a generic error.
  Subject to Google-side 503 outages (their capacity, transient).
- **Descriptive tracking views:** shot quality by closest-defender distance and
  by shot clock, plus playoff-vs-regular shot-quality splits, all on the
  `/model` (Vs-Model) view and labeled "not a model input."
- **Container:** Dockerfile/compose statically reviewed and sound; not executed
  here (Docker not installed on the dev machine).
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

## Current errors & known issues

- **Ask AI depends on Google's Gemini uptime.** When Google returns 503
  UNAVAILABLE (transient overload on their side) Ask AI cannot answer; the app
  now shows an actionable "overloaded, try again" message and auto-tries a
  backup model, but it cannot manufacture capacity Google is not giving. Not a
  code defect — clears on its own, usually within minutes.
- **xFG is at a feature ceiling.** Location + shot-type features cap make-
  probability prediction near Brier ~0.225 / AUC ~0.66. More rows do not help
  (Slice 5 confirmed); beating v2 needs new signal the model does not have.
- **A clean v2-vs-v3 comparison is impossible on the current dataset.** v2's
  training data (through mid-2026) overlaps this dataset's test fold (starts
  2026-02-21), so scoring v2 would leak test data. The pipeline now fails loudly
  on this instead of silently using a naive baseline. A true head-to-head needs
  a dataset whose test fold postdates v2's training, or an earlier-cutoff v2.
- **Player-percentile surface is slightly imprecise (cosmetic).** The player
  prior is derived partly from the model-selection fold and from uncalibrated
  OOF probabilities, so the displayed percentile can be a touch off. Does not
  affect the promotion gate. See MODEL_CARD limitations 1-2.
- **`pipeline.yml` cannot pass in ordinary CI.** It is a scheduled/dispatch-only
  job needing live NBA.com ingestion + optional secrets — by design, not a bug.
- **Docker not verified live.** The image was only statically reviewed because
  Docker is not installed on the dev machine; run `docker compose up --build`
  where Docker is available to confirm.

### Resolved this effort (for history)
- CI red (stale committed OpenAPI/TS contract) — fixed (Slice 1).
- AI budget lockout, serial request pile-up, silent starter-filter drop, AiMode
  wrong-turn keys — fixed (Slice 2).
- Ingestion memory blow-up + slow resume re-hashing — fixed (Slice 3).
- Ingestion missing playoffs — fixed (Slice 4).
- `--incumbent` silent naive fallback — fixed (fails loudly now).
- Gemini generic "could not complete" masking a closed-client RuntimeError —
  fixed (actionable message + working fallback).

## Future goals

Highest-value first; each is scoped against the honest data constraints.

1. **Earn a real v3 model.** Two prerequisites, in order:
   (a) produce a leak-free v2-vs-v3 comparison (train on a dataset whose test
   fold postdates v2's training, or export an earlier-cutoff v2); and
   (b) add predictive signal the model lacks. Per
   [RESEARCH_SHOT_CONTEXT](RESEARCH_SHOT_CONTEXT.md), per-shot contest/shot-clock
   is NOT available from public data (aggregate buckets only; current tracking is
   licensed), so realistic public-data signal is limited — licensing a tracking
   feed (Sportradar / Second Spectrum) is the only path to shot-level contest.
2. **Calibrate within each OOF fold** and derive the player prior only from
   pre-tuning windows, so the displayed percentile matches production
   probabilities (fixes MODEL_CARD limitations 1-2).
3. **Expand the descriptive tracking views.** The same `playerdashptshots`
   endpoint also exposes dribbles and touch-time buckets — add those as
   descriptive views alongside defender-distance and shot-clock, same pattern.
4. **Optionally surface the contested/shot-clock views on the player profile**,
   not only the Vs-Model page, if users expect them there.
5. **Verify + deploy the container.** Build and health-check the image where
   Docker is available, then wire the SHA-pinned model bootstrap for a real
   deployment (see DEPLOYMENT.md).
6. **Auto-retry affordance for Ask AI 503s** in the UI (brief backoff + retry)
   so transient Google outages are less jarring.

## Session history

The dated sections below are the chronological record of each change for
continuity; the summaries above are the authoritative current state.

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

### Session: #2 research + #4 playoff splits

- **#2 (contest/shot-clock features): researched, not built.** Verdict in
  docs/RESEARCH_SHOT_CONTEXT.md: not feasible at shot level from public data
  (public API = aggregate buckets only; one stale 2014-15 public shot-level set;
  current tracking is licensed). The model stays an honest location+type model.
- **#4 (playoff vs regular-season shot-quality splits): built and verified.**
  Backend service + additive endpoint + 2 tests; frontend card with
  loading/error/empty states; types regenerated. Gates green (backend 138
  passed; frontend 35 passed, build OK). No /api/v1 break.

### Session: Gemini failure fix + remove Preseason from player lookup

- **Gemini "could not complete the request" — root-caused and fixed.** The
  trigger is Google returning 503 UNAVAILABLE (transient overload). The real
  masked bug: on a 503 inside the SDK function-calling loop, google-genai's
  internal retry fires on an already-closed httpx client and raises
  RuntimeError("Cannot send a request, as the client has been closed"). That is
  neither ClientError nor ServerError, so it fell through the candidate loop
  uncaught and the router's catch-all flattened it to the generic message. The
  key/model were fine. Fix: the orchestrator candidate loop now catches the
  closed-client RuntimeError (and any unexpected SDK error) and tries the next
  candidate, then maps an all-failed run to an actionable AiRateLimited
  ("overloaded, try again"). Test added. 142 backend tests pass.
- **Removed the Preseason option from player lookup.** FilterBar no longer
  offers Preseason; PlayerProfile falls back to Regular Season if a URL still
  requests it. Backend SeasonType.PRE support is untouched (Games schedule view
  still allows it). Stale test rewritten to assert the fallback.

### Session: shot-clock shooting splits (descriptive)

Extended the contested-shooting feature with shot-clock splits from the same
NBA tracking endpoint (ShotClockShooting): `shooting.contested_shooting` now also
returns ordered `shot_clock` buckets (FG%/eFG%/frequency by shot-clock range,
early -> late). Frontend adds a `ShotClockChart` analytical component and a
"Shooting by shot clock" card in the Vs-Model view, labeled as descriptive NBA
tracking splits (not a model input). No contract change (opaque JsonObject
endpoint). Gates green: backend 141 passed; frontend lint 0, 35 tests, build OK.

### Session: contested-shooting view (descriptive)

Built the honest, public-data version of #2 (a view, not a model feature):

- **Backend:** `api.player_pt_shots` wraps NBA `playerdashptshots`;
  `shooting.contested_shooting()` normalizes the ClosestDefenderShooting buckets
  (FG%, eFG%, frequency by defender distance, tightest->open) and derives a
  descriptive **offensive** shot-making-under-tight-coverage rating (tight vs
  open FG%, contest drop, label, low-confidence flag under 30 tight FGA).
  Additive endpoint `GET /players/{id}/contested-shooting` (honors season +
  season type incl playoffs). 3 tests; gates green (141 passed).
- **Frontend:** `ContestedShooting` type + `api.contestedShooting`; a new
  `ContestedShootingChart` analytical component (FG% bars by defender distance +
  frequency + rating banner) matching the existing chart style, rendered in the
  Vs-Model view with loading/error/empty states.
- **Labeling:** explicitly "NBA tracking splits, descriptive, **not a model
  input and not a defensive rating**" in both the API `source_note` and the UI.
  This is the ceiling of what public data allows for contest (per #2 research:
  aggregate buckets only, no per-shot contest, no shot-level model feature).
