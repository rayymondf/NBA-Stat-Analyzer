import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.nba.seasons import forward_roster_season, next_season  # noqa: E402
from app.services import players  # noqa: E402


def row(player_id: int, first: str, last: str, team: str,
        pts: float | None = None) -> dict:
    return {
        "PERSON_ID": player_id,
        "PLAYER_FIRST_NAME": first,
        "PLAYER_LAST_NAME": last,
        "TEAM_ID": player_id + 100,
        "TEAM_ABBREVIATION": team,
        "TEAM_CITY": team,
        "TEAM_NAME": "Team",
        "POSITION": "G",
        "JERSEY_NUMBER": "1",
        "PTS": pts,
        "REB": None,
        "AST": None,
    }


class PlayerLookupTests(unittest.TestCase):
    def test_season_helpers_cover_offseason_transition(self):
        self.assertEqual(next_season("2025-26"), "2026-27")
        self.assertEqual(forward_roster_season(date(2026, 7, 17)), "2026-27")
        self.assertIsNone(forward_roster_season(date(2026, 2, 1)))

    @patch("app.services.players.static_players.get_active_players")
    @patch("app.services.players.forward_roster_season", return_value="2026-27")
    @patch("app.services.players.api.active_player_index")
    @patch("app.services.players.api.player_index")
    def test_lookup_merges_season_roster_and_zero_game_players(
        self, season_index, active_index, _roster_season, static_active,
    ):
        season_index.return_value = [row(1, "Season", "Player", "OLD", 20.0)]
        active_index.return_value = [
            row(1, "Season", "Player", "NEW"),
            row(2, "Injured", "Player", "NEW"),
        ]
        static_active.return_value = [
            {"id": 1, "first_name": "Season", "last_name": "Player"},
            {"id": 2, "first_name": "Injured", "last_name": "Player"},
            {"id": 3, "first_name": "Registry", "last_name": "Only"},
        ]

        merged = {item["PERSON_ID"]: item
                  for item in players.player_lookup_index("2025-26")}

        self.assertEqual(set(merged), {1, 2, 3})
        self.assertEqual(merged[1]["PTS"], 20.0)
        self.assertEqual(merged[1]["TEAM_ABBREVIATION"], "NEW")
        self.assertTrue(merged[1]["_HAS_SEASON_STATS"])
        self.assertFalse(merged[2]["_HAS_SEASON_STATS"])
        self.assertTrue(merged[2]["_CURRENT_ROSTER"])
        self.assertFalse(merged[3]["_HAS_SEASON_STATS"])


if __name__ == "__main__":
    unittest.main()
