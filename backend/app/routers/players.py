from fastapi import APIRouter, HTTPException, Query

from ..nba.seasons import current_season
from ..services import (efficiency, fouls, frames, gamelog, impact, ml,
                        players, playtime, shooting, trends)

router = APIRouter(prefix="/api/players", tags=["players"])


def _filters(season: str | None, season_type: str, location: str | None,
             outcome: str | None, starter: bool | None, last_n: int | None,
             opponent: str | None, date_from: str | None,
             date_to: str | None) -> frames.LogFilters:
    return frames.LogFilters(
        season=season or current_season(),
        season_type=season_type,
        location=location,
        outcome=outcome,
        starter=starter,
        last_n=last_n,
        opponent=opponent,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/search")
def search(q: str = Query(min_length=2)):
    return players.search(q)


@router.get("/{player_id}/summary")
def summary(player_id: int, season: str | None = None,
            season_type: str = "Regular Season"):
    return players.summary(player_id, season, season_type)


@router.get("/{player_id}/overview")
def overview(player_id: int, season: str | None = None,
             season_type: str = "Regular Season",
             location: str | None = None, outcome: str | None = None,
             starter: bool | None = None, last_n: int | None = None,
             opponent: str | None = None, date_from: str | None = None,
             date_to: str | None = None):
    f = _filters(season, season_type, location, outcome, starter, last_n,
                 opponent, date_from, date_to)
    return players.overview(player_id, f)


@router.get("/{player_id}/shooting")
def shot_profile(player_id: int, season: str | None = None,
                 season_type: str = "Regular Season",
                 opponent_team_id: int = 0, game_id: str | None = None):
    season = season or current_season()
    profile = shooting.shot_profile(player_id, season, season_type,
                                    opponent_team_id, game_id)
    profile["scoring_breakdown"] = shooting.scoring_breakdown(
        player_id, season, season_type)
    return profile


@router.get("/{player_id}/shot-quality")
def shot_quality(player_id: int, season: str | None = None,
                 season_type: str = "Regular Season"):
    return ml.shot_quality(player_id, season, season_type)


@router.get("/{player_id}/efficiency")
def efficiency_dashboard(player_id: int, season: str | None = None,
                         season_type: str = "Regular Season"):
    return efficiency.efficiency(player_id, season or current_season(),
                                 season_type)


@router.get("/{player_id}/playtime")
def playtime_dashboard(player_id: int, season: str | None = None,
                       season_type: str = "Regular Season"):
    return playtime.playtime(player_id, season or current_season(), season_type)


@router.get("/{player_id}/fouls")
def fouls_dashboard(player_id: int, season: str | None = None,
                    season_type: str = "Regular Season",
                    pbp_games: int = Query(default=10, le=20)):
    return fouls.fouls(player_id, season or current_season(), season_type,
                       pbp_games)


@router.get("/{player_id}/gamelog")
def game_log(player_id: int, season: str | None = None,
             season_type: str = "Regular Season",
             location: str | None = None, outcome: str | None = None,
             starter: bool | None = None, last_n: int | None = None,
             opponent: str | None = None, date_from: str | None = None,
             date_to: str | None = None):
    f = _filters(season, season_type, location, outcome, starter, last_n,
                 opponent, date_from, date_to)
    return gamelog.game_log(player_id, f)


@router.get("/{player_id}/games/{game_id}")
def game_detail(player_id: int, game_id: str):
    try:
        return gamelog.game_detail(player_id, game_id)
    except RuntimeError as err:
        raise HTTPException(status_code=502, detail=str(err))


@router.get("/{player_id}/trends")
def season_trends(player_id: int, season: str | None = None,
                  season_type: str = "Regular Season", window: int = 10):
    return trends.season_trends(player_id, season or current_season(),
                                season_type, window)


@router.get("/{player_id}/career")
def career(player_id: int):
    return trends.career(player_id)


@router.get("/{player_id}/impact")
def impact_dashboard(player_id: int, season: str | None = None,
                     season_type: str = "Regular Season"):
    info = players.bio(player_id)
    team_id = info.get("team_id")
    if not team_id:
        raise HTTPException(status_code=404, detail="Player has no current team")
    return impact.impact(player_id, team_id, season or current_season(),
                         season_type)
