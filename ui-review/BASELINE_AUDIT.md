# Baseline UI Audit — before M3 Expressive redesign

Method: the running app was driven with Playwright/Chrome DevTools at desktop
(1440x900) and mobile (390x844). Evidence: `baseline-home-desktop.png`,
`baseline-home-mobile.png` in this folder; console captured. Findings below
combine live evidence with a read of the current source.

> Caveat: the FastAPI-served build in `frontend/dist` is **stale** relative to
> the uncommitted working-tree source (it still shows the old nav
> "The Model / AI Mode"; source already has "Compare / Shot Quality / Ask AI").
> The redesign is iterated against the live source (Vite dev server); these
> screenshots are the pre-redesign baseline.

## Console / errors
- Home: **0 errors, 0 warnings** — clean baseline to protect.

## Prioritized findings

| # | Severity | Finding | Evidence | Redesign direction (M3 Expressive) |
|---|----------|---------|----------|-------------------------------------|
| 1 | High | Serif editorial display headline reads dated/newspaper, not modern big-tech (Google/Tesla). | `baseline-home-desktop.png` hero | Expressive geometric sans (Manrope) on an emphasized M3 type scale; remove serif display. |
| 2 | High | Weak hierarchy & containment — content floats on a flat near-black page; cards are dark-on-dark and low-contrast; leaderboard rows are hairline-only. | hero + leaderboard + "Player vs the Model" card | Tonal surface tiers (surface / surface-container / -high) + defined containers; stronger elevation and edges. |
| 3 | High | Sparse layout with large empty vertical gaps; single narrow column underuses 1440px width. | top gap above eyebrow; hero spacing | Tighter vertical rhythm; balanced multi-column hero/leaderboard; purposeful spacing scale. |
| 4 | Med | Primary actions lack prominence (muted search field + CTAs). | hero search, model teaser arrow | Prominent primary action with secondary/tertiary color emphasis; larger tap targets (>=48px). |
| 5 | Med | Nearly monochrome; color is barely used to guide attention. | whole page | Deliberate M3 color roles to draw the eye to key actions and active states. |
| 6 | Med | Chip/CTA affordances (Ask the Analyst) are low-contrast dark tiles. | "Ask the Analyst" grid | Expressive chips with clear container + hover/press motion. |
| 7 | Low | Footer is a dense, low-contrast paragraph block. | page footer | Improve rhythm/contrast; keep honesty text. |
| 8 | Info | All charts/visualizations must be preserved exactly (Recharts). | source | Restyle containers/tooltips/palette/motion only; never touch data or math. |

## M3 Expressive component specs to build against

- **Color roles:** primary / on-primary / primary-container / on-primary-container;
  same for secondary and tertiary; surface tiers (surface, surface-container,
  surface-container-high, surface-container-highest); outline / outline-variant.
  Keep the existing `--series-*` dataviz palette untouched for charts.
- **Shape scale:** none 0, xs 4px, sm 8px, md 12px, lg 16px, xl 28px, full 9999px.
  Use larger/pill radii for emphasis (buttons, chips, FABs, hero surfaces).
- **Size / tap targets:** interactive elements >= 48px in at least one axis;
  emphasized primary actions larger than secondary.
- **Motion tokens:** standard, emphasized, and spring easings with short/medium
  durations; all gated behind `prefers-reduced-motion: reduce`.
- **Containment:** group related elements in tonal containers with clear edges;
  raise key surfaces with elevation.
- **Guardrails:** keep familiar patterns (lists stay lists, labels stay);
  functionality over flourish; WCAG contrast; visible focus.
