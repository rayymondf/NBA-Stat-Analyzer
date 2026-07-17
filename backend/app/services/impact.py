"""On/off impact estimates from TeamPlayerOnOffDetails.

These are *estimates* — lineup-dependent and noisy in small samples. The UI
and AI must label them as such.
"""
from ..nba import api
from ..nba.seasons import previous_season


def _find_rows(data: dict, player_id: int) -> tuple[dict | None, dict | None]:
    on = next((r for r in data.get("PlayersOnCourtTeamPlayerOnOffDetails", [])
               if r.get("VS_PLAYER_ID") == player_id), None)
    off = next((r for r in data.get("PlayersOffCourtTeamPlayerOnOffDetails", [])
                if r.get("VS_PLAYER_ID") == player_id), None)
    return on, off


def on_off(player_id: int, team_id: int, season: str,
           season_type: str = "Regular Season") -> dict | None:
    try:
        data = api.team_player_on_off(team_id, season, season_type)
    except RuntimeError:
        return None
    on, off = _find_rows(data, player_id)
    if not on or not off:
        return None

    def block(r: dict) -> dict:
        return {
            "min": r.get("MIN"),
            "gp": r.get("GP"),
            "off_rating": r.get("OFF_RATING"),
            "def_rating": r.get("DEF_RATING"),
            "net_rating": r.get("NET_RATING"),
        }

    on_b, off_b = block(on), block(off)
    diff = None
    if on_b["net_rating"] is not None and off_b["net_rating"] is not None:
        diff = round(on_b["net_rating"] - off_b["net_rating"], 1)
    return {
        "season": season,
        "on_court": on_b,
        "off_court": off_b,
        "net_diff": diff,
        "off_diff": round((on_b["off_rating"] or 0) - (off_b["off_rating"] or 0), 1),
        "def_diff": round((on_b["def_rating"] or 0) - (off_b["def_rating"] or 0), 1),
    }


def impact(player_id: int, team_id: int, season: str,
           season_type: str = "Regular Season", history: int = 3) -> dict:
    seasons = [season]
    for _ in range(history - 1):
        seasons.append(previous_season(seasons[-1]))

    current = on_off(player_id, team_id, season, season_type)
    past = []
    for s in seasons[1:]:
        r = on_off(player_id, team_id, s, season_type)
        if r:
            past.append(r)

    return {
        "season": season,
        "season_type": season_type,
        "current": current,
        "history": past,
        "disclaimer": ("On/off numbers are estimates that depend on lineups, "
                       "opponents and schedule. Treat small samples (low "
                       "minutes) as noisy."),
    }
