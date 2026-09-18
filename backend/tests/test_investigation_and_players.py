from __future__ import annotations

import pytest

from app.services import frames, game_investigation, players


def _player(person_id: int, name: str, points: int, minutes: str = "PT36M00.00S") -> dict:
    first, family = name.split(" ", 1)
    return {
        "personId": person_id, "firstName": first, "familyName": family,
        "statistics": {
            "minutes": minutes, "points": points, "fieldGoalsAttempted": 15,
            "freeThrowsAttempted": 4,
        },
    }


def _team(team_id: int, code: str, points: int, bench_points: int,
          players: list[dict]) -> dict:
    return {
        "teamId": team_id, "teamTricode": code, "teamCity": code,
        "teamName": "Team", "bench": {"points": bench_points}, "players": players,
        "statistics": {
            "points": points, "fieldGoalsAttempted": 85, "fieldGoalsMade": 42,
            "threePointersMade": 14, "threePointersAttempted": 36,
            "freeThrowsAttempted": 20, "freeThrowsMade": 16, "turnovers": 10,
            "reboundsOffensive": 12, "reboundsDefensive": 35,
        },
    }


def test_four_factors_runs_and_full_investigation(monkeypatch):
    home_players = [_player(1, "Alpha One", 30), _player(2, "Alpha Two", 20)]
    away_players = [_player(3, "Beta One", 22), _player(4, "Beta Two", 18)]
    home = _team(1, "TOR", 110, 35, home_players)
    away = _team(2, "BOS", 100, 20, away_players)
    away["statistics"].update({
        "fieldGoalsMade": 37, "threePointersMade": 10, "turnovers": 16,
        "reboundsOffensive": 8, "freeThrowsMade": 14,
    })
    actions = [
        {"scoreHome": "2", "scoreAway": "0", "period": 1, "clock": "PT11M00.00S"},
        {"scoreHome": "5", "scoreAway": "0", "period": 1, "clock": "PT10M00.00S"},
        {"scoreHome": "8", "scoreAway": "0", "period": 1, "clock": "PT09M00.00S"},
        {"scoreHome": "80", "scoreAway": "76", "period": 3, "clock": "PT00M01.00S"},
        {"scoreHome": "110", "scoreAway": "100", "period": 4, "clock": "PT00M01.00S"},
    ]
    monkeypatch.setattr(game_investigation.api, "boxscore_traditional", lambda _gid: {
        "homeTeam": home, "awayTeam": away,
    })
    monkeypatch.setattr(game_investigation.api, "play_by_play", lambda _gid: actions)
    monkeypatch.setattr(game_investigation.api, "league_player_stats", lambda *_a, **_k: [
        {"PLAYER_ID": 1, "PTS": 25}, {"PLAYER_ID": 2, "PTS": 15},
        {"PLAYER_ID": 3, "PTS": 24}, {"PLAYER_ID": 4, "PTS": 20},
    ])

    result = game_investigation.investigate("0022500001")
    assert result["final"] == "TOR 110 - 100 BOS"
    assert result["teams"][0]["winner"] is True
    assert {item["key"] for item in result["explanations"]} >= {
        "efg", "tov", "orb", "ft", "bench", "stars", "q4", "runs",
    }
    assert result["runs"][0]["points"] >= 8
    assert result["q4"]["close_entering_q4"] is True
    assert game_investigation._ts(10, 0, 0) is None


def test_investigation_rejects_unfinished_game(monkeypatch):
    monkeypatch.setattr(game_investigation.api, "boxscore_traditional", lambda _gid: {})
    with pytest.raises(ValueError, match="no final boxscore"):
        game_investigation.investigate("0022500001")


