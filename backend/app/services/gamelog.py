"""Game log table + single-game detail (boxscore, shot chart, timeline).

Boxscore/play-by-play use the V3 endpoints (camelCase nested JSON).
"""
import re

import pandas as pd

from ..nba import api
from . import frames, shooting


def season_from_game_id(game_id: str) -> str:
    """Game IDs look like 0022500123: chars 3-4 = season start year % 100."""
    yy = int(game_id[3:5])
    start = 2000 + yy if yy < 70 else 1900 + yy
    return f"{start}-{str(start + 1)[-2:]}"


def season_type_from_game_id(game_id: str) -> str:
    return {"1": "Pre Season", "2": "Regular Season", "4": "Playoffs",
            "5": "PlayIn"}.get(game_id[2], "Regular Season")


def game_log(player_id: int, f: frames.LogFilters) -> dict:
    df = frames.merged_logs(player_id, f.season, f.season_type)
    filtered = frames.apply_filters(df, f)
    return {
        "filters": f.__dict__,
        "rows": frames.game_rows(filtered)[::-1],  # newest first
    }


def _elapsed_minutes(period: int, clock: str) -> float:
    """Game-time elapsed at a V3 clock stamp ('PT08M23.00S')."""
    m = re.match(r"PT(\d+)M([\d.]+)S", clock or "")
    remaining = (int(m.group(1)) + float(m.group(2)) / 60) if m else 0.0
    base = 12 * min(period, 4) + 5 * max(period - 4, 0)
    period_len = 12 if period <= 4 else 5
    return round(base - remaining, 2) if remaining <= period_len else round(base, 2)


def score_timeline(actions: list[dict]) -> list[dict]:
    """Score progression over game time from V3 play-by-play."""
    timeline = []
    for a in actions:
        if not a.get("scoreHome"):
            continue
        home, away = int(a["scoreHome"]), int(a["scoreAway"])
        timeline.append({
            "t": _elapsed_minutes(a.get("period", 1), a.get("clock", "")),
            "period": a.get("period"),
            "clock": a.get("clock"),
            "home": home,
            "away": away,
            "margin": home - away,
        })
    return timeline


def _player_scoring_events(actions: list[dict], player_id: int) -> list[dict]:
    out = []
    for a in actions:
        if a.get("personId") != player_id:
            continue
        made_fg = a.get("isFieldGoal") == 1 and a.get("shotResult") == "Made"
        made_ft = (a.get("actionType") == "Free Throw"
                   and "MISS" not in str(a.get("description", "")).upper())
        if not (made_fg or made_ft):
            continue
        out.append({
            "period": a.get("period"),
            "clock": a.get("clock"),
            "desc": a.get("description"),
            "home": a.get("scoreHome"),
            "away": a.get("scoreAway"),
        })
    return out


def _flatten_player(p: dict) -> dict:
    s = p.get("statistics", {})
    return {
        "player_id": p.get("personId"),
        "name": f"{p.get('firstName', '')} {p.get('familyName', '')}".strip(),
        "position": p.get("position"),
        "starter": bool(p.get("position")),
        "min": api.minutes_float(s.get("minutes")),
        "pts": s.get("points"),
        "reb": s.get("reboundsTotal"),
        "ast": s.get("assists"),
        "stl": s.get("steals"),
        "blk": s.get("blocks"),
        "tov": s.get("turnovers"),
        "pf": s.get("foulsPersonal"),
        "fgm": s.get("fieldGoalsMade"),
        "fga": s.get("fieldGoalsAttempted"),
        "fg3m": s.get("threePointersMade"),
        "fg3a": s.get("threePointersAttempted"),
        "ftm": s.get("freeThrowsMade"),
        "fta": s.get("freeThrowsAttempted"),
        "plus_minus": s.get("plusMinusPoints"),
    }


def game_detail(player_id: int, game_id: str) -> dict:
    season = season_from_game_id(game_id)
    season_type = season_type_from_game_id(game_id)

    box = api.boxscore_traditional(game_id)
    home, away = box.get("homeTeam", {}), box.get("awayTeam", {})

    def team_block(t: dict) -> dict:
        return {
            "team_id": t.get("teamId"),
            "abbr": t.get("teamTricode"),
            "name": f"{t.get('teamCity', '')} {t.get('teamName', '')}".strip(),
            "pts": t.get("statistics", {}).get("points"),
        }

    me = None
    for t in (home, away):
        for p in t.get("players", []):
            if p.get("personId") == player_id:
                me = _flatten_player(p)
                break

    shots = shooting.shot_profile(player_id, season, season_type, game_id=game_id)

    actions = []
    try:
        actions = api.play_by_play(game_id)
    except RuntimeError:
        pass

    return {
        "game_id": game_id,
        "season": season,
        "season_type": season_type,
        "home": team_block(home),
        "away": team_block(away),
        "player_line": me,
        "shots": shots,
        "timeline": score_timeline(actions),
        "scoring_events": _player_scoring_events(actions, player_id),
    }
