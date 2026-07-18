# NBA Stat Analyzer frontend

This directory contains the React interface for NBA Stat Analyzer. It is not an
independent data application: every statistic is requested from the FastAPI
backend under `/api`, and the frontend is responsible for interaction,
formatting, routing, and visualization.

For project-wide setup and product behavior, start with the
[`../README.md`](../README.md) and [`../docs/USER_GUIDE.md`](../docs/USER_GUIDE.md).

## Stack

- React 19 and TypeScript
- Vite 8
- React Router for client-side routes
- TanStack Query for request state and caching in the browser session
- Tailwind CSS 4 for styling
- Recharts plus a custom SVG shot chart for visualization
- Oxlint for static checks

## Routes

| URL | Page | Purpose |
|---|---|---|
| `/` | `Home.tsx` | Search entry point, scoring leaders, model and AI shortcuts |
| `/player/:id` | `PlayerProfile.tsx` | Eight-tab player dashboard |
| `/player/:id/game/:gameId` | `GameDetail.tsx` | One player's box score, shots, and scoring timeline for a game |
| `/games` | `Games.tsx` | Completed-game browser and ranked result investigation |
| `/model` | `ModelLab.tsx` | Player vs Model and Player vs Player modes |
| `/compare` | `Compare.tsx` | Redirects the legacy comparison URL to `/model?mode=h2h` |
| `/ai` | `AiMode.tsx` | Structured Gemini research reports |

The production backend serves `frontend/dist/index.html` for client-side routes,
so refreshing a route such as `/player/2544` still loads the React application.

## Local development

Install dependencies:

```powershell
Set-Location frontend
npm install
```

Start FastAPI in one terminal from the repository root:

```powershell
backend\venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Start Vite in another terminal:

```powershell
Set-Location frontend
npm run dev
```

Open <http://localhost:5173>. `vite.config.ts` proxies `/api` to
`http://127.0.0.1:8000`. The backend CORS configuration accepts the localhost
and 127.0.0.1 Vite origins.

If PowerShell prevents `npm.ps1` from running, replace `npm` with `npm.cmd` or
use Command Prompt.

## Scripts

| Command | Result |
|---|---|
| `npm run dev` | Starts Vite with hot module replacement |
| `npm run build` | Runs the TypeScript project build, then writes the Vite bundle to `dist/` |
| `npm run lint` | Runs Oxlint using `.oxlintrc.json` |
| `npm run preview` | Serves the already-built bundle with Vite for a frontend-only preview |

`preview` does not start FastAPI or configure the development `/api` proxy, so it
is useful for checking built assets but API-backed screens need an added proxy.
The normal production-like workflow is `npm run build` followed by the root
`start-app.bat`.

Vite 8 requires Node `^20.19.0` or `>=22.12.0`.

## Source organization

```text
src/
|-- App.tsx                    Navigation, routes, theme, freshness footer
|-- main.tsx                   React, router, and query-client bootstrap
|-- pages/                     Route-level screens
|-- components/
|   |-- profile/               The eight player-profile sections and filters
|   |-- model/                 xFG model and head-to-head views
|   |-- SearchPalette.tsx      Global Ctrl+K player search
|   |-- ShotChart.tsx          Dots, heatmap, and zone-vs-league SVG court
|   |-- charts.tsx             Recharts wrappers
|   `-- ui.tsx                 Shared cards, controls, states, and tooltips
`-- lib/
    |-- api.ts                 Typed request helpers and endpoint methods
    |-- format.ts              Number, percentage, sign, and logo formatting
    `-- glossary.ts            Explanations for basketball metrics
```

## Data and state conventions

- Keep statistical calculations in `backend/app/services/`. The frontend
  should render backend results rather than create a second formula source.
- Add backend calls through `src/lib/api.ts` and include every input that changes
  a request in the TanStack Query key.
- Profile filters have two scopes. Season and season type affect every tab;
  location, result, starter/bench, last-N, opponent, and date filters affect
  Overview and Game Log. The per-mode selector changes Overview display values.
- Percentiles are full-season, same-position comparisons and intentionally do
  not change with game-level profile filters.
- Model estimates and on/off estimates must remain visibly labeled. Missing
  data should use the shared loading/error/empty states rather than fabricated
  fallback values.
- The theme is stored only in the page's current React state; it is not persisted
  to local storage.

## Adding a page or dashboard

1. Implement or reuse a backend service and expose it through a router.
2. Add the client method and any reusable interfaces to `src/lib/api.ts`.
3. Build the page or section with explicit loading, error, and empty-data paths.
4. Add the route in `src/App.tsx` if it is a new page.
5. Update the user guide and architecture documentation.
6. Run `npm run lint` and `npm run build`.
