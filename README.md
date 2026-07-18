# NBA Stat Analyzer

NBA Stat Analyzer is a local-first web application for exploring NBA player and
game data. It combines interactive dashboards, a locally trained shot-quality
model, deterministic game analysis, and an optional Gemini-powered research
assistant.

The interface and API run on your computer. NBA statistics and headshots are
fetched from NBA.com when needed, and AI Mode sends questions and selected
computed results to Google Gemini. There is no subscription required by this
project, but upstream services have their own availability, quotas, and terms.

## What the application includes

- **Player search and profiles** for everyone who appeared in the displayed
  season, plus active players with no appearances. During July through
  September, the search index also uses the next season's published roster
  information when available.
- **Eight player dashboards**: Overview, Shooting, Efficiency, Playtime, Fouls,
  Game Log, Trends, and Impact.
- **Interactive shot charts** with individual shots, a frequency heatmap, and
  zone efficiency compared with league averages.
- **Player vs the Model**, which compares actual effective field-goal
  percentage with the result expected from the player's shot locations, shot
  types, clock, period, and home/away context.
- **Player vs Player** comparisons using per-game or per-75 statistics and
  side-by-side shot profiles.
- **Completed-game investigations** that rank likely reasons for a result using
  the four factors, bench scoring, star performance, fourth-quarter execution,
  and scoring runs.
- **Optional AI Mode** for player questions, claim checks, comparisons, and game
  analysis. Gemini selects from the app's statistical tools and returns a
  structured report with evidence, counterevidence, scope, and links.

## Technology

| Layer | Main tools |
|---|---|
| Backend and API | Python, FastAPI, Uvicorn, pandas |
| NBA data access | `nba_api`, requests, local SQLite cache |
| Frontend | React, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts |
| Shot-quality ML | scikit-learn gradient boosting and joblib |
| Optional language AI | Google Gen AI SDK with Gemini function calling and structured output |
| Verification | Python `unittest`, deterministic AI graders, Oxlint, TypeScript, Vite build |

## Quick start on the configured PC

Double-click [`start-app.bat`](start-app.bat). It starts FastAPI on
<http://localhost:8000> and opens that address in the default browser. Keep the
terminal window open while using the app; press `Ctrl+C` or close the window to
stop it.

If the browser opens before the server is ready, wait a few seconds and refresh.

## Set up a fresh checkout

The one-click launcher is for Windows. The application itself can also be
started manually on other operating systems.

### Prerequisites

- Python 3.12 is recommended.
- Node.js must satisfy Vite 8: Node 20.19.x, or Node 22.12 or newer.
- Internet access is required for initial dependency installation and uncached
  NBA.com requests.
- A Gemini API key is optional and is used only by AI Mode.

From PowerShell in the repository root:

```powershell
python -m venv backend\venv
backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt

Set-Location frontend
npm install
npm run build
Set-Location ..
```

If PowerShell blocks `npm.ps1`, use `npm.cmd install` and `npm.cmd run build`, or
run the npm commands in Command Prompt.

The built frontend is written to `frontend/dist/`. That directory and
`frontend/node_modules/` are generated locally and are intentionally ignored by
git.

### Enable AI Mode (optional)

Copy the example configuration and replace the placeholder key:

```powershell
Copy-Item backend\.env.example backend\.env
```

Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/),
then set `GEMINI_API_KEY` in `backend/.env`. Do not commit that file. All
non-AI features work without it.

### Create the shot-quality model (needed on a fresh clone)

The generated `backend/data/models/xfg.joblib` file is ignored by git. If it is
missing, The Model page reports that the model is unavailable until you run:

```powershell
backend\venv\Scripts\python.exe backend\scripts\train_models.py
```

Training downloads and caches team shot charts for the current and previous two
seasons, evaluates candidate gradient-boosted classifiers, and only saves the
new model if it passes the comparison gate. No GPU is required. The repository
does include `backend/data/shots_export.csv`, the downloadable training-data
export used by the UI.

### Launch

```powershell
.\start-app.bat
```

