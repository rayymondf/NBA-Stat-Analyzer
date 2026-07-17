# NBA Stat Analyzer

Explore NBA statistics visually, then use AI to investigate what those statistics
actually mean. Runs entirely on your own PC — 100% free, no subscriptions.

## What it does

- **Player analytics** — search any NBA player and open an interactive profile
  with eight dashboards: performance overview with position percentiles, an
  interactive shot chart (dots / heatmap / zones-vs-league), shooting,
  efficiency, playing time, fouls, a sortable game log, trends, and on/off
  impact.
- **Compare** — put two players side by side across scoring, efficiency,
  playmaking, rebounding, fouls and shot-location profiles.
- **Games** — pick any completed game and get a ranked, evidence-based
  explanation of why a team won or lost (four factors, star performances,
  scoring runs, fourth-quarter execution).
- **AI Mode** — ask questions in plain English ("Is Tatum inefficient in
  elimination games?", "Why did the Knicks lose on April 12?"). The AI answers
  using **this app's own computed statistics** — every conclusion shows its
  evidence, counterevidence, sample size and which seasons/games it looked at.

## How to start the app

Double-click **`start-app.bat`** in this folder. Your browser opens
http://localhost:8000 automatically. Keep the black window open while you use
the app; close it (or press Ctrl+C in it) to stop.

The first time you open a player or season, the data is fetched from NBA.com and
cached — later visits are instant.

## Documentation

- **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** — plain-English tour of every
  screen and how to use it.
- **[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)** — where the data comes from,
  how AI Mode reasons without inventing numbers, how freshness and caching work,
  and how the code is organized.
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** — fixes for the common
  issues (AI rate limits, slow first load, "port in use", blank data).

## One-time setup (already done on this PC)

Only needed if you move to a new computer:

1. Install [Python 3.12](https://www.python.org/downloads/) and
   [Node.js LTS](https://nodejs.org) (both free).
2. In this folder, run:
   ```
   python -m venv backend\venv
   backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   cd frontend && npm install && npm run build && cd ..
   ```
3. Copy `backend\.env.example` to `backend\.env` and paste your free Gemini API
   key (aistudio.google.com → "Get API key"). This key powers **AI Mode only** —
   every other feature works without it.
4. Optional, makes first use faster:
   `backend\venv\Scripts\python.exe backend\scripts\warm_cache.py`

## Good to know

- **Data source**: official NBA.com stats via the free `nba_api` library. No
  account or key needed for the stats themselves.
- **Data timeframe**: shown in the footer of every page ("2025-26 season · games
  through <date>"). The app automatically picks up each new NBA season in
  October — nothing to update.
- **Data freshness**: current-season numbers refresh every 12 hours; completed
  seasons are final and cached permanently in `backend\data\cache.sqlite` (safe
  to delete if you ever want a clean re-download).
- **AI limits**: the free Gemini tier allows a handful of questions per minute.
  If AI Mode says it's cooling down, wait a minute and retry — the app also
  falls back across several models automatically.
- **Privacy**: your Gemini key lives only in `backend\.env` on this PC and is
  never committed to git or sent anywhere except Google's API when you ask a
  question.

## Tech, in one line

FastAPI + pandas backend (all statistics computed server-side), React + Vite +
Tailwind + Recharts frontend, SQLite response cache, Google Gemini with
function-calling for AI Mode — the model decides which analyses to run but never
invents numbers. Full detail in [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).
