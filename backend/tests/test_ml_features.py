from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd

from app.services import ml


def test_action_group_precedence_and_fallback():
    assert ml.action_group("Driving Dunk Shot") == "dunk"
    assert ml.action_group("Step Back Jump Shot") == "stepback"
    assert ml.action_group("Unknown Shot") == "jump"
    assert ml.action_group("") == "jump"


def test_build_features_has_stable_schema(shots, monkeypatch):
    monkeypatch.setattr(ml, "_team_abbr", lambda: {1610612761: "TOR"})
    features = ml.build_features(shots)

    assert features.columns.tolist() == ml.FEATURE_COLUMNS
    assert features.shape == (2, len(ml.FEATURE_COLUMNS))
    assert features.loc[0, "seconds_left_period"] == 690
    assert features.loc[1, "seconds_left_period"] == 3
    assert features.loc[1, "is_three"] == 1
    assert features.loc[0, "is_home"] == 1
    assert features.loc[1, "action_stepback"] == 1
    assert np.isfinite(features.to_numpy()).all()


def test_build_features_defaults_optional_source_columns(shots):
    minimal = shots.drop(columns=[
        "MINUTES_REMAINING", "SECONDS_REMAINING", "SHOT_ZONE_AREA", "TEAM_ID", "HTM",
    ])
    features = ml.build_features(minimal)
    assert (features["seconds_left_period"] == 360).all()
    assert (features["is_home"] == 0).all()
    assert features.filter(like="area_").to_numpy().sum() == 0


def test_legacy_feature_bundle_remains_compatible(shots):
    features = ml.build_features(shots, ml.FEATURE_COLUMNS_V1)
    assert features.columns.tolist() == ml.FEATURE_COLUMNS_V1


def test_delta_percentile_boundaries():
    distribution = [-0.1, 0.0, 0.1, 0.2]
    assert ml._delta_percentile(-0.2, distribution) == 0
    assert ml._delta_percentile(0.15, distribution) == 75
    assert ml._delta_percentile(0.3, distribution) == 100
    assert ml._delta_percentile(0.0, []) is None


def test_empirical_bayes_delta_shrinks_small_samples_more():
    probability = np.full(20, 0.5)
    weights = np.ones(20)
    small, small_interval = ml._shrunken_delta(0.1, probability, weights, 0.0025)
    large, large_interval = ml._shrunken_delta(
        0.1, np.full(500, 0.5), np.ones(500), 0.0025
    )
    assert 0 < small < large < 0.1
    assert small_interval[0] < small < small_interval[1]
    assert (large_interval[1] - large_interval[0]) < (
        small_interval[1] - small_interval[0]
    )


class FakeProbabilityModel:
    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        probability = np.where(features["distance"].to_numpy() < 10, 0.75, 0.25)
        return np.column_stack([1 - probability, probability])


def test_shot_quality_math_and_zone_threshold(shots, monkeypatch):
    expanded = pd.concat([shots.iloc[[0]]] * 5 + [shots.iloc[[1]]] * 5, ignore_index=True)
    detail = expanded.assign(
        SHOT_ZONE_BASIC=["Restricted Area"] * 5 + ["Above the Break 3"] * 5,
    )
    monkeypatch.setattr(ml.api, "shot_chart", lambda *_args, **_kwargs: {
        "Shot_Chart_Detail": detail.to_dict("records")
    })
    monkeypatch.setattr(ml, "_team_abbr", lambda: {1610612761: "TOR"})
    monkeypatch.setattr(ml, "load_model", lambda: {
        "model": FakeProbabilityModel(),
        "feature_columns": ml.FEATURE_COLUMNS,
        "delta_distribution": [-0.2, 0, 0.2],
        "meta": {"model_version": 99, "dataset_version": "fixture"},
    })

    result = ml.shot_quality(1, "2025-26")
    assert result["available"] is True
    assert result["shots"] == 10
    assert result["expected_efg"] == 0.562
    assert result["actual_efg"] == 0.5
    assert len(result["zones"]) == 2


