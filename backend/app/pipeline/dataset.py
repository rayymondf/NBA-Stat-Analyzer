"""Validation and columnar storage for the NBA shot dataset."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from .manifest import DatasetManifest

REQUIRED_COLUMNS = {
    "GAME_ID",
    "GAME_EVENT_ID",
    "PLAYER_ID",
    "TEAM_ID",
    "HTM",
    "SEASON",
    "GAME_DATE",
    "PERIOD",
    "MINUTES_REMAINING",
    "SECONDS_REMAINING",
    "SHOT_ZONE_BASIC",
    "SHOT_ZONE_AREA",
    "ACTION_TYPE",
    "SHOT_TYPE",
    "SHOT_DISTANCE",
    "LOC_X",
    "LOC_Y",
    "SHOT_MADE_FLAG",
}
TARGET_VALUES = {0, 1}
SEASON_PATTERN = r"^(\d{4})-(\d{2})$"


class DatasetValidationError(ValueError):
    """Raised when source data violates the versioned shot-data contract."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True, slots=True)
class DatasetReport:
    rows: int
    columns: list[str]
    seasons: list[str]
    null_counts: dict[str, int]
    made_rate: float
    duplicate_rows: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "columns": self.columns,
            "seasons": self.seasons,
            "null_counts": self.null_counts,
            "made_rate": self.made_rate,
            "duplicate_rows": self.duplicate_rows,
        }


def _normalise_target(series: pd.Series) -> pd.Series:
    mapped = series.replace({"Made": 1, "Missed": 0, "made": 1, "missed": 0})
    return pd.to_numeric(mapped, errors="coerce")


def _read_frame(source_path: Path, *, nrows: int | None = None) -> pd.DataFrame:
    if source_path.suffix.lower() == ".csv":
        return pd.read_csv(
            source_path,
            nrows=nrows,
            low_memory=False,
            dtype={"GAME_ID": "string"},
        )
    frame = pd.read_parquet(source_path)
    return frame.head(nrows) if nrows is not None else frame


def validate_shots(frame: pd.DataFrame, *, strict: bool = True) -> DatasetReport:
    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise DatasetValidationError([f"missing required columns: {', '.join(missing)}"])

    errors: list[str] = []
    target = _normalise_target(frame["SHOT_MADE_FLAG"])
    invalid_target = int((target.isna() | ~target.isin(TARGET_VALUES)).sum())
    if invalid_target:
        errors.append(f"SHOT_MADE_FLAG has {invalid_target} invalid values")

    numeric_constraints = {
        "PERIOD": (1, 20),
        "MINUTES_REMAINING": (0, 12),
        "SECONDS_REMAINING": (0, 59),
        "SHOT_DISTANCE": (0, 100),
        "LOC_X": (-400, 400),
        "LOC_Y": (-100, 1000),
    }
    for column, (lower, upper) in numeric_constraints.items():
        values = pd.to_numeric(frame[column], errors="coerce")
        invalid = int((values.isna() | ~values.between(lower, upper)).sum())
        if column in {"PERIOD", "MINUTES_REMAINING", "SECONDS_REMAINING"}:
            invalid += int((values.dropna() % 1 != 0).sum())
        if invalid:
            errors.append(f"{column} has {invalid} missing or out-of-range values")

    seasons = frame["SEASON"].astype(str)
    season_parts = seasons.str.extract(SEASON_PATTERN)
    valid_season = season_parts.notna().all(axis=1) & (
        (pd.to_numeric(season_parts[0], errors="coerce") + 1) % 100
        == pd.to_numeric(season_parts[1], errors="coerce")
    )
    invalid_seasons = int((~valid_season).sum())
    if invalid_seasons:
        errors.append(f"SEASON has {invalid_seasons} invalid values")

    parsed_dates = pd.to_datetime(frame["GAME_DATE"].astype(str), format="%Y%m%d", errors="coerce")
    if parsed_dates.isna().any():
        errors.append(f"GAME_DATE has {int(parsed_dates.isna().sum())} invalid values")

    game_ids = frame["GAME_ID"].astype(str)
    invalid_game_ids = int((~game_ids.str.fullmatch(r"\d{10}")).sum())
    if invalid_game_ids:
        errors.append(f"GAME_ID has {invalid_game_ids} invalid values")
    for column in ("GAME_EVENT_ID", "PLAYER_ID", "TEAM_ID"):
        values = pd.to_numeric(frame[column], errors="coerce")
        invalid_identity = (
            values.isna()
            | (values % 1 != 0)
            | (values < (0 if column == "GAME_EVENT_ID" else 1))
        )
        if invalid_identity.any():
            errors.append(f"{column} has {int(invalid_identity.sum())} invalid values")
    invalid_home_team = ~frame["HTM"].astype(str).str.fullmatch(r"[A-Z]{2,4}")
    if invalid_home_team.any():
        errors.append(f"HTM has {int(invalid_home_team.sum())} invalid values")

    for column in ("SHOT_ZONE_BASIC", "SHOT_ZONE_AREA", "ACTION_TYPE", "SHOT_TYPE"):
        blank = frame[column].isna() | frame[column].astype(str).str.strip().eq("")
        if blank.any():
            errors.append(f"{column} has {int(blank.sum())} blank values")
    valid_shot_types = {"2PT Field Goal", "3PT Field Goal"}
    invalid_shot_types = ~frame["SHOT_TYPE"].isin(valid_shot_types)
    if invalid_shot_types.any():
        errors.append(f"SHOT_TYPE has {int(invalid_shot_types.sum())} invalid values")

    critical = sorted(REQUIRED_COLUMNS)
    null_counts = {column: int(frame[column].isna().sum()) for column in critical}
    critical_nulls = sum(null_counts.values())
    if strict and critical_nulls:
        errors.append(f"required columns contain {critical_nulls} null values")
    if frame.empty:
        errors.append("dataset is empty")
    if errors:
        raise DatasetValidationError(errors)

    duplicate_subset = [
        column for column in ("GAME_ID", "GAME_EVENT_ID") if column in frame.columns
    ]
    duplicate_rows = int(frame.duplicated(subset=duplicate_subset or None).sum())
    if duplicate_rows:
        raise DatasetValidationError([f"dataset has {duplicate_rows} duplicate shot events"])
    return DatasetReport(
        rows=len(frame),
        columns=frame.columns.astype(str).tolist(),
        seasons=sorted(seasons.unique().tolist()),
        null_counts=null_counts,
        made_rate=round(float(target.mean()), 6),
        duplicate_rows=duplicate_rows,
    )


