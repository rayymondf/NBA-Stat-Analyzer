---
name: nba-feature-delivery
description: Implement a cross-layer NBA Stat Analyzer feature spanning two or more of FastAPI, analytics/ML, React, tests, or operations. Use for substantial feature delivery and architecture changes; not for a one-file fix or read-only explanation.
---

# Cross-layer feature delivery

Keep the primary agent responsible for requirements, architecture decisions, integration, and final verification.

1. Map the affected request/data/UI path and define observable acceptance criteria.
2. When delegation is available, use `code_mapper` first for a read-only map. In parallel, use `ml_evaluator` when model/data semantics change and `api_reviewer` when endpoints, caching, concurrency, or security change.
3. Reconcile reviewer evidence before editing. Delegate implementation only into non-overlapping file sets; otherwise implement centrally.
4. Update tests at the lowest useful layer and add an integration/contract test for the cross-layer boundary.
5. Regenerate OpenAPI/TypeScript contracts after route changes. Preserve `/api/v1` compatibility or document a deliberate version break.
6. Finish with `$nba-release-readiness`. Do not call the feature complete while a required gate fails.

Return the user-visible result, architecture and model implications, tests and metrics, important tradeoffs, and remaining risks. Avoid listing raw agent transcripts.
