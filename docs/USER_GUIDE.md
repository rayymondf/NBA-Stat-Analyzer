# User Guide

A plain-English tour of every screen. No technical knowledge needed.

## Getting around

The top bar is always there:

- **NBA Stat Analyzer** (top left) — click to go home.
- **Players · Games · The Model · AI Mode** — the four main areas.
- **Search players** (or press `Ctrl + K` anywhere) — the fastest way to open a
  player.
- **Sun/moon icon** — switch between dark and light themes.

The **footer on every page** tells you exactly which season and date the data
covers, e.g. *"Data: official NBA.com stats · 2025-26 season · games through
2026-04-12."* Player lookup covers everyone who appeared during that season,
plus current roster additions and injured/inactive players who recorded no
appearances during the displayed season.

## Finding a player

1. Press `Ctrl + K` (or click **Search players**).
2. Type a name — partial or out-of-order works ("giannis", "SGA", "luka").
3. Click a result (or use arrow keys + Enter) to open their profile.

Players with no games in the displayed season are labeled **Current roster · no
2025-26 appearances**. Their profile can still be opened, but season dashboards
will show that no games are available rather than inventing statistics.

## The player profile

The top **hero** shows the headshot, team, number, position, age, and the
headline averages (points, rebounds, assists, true shooting, field-goal and
three-point percentages), plus a one-line summary of how they're playing.

Under the hero are **eight tabs**:

| Tab | What it shows |
|-----|----------------|
| **Overview** | The core box-score stats, plus percentile bars ("better than 84% of forwards") so you know what's good. |
| **Shooting** | Field-goal / 3PT / 2PT / free-throw percentages, points per shot, and the interactive shot chart (see below). |
| **Efficiency** | Advanced measures — true shooting, effective FG%, usage, assist-to-turnover, ratings — each with a plain-English tooltip. |
| **Playtime** | Minutes per game, games played vs missed, starts vs bench, a game-by-game minutes-and-points chart, and clutch-time numbers. |
| **Fouls** | Fouls per game and per 36 minutes, foul-out games, foul-trouble impact on minutes, and foul *types* (shooting/offensive/technical) from recent play-by-play. |
| **Game Log** | Every game as a sortable table. Click any date to open the full game view. |
| **Trends** | Rolling scoring and efficiency lines, whether recent form is unusual, and year-by-year career development. |
| **Impact** | On-court vs off-court team performance (clearly labeled as an *estimate*). |

### The filter bar

Below the tabs, the filters reshape the numbers: **season**, regular season vs
playoffs, per-game / per-36 / per-75 / per-100, home/away, wins/losses,
starter/bench, last 5/10/20 games, opponent, and a date range. Overview and Game
Log respond to all of them; the other tabs follow the season and season-type.

### The shot chart

Three views, switchable with the buttons above the court:

- **Shots** — every shot as a dot (made) or ✕ (missed). Hover any shot to see
  the distance, result, type and game.
- **Heatmap** — where the player shoots most often.
- **Zones vs league** — each area colored blue (better than league average) to
  red (worse), with the exact percentages listed below.

You can also filter the chart by quarter and by makes/misses.

### Shot quality (ML)

Next to the chart is a compact card powered by the app's machine-learning
model (trained on about 657,000 real NBA shots; the card shows the exact
number). It shows what an **average player would shoot from this player's
exact shot locations and types** (expected eFG%) next to what they
**actually** shot, plus a league percentile and per-zone breakdown. A green
delta means they make more than those shots usually yield (shot-making
skill); red means less. It is a model estimate built from shot locations and
types only, never video. Click **"See the full model breakdown"** to open The
Model with this player loaded.

### AI shortcuts on the profile

Under the hero are clickable **✦ question chips** ("How is this player playing
lately?", "Does this player beat the shot-quality model?"). Clicking one opens
AI Mode with that question already filled in and the player's context
attached.

## The Model

The Model is the machine-learning section, with two modes:

**Player vs the Model** (the default). Pick any player. The model plays the
part of an average NBA player taking that player's exact shots, and the page
shows who shoots better: actual vs expected eFG%, a chart placing the player
in the league-wide distribution, a zone-by-zone breakdown, and a calibration
chart proving the model's predictions match reality on shots it never saw
during training. The page also explains, step by step, how the model was
built, and includes a link to **download the full training dataset as a CSV**
you can open in Excel.

**Player vs Player.** The classic head-to-head comparison:

- A bar for every stat (bold = the better value; for turnovers, fouls and
  defensive rating, lower is better).
- A **Per game / Per 75** toggle so you can compare fairly regardless of pace.
- Both players' **shot-zone charts** side by side.

The page reminds you that winning one category doesn't make a player
universally better; context matters.

## Games

The left panel lists completed games. Controls:

- **Season** dropdown — defaults to the current season; every past season stays
  available.
- **Regular Season / Playoffs**.
- **Team** filter — narrow to one team's full schedule.
- **Date** picker — jump to a specific day's games.
- The header shows exactly what's listed: *"2025-26 Regular Season · newest
  first · showing 50 of 1,225 games."* Use **Show more** to load older games.

Click a game and the right side runs an **investigation**: the final score, a
ranked list of the strongest reasons that team won or lost (shooting, turnovers,
bench, star performances, scoring runs, fourth quarter), the four factors table,
and star lines versus their season averages. Each reason shows evidence for and,
where relevant, against it.

## AI Mode

Type any NBA question, or open it pre-filled from a player or game page. Pick a
mode if you want (**Auto** figures it out): Player, Claim check, Compare, or
Game.

Every answer is a **report card**:

- A short written answer.
- For claims, a **verdict** badge — Supported, Mostly supported, Mixed,
  Misleading, Not supported, or Insufficient evidence.
- **Evidence** rows with the exact numbers.
- **Counterevidence & caveats** — the honest other side.
- A collapsible **data scope** panel: which seasons, sample size, definitions,
  filters, the model used, and the timestamp.
- Clickable **chips** linking back to the players and games it analyzed.

If there isn't enough data, it says so instead of guessing. Early in a new
season it automatically also looks at the previous season so answers aren't based
on three games.

See **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)** for what's happening behind the
scenes, and **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** if something looks off.
