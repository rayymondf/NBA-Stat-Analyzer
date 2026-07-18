"""Dump the raw shot dataset the xFG model was trained on to a plain CSV file
you can open in Excel.

    backend\\venv\\Scripts\\python.exe backend\\scripts\\export_shots_csv.py

Reuses the same cached NBA.com data as train_models.py, so this is fast
(no new downloads) if you've already trained the model.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.train_models import collect_shots, train_seasons  # noqa: E402

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "shots_export.csv")

COLUMNS = [
    "PLAYER_NAME", "TEAM_NAME", "SEASON", "GAME_DATE", "PERIOD",
    "MINUTES_REMAINING", "SECONDS_REMAINING",
    "SHOT_ZONE_BASIC", "SHOT_ZONE_AREA", "ACTION_TYPE", "SHOT_TYPE",
    "SHOT_DISTANCE", "LOC_X", "LOC_Y", "HTM", "VTM", "SHOT_MADE_FLAG",
]


def main() -> None:
    seasons = train_seasons()
    print(f"Collecting shots for {seasons} (uses cache if already trained) …")
    shots = collect_shots(seasons)

    cols = [c for c in COLUMNS if c in shots.columns]
    out = shots[cols].copy()
    out["SHOT_MADE_FLAG"] = out["SHOT_MADE_FLAG"].map({1: "Made", 0: "Missed"})

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(out):,} shots -> {os.path.abspath(OUT_PATH)}")


if __name__ == "__main__":
    main()
