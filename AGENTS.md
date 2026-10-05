# NBA Stat Analyzer agent guide

## Mission

Build this repository as a production-grade ML/SWE portfolio project. Favor evidence, reproducibility, typed boundaries, leakage-resistant evaluation, and operational clarity over feature count.

## Repository map

- `backend/app`: FastAPI application, NBA client/cache, services, and pipeline code.
- `backend/tests`: offline unit and integration tests; never depend on live NBA.com or Gemini calls.
- `frontend/src`: strict TypeScript React client. API transport belongs in `lib/api.ts` and contracts in `lib/types.ts` or generated `lib/schema.d.ts`.
- `docs`: architecture, model, operations, security, and portfolio evidence.
- `.kiro/agents`: task-focused agents; `.kiro/skills`: the coordinating
  `nba-agent-workflow` skill.

## Working agreements

- Preserve unrelated user changes. Inspect `git status` before broad edits.
- Add or update tests with behavior changes. Mock third-party services in the default suite.
- Do not promote a model that fails its recorded quality gate. A forced promotion requires an explicit user instruction and must be documented.
- Do not deserialize an unverified remote model artifact. Check its configured SHA-256 first.
- Keep `/api/v1` backward compatible unless the task explicitly authorizes a breaking version.
- Keep secrets out of source, logs, fixtures, generated contracts, and documentation.

## Delegation

For work that spans independent areas, delegate read-heavy tasks in parallel and keep the primary agent responsible for decisions and integration. The task-focused agents live in `.kiro/agents/`; the `.kiro/skills/nba-agent-workflow` skill documents when to use which and the review DAG.

- `nba-data-scraper` for resumable NBA.com ingestion into verified Parquet.
- `web-researcher` for one scoped, cited external lookup (read-only).
- `bug-efficiency-validator` for read-only defect, correctness, and efficiency review.
- `api-contract-verifier` to keep OpenAPI and the generated TS client types in sync.
- `ml-model-evaluator` for leakage, calibration, uncertainty, slicing, and promotion review.
- `live-ui-auditor` to drive the running app and verify the four journeys work (functional only).
- `ui-design-validator` for a visual-design critique against Material Design (symmetry/spacing/grid/hierarchy).
- `feature-test-author` for offline tests covering one feature or bug.
- `docs-progress-tracker` to keep the progress docs current.

Do not parallelize edits to the same files. Reviewers run after edits settle; wait for all requested reviewers, reconcile findings against the code, and verify centrally.

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

Run the focused subset during iteration, then the full gate above before handoff.

## Code Review Rules

### Domain correctness
- Flag random shot-level splits, target leakage, evaluation on tuning data, and unreported slice regressions.
- Flag model results without dataset version, time boundaries, baseline comparison, and uncertainty.
- Flag unbounded NBA API retries, cache stampedes, unsafe stale data, leaked upstream details, and unvalidated query inputs.
- Flag frontend `any`, ad hoc fetches, missing loading/error/empty states, and claims that overstate what the model measures.

### Secrets and supply chain
- Flag any secret, token, or credential committed to source, logs, fixtures, generated contracts, or docs. A staged `.env` or key file is a blocker.
- Flag unpinned, newly added, or suspicious (possible typosquat) dependencies, and any ignored `npm audit --audit-level=high` or Python advisory. New deps use exact pins and a known, maintained package.

### Performance and efficiency
- Flag N+1 or redundant NBA.com calls, repeated full-dataframe passes, unbounded in-memory accumulation, and missing pagination/limits on large result sets.
- Flag frontend bundle-size regressions, unnecessary re-renders, and non-lazy heavy routes/charts. Measure before claiming a regression; cite the number.

### MCP and async safety
- Flag an MCP tool that bypasses the cached NBA client, recomputes statistics the services already own, widens its write scope, or drops a tool's read-only annotation.
- Flag blocking I/O on the async event loop, unguarded shared mutable state, and lock/semaphore use that can deadlock or starve under concurrency.
