from __future__ import annotations

import pandas as pd

from app.services import (
    compare,
    efficiency,
    fouls,
    gamelog,
    impact,
    league,
    percentiles,
    playoffs,
    playtime,
    shooting,
    trends,
)


def test_percentile_helpers_and_player_pool(monkeypatch):
    rows = [
        {"PLAYER_ID": i, "PLAYER_NAME": str(i), "GP": 20, "MIN": 25,
         "PTS": float(i), "TOV": float(i), "POSITION": "G"}
        for i in range(1, 8)
    ]
    monkeypatch.setattr(percentiles.api, "league_player_stats", lambda *_a, **_k: rows)
    monkeypatch.setattr(percentiles, "position_map", lambda _season: dict.fromkeys(range(1, 8), "G"))
    result = percentiles.player_percentiles(4, "2025-26", stats=["PTS", "TOV"])
    assert result["PTS"]["percentile"] == 43
    assert result["TOV"]["percentile"] == 57
    assert result["PTS"]["pool_size"] == 7
    assert percentiles.percentile_of(pd.Series([1, 2]), 1.5) == 50
    assert percentiles._position_group(None) == "F"
    assert percentiles._position_group("G-F") == "G"


def test_position_map_backfills_current_roster(monkeypatch):
    monkeypatch.setattr(percentiles, "current_season", lambda: "2025-26", raising=False)
    monkeypatch.setattr(percentiles.api, "player_index", lambda season: (
        [{"PERSON_ID": 1, "POSITION": "C"}] if season == "2024-25"
        else [{"PERSON_ID": 1, "POSITION": "F"}, {"PERSON_ID": 2, "POSITION": "G"}]
    ))
    # current_season is imported inside the function, so exercise the live-season path directly.
    current = percentiles.position_map("2025-26")
    assert current[1] == "F"


def test_shooting_profile_and_scoring_breakdown(shots, monkeypatch):
    detail = pd.concat([shots] * 3, ignore_index=True).assign(
        GAME_ID="0022500001", GAME_DATE="2025-10-20", VTM="BOS",
    )
    league_rows = [
        {"SHOT_ZONE_BASIC": "Restricted Area", "FGA": 100, "FGM": 70},
        {"SHOT_ZONE_BASIC": "Above the Break 3", "FGA": 100, "FGM": 35},
    ]
    monkeypatch.setattr(shooting.api, "shot_chart", lambda *_a, **_k: {
        "Shot_Chart_Detail": detail.to_dict("records"), "LeagueAverages": league_rows,
    })
    profile = shooting.shot_profile(1, "2025-26")
    assert len(profile["points"]) == 6
    assert profile["totals"]["fga"] == 6
    assert len(profile["zones"]) == 2
    assert profile["zones"][0]["league_pct"] == 0.7

    monkeypatch.setattr(shooting.api, "league_player_stats", lambda *_a, **_k: [{
        "PLAYER_ID": 1, "PCT_AST_FGM": 0.6, "PCT_PTS_PAINT": 0.4,
    }])
    breakdown = shooting.scoring_breakdown(1, "2025-26")
    assert breakdown == {"pct_ast_fgm": 0.6, "pct_pts_paint": 0.4}


def test_shooting_empty_data(monkeypatch):
    monkeypatch.setattr(shooting.api, "shot_chart", lambda *_a, **_k: {})
    result = shooting.shot_profile(1, "2025-26")
    assert result["points"] == []


def test_efficiency_combines_official_and_aggregate(game_logs, monkeypatch):
    monkeypatch.setattr(efficiency.api, "league_player_stats", lambda *_a, **_k: [{
        "PLAYER_ID": 1, "TS_PCT": 0.61, "USG_PCT": 0.28, "PIE": 0.15,
    }])
    monkeypatch.setattr(efficiency.frames, "merged_logs", lambda *_a: game_logs)
    monkeypatch.setattr(efficiency.percentiles, "player_percentiles", lambda *_a, **_k: {
        "TS_PCT": {"percentile": 80}
    })
    result = efficiency.efficiency(1, "2025-26")
    assert result["games"] == 3
    assert result["metrics"]["ts_pct"] == 0.61
    assert result["metrics"]["pie"] == 0.15


