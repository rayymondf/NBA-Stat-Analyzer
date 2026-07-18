# How NBA Stat Analyzer works

This document describes the runtime architecture, data sources, calculations,
machine-learning model, game-investigation method, AI workflow, HTTP API, and
code layout. For installation, see the [project README](../README.md). For the
interface, see the [user guide](USER_GUIDE.md).

## Runtime architecture

```text
Browser
  React + TypeScript
        |
        | HTTP /api requests
        v
FastAPI on 127.0.0.1:8000
  routers -> services -> pandas calculations
        |                 |
        |                 `-> local xFG model (when generated)
        |
        +-> stats.nba.com through nba_api
        |      `-> SQLite response cache
        |
        `-> Google Gemini, AI Mode only
               `-> calls the same Python services through AI tools
```

`start-app.bat` launches one Uvicorn process. When `frontend/dist/` exists,
FastAPI serves the compiled assets and returns `index.html` for client-side
routes. If the build is missing, the API can still start, but the website is not
available at `/`.

During development, Vite runs on port 5173 and proxies `/api` to FastAPI on port
8000. CORS is enabled only for the localhost and 127.0.0.1 Vite origins.

## A normal request

Opening a player profile typically follows this path:

1. React reads the player ID from the URL and the season from `/api/meta`.
2. TanStack Query requests the summary and then the active tab's endpoint.
3. A FastAPI router converts query parameters into service arguments.
4. The service requests the required NBA result sets through `app/nba/api.py`.
5. `app/nba/client.py` returns a cached response or makes a throttled, retried
   NBA.com request and stores the result in SQLite.
6. The service builds pandas DataFrames, filters rows, computes aggregates, and
   returns JSON.
7. React formats the values and draws the cards, tables, and charts. Statistical
   formulas are intentionally kept out of the frontend.

## Data sources

