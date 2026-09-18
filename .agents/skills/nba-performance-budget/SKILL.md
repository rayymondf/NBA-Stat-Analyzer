---
name: nba-performance-budget
description: Measure and optimize NBA Stat Analyzer latency, memory, cache size, model cold start, pipeline throughput, or frontend bundles. Use for profiling, performance regressions, load tests, and capacity evidence; not for unmeasured style refactors.
---

# NBA performance budget

Run `scripts/benchmark.py` first for a repeatable local snapshot. Use a running production-like server and load tool only when the task authorizes traffic.

Classify every result as cold start, warm cache, upstream network, CPU/dataframe, memory, SQLite I/O, model inference, browser render, or bundle transfer. Compare like-for-like inputs and record machine/runtime context.

Initial budgets:

- Warm summary and overview: under 150 ms p95.
- Warm xFG: under 250 ms p95, with model/native initialization paid before readiness.
- Runtime SQLite logical payload: under 100 MB after pipeline-only data is removed.
- Initial app JavaScript: under 100 KB gzip excluding lazy route/vendor chunks.
- No single API request may consume an unbounded retry or upstream fan-out budget.

Optimize the highest measured bottleneck, add a regression check where stable, rerun the same measurement, and report before/after values. Do not trade correctness, calibration, accessibility, or bounded failure behavior for a benchmark win.
