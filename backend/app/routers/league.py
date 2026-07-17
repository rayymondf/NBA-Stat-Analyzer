from fastapi import APIRouter

from ..nba.seasons import current_season, previous_season
from ..services import compare, game_investigation, league

router = APIRouter(prefix="/api", tags=["league"])


def _latest_game_date(season: str) -> str | None:
    """Most recent completed game across playoffs + regular season."""
    for season_type in ("Playoffs", "Regular Season"):
        try:
            games = game_investigation.list_games(season, season_type, limit=1)
        except RuntimeError:
            continue
        if games:
            return str(games[0]["date"])[:10]
    return None


@router.get("/meta")
def meta():
    # Everything derived from today's date at request time, so the app rolls
    # into new NBA seasons automatically (October) without code changes.
    cur = current_season()
    seasons = [cur]
    for _ in range(9):
        seasons.append(previous_season(seasons[-1]))
    data_through = _latest_game_date(cur)
    return {
        "current_season": cur,
        "seasons": seasons,
        "default_seasons": [cur, previous_season(cur)],
        "season_types": ["Regular Season", "Playoffs"],
        "data_through": data_through,
        "freshness_note": (
            f"Official NBA.com statistics through the {cur} season. "
            "Current-season numbers refresh automatically every 12 hours; "
            "completed seasons are final."),
    }


@router.get("/compare")
def compare_players(a: int, b: int, season: str | None = None,
                    season_type: str = "Regular Season"):
    return compare.compare(a, b, season or current_season(), season_type)


@router.get("/league/leaders")
def leaders(season: str | None = None, stat: str = "PTS",
            per_mode: str = "PerGame", measure: str = "Base",
            season_type: str = "Regular Season", limit: int = 15):
    return league.leaders(season or current_season(), stat, per_mode, measure,
                          season_type, limit)


@router.get("/league/improvers")
def improvers(season: str | None = None, metric: str = "TS_PCT",
              season_type: str = "Regular Season", limit: int = 15):
    return league.improvers(season or current_season(), metric, season_type,
                            limit)


@router.get("/league/similar/{player_id}")
def similar(player_id: int, season: str | None = None,
            season_type: str = "Regular Season", limit: int = 8):
    return league.similar_players(player_id, season or current_season(),
                                  season_type, limit)


@router.get("/league/low-minutes-efficient")
def low_minutes(season: str | None = None,
                season_type: str = "Regular Season",
                max_mpg: float = 24, limit: int = 15):
    return league.low_minutes_efficient(season or current_season(),
                                        season_type, max_mpg, limit)


@router.get("/league/team-defense")
def team_defense(season: str | None = None,
                 season_type: str = "Regular Season"):
    return league.team_defense(season or current_season(), season_type)
