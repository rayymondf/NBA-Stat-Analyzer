from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.pipeline import DatasetManifest, DatasetValidationError, build_parquet, validate_shots
from app.pipeline.artifacts import artifact_index, publish_local
from app.pipeline.cli import main
from app.pipeline.dataset import query_parquet
from app.pipeline.ingest import combine_raw, ingest_shots


def _source(rows: int = 4) -> pd.DataFrame:
    return pd.DataFrame({
        "GAME_ID": ["0022500001"] * rows,
        "GAME_EVENT_ID": list(range(rows)),
        "PLAYER_ID": [1] * rows,
        "TEAM_ID": [1610612761] * rows,
        "PLAYER_NAME": ["Player One"] * rows,
        "TEAM_NAME": ["Toronto Raptors"] * rows,
        "HTM": ["TOR"] * rows,
        "SEASON": ["2025-26"] * rows,
        "GAME_DATE": [20260119] * rows,
        "PERIOD": [1] * rows,
        "MINUTES_REMAINING": [11] * rows,
        "SECONDS_REMAINING": list(range(rows)),
        "SHOT_ZONE_BASIC": ["Restricted Area"] * rows,
        "SHOT_ZONE_AREA": ["Center(C)"] * rows,
        "ACTION_TYPE": ["Layup Shot"] * rows,
        "SHOT_TYPE": ["2PT Field Goal"] * rows,
        "SHOT_DISTANCE": [1] * rows,
        "LOC_X": [0] * rows,
        "LOC_Y": [10] * rows,
        "SHOT_MADE_FLAG": ["Made", "Missed"] * (rows // 2),
    })


def test_validate_and_reject_invalid_data():
    report = validate_shots(_source())
    assert report.rows == 4
    assert report.made_rate == 0.5

    invalid = _source().drop(columns=["LOC_X"])
    with pytest.raises(DatasetValidationError, match="LOC_X"):
        validate_shots(invalid)

    invalid = _source()
    invalid.loc[0, "PERIOD"] = 0
    invalid.loc[1, "SHOT_MADE_FLAG"] = "maybe"
    with pytest.raises(DatasetValidationError) as error:
        validate_shots(invalid)
    assert len(error.value.errors) == 2

    invalid = _source()
    invalid.loc[0, "SEASON"] = "2025-99"
    invalid.loc[1, "GAME_ID"] = "../game"
    invalid.loc[2, "PLAYER_ID"] = 0
    invalid.loc[3, "HTM"] = "toronto"
    with pytest.raises(DatasetValidationError) as identity_error:
        validate_shots(invalid)
    assert {"SEASON", "GAME_ID", "PLAYER_ID", "HTM"}.issubset(
        {message.split()[0] for message in identity_error.value.errors}
    )


@pytest.mark.parametrize("target", [0.5, 1000, float("inf"), "maybe"])
def test_invalid_targets_use_domain_validation_error(target):
    invalid = _source()
    invalid["SHOT_MADE_FLAG"] = invalid["SHOT_MADE_FLAG"].astype(object)
    invalid.loc[0, "SHOT_MADE_FLAG"] = target
    with pytest.raises(DatasetValidationError, match="SHOT_MADE_FLAG"):
        validate_shots(invalid)


def test_build_partitioned_parquet_manifest_and_query(tmp_path: Path):
    source = tmp_path / "shots.csv"
    _source().to_csv(source, index=False)
    output = tmp_path / "processed" / "shots"
    manifest_path = tmp_path / "manifests" / "shots.json"

    manifest = build_parquet(source, output, manifest_path=manifest_path)

    assert manifest.rows == 4
    assert pd.read_parquet(output)["GAME_ID"].iloc[0] == "0022500001"
    assert manifest.dataset_version.startswith("shots-v1-")
    assert list(output.rglob("*.parquet"))
    DatasetManifest.read(manifest_path).verify(source)
    DatasetManifest.read(manifest_path).verify_processed(output)
    result = query_parquet(output, "SELECT SEASON, count(*) AS shots FROM shots GROUP BY 1")
    assert result.to_dict("records") == [{"SEASON": "2025-26", "shots": 4}]

    source.write_text(source.read_text() + "\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        manifest.verify(source)
    with pytest.raises(ValueError, match="Only SELECT"):
        query_parquet(output, "DELETE FROM shots")
    with pytest.raises(ValueError, match="one SQL statement"):
        query_parquet(output, "SELECT 1; DELETE FROM shots")
    with pytest.raises(ValueError, match="External readers"):
        query_parquet(output, "SELECT * FROM read_csv_auto('secret.csv')")

    parquet_source = tmp_path / "combined.parquet"
    _source().to_parquet(parquet_source, index=False)
    second = build_parquet(parquet_source, tmp_path / "processed" / "parquet-source")
    assert second.rows == 4


def test_local_artifact_release_is_content_addressed(tmp_path: Path):
    model = tmp_path / "xfg.joblib"
    model.write_bytes(b"model bytes")
    index = artifact_index(model, version="v3", metadata={"dataset_version": "test"})
    assert len(index["sha256"]) == 64

    release = publish_local(
        model, tmp_path / "artifacts", version="v3", metadata={"dataset_version": "test"}
    )
    saved = json.loads((release / "index.json").read_text())
    assert saved["sha256"] == index["sha256"]
    assert (release / "xfg.joblib").read_bytes() == b"model bytes"
    with pytest.raises(FileExistsError, match="already exists"):
        publish_local(
            model, tmp_path / "artifacts", version="v3", metadata={"dataset_version": "test"}
        )


def test_pipeline_cli_validate_and_verify(tmp_path: Path, capsys):
    source = tmp_path / "shots.csv"
    _source().to_csv(source, index=False)
    manifest = DatasetManifest.create(
        source,
        rows=4,
        seasons=["2025-26"],
        columns=_source().columns.tolist(),
        source="fixture",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest.write(manifest_path)

    main(["validate", str(source)])
    assert '"rows": 4' in capsys.readouterr().out
    main(["verify", str(source), str(manifest_path)])
    assert "verified" in capsys.readouterr().out


def test_ingestion_is_partitioned_and_resumable(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.ingest.static_teams.get_teams",
        lambda: [{"id": 2}, {"id": 1}],
    )
    calls: list[tuple[int, str]] = []

    def fake_chart(team_id: int, season: str, *, persist_cache: bool = True):
        assert persist_cache is False
        calls.append((team_id, season))
        frame = _source(2).assign(TEAM_ID=team_id)
        return frame.to_dict("records")

    monkeypatch.setattr("app.pipeline.ingest.api.team_shot_chart", fake_chart)
    raw = tmp_path / "raw"
    first = ingest_shots(["2025-26"], raw)
    second = ingest_shots(["2025-26"], raw)

    assert first.fetched_partitions == 2
    assert second.reused_partitions == 2
    assert calls == [(1, "2025-26"), (2, "2025-26")]
    combined = combine_raw(first.paths, tmp_path / "combined.parquet")
    assert len(pd.read_parquet(combined)) == 4

    # A tampered partition must be fetched again rather than silently reused.
    first.paths[0].write_bytes(b"corrupt")
    third = ingest_shots(["2025-26"], raw)
    assert third.fetched_partitions == 1
    assert len(calls) == 3


def test_ingestion_rejects_path_like_or_impossible_seasons(tmp_path: Path):
    with pytest.raises(ValueError, match="Invalid NBA season"):
        ingest_shots(["../2025-26"], tmp_path)
    with pytest.raises(ValueError, match="Invalid NBA season"):
        ingest_shots(["2025-29"], tmp_path)


def test_current_season_partitions_expire_without_refetching_closed_seasons(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr("app.pipeline.ingest.current_season", lambda: "2025-26")
    monkeypatch.setattr(
        "app.pipeline.ingest.static_teams.get_teams",
        lambda: [{"id": 1}],
    )
    calls: list[str] = []

    def fake_chart(team_id: int, season: str, *, persist_cache: bool = True):
        calls.append(season)
        return _source(2).assign(TEAM_ID=team_id).to_dict("records")

    monkeypatch.setattr("app.pipeline.ingest.api.team_shot_chart", fake_chart)
    raw = tmp_path / "raw"
    ingest_shots(["2025-26", "2024-25"], raw)
    ingest_shots(["2025-26", "2024-25"], raw)
    assert calls == ["2025-26", "2024-25"]

    current_metadata = raw / "season=2025-26" / "team_id=1" / "partition.json"
    metadata = json.loads(current_metadata.read_text())
    metadata["ingested_at"] = "2000-01-01T00:00:00+00:00"
    current_metadata.write_text(json.dumps(metadata))
    ingest_shots(["2025-26", "2024-25"], raw)
    assert calls == ["2025-26", "2024-25", "2025-26"]
