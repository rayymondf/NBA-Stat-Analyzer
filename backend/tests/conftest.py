from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def game_logs() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "GAME_ID": "0022500001", "GAME_DATE": pd.Timestamp("2025-10-20"),
            "MATCHUP": "TOR vs. BOS", "HOME": True, "OPP": "BOS", "WL": "W",
            "STARTED": True, "MIN": 36.0, "FGM": 10, "FGA": 20, "FG3M": 4,
            "FG3A": 8, "FTM": 6, "FTA": 6, "OREB": 1, "DREB": 7, "REB": 8,
            "AST": 7, "TOV": 2, "STL": 1, "BLK": 1, "BLKA": 0, "PF": 2,
            "PFD": 4, "PTS": 30, "PLUS_MINUS": 8, "POSS": 72, "DD2": 0,
            "TD3": 0, "OFF_RATING": 120.0, "DEF_RATING": 108.0,
            "NET_RATING": 12.0, "PACE": 99.0,
        },
        {
            "GAME_ID": "0022500002", "GAME_DATE": pd.Timestamp("2025-10-22"),
            "MATCHUP": "TOR @ NYK", "HOME": False, "OPP": "NYK", "WL": "L",
            "STARTED": False, "MIN": 24.0, "FGM": 4, "FGA": 12, "FG3M": 1,
            "FG3A": 5, "FTM": 1, "FTA": 2, "OREB": 0, "DREB": 4, "REB": 4,
            "AST": 3, "TOV": 3, "STL": 0, "BLK": 0, "BLKA": 1, "PF": 5,
            "PFD": 1, "PTS": 10, "PLUS_MINUS": -6, "POSS": 48, "DD2": 0,
            "TD3": 0, "OFF_RATING": None, "DEF_RATING": None,
            "NET_RATING": None, "PACE": None,
        },
        {
            "GAME_ID": "0022500003", "GAME_DATE": pd.Timestamp("2025-10-24"),
            "MATCHUP": "TOR vs. MIA", "HOME": True, "OPP": "MIA", "WL": "W",
            "STARTED": True, "MIN": 30.0, "FGM": 6, "FGA": 15, "FG3M": 2,
            "FG3A": 6, "FTM": 2, "FTA": 3, "OREB": 2, "DREB": 5, "REB": 7,
            "AST": 5, "TOV": 1, "STL": 2, "BLK": 1, "BLKA": 0, "PF": 3,
            "PFD": 2, "PTS": 16, "PLUS_MINUS": 4, "POSS": 60, "DD2": 0,
            "TD3": 0, "OFF_RATING": 112.0, "DEF_RATING": 105.0,
            "NET_RATING": 7.0, "PACE": 97.0,
        },
    ])


@pytest.fixture
def shots() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "SHOT_DISTANCE": 2, "LOC_X": -10, "LOC_Y": 20, "PERIOD": 1,
            "MINUTES_REMAINING": 11, "SECONDS_REMAINING": 30,
            "SHOT_TYPE": "2PT Field Goal", "SHOT_ZONE_BASIC": "Restricted Area",
            "SHOT_ZONE_AREA": "Center(C)", "ACTION_TYPE": "Driving Layup Shot",
            "TEAM_ID": 1610612761, "HTM": "TOR", "SHOT_MADE_FLAG": 1,
        },
        {
            "SHOT_DISTANCE": 25, "LOC_X": 220, "LOC_Y": 80, "PERIOD": 4,
            "MINUTES_REMAINING": 0, "SECONDS_REMAINING": 3,
            "SHOT_TYPE": "3PT Field Goal", "SHOT_ZONE_BASIC": "Above the Break 3",
            "SHOT_ZONE_AREA": "Right Side Center(RC)", "ACTION_TYPE": "Step Back Jump shot",
            "TEAM_ID": 1610612761, "HTM": "TOR", "SHOT_MADE_FLAG": 0,
        },
    ])

