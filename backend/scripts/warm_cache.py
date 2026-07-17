"""Pre-fetch league-wide tables for the default seasons so percentiles,
league queries and search are instant on first use. Run once after setup:

    backend\\venv\\Scripts\\python.exe backend\\scripts\\warm_cache.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.nba import api  # noqa: E402
from app.nba.seasons import DEFAULT_SEASONS  # noqa: E402

def main() -> None:
    for season in DEFAULT_SEASONS:
        print(f"Warming {season}…")
        print("  player index:", len(api.player_index(season)), "players")
        for measure in ("Base", "Advanced", "Scoring"):
            for per_mode in ("PerGame", "Per100Possessions"):
                if measure == "Scoring" and per_mode != "PerGame":
                    continue
                rows = api.league_player_stats(season, per_mode=per_mode,
                                               measure=measure)
                print(f"  {measure}/{per_mode}: {len(rows)} rows")
        print("  team stats:", len(api.league_team_stats(season)), "teams")
        print("  games:", len(api.find_team_games(season)), "team-game rows")
    print("Done — cache stored in backend/data/cache.sqlite")


if __name__ == "__main__":
    main()
