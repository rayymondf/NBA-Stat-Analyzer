---
name: nba-agent-workflow
description: Orchestration guide for the NBA Stat Analyzer's task-focused agents. Use this skill whenever you are planning or coordinating work on this repo — deciding which agent runs which precise task, in what order, and how they hand off — for any change touching player lookup, player comparison, the AI/Gemini mode, the xFG model-comparison feature, the data pipeline, the API contract, the UI, docs, or tests. Consult it before delegating so each task goes to the least-privilege agent and the verification gate runs. Reach for this even when the user just says "work on feature X" without naming an agent.
---

# NBA Stat Analyzer — task-focused agent workflow

This project is a prototype NBA analytics platform (FastAPI backend + strict
TypeScript/React frontend + a leakage-resistant xFG ML pipeline). The four core
user features are: **look up a player**, **compare players**, **ask the AI /
Gemini NBA mode**, and **compare a player against the trained ML model (xFG)**.

Work is split across **task-focused agents** — each owns one precise task, not a
broad role. The primary (default) agent stays responsible for decisions,
integration, and the final gate. Agents do narrow, non-overlapping work and hand
results back.

Treat the code as a prototype: do not assume existing code, tests, or metrics
are correct until an agent verifies them.

## Product surfaces (don't confuse them)

Three distinct surfaces expose the same analytics; know which one a task touches:

- **`/api/v1` REST** — serves the React frontend and traditional clients.
- **In-app Ask AI (Gemini)** — Gemini is embedded **inside the backend**
  (`app/ai/orchestrator.py` + `app/ai/tools.py`) and called via
  `/api/v1/ai/ask`. It does **not** go through MCP. It is the project's own
  feature for its own users.
- **`nba_stats` MCP server** (`backend/mcp_servers/nba_mcp/`) — a local,
  read-only Model Context Protocol server that lets an **external** AI client
  (Claude Desktop, Kiro, Cursor) call this project's NBA tools. It wraps the
  same `app.ai.tools` functions. It is a distribution surface, not part of the
  web request path. A `nba-mcp-config` generator prints a ready-to-paste client
  config; see `backend/mcp_servers/README.md`.
  > A second `nba_gemini` MCP server was prototyped and then **removed** — an
  > external client already has its own LLM to orchestrate `nba_stats`, so a
  > hosted Gemini proxy added no value.

## The agents and their single task

| Agent | Precise task | Edits? |
|-------|--------------|--------|
| `nba-data-scraper` | Ingest NBA.com data → verified Parquet; manage request cache | data only (via pipeline) |
| `web-researcher` | Answer one scoped external question with citations | no |
| `bug-efficiency-validator` | Find bugs + efficiency problems, report with evidence | no (read-only) |
| `api-contract-verifier` | Keep OpenAPI ↔ TS types in sync; flag /api/v1 breaks | no (regenerates + diffs) |
| `ml-model-evaluator` | Review an xFG candidate: leakage, calibration, gate | no (read-only evaluate) |
| `live-ui-auditor` | Drive the running app, verify the 4 journeys WORK + runtime evidence | writes only `ui-review/` (functional prefixes) |
| `ui-design-validator` | Visual design critique (symmetry/spacing/grid/hierarchy) vs Material Design | writes only `ui-review/design-*` |
| `feature-test-author` | Write/adjust offline tests for one feature or bug | writes only test files |
| `docs-progress-tracker` | Record completed / remaining / next steps | writes only `docs/**` |

Full definitions live in `.kiro/agents/<name>.json`. Each has least-privilege
tools, scoped write paths, and pinned shell commands.

## When to use which agent

- **Need fresh/more NBA data, or cache is stale** → `nba-data-scraper`.
- **Unsure about an external API or library version** → `web-researcher` (before coding, to remove guesswork).
- **Changed backend schemas or regenerated types** → `api-contract-verifier`.
- **Touched the xFG model / have a training candidate** → `ml-model-evaluator` (never promote without its PASS).
- **Changed anything user-facing and want to confirm it still WORKS** → `live-ui-auditor` (journey works end to end).
- **Changed how the UI LOOKS / want a design-quality pass** → `ui-design-validator` (Material Design conformance: symmetry, spacing grid, hierarchy).
- **Any behavior change or bug fix** → `feature-test-author` (lock it with an offline test).
- **Want a defect/perf sweep of a module or diff** → `bug-efficiency-validator`.
- **Finished a chunk of work** → `docs-progress-tracker` (keep continuity).

## The workflow (DAG)

```
            web-researcher ──┐  (optional: close a knowledge gap first)
                              v
 nba-data-scraper ─► [PRIMARY implements the change] ─► feature-test-author
                              │                                │
      ml-model-evaluator ◄────┤ (ML path: candidate review)    │
                              │                                v
                              ├─► api-contract-verifier   (if API/schema touched)
                              ├─► bug-efficiency-validator (read-only review)
                              ├─► live-ui-auditor          (if UI touched — UI works?)
                              └─► ui-design-validator      (if UI touched — UI looks right?)
                                              │
                                              v
                                   docs-progress-tracker  (record done / next)
```

