# User guide

This guide explains every screen in NBA Stat Analyzer and how to interpret the
main results. No programming knowledge is required. For installation, use the
[project README](../README.md); for failures, use
[Troubleshooting](TROUBLESHOOTING.md).

## Start and stop the app

On the configured Windows PC, double-click `start-app.bat` in the project root.
The browser opens <http://localhost:8000>. Keep the terminal window open. Press
`Ctrl+C` in that window, or close it, to stop the backend.

The first browser tab can appear before the server has finished starting. If it
cannot connect, wait a few seconds and refresh.

## Navigation and data date

The header is available on every page:

- **NBA Stat Analyzer** and **Players** return to the home page.
- **Games** opens the completed-game browser.
- **The Model** contains Player vs Model and Player vs Player.
- **AI Mode** opens the optional Gemini research assistant.
- **Search players** or `Ctrl+K` opens global player search.
- The sun/moon button changes the theme for the current page session. The theme
  is not currently saved across a full refresh.

The footer shows:

- the season currently derived from the calendar;
- the latest completed game date the backend found for that season;
- the 12-hour refresh policy for current-season data;
- what kinds of players are included in search.

The season changes in October. During July through September, it is normal for
the footer to show the completed season while player search already reflects
some next-season roster moves.

## Home page

The home page has four entry points:

1. The large search button opens player search.
2. The points-per-game leaderboard links to the top eight qualified scorers.
3. The Model card opens the shot-quality model page.
4. Example AI questions open AI Mode with a question already filled and sent.

The leaderboard uses the same qualification rule as league percentiles: at
least 10 games and 15 minutes per game. Very early in a season, this can leave
the list short or empty.

## Find a player

1. Press `Ctrl+K` or select **Search players**.
2. Enter at least two characters.
3. Use the mouse, or the arrow keys and `Enter`, to choose a result.

Search accepts a partial name and multi-word parts in any order. If there is no
direct match, it makes a conservative attempt to correct a misspelling.

Each result can show current team, position, jersey, and current-season points,
rebounds, and assists. A result labeled **Current roster, no [season]
appearances** is still valid, but its profile tabs cannot show season statistics
until that player records a game or a different season is selected.

## Player profile

The hero section shows bio information and six headline numbers: points,
rebounds, assists, true shooting, field-goal percentage, and three-point
percentage. It follows the selected season and season type, but not the
game-level split filters described below.

Question chips under the hero open AI Mode with the player ID and selected
season attached. **Compare with another player** opens the Player vs Player
model mode with the current player in the first slot.

### Filter scopes

The filter bar is shared by all eight tabs, but not every control applies to
every tab.

| Control | Where it applies |
|---|---|
| Season | Hero and all profile tabs |
| Regular season / Playoffs | Hero and all profile tabs |
| Per game / Per 36 / Per 75 / Per 100 | Overview counting-stat tiles |
| Home/away | Overview and Game Log |
| Wins/losses | Overview and Game Log |
| Starter/bench | Overview and Game Log, when starter data is available |
| Last 5/10/20 | Overview and Game Log |
| Opponent | Overview and Game Log |
| Date range | Overview and Game Log |

Percentages do not change when switching between per-game and possession/minute
rate modes. Position percentiles always use full-season per-game league values,
so they also remain fixed when applying game-level splits.

The last-N option is applied after the other filters. For example, Boston +
away + last 5 means the most recent five matching road games against Boston,
not games drawn from the player's last five overall.

### Overview

Overview contains:

- games, filtered record, starts, and the active rate mode;
- points, rebounds, assists, steals, blocks, turnovers, fouls, plus-minus, and
  true shooting;
- position-group percentile bars.

“Better than 84% of guards” compares the player's full-season value with guards
who played at least 10 games and 15 minutes per game. For turnovers, fouls, and
defensive rating, lower values receive higher percentiles.

### Shooting

The top tiles show overall field goals, two-pointers, three-pointers, field-goal
points per attempt, average shot distance, and attempt count. Free throws are
not part of the shot chart or field-goal points-per-shot value.

