"""Export a human-readable CSV from the resumable raw shot partitions."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.nba.seasons import current_season, previous_season
from app.pipeline.ingest import ingest_shots

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
COLUMNS = [
    "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_NAME", "SEASON", "GAME_ID",
    "GAME_EVENT_ID",
    "GAME_DATE", "PERIOD", "MINUTES_REMAINING", "SECONDS_REMAINING",
    "SHOT_ZONE_BASIC", "SHOT_ZONE_AREA", "ACTION_TYPE", "SHOT_TYPE",
    "SHOT_DISTANCE", "LOC_X", "LOC_Y", "HTM", "VTM", "SHOT_MADE_FLAG",
]


def main() -> None:
    newest = current_season()
    seasons = [newest, previous_season(newest), previous_season(previous_season(newest))]
    result = ingest_shots(seasons, DATA_DIR / "raw" / "shots")
    frame = pd.concat((pd.read_parquet(path) for path in result.paths), ignore_index=True)
    columns = [column for column in COLUMNS if column in frame.columns]
    export = frame[columns].copy()
    export["SHOT_MADE_FLAG"] = export["SHOT_MADE_FLAG"].replace({1: "Made", 0: "Missed"})
    output = DATA_DIR / "shots_export.csv"
    export.to_csv(output, index=False)
    print(f"Wrote {len(export):,} shots to {output}")


if __name__ == "__main__":
    main()
