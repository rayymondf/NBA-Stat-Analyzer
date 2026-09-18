---
name: nba-release-readiness
description: Verify whether the NBA Stat Analyzer is ready to merge, deploy, demo, or present on a resume. Use for final checks, CI parity, release audits, and handoff evidence; not for implementing unrelated fixes.
---

# NBA release readiness

Run `scripts/verify.ps1` from this skill directory. Add `-Container` when Docker is available and the task includes deployment readiness.

The script must pass backend lint, typing, offline tests/coverage, OpenAPI export, generated TypeScript contracts, frontend lint/tests/build, and optionally the container build. It intentionally does not make repairs.

Before reporting ready:

- Inspect `git diff --check` and `git status --short`.
- Confirm generated contracts are current.
- Confirm no secret-shaped values, local databases, raw data, models, coverage, or build output became tracked.
- For an ML release, confirm dataset version and promotion evidence exist.
- For a deployment release, confirm health/readiness endpoints and artifact bootstrap configuration are documented.

Return pass/fail per gate, coverage totals, generated-contract status, container result when requested, and the smallest actionable blocker list.
