"""Why did a team win/lose? Ranked, evidence-based explanations.

Method: compute the classic four factors plus bench scoring, star performance
vs season baselines, fourth-quarter execution and scoring runs; score each
candidate explanation by how unusual/decisive it was; return them ranked with
evidence for AND against. Data comes from the V3 boxscore/play-by-play.
"""
import pandas as pd

from ..nba import api
from .gamelog import (score_timeline, season_from_game_id,
                      season_type_from_game_id)

# Four-factor weights (Dean Oliver) and typical single-game standard deviations
FACTORS = {
    "efg": {"weight": 0.40, "std": 0.06, "title": "Shooting efficiency"},
    "tov": {"weight": 0.25, "std": 0.045, "title": "Turnovers"},
    "orb": {"weight": 0.20, "std": 0.10, "title": "Offensive rebounding"},
    "ft": {"weight": 0.15, "std": 0.09, "title": "Free throws"},
}


def _team_totals(team: dict) -> dict:
    s = team.get("statistics", {})
    return {
        "team_id": team.get("teamId"),
        "abbr": team.get("teamTricode"),
        "name": f"{team.get('teamCity', '')} {team.get('teamName', '')}".strip(),
        "pts": s.get("points", 0),
        "fga": s.get("fieldGoalsAttempted", 0),
        "fgm": s.get("fieldGoalsMade", 0),
        "fg3m": s.get("threePointersMade", 0),
        "fg3a": s.get("threePointersAttempted", 0),
        "fta": s.get("freeThrowsAttempted", 0),
        "ftm": s.get("freeThrowsMade", 0),
        "tov": s.get("turnovers", 0),
        "oreb": s.get("reboundsOffensive", 0),
        "dreb": s.get("reboundsDefensive", 0),
        "bench_pts": team.get("bench", {}).get("points"),
        "players": team.get("players", []),
    }


def _four_factors(team: dict, opp: dict) -> dict:
    fga, fgm, fg3m = team["fga"], team["fgm"], team["fg3m"]
    fta, ftm, tov = team["fta"], team["ftm"], team["tov"]
    oreb, opp_dreb = team["oreb"], opp["dreb"]
    poss = fga + 0.44 * fta + tov - oreb
    return {
        "efg": round((fgm + 0.5 * fg3m) / fga, 3) if fga else None,
        "tov": round(tov / poss, 3) if poss else None,
        "orb": round(oreb / (oreb + opp_dreb), 3) if (oreb + opp_dreb) else None,
        "ft": round(ftm / fga, 3) if fga else None,
        "poss": round(poss, 1),
    }


def _detect_runs(actions: list[dict], home_abbr: str, away_abbr: str) -> list[dict]:
    """Largest unanswered scoring runs from the V3 score progression."""
    runs = []
    cur_team, cur_pts, cur_start = None, 0, None
    prev_home, prev_away = 0, 0
    for a in actions:
        if not a.get("scoreHome"):
            continue
        home, away = int(a["scoreHome"]), int(a["scoreAway"])
        d_home, d_away = home - prev_home, away - prev_away
        prev_home, prev_away = home, away
        if d_home <= 0 and d_away <= 0:
            continue
        team = home_abbr if d_home > 0 else away_abbr
        pts = d_home if d_home > 0 else d_away
        clock = str(a.get("clock", "")).replace("PT", "").replace("M", ":").split(".")[0]
        marker = f"Q{a.get('period')} {clock}"
        if team == cur_team:
            cur_pts += pts
        else:
            if cur_team and cur_pts >= 8:
                runs.append({"team": cur_team, "points": cur_pts,
                             "start": cur_start, "end": marker})
            cur_team, cur_pts, cur_start = team, pts, marker
    if cur_team and cur_pts >= 8:
        runs.append({"team": cur_team, "points": cur_pts,
                     "start": cur_start, "end": "end"})
    runs.sort(key=lambda r: -r["points"])
    return runs[:6]


def _season_baselines(season: str, season_type: str) -> dict[int, dict]:
    rows = api.league_player_stats(season, per_mode="PerGame", measure="Base",
                                   season_type=season_type)
    return {r["PLAYER_ID"]: r for r in rows}


def _ts(pts: float, fga: float, fta: float) -> float | None:
    tsa = fga + 0.44 * fta
    return round(pts / (2 * tsa), 3) if tsa else None


