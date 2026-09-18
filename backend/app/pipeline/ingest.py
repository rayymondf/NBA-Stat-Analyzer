"""Resumable league-wide shot ingestion from NBA.com."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from nba_api.stats.static import teams as static_teams

from ..nba import api
from ..nba.seasons import current_season
from .manifest import sha256_file

SEASON_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


def _validate_season(season: str) -> None:
    match = SEASON_PATTERN.fullmatch(season)
    if not match or (int(match.group(1)) + 1) % 100 != int(match.group(2)):
        raise ValueError(f"Invalid NBA season: {season!r}; expected YYYY-YY")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _reusable_partition(
    path: Path,
    metadata_path: Path,
    *,
    season: str,
    team_id: int,
    max_age_seconds: float | None = None,
) -> tuple[bool, int, bool]:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("season") != season or metadata.get("team_id") != team_id:
            return False, 0, False
        if max_age_seconds is not None:
            ingested_at = datetime.fromisoformat(str(metadata["ingested_at"]))
            if ingested_at.tzinfo is None:
                ingested_at = ingested_at.replace(tzinfo=UTC)
            if (datetime.now(UTC) - ingested_at).total_seconds() >= max_age_seconds:
                return False, 0, False
        if metadata.get("status") == "empty":
            return not path.exists() and metadata.get("rows") == 0, 0, True
        if metadata.get("status") != "complete" or not path.is_file():
            return False, 0, False
        if sha256_file(path) != metadata.get("sha256"):
            return False, 0, False
        frame = pd.read_parquet(path, columns=["SEASON", "TEAM_ID"])
        valid = (
            len(frame) == metadata.get("rows")
            and frame["SEASON"].astype(str).eq(season).all()
            and pd.to_numeric(frame["TEAM_ID"], errors="coerce").eq(team_id).all()
        )
        return bool(valid), len(frame), False
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return False, 0, False


@dataclass(frozen=True, slots=True)
class IngestionResult:
    rows: int
    fetched_partitions: int
    reused_partitions: int
    paths: list[Path]


def ingest_shots(
    seasons: list[str],
    raw_dir: Path,
    *,
    force: bool = False,
    refresh_current_after_hours: float = 24,
) -> IngestionResult:
    """Fetch one team-season partition at a time so interrupted runs resume."""
    for season in seasons:
        _validate_season(season)
    team_ids = sorted(int(team["id"]) for team in static_teams.get_teams())
    paths: list[Path] = []
    rows = fetched = reused = 0
    for season in seasons:
        for team_id in team_ids:
            partition = raw_dir / f"season={season}" / f"team_id={team_id}"
            path = partition / "shots.parquet"
            metadata_path = partition / "partition.json"
            max_age_seconds = (
                max(0.0, refresh_current_after_hours) * 3600
                if season == current_season()
                else None
            )
            reusable, partition_rows, is_empty = _reusable_partition(
                path,
                metadata_path,
                season=season,
                team_id=team_id,
                max_age_seconds=max_age_seconds,
            ) if not force else (False, 0, False)
            if reusable:
                reused += 1
                rows += partition_rows
                if not is_empty:
                    paths.append(path)
                continue
            else:
                records = api.team_shot_chart(team_id, season, persist_cache=False)
                frame = pd.DataFrame(records)
                if frame.empty:
                    path.unlink(missing_ok=True)
                    _write_json(metadata_path, {
                        "schema_version": "raw-shot-partition-v1",
                        "season": season,
                        "team_id": team_id,
                        "rows": 0,
                        "status": "empty",
                        "sha256": None,
                        "ingested_at": datetime.now(UTC).isoformat(),
                    })
                    fetched += 1
                    continue
                frame["SEASON"] = season
                frame["INGESTED_AT"] = datetime.now(UTC).isoformat()
                partition.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".parquet.tmp")
                frame.to_parquet(temporary, index=False)
                temporary.replace(path)
                _write_json(metadata_path, {
                    "schema_version": "raw-shot-partition-v1",
                    "season": season,
                    "team_id": team_id,
                    "rows": len(frame),
                    "status": "complete",
                    "sha256": sha256_file(path),
                    "ingested_at": datetime.now(UTC).isoformat(),
                })
                fetched += 1
            rows += len(frame)
            paths.append(path)

    raw_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": "raw-shots-v1",
        "seasons": seasons,
        "rows": rows,
        "partitions": len(paths),
        "fetched_partitions": fetched,
        "reused_partitions": reused,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    _write_json(raw_dir / "ingestion.json", summary)
    return IngestionResult(rows, fetched, reused, paths)


def combine_raw(partitions: list[Path], output: Path) -> Path:
    """Combine raw partitions into a validated-build input without index drift."""
    if not partitions:
        raise ValueError("No raw partitions were provided")
    frame = pd.concat((pd.read_parquet(path) for path in partitions), ignore_index=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    if output.suffix.lower() == ".parquet":
        frame.to_parquet(temporary, index=False)
    else:
        frame.to_csv(temporary, index=False)
    temporary.replace(output)
    return output
