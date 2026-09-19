# NBA Stat Analyzer — M3 Expressive Revamp + Task-Scoped Agent Workflow

## Status

- **State:** COMPLETE. All 10 tasks landed and verified; see `docs/WORK_LOG.md`
  for per-task checkpoints and the final gate evidence.
- **Effort:** Full Material 3 Expressive UI redesign + a clean task-scoped agent
  workflow, plus laptop-scoped technical upgrades. Replaces the earlier
  navigation/visual-refresh effort (which landed and is preserved).
- **Baseline:** `main` at `717cbb1`. The prior redesign is present as
  **uncommitted** working-tree changes and must be preserved, not reverted.
- **Scope:** Redesign presentation and the design system across every page while
  preserving all charts, graphs, stat-analysis features, and the `/api/v1`
  contract.
- **ML constraint:** The xFG artifact stays v2 (honest status). No forced
  promotion. No heavy training/ingestion — laptop is a Lenovo Yoga 7
  (Core Ultra 256V, 16 GB RAM, 1 TB); keep technical upgrades lightweight.

## Task-scoped agents (`.kiro/agents/`)

Role-based agents were removed in favor of task-scoped ones:

- `ui-implementer` — apply M3 Expressive changes to `frontend/src` (context7).
- `live-ui-auditor` — drive the running app, report only (playwright + chrome-devtools).
- `web-researcher` — pull current design/library docs (context7 + web).
- `code-cleanup` — tidy/optimize just-written code without behavior change.
- `test-author` — write/adjust tests; keep the default suite offline.
- `api-contract-verifier` — keep OpenAPI ↔ TS types in sync.
- `progress-tracker` — maintain this file + `WORK_LOG.md` for continuity.
- `v3-trainer` — retained; not run this round (laptop constraint).

Removed: `ui-ux-reviewer` (→ `live-ui-auditor`), `code-optimizer` (→ `code-cleanup`),
`doc-writer` (superseded by `progress-tracker` for this effort).

> Session note: when the running CLI session was started before these files
> existed, spawn them as they become available; otherwise the primary agent
> performs the task-scoped work directly using the same tools (Playwright,
> Chrome DevTools, context7, read/write). Behavior and constraints are identical.

## Design direction — Material 3 Expressive

Levers: **color, shape, size, motion, containment.** Prominent primary actions
with secondary-color emphasis, spring motion, high-contrast containment, an
expressive shape scale, and larger tap targets. Do **not** break familiar
patterns (lists stay lists; labels stay). Functionality over flourish; respect
`prefers-reduced-motion` and WCAG contrast. Evolve the existing
`frontend/src/index.css` token layer into M3 tonal color roles + expressive
shape scale + motion tokens rather than discarding it. Preserve the `--series-*`
chart palette and dark/light themes. Charts are Recharts
(`components/charts.tsx`, `ShotChart.tsx`, model charts) — restyle containers,
tooltips, palette, and motion only; never change data or math.

## Task sequence

1. **Agent workflow + MCP** — rewrite `.kiro/agents/*`; wire context7 / playwright
   / chrome-devtools per least privilege; add `progress-tracker`.
2. **Baseline live audit** — enumerate real sluggishness/layout bugs + Core Web
   Vitals; compile M3 Expressive component specs; write findings under `ui-review/`.
3. **Token foundation** — tonal color roles, expressive shape scale, motion
   tokens, refined elevation; preserve dark/light + `--series-*`.
4. **Core primitives** — rebuild `components/ui.tsx` to M3 with motion + a11y.
5. **App shell + navigation** — modern M3 header/nav; keep routes + skip-link.
6. **Home + Player Profile** — apply system; restyle chart containers only.
7. **Shot Quality, Compare, Games, Ask AI** — apply system; preserve every viz.
8. **Motion, performance & a11y polish** — reduced-motion, memoization,
   bundle/code-split budgets, re-audit CWV + WCAG.
9. **Lightweight technical upgrades** — per-route error boundaries, richer
   loading/empty/error states, model-info/SHAP panel polish (honest v2 status).
10. **Full verification + handoff** — backend + frontend gates + release
    readiness; finalize continuity docs.

## Verification commands

Backend (from `backend`): `uv sync --locked --extra dev`;
`uv run ruff check app scripts tests`; `uv run mypy app`;
`uv run pytest --cov=app --cov-report=term-missing`;
`uv run python scripts/export_openapi.py`.

Frontend (from `frontend`): `npm ci`; `npm run generate:api`;
`npm run lint -- --deny-warnings`; `npm test`; `npm run build`.

Record exact results in `docs/WORK_LOG.md`.

## Resume prompt

```text
This M3 Expressive revamp is COMPLETE and verified (see docs/WORK_LOG.md). To
continue: read AGENTS.md, docs/IMPLEMENTATION_PLAN.md, and docs/WORK_LOG.md, then
run git status and git diff to review the uncommitted changes. All backend and
frontend gates pass. Nothing is committed yet — the natural next step is to
review the diff and commit (do not revert completed work). Preserve all charts
and /api/v1 compatibility; do not promote an ML model or run heavy training.
If starting new UI work, iterate against the Vite dev server (npm run dev, :5173,
proxies /api -> :8000) and re-run the gates before handoff.
```
