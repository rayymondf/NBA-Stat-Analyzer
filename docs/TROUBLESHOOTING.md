# Troubleshooting

Start with the symptom below. Commands assume PowerShell in the repository root
unless stated otherwise. Stop the running app before deleting a cache, replacing
an environment, or rebuilding files that it serves.

## Quick health check

With the backend running, open these addresses:

- <http://localhost:8000/api/meta> should return JSON.
- <http://localhost:8000/docs> should show FastAPI's API explorer.
- <http://localhost:8000> should show the React application if
  `frontend/dist/` exists.

You can test the API from PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/meta
```

If `/api/meta` works but `/` does not, the backend is healthy and the production
frontend probably needs to be built. If neither works, use the terminal error
and the startup sections below.

## The launcher says the Python environment is missing

`start-app.bat` specifically looks for
`backend\venv\Scripts\python.exe`. Create that environment and install the
backend packages:

```powershell
python -m venv backend\venv
backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

If `python` is not recognized, install Python 3.12 and make sure the installer
adds Python to `PATH`, then open a new terminal.

Do not create the environment under a different name unless you also intend to
start Uvicorn manually; the batch launcher will not find it.

## The browser says it cannot connect just after launch

The launcher opens the browser before Uvicorn finishes importing the app. Wait a
few seconds and refresh. If the terminal shows `Uvicorn running on
http://127.0.0.1:8000`, the server is ready.

If the terminal exits or shows a traceback, use the last exception rather than
the early browser message.

## The API works but the home page is 404 or blank

The compiled frontend is missing or stale. Rebuild it:

```powershell
Set-Location frontend
npm install
npm run build
Set-Location ..
```

Then restart `start-app.bat`. FastAPI detects `frontend/dist/` only when the
backend process starts.

A successful build ends with files under `frontend/dist/`. If a recent UI edit
does not appear at port 8000, rebuild and hard-refresh the browser. During active
frontend development, use Vite at <http://localhost:5173> instead.

## PowerShell refuses to run npm

An error such as “npm.ps1 cannot be loaded because running scripts is disabled”
comes from the PowerShell execution policy, not this project. Use the Windows
command shim without changing machine policy:

```powershell
Set-Location frontend
npm.cmd install
npm.cmd run build
```

You can also run the npm commands in Command Prompt. Vite 8 requires Node
20.19.x or Node 22.12+; `node --version` shows the installed version.

## Port 8000 is already in use

First identify the listener instead of stopping an unknown process blindly:

```powershell
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$listener
if ($listener) { Get-Process -Id $listener.OwningProcess }
```

If it is an old NBA Stat Analyzer/Uvicorn process, close its original terminal
or stop that confirmed process:

```powershell
Stop-Process -Id $listener.OwningProcess
```

Then launch the app again. If another application owns the port and must remain
running, start this backend on another port manually. The compiled frontend uses
relative `/api` URLs and will work on that port:

```powershell
backend\venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8010
```

Open <http://localhost:8010>. For Vite development, update its proxy target if
the backend is not on 8000.

## Port 5173 is already in use

This affects development mode only. Vite may automatically choose another port,
but the backend CORS list accepts only localhost/127.0.0.1 on port 5173. Stop the
old Vite process or explicitly return to port 5173 before testing cross-origin
API calls.

## The first player, season, Fouls tab, or game is slow

This is expected for uncached data. A player profile can need base and advanced
logs, league pools, player info, shot charts, and split dashboards. Fouls can
add up to ten play-by-play requests, and game investigation needs a V3 box score,
play-by-play, and season baselines.

NBA requests are deliberately spaced by at least 0.65 seconds and retried on
failure. After a successful load, the local SQLite cache makes the same data
substantially faster.

To pre-load player lookup and league-wide tables for the current and previous
season:

```powershell
backend\venv\Scripts\python.exe backend\scripts\warm_cache.py
```

This does not pre-load every individual player's logs, shots, foul
play-by-play, or game investigation.

## NBA data times out or a section shows an upstream error

NBA.com can throttle or temporarily fail the statistics endpoints. The backend
uses a 45-second request timeout and three attempts with backoff, so an uncached
failure can take more than a minute to surface.

Try these in order:

1. Leave the app running and retry the tab once after a minute.
2. Check whether other uncached NBA pages also fail.
3. Confirm the PC has internet access and that a VPN, firewall, or filtered
   network is not blocking `stats.nba.com` or `cdn.nba.com`.
4. Read the terminal for the endpoint name and all retry messages.
5. Restart the backend after the upstream service recovers.

Cached pages can keep working while a new endpoint is unavailable.

## A player or statistic has no data

Common valid causes are:

- the player recorded no appearance in the selected season;
- the selected season type is Playoffs and the player/team did not participate;
- the combination of home/away, result, starter status, last-N, opponent, and
  date filters leaves zero games;
- a current-roster player has not yet appeared in the season shown in the
  footer;
- the selected card depends on an NBA endpoint that returned no row;
- the xFG zone had fewer than five attempts and was intentionally omitted;
- on/off data did not include both the player-on and player-off rows.

Select **Reset filters**, switch back to Regular Season, or choose a season in
which the player appeared. The interface should display an empty state instead
of manufacturing a value.

## Starter/bench filtering seems unchanged

Starter game IDs come from a separate NBA Game Finder request. If that request
fails, the game log preserves an unknown starter state and the service avoids
applying a misleading starter/bench split. Retry after the NBA endpoint is
available. A failed request is not cached, so the next profile request can try
it again.

## The data looks out of date

Check the footer's **games through** date first. Current-season responses expire
after 12 hours, so the app is not intended to update immediately after every
final buzzer. Completed seasons do not expire.

