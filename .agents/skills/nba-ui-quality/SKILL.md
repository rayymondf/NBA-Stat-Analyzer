---
name: nba-ui-quality
description: Review or improve NBA Stat Analyzer accessibility, responsive design, async states, chart usability, and ML-result communication. Use for frontend quality, browser QA, and user-flow polish; not for backend-only work.
---

# NBA UI quality

Use `frontend_quality` for a read-only review when delegation is available. If browser tooling is available, verify the main flows at mobile and desktop widths with keyboard-only navigation.

Require loading, error with retry, empty, unavailable, stale, and success behavior for every remote section. Preserve focus for dialogs; use correct dialog/combobox/listbox or button semantics; expose selection state; respect reduced motion and sufficient contrast.

For ML views, show dataset/model version, sample size, temporal boundaries, baseline, uncertainty, calibration, important slices, and limitations. Phrase residuals as model estimates rather than causal skill.

Run strict TypeScript, lint, Vitest, production build, and targeted accessibility/browser checks. Report observable before/after behavior rather than CSS implementation detail.
