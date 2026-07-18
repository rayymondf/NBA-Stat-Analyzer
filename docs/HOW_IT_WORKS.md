# How It Works

This explains what happens under the hood — accessible enough for a non-technical
owner, detailed enough for a future developer.

## The big picture

```
Your browser  ──►  FastAPI backend (Python)  ──►  NBA.com stats  (cached in SQLite)
   (React UI)          computes every stat            +  Google Gemini (AI Mode only)
```

One program (`start-app.bat` → `uvicorn`) runs the whole thing on
`http://localhost:8000`. It serves both the website and the data API from the
same address, so there's nothing else to start.

## Where the data comes from

All statistics are **official NBA.com data**, pulled through the free
[`nba_api`](https://github.com/swar/nba_api) library. There is **no dataset file
to download and no key** for the stats themselves — the app fetches live and
remembers what it fetched.

Key sources it uses:

- Player index & bios (search, team, position, headshot, height/weight/age)
- Player game logs (basic + advanced) — the backbone of most numbers
- League-wide season tables — used for percentile rankings and leaderboards
- Shot chart detail (every shot's location + a league-average baseline)
- Box scores and play-by-play (V3 endpoints) — for game investigations, the
  scoring timeline, and foul-type breakdowns
- Team on/off splits — for the Impact tab

## Caching and freshness

Every NBA.com response is stored in `backend/data/cache.sqlite`:

- **Completed seasons** are cached **permanently** — their final stats never
  change, so they're fetched once and reused forever (this is why old seasons
  load instantly).
- **The current season** uses a **12-hour** cache, so new games show up within
  half a day without ever going stale for long.

The **current season is derived from today's date** every time it's needed
(a new season begins each October). So when 2026-27 tips off, the app starts
pulling it automatically — no code change, no reinstall. Old seasons are never
deleted; they just move into the "completed" bucket and stay browsable through
every season dropdown. The footer on each page shows the exact latest game date
so you always know how current the data is.

`backend/scripts/warm_cache.py` is optional — it pre-loads the league-wide
tables for the two most recent seasons so the very first search feels instant.
The app works fine without it.

## How the statistics are computed

**Every number shown in the app is calculated by the Python backend**, never by
the AI. The `backend/app/services/` folder is the stats engine — one file per
concern:

| File | Responsibility |
|------|----------------|
| `frames.py` | Builds the game-log DataFrame and does all per-game / per-36 / per-75 / per-100 conversions and shooting math. The single source of truth. |
| `players.py` | Search, bio, the summary card, and filtered stat bundles. |
| `percentiles.py` | Position-based percentile rankings (vs same-position peers, minimum games/minutes). |
| `shooting.py` | Shot-chart points, zone and distance breakdowns, league comparison. |
| `efficiency.py` | True shooting, effective FG%, usage, ratings, turnover rate. |
| `playtime.py` / `fouls.py` | Minutes, availability, clutch; foul counts and types. |
| `gamelog.py` | The game-log table and the single-game detail (shot chart, timeline). |
| `trends.py` | Rolling averages, "is recent form unusual" (a z-score), career history. |
| `impact.py` | On/off net-rating estimates (flagged as estimates). |
| `compare.py` | Bundles two players for the Compare page. |
| `league.py` | Leaders, most-improved, similar players, team-defense rankings. |
| `game_investigation.py` | Ranks the reasons a team won/lost using the four factors + play-by-play. |

The `backend/app/routers/` files expose these as web addresses (e.g.
`/api/players/2544/shooting`). The frontend just asks for computed results and
draws them.

## The ML model: shot quality (xFG)

This is the app's only *trained* machine-learning component, different from
AI Mode, which reasons in language but trains nothing.

**What it does, in plain English.** The model studied about 657,000 real NBA
shots (three full seasons) and learned how often shots go in from every spot
and shot type: a dunk goes in 90%+ of the time, a wide corner three about 39%,
a deep stepback about 33%. For any player it then answers: *from the exact
spots and shot types this player used, what would an average NBA player have
shot?* That is **expected eFG% (xFG)**. Comparing it with the player's
**actual eFG%** isolates pure shot-*making* skill from shot *selection*. A
+3.0 delta means the player converts well above what their shot locations
usually yield.

**What it is NOT.** The model only sees shot data NBA.com records: court
location, distance, angle, shot type (dunk, layup, pull-up and so on),
quarter, seconds left in the quarter, home or away. It **never sees video or
images**; judging shooting *form* from clips is computer vision, a much
heavier kind of ML that is out of scope for this app.

**How it was trained (and how to retrain).**
`backend/scripts/train_models.py` downloads the league-wide shots (30 cached
requests per season), tries several gradient-boosted classifier settings
(scikit-learn: free, local, a few minutes), grades the winner on 87,738
held-out shots it never trained on, and only saves the new model if it beats
the previous one on those exact same shots. Its predicted make rates match
reality within about one point at every distance, and it knows an
end-of-quarter half-court heave is a low-percentage shot, not a normal
three-pointer. The result is saved to `backend/data/models/xfg.joblib`.
Re-run the script once a season if you want it refreshed:

```
backend\venv\Scripts\python.exe backend\scripts\train_models.py
```

**Where it shows up.** "The Model" section in the top navigation is its home:
pick a player and see actual vs expected eFG%, a league-distribution chart, a
calibration chart, per-zone deltas, and a download link for the full training
dataset as a CSV. A compact "Shot quality (ML)" card also stays in every
player's Shooting tab, and AI Mode can cite it through the `get_shot_quality`
tool. It is always labeled as a model estimate, never presented as a box-score
fact.

## How AI Mode works (and why it doesn't make things up)

AI Mode uses Google Gemini, but with a strict contract: **the language model
never calculates or invents statistics.** Its only jobs are to interpret your
question, decide which analyses to run, read the results, look for
counterexamples, and explain the answer.

Mechanically (`backend/app/ai/`):

1. Your question goes to Gemini with the relevant subset of **14 available
   tools** — each tool is a thin wrapper around one of the stats services above
   (`get_player_stats`, `get_shot_profile`, `compare_players`,
   `investigate_game`, `league_query`, `find_similar_players`, …). Explicit
   Player, Claim, Compare and Game modes expose only the tools they can use;
   Auto keeps the full set, except exact game-page context is safely routed to
   Game mode.
2. Gemini calls the tools it needs. Those tools run the **real Python
   calculations** and hand back computed JSON.
3. Gemini writes its answer into a fixed structure: a written explanation, a
   verdict (for claims), evidence and counterevidence items, and a data-scope
   block (seasons, sample size, definitions, filters, timestamp).
4. The frontend renders that as the report card, with clickable links back to
   the players and games involved.

Guardrails baked into the instructions:

- State sample sizes; call anything under ~10 games weak evidence.
- If a season is very young (fewer than ~15 games), the tools flag it and the AI
  also pulls the **previous season**, labeling which season each number is from.
- Look for counterevidence before concluding; never declare one player
  universally "better" on a single-category edge.
- If the data is insufficient, say **"Insufficient evidence"** instead of
  guessing.

Successful identical questions are cached for 12 hours, including their page
context, mode, model and current season. Concurrent duplicates share the same
in-progress request. This prevents refreshes and double-clicks from consuming
the free quota twice. The response's data-scope panel also shows token use,
model attempts and whether an answer came from this local cache.

Because the model only ever repeats numbers the tools computed, you can trust the
evidence panel — and verify it yourself by opening the same player or game.

### AI reliability & limits

Gemini's free tier has per-minute and per-day caps, and its newest models
occasionally get overloaded. The app handles this:

- It tries the configured primary model, then the stable
  `gemini-3.1-flash-lite` efficiency fallback.
- If a rate limit says "retry in N seconds" and N is short, it waits and retries
  once on its own.
- If everything is capped, you get a clear message ("wait a minute" vs "daily
  free allowance used up — resets around midnight Pacific"). All non-AI features
  keep working regardless.

The app limits the final report to 1,600 output tokens and uses low thinking
effort by default. Both are configurable in `backend/.env`. Gemini's exact
free-tier RPM, input-token-per-minute and daily request limits vary by project
and model, so Google AI Studio is the source of truth rather than hard-coded
numbers in the app.

The model is configured in `backend/.env` (`GEMINI_MODEL`); the key lives there
too and never leaves your PC except to call Google's API.

## Project layout

```
NBA-Stat-Analyzer/
├── start-app.bat          One-click launcher
├── README.md              Overview + setup
├── docs/                  This documentation
├── backend/               Python / FastAPI
│   ├── app/
│   │   ├── main.py        Wires everything together; also serves the built UI
│   │   ├── nba/           NBA.com access + SQLite cache + season helpers
│   │   ├── services/      The statistics engine (all math lives here)
│   │   ├── routers/       Web addresses (/api/...)
│   │   └── ai/            Gemini orchestrator + tools
│   ├── scripts/warm_cache.py
│   ├── data/cache.sqlite  Cached NBA responses (auto-created)
│   └── .env               Your Gemini key (not committed)
└── frontend/              React + Vite + Tailwind
    ├── src/pages/         Home, PlayerProfile, Compare, Games, GameDetail, AiMode
    ├── src/components/    Shot chart, charts, search palette, profile sections, UI
    └── dist/              The built site the backend serves (after `npm run build`)
```

## Making a change

- **Backend logic**: edit files under `backend/app/`, then restart the app
  (close the window and re-run `start-app.bat`).
- **Frontend**: edit files under `frontend/src/`, then rebuild with
  `cd frontend && npm run build`, and restart the app. For live editing during
  development, run `npm run dev` in `frontend/` (opens on port 5173 and proxies
  the API to 8000).
