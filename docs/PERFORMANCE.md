# Performance evidence

Measurements below were taken on Windows 11 with Python 3.12.10. They are local
engineering evidence, not a hosted-service SLA. Reproduce them with:

```powershell
backend\.venv\Scripts\python.exe .agents\skills\nba-performance-budget\scripts\benchmark.py
```

## Implemented optimizations

| Area | Before | After | Result |
|---|---:|---:|---|
| SQLite logical payload | 451.3 MB | 54.0 MB | Removed 397.3 MB across 90 training-only team-season entries |
| SQLite main file | 452.2 MB | 54.4 MB | Vacuumed after narrow verified-key deletion |
| PlayerProfile entry, gzip | 8,889 B | 4,431 B | Analytics tabs now load on selection (~50% smaller entry) |
| Feature dtype | float64/mixed construction | float32 one-pass construction | Current 100k-row matrix is 13.73 MiB |

The removed cache entries were only `ShotChartDetail` team-level requests with
`player_id=0`, used by the superseded training path. Player-facing entries,
the 657k-row legacy export, and the working v2 model remain. Those 90 payloads
are recoverable by re-fetching NBA.com.

## Current snapshot

- 100,000 strict feature rows: 271.5 ms (~368k rows/s), 13.73 MiB, `float32`.
- Cold local v2 joblib load in the snapshot process: 2.37 s.
- First model warmup/native prediction: 1.65 s; application lifespan pays this
  before readiness so the first visitor does not.
- Initial shared JS is approximately 92 KiB gzip when counting the entry,
  runtime, API, and UI chunks. Large Recharts code is isolated in a lazy chart
  chunk (~105 KiB gzip).
- Runtime cache after cleanup: 331 entries, 54.0 MB logical payload.

Numbers vary with antivirus, disk cache, CPU power state, and whether native ML
libraries were already initialized. Compare like-for-like processes.

## Code-level changes

- Feature construction builds one float32 column dictionary and one dataframe
  rather than repeatedly inserting columns.
- Grouped bootstraps now represent re-sampled games with sample weights instead
  of concatenating repeated row-index arrays.
- The model loads once under a lock and is explicitly warmed in lifespan.
- Pipeline imports are lazy, so API startup does not eagerly load PyArrow and
  DuckDB.
- SQLite uses WAL, decoded-object LRU, logical-size pruning, checkpoints, and a
  narrow training-payload cleanup path.
- Search debounces 250 ms and aborts superseded network work.
- React routes and expensive profile tabs use code splitting.
- Immutable frontend assets receive a one-year cache header; HTML is no-cache.

## Budgets and next experiments

| Budget | Target | Status |
|---|---:|---|
| Runtime SQLite logical payload | <100 MB | Pass locally (54.0 MB) |
| Initial JS excluding lazy route/vendor | <100 KiB gzip | Pass locally (~92 KiB) |
| Warm summary/overview | <150 ms p95 | Measure with Locust against a stable warm host |
| Warm xFG | <250 ms p95 | Measure after v3 artifact deployment |
| Upstream failure duration | Bounded | Two 15-second attempts plus one-second backoff is the dominant network budget |

The included Locust file models health/model-info plus weighted player summary,
overview, and shooting reads. Record user count, spawn rate, cache warmth,
player/season, host instance, p50/p95/p99, error rate, and cache headers with any
published result.