def test_v3_shot_quality_reports_shrinkage_and_uncertainty(shots, monkeypatch):
    expanded = pd.concat([shots.iloc[[0]]] * 10, ignore_index=True)
    monkeypatch.setattr(ml.api, "shot_chart", lambda *_args, **_kwargs: {
        "Shot_Chart_Detail": expanded.to_dict("records")
    })
    monkeypatch.setattr(ml, "_team_abbr", lambda: {1610612761: "TOR"})
    monkeypatch.setattr(ml, "load_model", lambda: {
        "model": FakeProbabilityModel(),
        "feature_columns": ml.FEATURE_COLUMNS,
        "delta_distribution": [-0.1, 0, 0.1],
        "meta": {"model_version": 3, "prior_variance": 0.0025},
    })
    result = ml.shot_quality(1, "2025-26")
    assert abs(result["delta"]) < abs(result["raw_delta"])
    assert len(result["confidence_interval_95"]) == 2
    assert "shrunk" in result["uncertainty_note"]


def test_reload_model_does_not_deadlock(tmp_path, monkeypatch):
    path = tmp_path / "xfg.joblib"
    joblib.dump({
        "model": FakeProbabilityModel(),
        "feature_columns": ml.FEATURE_COLUMNS,
        "meta": {"model_version": 3},
    }, path)
    monkeypatch.setattr(ml, "MODEL_PATH", str(path))
    monkeypatch.setattr(ml, "get_settings", lambda: SimpleNamespace(
        artifact_base_url=None,
        artifact_expected_sha256=None,
        environment="development",
    ))
    ml._model_bundle = {"old": True}
    ml._model_load_attempted = True
    with ThreadPoolExecutor(max_workers=1) as pool:
        loaded = pool.submit(ml.reload_model).result(timeout=2)
    assert loaded["meta"]["model_version"] == 3


def test_production_model_requires_checksum_pin(tmp_path, monkeypatch):
    path = tmp_path / "xfg.joblib"
    joblib.dump({
        "model": FakeProbabilityModel(),
        "feature_columns": ml.FEATURE_COLUMNS,
        "meta": {"model_version": 3},
    }, path)
    monkeypatch.setattr(ml, "MODEL_PATH", str(path))
    monkeypatch.setattr(ml, "get_settings", lambda: SimpleNamespace(
        artifact_base_url=None,
        artifact_expected_sha256=None,
        environment="production",
    ))
    monkeypatch.setattr(ml, "_model_bundle", None)
    monkeypatch.setattr(ml, "_model_load_attempted", False)
    monkeypatch.setattr(ml, "_model_load_error", None)

    assert ml.load_model() is None
    assert ml.model_status()["error"] == "artifact_pin_required"



def test_shot_difficulty_explainer_attributes_features(shots, monkeypatch):
    import pytest
    pytest.importorskip("shap")
    from sklearn.ensemble import HistGradientBoostingClassifier

    # Train a tiny real tree model so SHAP's TreeExplainer can run.
    rng = np.random.default_rng(0)
    base = pd.concat([shots.iloc[[0]]] * 60 + [shots.iloc[[1]]] * 60, ignore_index=True)
    monkeypatch.setattr(ml, "_team_abbr", lambda: {1610612761: "TOR"})
    features = ml.build_features(base, ml.FEATURE_COLUMNS)
    target = (features["distance"].to_numpy() < 10).astype(int)
    target[rng.integers(0, len(target), 10)] ^= 1  # a little noise
    model = HistGradientBoostingClassifier(max_iter=30, random_state=0).fit(features, target)

    monkeypatch.setattr(ml.api, "shot_chart", lambda *_a, **_k: {
        "Shot_Chart_Detail": base.to_dict("records")
    })
    monkeypatch.setattr(ml, "load_model", lambda: {
        "model": model,
        "feature_columns": ml.FEATURE_COLUMNS,
        "delta_distribution": [],
        "meta": {"model_version": 2},
    })

    result = ml.shot_difficulty_explainer(1, "2025-26")
    assert result["available"] is True
    assert result["shots_explained"] > 0
    assert result["contributions"], "expected at least one feature contribution"
    top = result["contributions"][0]
    assert {"feature", "label", "mean_abs_impact", "mean_signed_impact", "direction"} <= set(top)
    assert top["mean_abs_impact"] >= result["contributions"][-1]["mean_abs_impact"]


def test_shot_difficulty_explainer_unavailable_without_model(monkeypatch):
    monkeypatch.setattr(ml, "load_model", lambda: None)
    result = ml.shot_difficulty_explainer(1, "2025-26")
    assert result["available"] is False
    assert result["reason"]
