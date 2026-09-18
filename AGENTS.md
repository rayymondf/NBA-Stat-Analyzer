# NBA Stat Analyzer agent guide

## Mission

Build this repository as a production-grade ML/SWE portfolio project. Favor evidence, reproducibility, typed boundaries, leakage-resistant evaluation, and operational clarity over feature count.

## Repository map

- `backend/app`: FastAPI application, NBA client/cache, services, and pipeline code.
- `backend/tests`: offline unit and integration tests; never depend on live NBA.com or Gemini calls.
- `frontend/src`: strict TypeScript React client. API transport belongs in `lib/api.ts` and contracts in `lib/types.ts` or generated `lib/schema.d.ts`.
- `docs`: architecture, model, operations, security, and portfolio evidence.
- `.agents/skills`: repo-specific repeatable workflows.

## Working agreements

- Preserve unrelated user changes. Inspect `git status` before broad edits.
- Add or update tests with behavior changes. Mock third-party services in the default suite.
- Do not promote a model that fails its recorded quality gate. A forced promotion requires an explicit user instruction and must be documented.
- Do not deserialize an unverified remote model artifact. Check its configured SHA-256 first.
- Keep `/api/v1` backward compatible unless the task explicitly authorizes a breaking version.
- Keep secrets out of source, logs, fixtures, generated contracts, and documentation.

## Delegation

For work that spans independent areas, delegate read-heavy tasks in parallel and keep the primary agent responsible for decisions and integration.

- Use `code_mapper` to trace ownership and request flow before a cross-layer change.
- Use `ml_evaluator` for leakage, calibration, uncertainty, slicing, and promotion review.
- Use `api_reviewer` for FastAPI contracts, cache/concurrency behavior, security, and compatibility review.
- Use `release_verifier` only after edits settle; it runs checks and reports evidence but does not repair failures unless asked.
- Use `performance_profiler` for measured latency, memory, cache, pipeline, and bundle regressions.
- Use `frontend_quality` for accessibility, responsive behavior, browser evidence, and async-state UX.
- Use `security_reviewer` for threat modeling, dependency exposure, artifact trust, abuse controls, and secret handling.
- Use `portfolio_reviewer` to turn verified architecture, tests, and metrics into honest resume/demo evidence.
- Use the built-in `worker` for a bounded implementation only when it owns a non-overlapping file set.

Do not parallelize edits to the same files. Wait for all requested reviewers, reconcile findings against the code, and verify centrally.

## Required verification

From `backend`:

```text
uv sync --locked --extra dev
uv run ruff check app scripts tests
uv run mypy app
uv run pytest --cov=app --cov-report=term-missing
uv run python scripts/export_openapi.py
```

From `frontend`:

```text
npm ci
npm run generate:api
npm run lint -- --deny-warnings
npm test
npm run build
```

Use the `$nba-release-readiness` skill for the full local gate. Run only the focused subset during iteration, then the full gate before handoff.

## Code Review Rules

- Flag random shot-level splits, target leakage, evaluation on tuning data, and unreported slice regressions.
- Flag model results without dataset version, time boundaries, baseline comparison, and uncertainty.
- Flag unbounded NBA API retries, cache stampedes, unsafe stale data, leaked upstream details, and unvalidated query inputs.
- Flag frontend `any`, ad hoc fetches, missing loading/error/empty states, and claims that overstate what the model measures.