def inspect_dataset(source_path: Path, *, sample_rows: int | None = None) -> DatasetReport:
    return validate_shots(_read_frame(source_path, nrows=sample_rows))


def build_parquet(
    source_path: Path,
    output_dir: Path,
    *,
    manifest_path: Path | None = None,
) -> DatasetManifest:
    """Validate CSV input and atomically write Hive-partitioned Parquet."""
    if source_path.suffix.lower() not in {".csv", ".parquet", ".pq"}:
        raise ValueError("Source must be a .csv, .parquet, or .pq file")
    frame = _read_frame(source_path)
    report = validate_shots(frame)
    frame["SHOT_MADE_FLAG"] = _normalise_target(frame["SHOT_MADE_FLAG"]).astype("Int8")
    partition_columns = [column for column in ("SEASON", "TEAM_NAME") if column in frame.columns]

    temporary = output_dir.with_name(output_dir.name + ".building")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    table = pa.Table.from_pandas(frame, preserve_index=False)
    ds.write_dataset(
        table,
        temporary,
        format="parquet",
        partitioning=partition_columns,
        partitioning_flavor="hive",
        existing_data_behavior="delete_matching",
        max_rows_per_file=100_000,
        max_rows_per_group=50_000,
    )
    manifest = DatasetManifest.create(
        source_path,
        rows=report.rows,
        seasons=report.seasons,
        columns=report.columns,
        source="stats.nba.com via nba_api",
        partitions=partition_columns,
        validation=report.as_dict(),
        processed_dir=temporary,
    )
    manifest.write(temporary / "_manifest.json")

    backup = output_dir.with_name(output_dir.name + ".previous")
    moved_existing = False
    if output_dir.exists():
        if backup.exists():
            shutil.rmtree(backup)
        output_dir.replace(backup)
        moved_existing = True
    try:
        temporary.replace(output_dir)
    except Exception:
        if moved_existing and backup.exists() and not output_dir.exists():
            backup.replace(output_dir)
        raise
    if backup.exists():
        shutil.rmtree(backup)
    if manifest_path:
        manifest.write(manifest_path)
    return manifest


def query_parquet(dataset_dir: Path, sql: str) -> pd.DataFrame:
    """Run a read-only SELECT against the partitioned dataset with DuckDB."""
    statement = sql.strip()
    if ";" in statement.rstrip(";"):
        raise ValueError("Only one SQL statement is allowed")
    statement = statement.rstrip(";").strip()
    if not statement.lower().startswith(("select ", "with ")):
        raise ValueError("Only SELECT/CTE queries are allowed")
    lowered = statement.lower()
    forbidden = (
        "read_csv", "read_parquet", "sqlite_scan", "postgres_scan", "httpfs",
        " attach ", " copy ", " pragma ", " install ", " load ", " export ", " import ",
    )
    padded = f" {lowered} "
    if any(token in padded for token in forbidden):
        raise ValueError("External readers and mutating SQL are not allowed")
    glob = str(dataset_dir / "**" / "*.parquet").replace("\\", "/")
    connection = duckdb.connect(":memory:")
    try:
        connection.from_parquet(glob, hive_partitioning=True).create_view("shots")
        return connection.execute(statement).fetchdf()
    finally:
        connection.close()
