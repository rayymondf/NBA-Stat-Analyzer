# Live UI/UX review

Method: the running app (`http://localhost:8000`, built frontend served by FastAPI)
was driven with the Playwright MCP across desktop (1440x900) and mobile (390x844)
viewports. Findings are evidence-based (accessibility snapshot, screenshots,
console). Screenshots are in this folder.

## Summary

The navigation/IA overhaul (Task 7) and visual refresh (Task 8) landed cleanly.
All graphs, visualizations, and stat-analysis features are preserved; the change
is presentation-only. Zero console errors or warnings across pages.

## What was verified

- **Home** (`home-desktop.png`, `home-mobile.png`): new brand mark (blue "N" tile
  + serif wordmark), pill-style active nav with a clear active state, hero radial
  glow, live PPG leaderboard, model teaser, AI prompt chips. Landmarks present:
  `banner`, `navigation[aria-label="Primary"]`, `main`, `contentinfo`; single H1.
- **Player profile** (`player-desktop.png`): header + headshot + team logo, six
  headline stats, AI question chips, full tab bar (Overview / Shooting /
  Efficiency / Playtime / Fouls / Game Log / Trends / Impact), filter bar
  (season / splits / date range), stat-tile grid (now softly elevated), and the
  color-coded percentile bars using the dataviz palette. All intact.
- **The Model** (`model-desktop.png`): "how this model was built" explainer,
  Player-vs-Model / Player-vs-Player toggle, metric tiles, dataset download.
- **Responsive**: mobile collapses the wordmark to the logo tile and keeps the
  primary nav in a horizontal-scroll row; hero and cards reflow correctly.
- **Accessibility**: added a global `:focus-visible` ring; nav has an accessible
  name; images use empty alt where decorative.

## Findings

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| 1 | info | The Model page shows metrics as "-" and "legacy" because the loaded artifact is xFG v2 (v3 candidate did not pass the gate and is intentionally not promoted). Honest and expected. | Documented, not a bug |
| 2 | low | Mobile primary nav uses horizontal scroll rather than a hamburger. Acceptable for 4 items; revisit if nav grows. | Deferred |
| 3 | low | Decorative headshots use empty alt (correct); leaderboard rows could add richer aria labels. Current labels are adequate. | Deferred |
| 4 | resolved | Keyboard focus was not consistently visible. | Fixed via global `:focus-visible` ring |
| 5 | resolved | Flat cards lacked depth/hierarchy. | Fixed via elevation tokens + `.card-hover` |
| 6 | resolved | Nav active state was a thin underline, low-emphasis. | Fixed via pill active state |

## Deferred to future UI work

- Optional hamburger/drawer nav if primary items exceed ~5.
- Richer ARIA on leaderboard/table rows.
- Populate The Model metric tiles fully once a v3 candidate passes the gate.
