# Research: contest / defender-distance / shot-clock features for xFG (#2)

**Question.** Can we add per-shot defender distance, contest quality, or shot-clock
features to the xFG shot-quality model using **public** data?

**Verdict: not feasible at shot level with current public data.** The signals
exist publicly only as **per-player aggregate buckets**, never joined to
individual shots. The only public shot-level contest dataset is a single stale
2014-15 season. Current shot-level tracking is licensed (paid). Detail and
citations below.

## Why it matters

The xFG model is **shot-level**: one row per shot, features derived from shot
location and type (distance, x/y, angle, period, seconds-left, 2/3, home/away,
zone). It does not know how contested a shot was. "How contested" (defender
distance, shot clock, touch time) is the biggest missing predictive signal — the
realistic path to beating the incumbent v2. To use it, we would need a
**per-shot** contest value we can attach to each shot row.

## What the public NBA Stats API actually exposes

### `shotchartdetail` — our ingestion source (shot-level, no contest)

Result set `Shot_Chart_Detail` columns:

```text
GRID_TYPE, GAME_ID, GAME_EVENT_ID, PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_NAME,
PERIOD, MINUTES_REMAINING, SECONDS_REMAINING, EVENT_TYPE, ACTION_TYPE, SHOT_TYPE,
SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE, SHOT_DISTANCE, LOC_X, LOC_Y,
SHOT_ATTEMPTED_FLAG, SHOT_MADE_FLAG, GAME_DATE, HTM, VTM
```

There is **no defender-distance and no shot-clock field.** It is pure location
and context. (Source: swar/nba_api `shotchartdetail` docs.)

### `playerdashptshots` / `leaguedashplayerptshot` — tracking, aggregate only

These tracking endpoints *do* carry contest/shot-clock, but only as **per-player
summary buckets**. Every result set
(`ClosestDefenderShooting`, `ShotClockShooting`, `TouchTimeShooting`,
`DribbleShooting`) has the shape:

```text
PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, GP, G,
<RANGE bucket e.g. CLOSE_DEF_DIST_RANGE / SHOT_CLOCK_RANGE>,
FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2.., FG3..
```

They answer "what % did player X shoot with a defender 2-4 ft away," **not**
"how contested was this specific shot." There is **no `GAME_ID` or
`GAME_EVENT_ID`**, so these numbers cannot be joined back to the shot rows in
`shotchartdetail`. (Source: swar/nba_api `playerdashptshots` /
`leaguedashplayerptshot` docs.)

So the public API gives contest/shot-clock **only as aggregates**, never
shot-level.

## Alternative public datasets

The only widely-cited public **shot-level** dataset with contest data is the
**2014-15 Kaggle "NBA Shot Logs"** (~128k shots with `SHOT_DIST`,
`CLOSE_DEF_DIST`, `SHOT_CLOCK`, `DRIBBLES`, `TOUCH_TIME`, and the result). It is
used by many public projects. But it is a **one-off release of the 2014-15
season only**, never updated — roughly a decade stale, and it does not cover the
players or seasons this project serves (2023-26). It is unusable for the current
model except as a historical curiosity. (Source: numerous public analyses built
on the Kaggle "NBA shot logs" 2014-15 set.)

## Licensed / current tracking

Current NBA optical tracking is provided by **Second Spectrum (Genius Sports)**,
and **Sportradar** is the exclusive worldwide distributor of official NBA data
(an equity partnership since the 2023-24 season). Both are **paid, licensed**
feeds; the data is not publicly scrapeable and redistribution is contractually
restricted. (Sources: NBA/Genius Sports and NBA/Sportradar partnership
announcements; Sportradar developer docs.)

## Recommended path

1. **Accept the limitation and keep the model honest (recommended default).**
   Leave xFG as a location+type model and keep stating plainly, as the model
   card already does, that it does **not** observe defender distance, contest,
   or shot clock. This is the correct, honest status.
2. **Add a descriptive "contested shooting" view, not a model feature.** We can
   fetch the aggregate `playerdashptshots` buckets and *display* a player's
   FG%/eFG% by closest-defender range and shot-clock range. This is a real,
   public, honest feature — but it is descriptive splits, **not** a per-shot
   input to xFG, and must be labeled as such.
3. **Only pursue shot-level contest features by licensing** a current tracking
   feed (Sportradar / Second Spectrum). This is a paid, contractual step and out
   of scope for a public portfolio build.

**Decision for this iteration:** do not attempt #2 as a model feature (paths 1
is the honest status; path 2 is an optional descriptive view for a future
iteration). Proceed with #4 (playoff vs regular-season shot-quality splits),
which needs no new data.