The numbers originate from NBA.com's statistics endpoints. The project uses the
community-maintained [`nba_api`](https://github.com/swar/nba_api) client; it is
not an official supported NBA SDK. NBA.com does not require an API key for these
requests, but can throttle, delay, change, or temporarily fail endpoints.

| NBA result | Used for |
|---|---|
| Player index and common player info | Search, roster state, bio, team, position, jersey, height, weight, experience |
| Base and advanced player game logs | Player aggregates, filters, per-mode rates, game logs, trends |
| League player dashboards | Leaderboards, position percentiles, efficiency, scoring splits, player similarity |
| Shot Chart Detail | Shot points, zones, league zone baselines, xFG training and inference |
| Player split and clutch dashboards | Starts, period production, assisted scoring, clutch performance |
| Team player on/off details | On-court and off-court team ratings |
| League team dashboard | Team defensive-rating rankings |
| V3 traditional box score | Player game detail and team totals for investigations |
| V3 play-by-play | Score timelines, player scoring events, foul types, scoring runs |
| League Game Finder | Completed-game lists, team game counts, starter game IDs |

Player headshots and team logos are loaded directly from NBA CDN URLs by the
browser, so they are not stored in SQLite.

## Seasons and player lookup

NBA seasons are represented as strings such as `2025-26`.

- From October through December, the current season starts in the current
  calendar year.
- From January through September, it starts in the previous calendar year.
- `/api/meta` returns the derived current season plus the previous nine seasons.
- The footer's `data_through` value is the newest completed playoff or regular-
  season game the backend can find for the derived current season.

Search starts with everyone in the current season's Player Index. It then adds
active players from the static `nba_api` registry so an injured or inactive
player with zero games remains searchable. During July through September, it
also merges NBA.com's active next-season roster index when available. Existing
season statistics are preserved while current team, jersey, and position data
can be updated from that forward roster.

Search first performs case-insensitive substring and all-word matching. If that
finds nothing, `difflib` supplies conservative typo tolerance. Results are
limited to 12 in the UI and include flags that distinguish season participants
from current-roster players with no season statistics.

## Caching, retries, and freshness

`backend/app/nba/client.py` is the single wrapper for NBA endpoint calls.

- Requests are spaced at least 0.65 seconds apart across threads.
- Each request has a 45-second timeout.
- A failure is tried up to three times with 2-, 4-, and 6-second backoff.
- The cache key includes the endpoint class, raw/normalized response mode, and
  sorted endpoint parameters.

The SQLite database is `backend/data/cache.sqlite` and contains one `cache`
table with JSON payloads, creation times, and optional TTL values.

| Cached value | Lifetime |
|---|---|
| Request whose parameters mention the derived current season | 12 hours |
| Completed-season request | No expiration |
| Automatically cached request with no season parameter | No expiration unless its wrapper sets a TTL |
| Completed-game V3 box score or play-by-play | No expiration |
| Successful AI report | 12 hours by default |

The automatic TTL decision is parameter-based. Some roster and career calls
explicitly use a 12-hour TTL even when their parameters do not include the
current season. Other no-season calls, such as common player info, remain cached
until the database is cleared; this can matter after a roster or bio change.

Deleting `cache.sqlite` is safe because it contains only reproducible responses,
but it clears both NBA data and cached AI reports. The next request recreates the
database. Its size grows with the number of players, seasons, shot charts, and
play-by-play games opened.

## Player statistics engine

`backend/app/services/frames.py` is the main aggregation source. It merges each
player's base and advanced game logs by game ID, sorts them chronologically,
derives home/away and opponent values from the matchup string, and queries
starter game IDs.

### Filters and rate modes

The backend can filter by:

- regular season or playoffs;
- home or away;
- win or loss;
- starter or bench, when the starter endpoint returned complete data;
- most recent 5, 10, or 20 games;
- opponent abbreviation;
- inclusive start and end dates.

The `last_n` filter is applied after the other filters and chronological sort,
so it means the most recent N games remaining in the selected split.

Counting statistics are returned as totals and four rates:

| Mode | Calculation |
|---|---|
| Per game | total / games |
| Per 36 | total / minutes x 36 |
| Per 75 | total / possessions x 75 |
| Per 100 | total / possessions x 100 |

Possessions come from the advanced game log when available. The fallback for a
player is `FGA + 0.44 x FTA + TOV`.

In the interface, game-level filters affect Overview and Game Log. Season and
season type affect every profile section. The per-mode switch changes the
counting-stat display in Overview; it does not rewrite percentages or fixed
full-season percentiles.

### Core formulas

The service calculates percentages from aggregate totals, not by averaging
game percentages.

| Metric | Formula |
|---|---|
| FG% | `FGM / FGA` |
| 2P% | `(FGM - 3PM) / (FGA - 3PA)` |
| 3P% | `3PM / 3PA` |
| FT% | `FTM / FTA` |
| True shooting | `PTS / (2 x (FGA + 0.44 x FTA))` |
| Effective FG% | `(FGM + 0.5 x 3PM) / FGA` |
| Free-throw rate | `FTA / FGA` |
| Three-point attempt rate | `3PA / FGA` |
| Field-goal points per shot | `(PTS - FTM) / FGA` |
| Assist-to-turnover ratio | `AST / TOV` |
| Turnover rate | `TOV / (FGA + 0.44 x FTA + TOV)` |
| Points per used possession | `PTS / (FGA + 0.44 x FTA + TOV)` |

Offensive, defensive, net rating, pace, and several usage/assist metrics come
from NBA advanced result sets when present. Game-log ratings are
possession-weighted when aggregated.

### Position percentiles

Percentiles compare a player's full-season per-game values with qualified peers
in the same broad position group: guard, forward, or center. The first character
of the listed position selects the group, so `G-F` is treated as guard.

The qualification floor is 10 games and 15 minutes per game. Lower-is-better
metrics, including turnovers, fouls, team turnover percentage, and defensive
rating, are inverted so a higher percentile always reads as better. A pool with
fewer than five valid values returns a neutral 50th percentile.

Percentiles do not respond to location, outcome, last-N, opponent, date, or
per-mode controls. The UI states this under the percentile card.

## What each service computes

| Service | Responsibility and qualifications |
|---|---|
| `players.py` | Search, bio, summary, filtered stats, full-season percentiles, and a rule-based summary sentence |
| `shooting.py` | Every shot point, five distance buckets, seven basic zones, frequency, and zone FG% vs NBA.com's league baseline |
| `efficiency.py` | TS%, eFG%, usage, AST/TO, turnover rate, free-throw rate, points per used possession, ratings, pace, PIE, and percentiles |
| `playtime.py` | Minutes, starts, minutes buckets, estimated games missed, Q4 production, foul-trouble splits, and clutch stats (last five minutes, within five points) |
| `fouls.py` | Season foul totals/rates plus foul-type classification from up to the ten most recent games' play-by-play |
| `gamelog.py` | Sortable game rows and a single player's game box score, shot chart, scoring events, and score timeline |
| `trends.py` | Adaptive rolling windows, last-10 vs season scoring/TS%, a scoring z-score, and career season rows |
| `impact.py` | Current and up to two prior seasons of team on/off ratings when the current team/season endpoint supplies them |
| `compare.py` | Two complete player blocks with per-game, per-75, efficiency, percentiles, and shot data |
| `league.py` | Qualified leaders, year-over-year TS% improvers, low-minute efficient scorers, team defense, and z-scored similar players |
| `playoffs.py` | Elimination and closeout games derived from ordered playoff logs for up to six seasons |

Some outputs are approximations:

- Games missed is team games minus player games and can be misleading around a
  trade or incomplete team data.
- Foul types use recent play-by-play only. The displayed free throws attributed
  to shooting fouls use a rough two-per-foul estimate because descriptions do
  not provide the exact count.
- The recent-form z-score compares the last-ten scoring mean with the season
  distribution. The UI labels an absolute z-score of 1.5 or more unusual; it is
  a signal, not a formal claim of causality.
- On/off data is lineup-, opponent-, and schedule-dependent.

## Shot chart and xFG model

The regular shot chart is descriptive: dots are individual attempts, the
heatmap counts attempts in court bins, and zones compare the player's raw field-
goal percentage with NBA.com's league average for the same basic zone.

The xFG component is a separately trained, local model.

### Inputs and output

`HistGradientBoostingClassifier` receives 36 numeric features derived from:

- distance, absolute horizontal location, vertical location, and court angle;
- period, capped at the fifth period;
- seconds remaining in the period;
- two- vs three-point status and home/away status;
- one-hot basic zone and zone-area values;
- one of 15 action groups such as dunk, layup, hook, floater, pull-up,
  step-back, turnaround, driving, or jump shot.

It does not receive player identity, defender location, score margin, tracking
data, video, or shooting mechanics.

For each player shot, the model predicts make probability `p`. Expected eFG is:

```text
sum(p x 1.0 for twos, p x 1.5 for threes) / number of shots
```

Actual eFG uses make-or-miss in place of `p`. The displayed delta is actual eFG
minus expected eFG. `delta_per_100_shots` converts that difference to extra
points per 100 field-goal attempts. Zone rows use raw actual FG% minus expected
FG% and omit zones with fewer than five shots.

The percentile compares the player's delta with the saved distribution of
players who had at least 200 shots in the training set. It measures model
outperformance, not overall player quality.

### Training and evaluation

`backend/scripts/train_models.py`:

1. Collects every available regular-season shot through 30 team requests for
   each of the current and previous two seasons.
2. Reserves a stratified 20% test slice from the two most recent seasons.
3. Trains the previous feature design as Model A on the remaining recent data.
4. Tunes eight Model B parameter combinations on a validation slice, then
   refits the winner on the full three-season training pool minus the test set.
5. Compares A and B on identical held-out shots using Brier score and ROC AUC.
6. Saves B only when its Brier score is lower and its AUC is no more than 0.002
   below A.
7. Saves calibration tables and the qualified-player delta distribution with
   the model bundle.

The Model page reads the saved metadata rather than hard-coding its sample,
seasons, features, or metrics. The local artifact present during this audit was
version 2, trained on 657,387 shots from 2023-24 through 2025-26 and tested on
87,738 held-out shots. Those values change after retraining.

`backend/data/models/xfg.joblib` is generated and git-ignored. A fresh checkout
must train the model before xFG pages work. `backend/data/shots_export.csv` is a
separate, tracked, human-readable export served by `/api/ml/dataset.csv`.
`export_shots_csv.py` can regenerate it from the cached or remote team shot
charts.

## Completed-game investigation

`game_investigation.py` analyzes a completed game's V3 box score and
play-by-play. It identifies the winner, computes candidate explanations, gives
each a normalized score, and sorts them from strongest to weakest.

The four-factor candidates use these weights:

| Factor | Formula | Weight |
|---|---|---:|
| Shooting efficiency | `(FGM + 0.5 x 3PM) / FGA` | 0.40 |
| Turnover rate | `TOV / estimated possessions` | 0.25 |
| Offensive rebound rate | `OREB / (OREB + opponent DREB)` | 0.20 |
| Free-throw factor | `FTM / FGA` | 0.15 |

Each margin is divided by a typical single-game standard deviation before the
weight is applied. The service also scores:

- bench-point difference;
- the top three minutes players on each team versus their season scoring
  averages;
- fourth-quarter scoring when the game was within eight points after Q3;
- unanswered runs of at least eight points from the play-by-play.

An explanation can favor the losing team; that becomes counterevidence rather
than being hidden. This is a transparent ranking heuristic, not a learned model
or proof of why the result occurred.

## AI Mode

AI Mode is distinct from the xFG model. The xFG model is trained locally to
predict shot makes. Gemini is a remote language model used to choose analyses
and explain their outputs.

### Request and modes

`POST /api/ai/ask` accepts:

- a question from 2 to 500 characters;
- `auto`, `player`, `claim`, `compare`, or `game` mode;
- optional page context whose serialized JSON is limited to 2,000 characters.

Auto mode can access all 16 statistical tools. Explicit modes expose smaller
sets to reduce irrelevant tool choices. If Auto receives an exact `game_id` in
page context, the backend routes it to the two-tool Game set.

The tool collection covers player search and splits, percentiles, shots, trends,
career history, comparisons, league queries, similar players, game listing and
investigation, game logs, on/off impact, previous-season lookup,
elimination-game analysis, and xFG shot quality.

### Grounding contract and report structure

The system instruction tells Gemini to:

- resolve names before using IDs;
- state only statistics returned by tools in that request;
- report sample sizes and warn below about 10 games;
- fetch the previous season when the current subject has fewer than about 15
  games, unless the small sample was intentionally requested;
- seek counterevidence and avoid universal comparison claims based on one edge;
- define measurable claims and use one of six verdicts;
- say that evidence is insufficient rather than guess.

Gemini must return JSON matching a Pydantic-compatible schema: answer Markdown,
optional verdict, key findings, counterevidence, data scope, entity links, and
confidence. The backend adds the selected model, UTC generation time, token
usage, model-attempt count, cache status, and a tool trace with captured tool
arguments and results.

The application does not currently run the deterministic eval grader as a
production response gate. Structured output, restricted tools, instructions,
and traceability reduce hallucination risk, but cannot make generated language
infallible. The evidence and tool trace are there so users can verify the report.

### Model selection, limits, and caching

The configured `GEMINI_MODEL` is tried first. A unique fallback candidate,
`gemini-3.1-flash-lite`, is tried for retired models, overloads, and applicable
rate-limit failures. A rate-limit response that explicitly asks for a delay of
35 seconds or less can be retried once on the same model before fallback.

Defaults:

| Setting | Default | Purpose |
|---|---:|---|
| `GEMINI_API_KEY` | none | Required credential for AI Mode |
| `GEMINI_MODEL` | `gemini-flash-latest` | Primary model requested before fallback |
| `AI_RESPONSE_CACHE` | `1` | Enable successful-report caching |
| `AI_RESPONSE_CACHE_TTL` | `43200` | Cache lifetime in seconds |
| `AI_MAX_REMOTE_CALLS` | `6` | Maximum remote calls in the automatic function-calling loop |
| `AI_MAX_OUTPUT_TOKENS` | `1600` | Generated report limit |
| `AI_THINKING_LEVEL` | `low` | Gemini thinking setting |

The generation temperature is 0.2. The cache key includes the normalized
question, effective mode, context, requested model, current season, and prompt
version. Concurrent identical requests share a per-key lock, so the second
request can reuse the first successful result instead of spending duplicate
quota. Only successful reports are stored.

## HTTP API

FastAPI exposes interactive OpenAPI documentation at `/docs` while the backend
is running. The primary routes are:

### Metadata and league

| Method and path | Purpose |
|---|---|
| `GET /api/meta` | Current season, selectable seasons/types, freshness, player-lookup note |
| `GET /api/compare?a=&b=` | Two-player bundle |
| `GET /api/league/leaders` | Qualified leaderboard for a requested stat/mode/measure |
| `GET /api/league/improvers` | Current vs previous-season metric improvement |
| `GET /api/league/similar/{player_id}` | Nearest z-scored statistical profiles |
| `GET /api/league/low-minutes-efficient` | Efficient qualified players below a minutes cap |
| `GET /api/league/team-defense` | Teams sorted by defensive rating |

### Players

| Method and path | Purpose |
|---|---|
| `GET /api/players/search?q=` | Current-season and active-roster lookup |
| `GET /api/players/{id}/summary` | Bio, headline aggregate, percentiles, blurb |
| `GET /api/players/{id}/overview` | Fully filtered aggregate and percentile block |
| `GET /api/players/{id}/shooting` | Shots, zones, distances, scoring-source split |
| `GET /api/players/{id}/shot-quality` | xFG estimate from the generated model |
| `GET /api/players/{id}/efficiency` | Advanced metrics and percentiles |
| `GET /api/players/{id}/playtime` | Availability, minutes, Q4, clutch, foul trouble |
| `GET /api/players/{id}/fouls` | Season foul profile and recent types |
| `GET /api/players/{id}/gamelog` | Filtered game rows |
| `GET /api/players/{id}/games/{game_id}` | Player-specific completed-game detail |
| `GET /api/players/{id}/trends` | Rolling season form |
| `GET /api/players/{id}/career` | Regular-season and playoff career rows |
| `GET /api/players/{id}/impact` | Team on/off ratings and history |

### Games, model, and AI

| Method and path | Purpose |
|---|---|
| `GET /api/games` | Completed games, newest first, with season/type/team/limit controls |
| `GET /api/games/{game_id}/investigate` | Ranked game-result analysis |
| `GET /api/ml/model-info` | Model availability, metadata, metrics, calibration, and dataset info |
| `GET /api/ml/dataset.csv` | Download the tracked shot export |
| `POST /api/ai/ask` | Run or retrieve a structured Gemini investigation |

The game-detail and investigation routes translate upstream NBA failures to 502
responses, while an uncaught service failure on another route appears as 500.
Missing games become 404; AI rate limits become 429; rejected/missing AI setup
becomes 503; and unexpected AI failures become 502.

## Code layout and ownership

```text
backend/app/
|-- main.py                 FastAPI setup, routers, CORS, production SPA serving
|-- nba/
|   |-- api.py              Typed endpoint wrappers
|   |-- cache.py            Thread-safe SQLite JSON cache
|   |-- client.py           Throttle, retry, timeout, and TTL selection
|   `-- seasons.py          Current/previous/next/offseason season helpers
|-- routers/                HTTP validation and service dispatch
|-- services/               Statistical, investigation, and xFG logic
`-- ai/
    |-- tools.py            Small Gemini-callable wrappers around services
    `-- orchestrator.py     Prompt, tool routing, schema, fallbacks, cache

frontend/src/
|-- App.tsx                 Routes, navigation, theme, freshness footer
|-- lib/api.ts              Browser API client
|-- pages/                  Route-level screens
`-- components/             Shared UI, charts, profile sections, model views
```

When changing a formula, update the backend service first and add a test there;
do not reproduce it in React or an AI prompt. When adding an endpoint, update the
router, `frontend/src/lib/api.ts`, the relevant screen, and this API table. When
adding an AI tool, also update explicit-mode routing and the deterministic eval
cases.
