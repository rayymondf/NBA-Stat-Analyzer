"""Playoff situational analysis: elimination and closeout games.

An elimination game = the player's team has 3 losses in the series entering the
game (facing elimination; every playoff round has been best-of-7 since 2003).
A closeout game = the opponent has 3 losses (a chance to end the series).
Both are derived purely from the ordered playoff game logs.
"""
import pandas as pd

from ..nba.seasons import current_season, previous_season
from . import frames


def _ts(pts: float, fga: float, fta: float) -> float | None:
    tsa = fga + 0.44 * fta
    return round(pts / (2 * tsa), 3) if tsa else None


def _aggregate(games: list[dict]) -> dict:
    if not games:
        return {"games": 0}
    n = len(games)
    pts = sum(g["pts"] for g in games)
    fga = sum(g["fga"] for g in games)
    fta = sum(g["fta"] for g in games)
    return {
        "games": n,
        "wins": sum(1 for g in games if g["wl"] == "W"),
        "losses": sum(1 for g in games if g["wl"] == "L"),
        "pts_per_game": round(pts / n, 1),
        "ts_pct": _ts(pts, fga, fta),
        "fga_per_game": round(fga / n, 1),
    }


def elimination_stats(player_id: int, seasons_back: int = 6) -> dict:
    """Elimination/closeout splits vs overall playoff baseline, per season."""
    season = current_season()
    seasons = [season]
    for _ in range(seasons_back - 1):
        seasons.append(previous_season(seasons[-1]))

    elim_games: list[dict] = []
    closeout_games: list[dict] = []
    all_playoff: list[dict] = []
    seasons_with_playoffs: list[str] = []

    for s in seasons:
        df = frames.merged_logs(player_id, s, "Playoffs")
        if df.empty:
            continue
        seasons_with_playoffs.append(s)
        # A playoff series = the run of games vs one opponent in one season.
        for _, series in df.groupby("OPP"):
            series = series.sort_values("GAME_DATE")
            losses = 0
            opp_losses = 0
            for _, r in series.iterrows():
                game = {
                    "season": s,
                    "date": r["GAME_DATE"].strftime("%Y-%m-%d"),
                    "matchup": r["MATCHUP"],
                    "wl": r.get("WL"),
                    "pts": float(r.get("PTS", 0)),
                    "fga": float(r.get("FGA", 0)),
                    "fta": float(r.get("FTA", 0)),
                    "min": round(float(r.get("MIN", 0)), 1),
                }
                game["ts_pct"] = _ts(game["pts"], game["fga"], game["fta"])
                all_playoff.append(game)
                if losses == 3:
                    elim_games.append(game)
                if opp_losses == 3:
                    closeout_games.append(game)
                if r.get("WL") == "L":
                    losses += 1
                else:
                    opp_losses += 1

    return {
        "player_id": player_id,
        "seasons_checked": seasons,
        "seasons_with_playoffs": seasons_with_playoffs,
        "elimination": {
            **_aggregate(elim_games),
            "game_lines": [{k: g[k] for k in
                            ("season", "date", "matchup", "wl", "pts", "ts_pct", "min")}
                           for g in elim_games],
        },
        "closeout": _aggregate(closeout_games),
        "all_playoffs_baseline": _aggregate(all_playoff),
        "definitions": {
            "elimination_game": ("Player's team entered the game down 3 losses "
                                 "in the series (loss ends their season/series)."),
            "closeout_game": "Opponent entered the game facing elimination.",
        },
    }