The court has three views:

- **Shots** displays each make and miss. Hover a point for distance, action,
  period, game, and result.
- **Heatmap** groups attempts into court bins. Darker cells mean more attempts,
  not better accuracy.
- **Zones vs league** colors basic zones by field-goal percentage difference
  from NBA.com's league average for that zone. Blue is better, red is worse,
  and gray is close to average.

Quarter and make/miss controls filter the points shown on the chart. They do not
recalculate the summary tiles, zone table, or xFG card.

The right side also includes distance buckets and, when NBA data is available,
assisted versus self-created makes and scoring-source percentages.

#### Shot quality (ML)

The ML card compares:

- **Actual eFG%**: how the player actually converted, with three-pointers worth
  1.5 makes in the effective-FG calculation.
- **Expected eFG%**: what the local model predicts an average NBA player would
  produce from the same recorded shots.
- **Delta**: actual minus expected. Positive means outperformance of the modeled
  shot mix; negative means underperformance.
- **Percentile**: where that delta falls among players with at least 200 shots
  in the model's saved training distribution.

This is not a measure of shooting form or defender pressure. The model sees
location, distance, angle, shot category, period, clock, and home/away status,
not video, tracking data, or player identity. Open **See the full model
breakdown** for calibration and training context.

### Efficiency

Efficiency shows true shooting, effective FG%, usage, assist-to-turnover ratio,
turnover rate, free-throw rate, points per used possession, offensive rating,
defensive rating, and net rating. Hover or select the glossary icons for short
definitions.

Advanced ratings describe production and team results in a role; they should
not be treated as a context-free ranking of players. Position percentiles on
this tab use the same full-season qualification pool as Overview.

### Playtime

Playtime shows:

- minutes per game and total minutes;
- games played and an estimated games-missed value;
- starts and bench games;
- fourth-quarter minutes;
- minutes and points by game;
- performance in minutes-played buckets;
- minutes in games with five or more fouls;
- clutch stats for the last five minutes of games within five points.

Games missed is team games minus player appearances. It can be imperfect for a
traded player or when team schedule data is incomplete.

### Fouls

Season-wide cards show personal fouls per game and per 36 minutes, total fouls,
fouls drawn, five-foul games, foul-outs, and minutes in foul-trouble games.

Foul types are parsed from play-by-play for at most the ten most recent games,
not the entire season. The card states the actual number analyzed. Technical,
offensive, shooting, loose-ball, personal, and unclassified fouls depend on the
descriptions supplied by the feed.

### Game Log

Game Log lists the games that match every active split. The table is sortable
and includes opponent, result, start status, minutes, basic box-score values,
shooting line, true shooting, fouls, and plus-minus when available.

Select a date to open a player-specific game page. That page contains the
player’s line, individual shot chart, scoring events, score timeline, and the
final team score. It is different from the ranked team-level investigation on
the Games page.

### Trends

Trends compares the player's most recent ten games with the full season and
plots rolling scoring, true shooting, minutes, shot volume, usage, and
three-point attempt rate. If a player has fewer than 30 games, the rolling
window automatically becomes smaller; the chart title shows the actual window.

The scoring z-score asks whether the recent scoring mean is far from the season
distribution. The interface marks an absolute score of 1.5 or greater as
unusual. It is a descriptive signal and can be affected by opponents, role,
injury, and minutes.

Career development uses regular-season per-game rows. Players who changed teams
can have more than one row for a season; the service excludes aggregate `TOT`
rows when team-specific rows are present.

### Impact

Impact compares the team's offensive, defensive, and net ratings with the
player on and off the court and can show up to two prior seasons when data is
available.

The net swing is on-court net rating minus off-court net rating per 100
possessions. It is an observational estimate. Teammates, lineups, opponents,
role, injuries, and schedule all influence it, so it is not a standalone causal
player-value metric.

## The Model

The Model page has two modes. Both currently use the derived current regular
season; the page does not expose the player-profile season/split filters.

