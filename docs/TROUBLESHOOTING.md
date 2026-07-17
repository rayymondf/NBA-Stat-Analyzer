# Troubleshooting

Common issues and quick fixes. Most problems are one of the first three.

## AI Mode says it's rate-limited or cooling down

**"Wait a minute and ask again"** — the free Gemini tier allows only a handful of
questions per minute. Pause ~60 seconds and retry.

**"Daily free allowance used up — resets around midnight Pacific"** — you've hit
the per-day cap. AI Mode returns the next day. Everything else in the app keeps
working. If you want more headroom, create a fresh free key at
[aistudio.google.com](https://aistudio.google.com) → "Get API key" and paste it
into `backend\.env` as `GEMINI_API_KEY`.

**"Google's AI servers are overloaded"** — temporary on Google's side; the app
already tries backup models. Wait a minute and retry.

The whole rest of the app (player profiles, shot charts, compare, games) works
with **no AI key at all** — AI Mode is the only feature that uses it.

## The first load of a player or season is slow

Expected. The first time you view something, the app downloads it from NBA.com
and caches it. The same player/season is instant afterward. The **Fouls** tab
takes longest on first open (it reads recent play-by-play).

To pre-warm the two most recent seasons so first use is fast:
```
backend\venv\Scripts\python.exe backend\scripts\warm_cache.py
```

## "Port 8000 is already in use" / the app won't start

An old copy is still running. Close any leftover black terminal windows, or run
this once in PowerShell:
```
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```
Then double-click `start-app.bat` again.

## A player or stat shows blank / "no data"

- The player may not have played in the selected **season or season type** (e.g.
  Playoffs when their team missed the playoffs). Check the filter bar.
- Very tight filters (a single opponent + wins only + last 5) can leave zero
  matching games — loosen them.
- NBA.com occasionally times out. The app retries automatically; if a section
  stays blank, switch tabs and back, or restart the app.

## The data looks out of date

Check the **footer** — it shows the latest game date the app has. Current-season
data refreshes every 12 hours. To force a fresh pull, close the app, delete
`backend\data\cache.sqlite`, and restart (the next views will re-download).
Deleting the cache is always safe — it only removes saved copies, never anything
you can't re-fetch.

## AI answer seems to only use a tiny sample

Early in a new season there aren't many games yet. AI Mode flags this and also
pulls the previous season, labeling which season each number is from. If you want
a specific season, say so in your question ("...in the 2025-26 season").

## Moving to a new computer

Follow **One-time setup** in the [README](../README.md). You'll need Python 3.12,
Node.js LTS, and your Gemini key. No data needs to be copied — it re-downloads on
demand.

## Where to look when something's really wrong

The black terminal window prints errors as they happen. The backend also logs
NBA.com retry warnings there. If you report a problem, copy the last ~20 lines
from that window.