To force every cached response to be fetched again, stop the backend and remove
the explicit cache file:

```powershell
Remove-Item -LiteralPath backend\data\cache.sqlite
```

Restart the app. This is recoverable from upstream services, but it also removes
cached AI reports and can make many first loads slow. It does not delete the
shot CSV or generated model.

During July through September, roster details can be newer than the displayed
statistics season by design. The season helper does not roll to the next stats
season until October.

## The cache database is locked or corrupt

Only delete or move `cache.sqlite` after every backend process is stopped. A
live process keeps an SQLite connection open.

If the terminal reports malformed-database errors, stop the app, preserve the
file for diagnosis if needed, then remove the explicit file and restart:

```powershell
Move-Item -LiteralPath backend\data\cache.sqlite -Destination backend\data\cache.sqlite.bak
```

The app creates a fresh database. The `.bak` copy is local and can be removed
later after the replacement is confirmed.

## The Model page says the model is not trained

The generated model bundle is intentionally ignored by git, so a fresh clone
does not contain `backend/data/models/xfg.joblib`. Create it with:

```powershell
backend\venv\Scripts\python.exe backend\scripts\train_models.py
```

The script performs 30 team shot-chart requests for each of three seasons.
Those requests are cached, but the first run needs internet access and can take
time. The final console output compares the new and previous designs. A bundle
is saved only if the candidate passes the Brier/AUC gate.

If training fails:

- confirm `scikit-learn` and `joblib` were installed from
  `backend/requirements.txt`;
- look for an NBA endpoint retry error earlier in the output;
- rerun later so completed team requests are reused from SQLite;
- confirm the final line says the model was saved and that
  `backend/data/models/xfg.joblib` exists;
- restart the backend so the model-info endpoint and lazy model loader see the
  new file.

Do not delete the entire `backend/data` directory to fix this issue; it also
contains the tracked downloadable dataset.

## The model dataset download is missing

The API serves `backend/data/shots_export.csv`. Regenerate that file from the
same team shot-chart source with:

```powershell
backend\venv\Scripts\python.exe backend\scripts\export_shots_csv.py
```

This can make the same 90 season/team requests as training, but reuses existing
SQLite entries. Rebuilding the frontend is not required after replacing the
CSV; restart the backend only if it was started before the file existed and the
page still appears stale.

## AI Mode says the API key is missing or rejected

AI Mode needs `backend/.env` with a real key:

```powershell
Copy-Item backend\.env.example backend\.env
```

Edit the new file and set:

```dotenv
GEMINI_API_KEY=your-real-key
```

The literal `your-key-here` placeholder is not valid. Create a key in
[Google AI Studio](https://aistudio.google.com/), save the file, and restart the
backend so it reloads the environment.

If `/api/ai/ask` is missing entirely, reinstall backend requirements; `main.py`
skips the AI router only when its import dependencies are unavailable.

## AI Mode is rate-limited, cooling down, or overloaded

- **Wait about a minute** indicates a request- or token-per-minute limit.
- **Today's allowance is used up** indicates a per-day project limit and the
  message reports the expected Pacific-time reset window.
- **Servers are overloaded** indicates a temporary provider-side failure.

The backend tries the configured model and one stable Flash-Lite fallback. It
can wait and retry once when Google explicitly returns a short reset interval.
It does not continually retry because that can spend more quota.

Gemini limits are applied by Google and vary by model, project, and account.
Check Google AI Studio for the active values. All non-AI dashboards continue to
work during an AI outage.

## An AI answer is unexpectedly cached

The same normalized question, mode, page context, requested model, prompt
version, and current season reuses a successful answer for 12 hours. The Data
Scope panel says when a report is cached.

To test generation without cache, stop the app, set this in `backend/.env`, and
restart:

```dotenv
AI_RESPONSE_CACHE=0
```

Restore it to `1` afterward. Disabling the cache does not delete existing rows;
it only stops reading and writing AI reports while disabled. Deleting
`cache.sqlite` also clears the report but unnecessarily clears all NBA data.

For the evaluation runner, `--fresh` temporarily disables response-cache use
for that process.

## An AI answer uses too little data or seems wrong

Open **Data scope, definitions & tool calls** and check:

- season and season type;
- sample size and filters;
- which tools were called;
- whether the report used the current or previous season;
- counterevidence, confidence, and cached status.

For fewer than about 15 current-season games, the tools prompt Gemini to fetch
the previous season and label both. An intentional last-N question remains a
small sample and is not automatically expanded.

Generated language is not guaranteed correct even though the system requires
tool-grounded values. Compare surprising numbers with the linked player or game
page. Rephrase ambiguous questions with a player, season, season type, and
measurable claim. Each AI submission is independent, so do not rely on an
earlier answer to supply an omitted name.

## Unit tests, lint, or build fail

Run the checks independently to isolate the layer:

```powershell
backend\venv\Scripts\python.exe -m unittest discover -s backend\tests

Set-Location frontend
npm run lint
npm run build
```

The default AI eval is also local and quota-free:

```powershell
backend\venv\Scripts\python.exe backend\evals\run_evals.py
```

If imports fail, reinstall `backend/requirements.txt` into the exact
`backend/venv` interpreter. If TypeScript cannot find modules, run `npm install`
inside `frontend`, not the repository root.

## Collect useful information for a bug report

Include:

- the exact page, player/game ID, selected season/type, and filters;
- whether the data was cached or this was the first load;
- the last 20 to 40 terminal lines, including the first exception;
- browser developer-console errors for a blank UI;
- Python and Node versions (`python --version`, `node --version`);
- the result of `/api/meta` and whether `/docs` opens;
- for AI issues, the mode, Data Scope/tool trace, HTTP status, and error message,
  but never the API key.
