"""Resumable league-wide shot ingestion from NBA.com."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
from nba_api.stats.static import teams as static_teams

from ..nba import api
from ..nba.seasons import current_season
from .manifest import sha256_file

SEASON_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
# The 2026-27 NBA regular season opens on October 20, 2026. Unknown seasons
# deliberately default to ingestion so a stale schedule table cannot hide an
# upstream outage or missing data after a season has begun.
REGULAR_SEASON_STARTS = {"2026-27": date(2026, 10, 20)}


def _validate_season(season: str) -> None:
    match = SEASON_PATTERN.fullmatch(season)
    if not match or (int(match.group(1)) + 1) % 100 != int(match.group(2)):
        raise ValueError(f"Invalid NBA season: {season!r}; expected YYYY-YY")


def _regular_season_started(season: str, *, today: date) -> bool:
    start = REGULAR_SEASON_STARTS.get(season)
    return start is None or today >= start


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
        recorded_rows = metadata.get("rows")
        # Fast path: if the file's size and mtime still match what we recorded
        # at ingest, trust the partition without re-hashing and re-reading it.
        # Re-hashing every partition on every resume is O(corpus) I/O; the slow
        # verified path still runs whenever the fingerprint does not match.
        recorded_size = metadata.get("size_bytes")
        recorded_mtime = metadata.get("mtime_ns")
        if recorded_size is not None and recorded_mtime is not None:
            stat = path.stat()
            if stat.st_size == recorded_size and stat.st_mtime_ns == recorded_mtime:
                return True, int(recorded_rows or 0), False
        if sha256_file(path) != metadata.get("sha256"):
            return False, 0, False
        frame = pd.read_parquet(path, columns=["SEASON", "TEAM_ID"])
        valid = (
            len(frame) == recorded_rows
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
    empty_partitions: int
    failed_partitions: list[dict[str, object]]
    deferred_seasons: list[dict[str, str]]
    paths: list[Path]


class IngestionError(RuntimeError):
    """Raised after persisting diagnostics for one or more failed partitions."""

    def __init__(self, failures: list[dict[str, object]]) -> None:
        self.failures = failures
        partitions = ", ".join(
            f"{failure['season']}/team={failure['team_id']}"
            for failure in failures[:5]
        )
        suffix = "" if len(failures) <= 5 else f" (+{len(failures) - 5} more)"
        super().__init__(f"Shot ingestion failed for {len(failures)} partition(s): {partitions}{suffix}")


def ingest_shots(
    seasons: list[str],
    raw_dir: Path,
    *,
    force: bool = False,
    refresh_current_after_hours: float = 24,
    today: date | None = None,
) -> IngestionResult:
    """Fetch one team-season partition at a time so interrupted runs resume."""
    for season in seasons:
        _validate_season(season)
    today = today or date.today()
    deferred_seasons = [
        {"season": season, "regular_season_starts": REGULAR_SEASON_STARTS[season].isoformat()}
        for season in seasons
        if season == current_season() and not _regular_season_started(season, today=today)
    ]
    deferred = {item["season"] for item in deferred_seasons}
    team_ids = sorted(int(team["id"]) for team in static_teams.get_teams())
    paths: list[Path] = []
    rows = fetched = reused = empty = 0
    failures: list[dict[str, object]] = []
    for season in seasons:
        if season in deferred:
            continue
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
                else:
                    empty += 1
                continue
            else:
                try:
                    records = api.team_shot_chart(team_id, season, persist_cache=False)
                except Exception as error:
                    failures.append({
                        "season": season,
                        "team_id": team_id,
                        "error_type": type(error).__name__,
                        "message": str(error),
                    })
                    continue
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
                    empty += 1
                    continue
                frame["SEASON"] = season
                frame["INGESTED_AT"] = datetime.now(UTC).isoformat()
                partition.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".parquet.tmp")
                frame.to_parquet(temporary, index=False)
                temporary.replace(path)
                partition_stat = path.stat()
                _write_json(metadata_path, {
                    "schema_version": "raw-shot-partition-v1",
                    "season": season,
                    "team_id": team_id,
                    "rows": len(frame),
                    "status": "complete",
                    "sha256": sha256_file(path),
                    "size_bytes": partition_stat.st_size,
                    "mtime_ns": partition_stat.st_mtime_ns,
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
        "empty_partitions": empty,
        "failed_partitions": failures,
        "deferred_seasons": deferred_seasons,
        "season_status": {
            season: (
                "regular_season_not_started"
                if season in deferred
                else "failed"
                if any(failure["season"] == season for failure in failures)
                else "complete"
                if any(path.parent.parent.name == f"season={season}" for path in paths)
                else "no_regular_season_games_yet"
                if season == current_season()
                else "no_data"
            )
            for season in seasons
        },
        "completed_at": datetime.now(UTC).isoformat(),
    }
    _write_json(raw_dir / "ingestion.json", summary)
    if failures:
        raise IngestionError(failures)
    return IngestionResult(rows, fetched, reused, empty, failures, deferred_seasons, paths)


def combine_raw(partitions: list[Path], output: Path) -> Path:
    """Combine raw partitions into a validated-build input without index drift.

    Partitions are streamed one at a time rather than concatenated into a
    single in-memory frame: the full league across several seasons is 650k+
    rows, so a single pd.concat held peak memory proportional to the entire
    corpus. For Parquet output we append each partition as a row group via a
    pyarrow ParquetWriter, keeping only one partition resident at a time. The
    CSV fallback streams append-mode writes with the header written once.
    """
    if not partitions:
        raise ValueError("No non-empty raw partitions were provided; inspect ingestion.json for details")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    is_parquet = output.suffix.lower() == ".parquet"
    try:
        if is_parquet:
            import pyarrow as pa
            import pyarrow.parquet as pq

            writer: pq.ParquetWriter | None = None
            try:
                for path in partitions:
                    table = pa.Table.from_pandas(
                        pd.read_parquet(path), preserve_index=False
                    )
                    if writer is None:
                        writer = pq.ParquetWriter(temporary, table.schema)
                    else:
                        # Align later partitions to the first partition's schema
                        # so an incidental column-order/type drift cannot abort
                        # the whole combine.
                        table = table.cast(writer.schema, safe=False)
                    writer.write_table(table)
            finally:
                if writer is not None:
                    writer.close()
        else:
            header_written = False
            with open(temporary, "w", encoding="utf-8", newline="") as handle:
                for path in partitions:
                    chunk = pd.read_parquet(path)
                    chunk.to_csv(handle, index=False, header=not header_written)
                    header_written = True
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return output