def test_playtime_full_dashboard(game_logs, monkeypatch):
    logs = game_logs.copy()
    logs["TEAM_ABBREVIATION"] = "TOR"
    monkeypatch.setattr(playtime.frames, "merged_logs", lambda *_a: logs)
    monkeypatch.setattr(playtime.api, "find_team_games", lambda *_a: [
        {"TEAM_ABBREVIATION": "TOR"} for _ in range(5)
    ])
    monkeypatch.setattr(playtime.api, "game_splits", lambda *_a: {
        "ByPeriodPlayerDashboard": [{"GROUP_VALUE": 4, "MIN": 24, "PTS": 20, "FG_PCT": 0.5}]
    })
    monkeypatch.setattr(playtime.api, "clutch_dashboard", lambda *_a: {
        "Last5Min5PointPlayerDashboard": [{
            "GP": 2, "MIN": 8, "PTS": 9, "FG_PCT": 0.5, "PLUS_MINUS": 4, "W": 2, "L": 0,
        }]
    })
    result = playtime.playtime(1, "2025-26")
    assert result["games"] == 3
    assert result["games_missed"] == 2
    assert result["q4"]["min_per_game"] == 8
    assert result["clutch"]["pts_per_game"] == 4.5
    assert result["by_minutes"]


def test_foul_classification_and_dashboard(game_logs, monkeypatch):
    assert fouls._classify("Shooting", "") == "shooting"
    assert fouls._classify("", "Technical foul") == "technical"
    assert fouls._classify("Charge", "") == "offensive"
    assert fouls._classify("Loose Ball", "") == "loose_ball"
    assert fouls._classify("Personal", "") == "personal"
    assert fouls._classify("Transition", "") == "other"

    logs = game_logs.assign(PLAYER_NAME="Player")
    monkeypatch.setattr(fouls.frames, "merged_logs", lambda *_a: logs)
    monkeypatch.setattr(fouls.api, "play_by_play", lambda _gid: [
        {"actionType": "Foul", "personId": 1, "subType": "Shooting", "description": ""},
        {"actionType": "Foul", "personId": 2, "subType": "Personal", "description": ""},
    ])
    result = fouls.fouls(1, "2025-26", pbp_games=2)
    assert result["foul_types_recent"]["counts"]["shooting"] == 2
    assert result["foul_types_recent"]["games_analyzed"] == 2
    assert result["games_5_fouls"] == 1


def test_game_log_helpers_and_detail(monkeypatch):
    assert gamelog.season_from_game_id("0022500001") == "2025-26"
    assert gamelog.season_type_from_game_id("0042500001") == "Playoffs"
    assert gamelog._elapsed_minutes(1, "PT08M30.00S") == 3.5
    actions = [
        {"scoreHome": "2", "scoreAway": "0", "period": 1, "clock": "PT11M00.00S",
         "personId": 1, "isFieldGoal": 1, "shotResult": "Made", "description": "Layup"},
        {"scoreHome": "2", "scoreAway": "1", "period": 1, "clock": "PT10M00.00S",
         "personId": 1, "actionType": "Free Throw", "description": "Free Throw 1 of 1"},
    ]
    assert gamelog.score_timeline(actions)[-1]["margin"] == 1
    assert len(gamelog._player_scoring_events(actions, 1)) == 2

    player = {"personId": 1, "firstName": "Test", "familyName": "Player", "position": "G",
              "statistics": {"minutes": "PT30M00.00S", "points": 20,
                             "reboundsTotal": 5, "assists": 4, "fieldGoalsAttempted": 12,
                             "freeThrowsAttempted": 3}}
    def team(team_id, code, points):
        return {
            "teamId": team_id, "teamTricode": code, "teamCity": code, "teamName": "Team",
            "statistics": {"points": points}, "players": [player] if team_id == 1 else [],
        }
    monkeypatch.setattr(gamelog.api, "boxscore_traditional", lambda _gid: {
        "homeTeam": team(1, "TOR", 100), "awayTeam": team(2, "BOS", 90),
    })
    monkeypatch.setattr(gamelog.api, "play_by_play", lambda _gid: actions)
    monkeypatch.setattr(gamelog.shooting, "shot_profile", lambda *_a, **_k: {"points": []})
    detail = gamelog.game_detail(1, "0022500001")
    assert detail["player_line"]["name"] == "Test Player"
    assert detail["home"]["pts"] == 100


def test_trends_and_career(game_logs, monkeypatch):
    monkeypatch.setattr(trends.frames, "merged_logs", lambda *_a: game_logs)
    result = trends.season_trends(1, "2025-26", window=3)
    assert result["games"] == 3
    assert result["window"] == 3
    assert result["recent_form"]["season_pts"] == 18.7

    monkeypatch.setattr(trends.api, "career_stats", lambda *_a, **_k: {
        "SeasonTotalsRegularSeason": [{
            "SEASON_ID": "2025-26", "TEAM_ABBREVIATION": "TOR", "PTS": 20,
            "FGA": 15, "FTA": 5,
        }],
        "SeasonTotalsPostSeason": [],
    })
    career = trends.career(1)
    assert career["regular_season"][0]["ts_pct"] is not None


