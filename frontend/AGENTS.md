# Frontend-specific guidance

- Keep TypeScript strict and do not introduce `any` as a shortcut around an API or chart contract.
- Use the centralized client in `src/lib/api.ts`; do not scatter raw `fetch` calls through components.
- Handle loading, error, empty, stale/unavailable, and success states for remote data.
- Describe model outputs as estimates. Surface sample size, evaluation period, confidence intervals, dataset version, and known limitations where relevant.
- Update Vitest coverage and regenerate `src/lib/schema.d.ts` when a user-visible API contract changes.