Rules of the DAG:
- Reviewers (`bug-efficiency-validator`, `api-contract-verifier`,
  `ml-model-evaluator`, `live-ui-auditor`, `ui-design-validator`) run **after**
  edits settle and run in parallel where independent. They report; the primary
  agent reconciles and fixes.
- Never let two agents edit the same files. Writers have disjoint write scopes by
  design (data / tests / ui-review / docs); keep it that way.
- `live-ui-auditor` (functional) and `ui-design-validator` (visual) both write
  `ui-review/` but with disjoint filename prefixes (functional
  `journey-`/`task-`/`polish-` vs `design-`); never the same files.
- `docs-progress-tracker` runs last so the record reflects verified reality.

## Typical flows

**Add a filter to player comparison (API + UI):**
1. (optional) `web-researcher` — confirm any library detail.
2. Primary — implement across backend service, router, and frontend.
3. `api-contract-verifier` — regenerate OpenAPI + TS types, confirm /api/v1 compatible.
4. `feature-test-author` — offline tests for the new param + UI state.
5. `bug-efficiency-validator` — review the diff for defects/perf.
6. `live-ui-auditor` — prove the compare journey still works.
7. `docs-progress-tracker` — log it.

**Evaluate a new xFG candidate:**
1. `nba-data-scraper` — run resumable ingestion for an ID-complete v3 dataset.
2. Primary — train the candidate (saves evidence even if the gate fails).
3. `ml-model-evaluator` — leakage/calibration/slice/gate review → PROMOTE / DO NOT PROMOTE / INSUFFICIENT EVIDENCE.
4. Primary — promote **only** on an explicit PASS and explicit user instruction.
5. `docs-progress-tracker` — record the honest status (stays v2 unless a gate-passing v3 is promoted).

**Design-quality pass on the UI:**
1. Ensure the app is running (dev server or built app).
2. `ui-design-validator` — measure each page at desktop + mobile widths against
   the Material rubric; write `design-*` reports/screenshots to `ui-review/`.
3. Primary — apply the highest-impact visual fixes, preserving charts and the
   existing M3 tokens / `--series-*` palette.
4. `ui-design-validator` — re-run to confirm the fixes landed.
5. `docs-progress-tracker` — log it.

**Investigate "the AI mode feels broken":**
1. `live-ui-auditor` — reproduce in the running app; capture console/network.
2. `bug-efficiency-validator` — trace the orchestrator/tools path read-only.
3. `feature-test-author` — write a failing offline test (Gemini mocked).
4. Primary — fix. 5. Re-run auditor + tests. 6. `docs-progress-tracker` — log.

**Change an `nba_stats` MCP tool (`backend/mcp_servers/nba_mcp/`):**
1. Primary — edit the tool wrapper (it should stay a thin wrapper over
   `app.ai.tools`; the backend already validates and caches).
2. Primary — re-verify: `backend/.venv/Scripts/python.exe -m py_compile …`,
   import the server and confirm the tool count/flat schema
   (`await nba_stats.mcp.list_tools()`), launch `nba-mcp-stats` once.
3. `bug-efficiency-validator` — read-only review of the wrapper diff.
4. `docs-progress-tracker` — log it; update `backend/mcp_servers/README.md` if
   the tool surface changed.

## Non-negotiable constraints (from AGENTS.md)

These bind every agent and the primary:
- Default test suite stays **offline** — mock NBA.com and Gemini.
- **No forced model promotion**; a candidate that fails its gate is not promoted
  without explicit, documented user instruction.
- **Never deserialize an unverified remote artifact** — check its SHA-256 first.
- Keep **/api/v1 backward compatible** unless a breaking version is explicitly authorized.
- Keep **secrets** out of source, logs, fixtures, generated contracts, and docs.

## The verification gate (primary runs before handoff)

Backend (from `backend`):
```
uv sync --locked --extra dev
uv run ruff check app scripts tests
uv run mypy app
uv run pytest --cov=app --cov-report=term-missing
uv run python scripts/export_openapi.py
```
Frontend (from `frontend`):
```
npm ci
npm run generate:api
npm run lint -- --deny-warnings
npm test
npm run build
```
Reviewer agents may run read-only subsets during iteration; the primary agent
runs the full gate before declaring work done, then `docs-progress-tracker`
records the result.

## Note on skill locations

Kiro discovers skills from `skill://` resources, by default
`.kiro/skills/*/SKILL.md` — this file. The repo also keeps Codex-style skills in
`.agents/skills/` (e.g. `skill-creator`, `mcp-builder`); those serve the Codex
toolchain and are not auto-loaded by the Kiro default agent.