def investigate(game_id: str) -> dict:
    season = season_from_game_id(game_id)
    season_type = season_type_from_game_id(game_id)

    box = api.boxscore_traditional(game_id)
    if not box.get("homeTeam"):
        raise ValueError(f"Game {game_id} has no final boxscore yet.")
    home = _team_totals(box["homeTeam"])
    away = _team_totals(box["awayTeam"])

    actions = api.play_by_play(game_id)

    winner, loser = (home, away) if home["pts"] > away["pts"] else (away, home)
    ff_w = _four_factors(winner, loser)
    ff_l = _four_factors(loser, winner)

    explanations = []

    # --- Four factors ---
    for key, cfg in FACTORS.items():
        vw, vl = ff_w[key], ff_l[key]
        if vw is None or vl is None:
            continue
        diff = vw - vl
        if key == "tov":  # fewer turnovers is better
            diff = -diff
        score = round(abs(diff) / cfg["std"] * cfg["weight"], 3)
        favored = winner["abbr"] if diff > 0 else loser["abbr"]
        explanations.append({
            "key": key,
            "title": cfg["title"],
            "favored": favored,
            "score": score,
            "summary": (f"{winner['abbr']} {cfg['title'].lower()}: {vw:.3f} vs "
                        f"{loser['abbr']} {vl:.3f}"),
            "evidence_for": [
                {"label": f"{winner['abbr']} {key.upper()}", "value": vw},
                {"label": f"{loser['abbr']} {key.upper()}", "value": vl},
            ],
            "evidence_against": [] if diff > 0 else [
                {"label": "Winner actually lost this factor",
                 "value": round(diff, 3)}],
        })

    # --- Bench scoring ---
    if winner["bench_pts"] is not None and loser["bench_pts"] is not None:
        bw, bl = winner["bench_pts"], loser["bench_pts"]
        diff = bw - bl
        explanations.append({
            "key": "bench",
            "title": "Bench scoring",
            "favored": winner["abbr"] if diff > 0 else loser["abbr"],
            "score": round(abs(diff) / 12 * 0.5, 3),
            "summary": f"Bench points: {winner['abbr']} {bw}, {loser['abbr']} {bl}",
            "evidence_for": [
                {"label": f"{winner['abbr']} bench PTS", "value": bw},
                {"label": f"{loser['abbr']} bench PTS", "value": bl},
            ],
            "evidence_against": [] if diff > 0 else [
                {"label": "Winner's bench was outscored", "value": diff}],
        })

    # --- Star performance vs season baselines ---
    baselines = _season_baselines(season, season_type)
    star_lines = []
    star_delta = {home["abbr"]: 0.0, away["abbr"]: 0.0}
    for team in (home, away):
        flat = [{
            "player_id": p.get("personId"),
            "name": f"{p.get('firstName', '')} {p.get('familyName', '')}".strip(),
            "min": api.minutes_float(p.get("statistics", {}).get("minutes")),
            "pts": p.get("statistics", {}).get("points", 0),
            "fga": p.get("statistics", {}).get("fieldGoalsAttempted", 0),
            "fta": p.get("statistics", {}).get("freeThrowsAttempted", 0),
        } for p in team["players"]]
        flat.sort(key=lambda p: -p["min"])
        for p in flat[:3]:
            base = baselines.get(p["player_id"])
            if not base:
                continue
            season_pts = base.get("PTS", 0)
            delta = float(p["pts"]) - season_pts
            star_delta[team["abbr"]] += delta
            star_lines.append({
                "player_id": p["player_id"],
                "name": p["name"],
                "team": team["abbr"],
                "pts": int(p["pts"]),
                "season_ppg": season_pts,
                "delta": round(delta, 1),
                "ts_pct": _ts(p["pts"], p["fga"], p["fta"]),
                "min": round(p["min"], 0),
            })
    sd_w, sd_l = star_delta[winner["abbr"]], star_delta[loser["abbr"]]
    diff = sd_w - sd_l
    explanations.append({
        "key": "stars",
        "title": "Star-player performance vs season averages",
        "favored": winner["abbr"] if diff > 0 else loser["abbr"],
        "score": round(abs(diff) / 15 * 0.7, 3),
        "summary": (f"Top-3 minute players vs their season scoring averages: "
                    f"{winner['abbr']} {sd_w:+.1f} pts, "
                    f"{loser['abbr']} {sd_l:+.1f} pts"),
        "evidence_for": [
            {"label": f"{l['name']} ({l['team']})",
             "value": f"{l['pts']} pts vs {l['season_ppg']} avg ({l['delta']:+.1f})"}
            for l in star_lines],
        "evidence_against": [] if diff > 0 else [
            {"label": "The losing team's stars actually outperformed",
             "value": round(diff, 1)}],
    })

    # --- Fourth quarter execution ---
    timeline = score_timeline(actions)
    q4 = None
    end_q3 = next((t for t in reversed(timeline) if t["period"] == 3), None)
    final = timeline[-1] if timeline else None
    if end_q3 and final:
        q4_home = final["home"] - end_q3["home"]
        q4_away = final["away"] - end_q3["away"]
        q4 = {
            "entering_q4": {"home": end_q3["home"], "away": end_q3["away"],
                            "margin": end_q3["home"] - end_q3["away"]},
            "q4_scoring": {home["abbr"]: q4_home, away["abbr"]: q4_away},
            "close_entering_q4": abs(end_q3["home"] - end_q3["away"]) <= 8,
        }
        q4_diff = (q4_home - q4_away) if winner is home else (q4_away - q4_home)
        if q4["close_entering_q4"]:
            explanations.append({
                "key": "q4",
                "title": "Fourth-quarter execution",
                "favored": winner["abbr"] if q4_diff > 0 else loser["abbr"],
                "score": round(abs(q4_diff) / 8 * 0.8, 3),
                "summary": (f"Close entering Q4 ({end_q3['home']}-"
                            f"{end_q3['away']}); Q4 scoring {home['abbr']} "
                            f"{q4_home}, {away['abbr']} {q4_away}"),
                "evidence_for": [
                    {"label": "Score entering Q4",
                     "value": f"{end_q3['home']}-{end_q3['away']}"},
                    {"label": f"{home['abbr']} Q4 points", "value": q4_home},
                    {"label": f"{away['abbr']} Q4 points", "value": q4_away},
                ],
                "evidence_against": [] if q4_diff > 0 else [
                    {"label": "Winner lost the fourth quarter",
                     "value": q4_diff}],
            })

    # --- Runs / turning points ---
    runs = _detect_runs(actions, home["abbr"], away["abbr"])
    if runs:
        big = runs[0]
        explanations.append({
            "key": "runs",
            "title": "Scoring runs / turning points",
            "favored": big["team"],
            "score": round(big["points"] / 14 * 0.6, 3),
            "summary": (f"Biggest unanswered run: {big['points']}-0 by "
                        f"{big['team']} ({big['start']} → {big['end']})"),
            "evidence_for": [
                {"label": f"{r['points']}-0 run by {r['team']}",
                 "value": f"{r['start']} → {r['end']}"} for r in runs[:4]],
            "evidence_against": [],
        })

    explanations.sort(key=lambda e: -e["score"])

    return {
        "game_id": game_id,
        "season": season,
        "season_type": season_type,
        "teams": [{
            "team_id": t["team_id"],
            "abbr": t["abbr"],
            "name": t["name"],
            "pts": t["pts"],
            "home": t is home,
            "winner": t is winner,
        } for t in (home, away)],
        "final": f"{winner['abbr']} {winner['pts']} - {loser['pts']} {loser['abbr']}",
        "four_factors": {winner["abbr"]: ff_w, loser["abbr"]: ff_l},
        "explanations": explanations,
        "star_lines": star_lines,
        "runs": runs,
        "q4": q4,
        "method": ("Explanations are scored by weighted, normalized four-factor "
                   "margins plus bench, star-baseline, fourth-quarter and "
                   "scoring-run analysis from the official play-by-play."),
    }


def list_games(season: str, season_type: str = "Regular Season",
               team: str | None = None, limit: int = 100) -> list[dict]:
    """Completed games, newest first, one row per game."""
    rows = api.find_team_games(season, season_type)
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    df = df[df["WL"].notna()]
    games: dict[str, dict] = {}
    for _, r in df.iterrows():
        gid = r["GAME_ID"]
        g = games.setdefault(gid, {"game_id": gid, "date": r["GAME_DATE"],
                                   "home": None, "away": None})
        side = "home" if "vs." in r["MATCHUP"] else "away"
        g[side] = {"team_id": int(r["TEAM_ID"]),
                   "abbr": r["TEAM_ABBREVIATION"],
                   "name": r["TEAM_NAME"],
                   "pts": int(r["PTS"]),
                   "wl": r["WL"]}
    out = [g for g in games.values() if g["home"] and g["away"]]
    if team:
        team = team.upper()
        out = [g for g in out
               if g["home"]["abbr"] == team or g["away"]["abbr"] == team]
    out.sort(key=lambda g: g["date"], reverse=True)
    return out[:limit]