### Player vs the Model

Choose a player to see:

- actual and expected eFG%, their delta, extra points per 100 field-goal
  attempts, shot count, and delta percentile;
- a histogram showing the saved league distribution;
- zone-by-zone actual versus expected field-goal results for zones with at
  least five attempts;
- held-out calibration by distance;
- the exact training seasons, sample, feature count, Brier score, AUC, and
  baseline comparison read from the generated model file;
- a CSV download of the exported shot dataset when it is present.

If the page says the model has not been trained, follow the model instructions
in [Troubleshooting](TROUBLESHOOTING.md#the-model-page-says-the-model-is-not-trained).

### Player vs Player

Choose a player in each slot. The comparison shows:

- per-game or per-75 basic counting stats;
- TS%, eFG%, 3P%, free-throw rate, assist-to-turnover ratio, usage, and ratings;
- side-by-side zone shot charts.

Bold indicates the better raw value. Turnovers, fouls, and defensive rating are
treated as lower-is-better. A bold value is not adjusted for role, position,
opponent, or uncertainty and does not establish that one player is universally
better.

## Games

Games lists completed games only, newest first. Use the season, regular
season/playoffs, team, and date controls to narrow the list. The page requests
up to 1,500 completed games for the selected season and team, displays 50 at a
time, and applies the exact-date filter in the browser. **Show more** reveals the
next 50 already loaded games.

Select a game to run the team-level investigation. It shows:

- final score and winner;
- ranked explanation cards;
- effective FG%, turnover rate, offensive rebound rate, and free-throw factor;
- the top-minute players versus their season scoring averages;
- major unanswered runs;
- fourth-quarter scoring when the game was close after three quarters;
- evidence and counterevidence for the ranked factors.

An explanation can favor the losing team. That means the winner overcame that
factor; it is useful counterevidence. The ranking is a transparent statistical
heuristic, not a film review or causal model.

Game links from AI Mode can open `/games` with that game selected.

## AI Mode

AI Mode requires a valid Gemini key in `backend/.env`. Regular player, model,
and game dashboards do not need the key.

Choose a mode when it helps:

- **Auto** gives Gemini the full set of statistical tools.
- **Player** focuses on one player's stats, shooting, form, history, similar
  players, impact, elimination games, and xFG.
- **Claim check** asks for a measurable definition and a verdict.
- **Compare** narrows the tool set to player comparison evidence.
- **Game** uses completed-game lookup and investigation only.

A player or game shortcut supplies exact page context automatically. The first
uncached answer can take 20 to 60 seconds or longer when NBA data is also
uncached.

Each report can contain:

- a short answer;
- one of six claim verdicts: Supported, Mostly supported, Mixed, Misleading,
  Not supported, or Insufficient evidence;
- exact key findings;
- counterevidence and caveats;
- links to analyzed players and games;
- confidence;
- a collapsible panel with seasons, sample, filters, definitions, tool calls,
  model, generation time, token usage, model attempts, and cache status.

Questions shown in one browser session look like a conversation, but each
submission is analyzed independently; previous answers are not sent back as
chat history. Write self-contained follow-up questions and repeat the player or
season name when needed.

Identical successful questions with the same mode, context, model, prompt
version, and current season are cached for 12 hours. A cached report uses no new
Gemini quota and retains the original generation metadata.

AI Mode is designed to ground numbers in the app's tools, and the trace makes
those calls inspectable. It is still generated language. Verify high-stakes or
surprising conclusions against the linked dashboard and data-scope panel.

## Reading empty and error states

- **No games match these filters** means the combination produced zero rows;
  reset or loosen the split.
- **No shot data** means NBA.com returned no attempts for that season/type, which
  is common for zero-game players or a playoff season their team missed.
- **No on/off data** means the team/player endpoint did not contain both on- and
  off-court rows for that selection.
- A loading skeleton is normal during an uncached request. Repeated errors or a
  card that never resolves should be handled with
  [Troubleshooting](TROUBLESHOOTING.md).
