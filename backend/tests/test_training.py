from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from app.pipeline.training import (
    classification_metrics,
    cluster_bootstrap_intervals,
    log_mlflow,
    promote_candidate,
    save_candidate,
    temporal_split,
    train_xfg,
)


def _training_data(games: int = 20, shots_per_game: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = games * shots_per_game
    game = np.repeat(np.arange(games), shots_per_game)
    distance = rng.integers(0, 34, rows)
    is_three = distance >= 23
    probability = np.clip(0.72 - distance * 0.012 - is_three * 0.04, 0.12, 0.8)
    made = rng.binomial(1, probability)
    dates = pd.date_range("2024-10-01", periods=games, freq="D")
    return pd.DataFrame({
        "PLAYER_ID": np.tile(np.arange(1, 7), rows // 6 + 1)[:rows],
        "PLAYER_NAME": ["Fixture Player"] * rows,
        "TEAM_ID": [1610612761] * rows,
        "SEASON": np.where(game < games // 2, "2024-25", "2025-26"),
        "GAME_ID": [f"00225{value:05d}" for value in game],
        "GAME_DATE": [int(dates[value].strftime("%Y%m%d")) for value in game],
        "PERIOD": rng.integers(1, 5, rows),
        "MINUTES_REMAINING": rng.integers(0, 12, rows),
        "SECONDS_REMAINING": rng.integers(0, 60, rows),
        "SHOT_ZONE_BASIC": np.where(is_three, "Above the Break 3", "Restricted Area"),
        "SHOT_ZONE_AREA": ["Center(C)"] * rows,
        "ACTION_TYPE": np.where(is_three, "Jump Shot", "Driving Layup Shot"),
        "SHOT_TYPE": np.where(is_three, "3PT Field Goal", "2PT Field Goal"),
        "SHOT_DISTANCE": distance,
        "LOC_X": rng.integers(-250, 251, rows),
        "LOC_Y": rng.integers(0, 350, rows),
        "HTM": ["TOR"] * rows,
        "SHOT_MADE_FLAG": made,
    })


def test_temporal_split_keeps_games_whole_and_ordered():
    frame = _training_data()
    split = temporal_split(frame)
    train_games = set(frame.iloc[split.train]["GAME_ID"])
    tuning_games = set(frame.iloc[split.tuning]["GAME_ID"])
    calibration_games = set(frame.iloc[split.calibration]["GAME_ID"])
    test_games = set(frame.iloc[split.test]["GAME_ID"])
    assert not train_games & tuning_games
    assert not train_games & test_games
    assert not tuning_games & calibration_games
    assert not tuning_games & test_games
    assert not calibration_games & test_games
    assert (
        split.train_through < split.tuning_from <= split.tuning_through
        < split.calibration_from <= split.calibration_through
        < split.test_from <= split.test_through
    )


def test_temporal_split_never_splits_same_date_games():
    frame = _training_data(games=20, shots_per_game=30)
    duplicate_date = frame["GAME_ID"] == "0022500001"
    frame.loc[duplicate_date, "GAME_DATE"] = frame.loc[
        frame["GAME_ID"] == "0022500000", "GAME_DATE"
    ].iloc[0]
    split = temporal_split(frame)
    fold_by_index = {}
    for fold, indices in (
        ("train", split.train), ("tuning", split.tuning),
        ("calibration", split.calibration), ("test", split.test),
    ):
        for date in frame.iloc[indices]["GAME_DATE"].unique():
            assert date not in fold_by_index
            fold_by_index[date] = fold


def test_metrics_and_clustered_confidence_intervals():
    y = np.array([0, 1, 0, 1, 0, 1, 1, 0])
    probability = np.array([0.1, 0.8, 0.3, 0.7, 0.2, 0.9, 0.6, 0.4])
    groups = np.array([1, 1, 2, 2, 3, 3, 4, 4])
    metrics = classification_metrics(y, probability)
    intervals = cluster_bootstrap_intervals(y, probability, groups, iterations=20)
    assert metrics["brier"] < 0.2
    assert intervals["brier"]["lower"] <= metrics["brier"] <= intervals["brier"]["upper"]


def test_fractional_target_is_rejected(monkeypatch):
    frame = _training_data()
    frame["SHOT_MADE_FLAG"] = frame["SHOT_MADE_FLAG"].astype(float)
    frame.loc[0, "SHOT_MADE_FLAG"] = 0.9
    monkeypatch.setattr("app.services.ml._team_abbr", lambda: {1610612761: "TOR"})
    with pytest.raises(ValueError, match="binary"):
        train_xfg(frame, dataset_version="fixture", bootstrap_iterations=2)


def test_xfg_v3_training_evaluation_and_gated_promotion(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.services.ml._team_abbr", lambda: {1610612761: "TOR"})
    result = train_xfg(
        _training_data(),
        dataset_version="shots-v1-fixture",
        bootstrap_iterations=20,
    )
    assert result.bundle["meta"]["model_version"] == 3
    assert result.evaluation["split"]["test"] == 90
    assert len(result.evaluation["candidates"]) == 3
    assert {"brier", "auc", "ece"}.issubset(result.evaluation["test"])
    assert result.evaluation["feature_importance"]

    candidate = tmp_path / "candidate.joblib"
    report = tmp_path / "evaluation.json"
    save_candidate(result, candidate, report)
    assert candidate.exists() and report.exists()

    result.bundle["meta"]["promotion"]["passed"] = False
    joblib.dump(result.bundle, candidate)
    with pytest.raises(RuntimeError, match="checksum"):
        promote_candidate(
            candidate,
            tmp_path / "production.joblib",
            force=True,
            expected_sha256="0" * 64,
        )
    with pytest.raises(RuntimeError, match="quality gate"):
        promote_candidate(candidate, tmp_path / "production.joblib")
    checksum = promote_candidate(candidate, tmp_path / "production.joblib", force=True)
    assert len(checksum) == 64



def test_log_mlflow_records_run_metrics_and_registers_on_gate_pass(tmp_path, monkeypatch):
    mlflow = pytest.importorskip("mlflow")
    monkeypatch.setattr("app.services.ml._team_abbr", lambda: {1610612761: "TOR"})
    # Isolate tracking + registry to a temp file store so the test is hermetic.
    tracking_uri = (tmp_path / "mlruns").as_uri()
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)

    result = train_xfg(
        _training_data(),
        dataset_version="shots-v1-fixture",
        bootstrap_iterations=20,
    )
    # Force the gate outcome so we deterministically exercise registration.
    result.promoted = True

    logged = log_mlflow(result, experiment="nba-xfg-test", registered_model_name="xfg-test")
    assert logged is True

    client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
    experiment = client.get_experiment_by_name("nba-xfg-test")
    assert experiment is not None
    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 1
    run = runs[0]

    # Params and tags captured the run identity.
    assert run.data.params["dataset_version"] == "shots-v1-fixture"
    assert run.data.tags["model_version"] == "3"
    assert run.data.tags["promotion_gate"] == "passed"

    # Final test metrics plus per-candidate tuning metrics were logged.
    assert "brier" in run.data.metrics
    assert any(key.startswith("tuning_") for key in run.data.metrics)
    assert any(key.startswith("baseline_") for key in run.data.metrics)

    # Artifacts for offline inspection were attached.
    artifacts = {item.path for item in client.list_artifacts(run.info.run_id)}
    assert {"evaluation.json", "calibration.json", "drift.json", "promotion.json"} <= artifacts

    # A gate-passing candidate was registered in the local model registry.
    registered = {model.name for model in client.search_registered_models()}
    assert "xfg-test" in registered
    assert run.data.tags.get("registered_model_version") is not None


def test_log_mlflow_skips_registration_when_gate_fails(tmp_path, monkeypatch):
    mlflow = pytest.importorskip("mlflow")
    monkeypatch.setattr("app.services.ml._team_abbr", lambda: {1610612761: "TOR"})
    tracking_uri = (tmp_path / "mlruns").as_uri()
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)

    result = train_xfg(
        _training_data(),
        dataset_version="shots-v1-fixture",
        bootstrap_iterations=20,
    )
    result.promoted = False

    assert log_mlflow(result, experiment="nba-xfg-fail", registered_model_name="xfg-fail") is True
    client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
    # Run is recorded for history, but nothing is registered when the gate fails.
    registered = {model.name for model in client.search_registered_models()}
    assert "xfg-fail" not in registered