def test_impact_on_off_and_history(monkeypatch):
    rows = {
        "PlayersOnCourtTeamPlayerOnOffDetails": [{
            "VS_PLAYER_ID": 1, "MIN": 100, "GP": 10, "OFF_RATING": 115,
            "DEF_RATING": 105, "NET_RATING": 10,
        }],
        "PlayersOffCourtTeamPlayerOnOffDetails": [{
            "VS_PLAYER_ID": 1, "MIN": 50, "GP": 10, "OFF_RATING": 108,
            "DEF_RATING": 110, "NET_RATING": -2,
        }],
    }
    monkeypatch.setattr(impact.api, "team_player_on_off", lambda *_a: rows)
    current = impact.on_off(1, 10, "2025-26")
    assert current["net_diff"] == 12
    assert current["off_diff"] == 7
    result = impact.impact(1, 10, "2025-26", history=2)
    assert len(result["history"]) == 1


def test_league_queries(monkeypatch):
    base = pd.DataFrame([
        {"PLAYER_ID": i, "PLAYER_NAME": f"P{i}", "TEAM_ABBREVIATION": "TOR",
         "GP": 20, "MIN": 20 + i, "PTS": 10 + i, "FGA": 8 + i, "REB": 4,
         "AST": 3, "STL": 1, "BLK": 1, "TOV": 2, "FG3A": 4, "FTA": 3,
         "POS_GROUP": "G"}
        for i in range(1, 7)
    ])
    advanced = base[["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN", "FGA"]].copy()
    advanced["TS_PCT"] = [0.5, 0.52, 0.54, 0.56, 0.58, 0.6]
    advanced["USG_PCT"] = 0.2
    advanced["AST_PCT"] = 0.2
    advanced["REB_PCT"] = 0.1
    monkeypatch.setattr(league, "league_pool", lambda _s, _st="Regular Season", measure="Base", _pm="PerGame": advanced if measure == "Advanced" else base)
    assert league.leaders("2025-26", limit=2)[0]["name"] == "P6"
    assert league.similar_players(1, "2025-26", limit=2)["matches"]
    assert league.low_minutes_efficient("2025-26", max_mpg=25)
    monkeypatch.setattr(league.api, "league_team_stats", lambda *_a: [
        {"TEAM_ID": 1, "TEAM_NAME": "A", "DEF_RATING": 100, "NET_RATING": 5},
        {"TEAM_ID": 2, "TEAM_NAME": "B", "DEF_RATING": 110, "NET_RATING": -5},
    ])
    assert league.team_defense("2025-26")[0]["rank"] == 1


def test_compare_composes_existing_services(monkeypatch):
    monkeypatch.setattr(compare.players, "bio", lambda pid: {"player_id": pid, "name": str(pid)})
    monkeypatch.setattr(compare.frames, "merged_logs", lambda *_a: pd.DataFrame())
    monkeypatch.setattr(compare.percentiles, "player_percentiles", lambda *_a, **_k: {})
    monkeypatch.setattr(compare.shooting, "shot_profile", lambda *_a: {"zones": [], "points": []})
    monkeypatch.setattr(compare.efficiency, "efficiency", lambda *_a: {"metrics": {}})
    result = compare.compare(1, 2, "2025-26")
    assert result["a"]["info"]["player_id"] == 1
    assert result["b"]["info"]["player_id"] == 2


def test_playoff_elimination_and_closeout(monkeypatch):
    games = pd.DataFrame([
        {"OPP": "BOS", "GAME_DATE": pd.Timestamp(f"2025-04-{day:02d}"),
         "MATCHUP": "TOR vs. BOS", "WL": result, "PTS": 20, "FGA": 15,
         "FTA": 5, "MIN": 35}
        for day, result in enumerate(["L", "L", "L", "W", "W", "W", "L"], 1)
    ])
    monkeypatch.setattr(playoffs, "current_season", lambda: "2025-26")
    monkeypatch.setattr(playoffs.frames, "merged_logs", lambda *_a: games)
    result = playoffs.elimination_stats(1, seasons_back=1)
    assert result["elimination"]["games"] == 4
    assert result["closeout"]["games"] == 1
    assert result["all_playoffs_baseline"]["games"] == 7
