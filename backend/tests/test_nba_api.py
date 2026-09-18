from __future__ import annotations

import pytest

from app.nba import api


@pytest.fixture
def fake_fetch(monkeypatch):
    payload = {
        "PlayerGameLogs": [{"GAME_ID": "1"}],
        "LeagueDashPlayerStats": [{"PLAYER_ID": 1}],
        "PlayerIndex": [{"PERSON_ID": 1}],
        "CommonPlayerInfo": [{"PERSON_ID": 1}],
        "Shot_Chart_Detail": [{"SHOT_MADE_FLAG": 1}],
        "LeagueDashTeamStats": [{"TEAM_ID": 1}],
        "LeagueGameFinderResults": [{"GAME_ID": "1"}],
        "boxScoreTraditional": {"homeTeam": {}},
        "game": {"actions": [{"actionType": "Made Shot"}]},
    }
    calls = []

    def fetch(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return payload

    monkeypatch.setattr(api, "fetch", fetch)
    return payload, calls


def test_endpoint_wrappers_return_expected_result_sets(fake_fetch):
    payload, calls = fake_fetch
    assert api.player_game_logs(1, "2025-26") == payload["PlayerGameLogs"]
    assert api.league_player_stats("2025-26") == payload["LeagueDashPlayerStats"]
    assert api.player_index("2025-26") == payload["PlayerIndex"]
    assert api.active_player_index("2025-26") == payload["PlayerIndex"]
    assert api.common_player_info(1) == payload["CommonPlayerInfo"][0]
    assert api.career_stats(1) is payload
    assert api.shot_chart(1, "2025-26") is payload
    assert api.team_shot_chart(1, "2025-26") == payload["Shot_Chart_Detail"]
    assert api.general_splits(1, "2025-26") is payload
    assert api.game_splits(1, "2025-26") is payload
    assert api.clutch_dashboard(1, "2025-26") is payload
    assert api.team_player_on_off(1, "2025-26") is payload
    assert api.league_team_stats("2025-26") == payload["LeagueDashTeamStats"]
    assert api.starter_game_ids(1, "2025-26") == {"1"}
    assert api.boxscore_traditional("0022500001") == payload["boxScoreTraditional"]
    assert api.play_by_play("0022500001") == payload["game"]["actions"]
    assert api.find_team_games("2025-26") == payload["LeagueGameFinderResults"]
    assert len(calls) == 17


@pytest.mark.parametrize(("raw", "expected"), [
    (None, 0.0), ("", 0.0), (36, 36.0), (36.5, 36.5),
    ("PT36M30.00S", 36.5), ("36:30", 36.5), ("12.25", 12.25), ("bad", 0.0),
])
def test_minutes_float_formats(raw, expected):
    assert api.minutes_float(raw) == expected


def test_common_player_info_handles_empty_result(fake_fetch):
    payload, _ = fake_fetch
    payload["CommonPlayerInfo"] = []
    assert api.common_player_info(99) == {}