## Development workflow

Run the backend and frontend in separate terminals for hot reload.

Terminal 1:

```powershell
backend\venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Terminal 2:

```powershell
Set-Location frontend
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to the backend on port 8000.
FastAPI's generated API explorer is available at <http://localhost:8000/docs>.

Before handing off a change, run:

```powershell
backend\venv\Scripts\python.exe -m unittest discover -s backend\tests
Set-Location frontend
npm run lint
npm run build
```

The deterministic AI evaluation suite is separate from the unit tests:

```powershell
backend\venv\Scripts\python.exe backend\evals\run_evals.py
```

That default command does not call Gemini or consume quota. See
[`backend/evals/README.md`](backend/evals/README.md) before running live cases.

## Data, caching, and privacy

- Statistics originate from NBA.com's stats endpoints and are accessed through
  the community-maintained [`nba_api`](https://github.com/swar/nba_api) Python
  package. No NBA stats API key is required, but NBA.com can throttle or time
  out requests.
- Responses involving the season derived as current are cached for 12 hours.
  Completed-season responses and completed-game box scores/play-by-play are
  cached without expiration.
- The cache is `backend/data/cache.sqlite`. It contains both NBA responses and
  cached successful AI reports. Deleting it is safe but removes all cached data
  and makes subsequent views download or recompute it again.
- The displayed current season is derived from the calendar and changes in
  October. The footer reports the most recent completed game date found for
  that season. During the offseason, the completed season can remain the data
  season while next-season roster details appear in search.
- The Gemini key remains in `backend/.env`. When AI Mode is used, the question,
  page context, system instructions, and results returned by selected stats
  tools are sent to Google's API. Regular dashboards do not call Gemini.
- The server binds to the local machine by default and has no user accounts or
  authentication. It is designed as a personal local application, not as a
  hardened public deployment.

## Important interpretation limits

- The shot-quality model estimates make probability from recorded shot context;
  it does not see defenders, video, player identity, or shooting mechanics.
- On/off ratings are observational and lineup-dependent, not proof that a player
  caused a team's rating change.
- Game investigations are ranked statistical explanations, not a complete film
  review or causal model.
- AI Mode is instructed to use tool-returned values and is evaluated for numeric
  grounding, but generated language can still be wrong. Use its data-scope and
  tool-trace panels to verify consequential conclusions.
- Small samples, incomplete NBA endpoints, trades, and unavailable
  play-by-play can leave some cards empty or make estimates noisy.

## Project structure

```text
NBA-Stat-Analyzer/
|-- start-app.bat              Windows one-click launcher
|-- README.md                  Setup and project overview
|-- docs/
|   |-- USER_GUIDE.md          Screen-by-screen usage
|   |-- HOW_IT_WORKS.md        Architecture, calculations, and API
|   `-- TROUBLESHOOTING.md     Common failures and recovery
|-- backend/
|   |-- app/
|   |   |-- ai/                Gemini orchestration and statistical tools
|   |   |-- nba/               NBA endpoint wrappers, seasons, and cache
|   |   |-- routers/           FastAPI routes
|   |   `-- services/          Statistical and ML business logic
|   |-- data/                  Generated cache/model and exported shot CSV
|   |-- evals/                 Deterministic and live AI evaluations
|   |-- scripts/               Cache warming, model training, CSV export
|   `-- tests/                 Python unit tests
`-- frontend/
    |-- src/components/        Shared UI, charts, profile and model sections
    |-- src/pages/             Route-level React components
    `-- dist/                  Production build served by FastAPI (generated)
```

## Documentation

- [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md): how to use every screen and
  interpret the main outputs.
- [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md): data flow, formulas, model,
  game investigation, AI grounding, API routes, and code organization.
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md): startup, data, model,
  build, cache, and AI problems.
- [`frontend/README.md`](frontend/README.md): frontend architecture and scripts.
- [`backend/evals/README.md`](backend/evals/README.md): AI evaluation cases,
  graders, CLI options, and quota-safe workflow.