def test_game_listing_deduplicates_and_filters(monkeypatch):
    rows = [
        {"GAME_ID": "1", "GAME_DATE": "2025-10-20", "MATCHUP": "TOR vs. BOS",
         "TEAM_ID": 1, "TEAM_ABBREVIATION": "TOR", "TEAM_NAME": "Toronto",
         "PTS": 100, "WL": "W"},
        {"GAME_ID": "1", "GAME_DATE": "2025-10-20", "MATCHUP": "BOS @ TOR",
         "TEAM_ID": 2, "TEAM_ABBREVIATION": "BOS", "TEAM_NAME": "Boston",
         "PTS": 90, "WL": "L"},
        {"GAME_ID": "2", "GAME_DATE": "2025-10-21", "MATCHUP": "NYK vs. MIA",
         "TEAM_ID": 3, "TEAM_ABBREVIATION": "NYK", "TEAM_NAME": "New York",
         "PTS": 0, "WL": None},
    ]
    monkeypatch.setattr(game_investigation.api, "find_team_games", lambda *_a: rows)
    games = game_investigation.list_games("2025-26", team="tor")
    assert len(games) == 1
    assert games[0]["home"]["abbr"] == "TOR"


def test_player_bio_summary_and_filtered_bundle(game_logs, monkeypatch):
    monkeypatch.setattr(players.api, "common_player_info", lambda _pid: {
        "DISPLAY_FIRST_LAST": "Test Player", "TEAM_ABBREVIATION": "TOR",
        "TEAM_ID": 1, "TEAM_CITY": "Toronto", "TEAM_NAME": "Raptors",
        "POSITION": "G", "JERSEY": "1", "HEIGHT": "6-5", "WEIGHT": "200",
        "BIRTHDATE": "2000-01-01T00:00:00", "COUNTRY": "Canada", "SEASON_EXP": 3,
        "DRAFT_YEAR": "2020", "DRAFT_ROUND": "1", "DRAFT_NUMBER": "1",
        "FROM_YEAR": "2020", "TO_YEAR": "2026",
    })
    monkeypatch.setattr(players.frames, "merged_logs", lambda *_a: game_logs)
    monkeypatch.setattr(players.percentiles, "player_percentiles", lambda *_a, **_k: {
        "TS_PCT": {"percentile": 82}, "PTS": {"percentile": 90},
    })

    bio = players.bio(1)
    assert bio["team_name"] == "Toronto Raptors"
    assert bio["draft"]["pick"] == "1"
    summary = players.summary(1, "2025-26")
    assert summary["stats"]["games"] == 3
    assert "elite efficiency" in summary["blurb"]
    assert summary["age"] is not None

    filters = frames.LogFilters(season="2025-26", location="away")
    overview = players.overview(1, filters)
    assert overview["stats"]["games"] == 1
    assert overview["season_games"] == 3


def test_player_search_typo_fallback(monkeypatch):
    monkeypatch.setattr(players, "player_lookup_index", lambda _season: [{
        "PERSON_ID": 1, "PLAYER_FIRST_NAME": "Damian", "PLAYER_LAST_NAME": "Lillard",
        "TEAM_ABBREVIATION": "MIL", "TEAM_CITY": "Milwaukee", "TEAM_NAME": "Bucks",
        "POSITION": "G", "JERSEY_NUMBER": "0", "PTS": 24, "REB": 4, "AST": 7,
    }])
    result = players.search("Damin Lilard")
    assert result[0]["name"] == "Damian Lillard"


def test_merged_logs_derives_and_handles_starter_failure(monkeypatch):
    base = [{
        "GAME_ID": "1", "GAME_DATE": "2025-10-20", "MATCHUP": "TOR vs. BOS",
        "WL": "W", "MIN": 30,
    }]
    monkeypatch.setattr(frames.api, "player_game_logs", lambda *_a, **kwargs: (
        [{"GAME_ID": "1", "OFF_RATING": 110}] if kwargs.get("measure") == "Advanced" else base
    ))
    monkeypatch.setattr(frames.api, "starter_game_ids", lambda *_a: {"1"})
    result = frames.merged_logs(1, "2025-26")
    assert result.iloc[0]["HOME"]
    assert result.iloc[0]["OPP"] == "BOS"
    assert result.iloc[0]["STARTED"]

    monkeypatch.setattr(frames.api, "starter_game_ids", lambda *_a: (_ for _ in ()).throw(RuntimeError()))
    assert frames.merged_logs(1, "2025-26").iloc[0]["STARTED"] is None

