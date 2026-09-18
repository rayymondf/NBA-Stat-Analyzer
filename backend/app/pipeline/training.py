"""Leakage-resistant training, evaluation, calibration, and promotion for xFG v3."""

from __future__ import annotations

import json
import math
import os
import platform
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..services.ml import FEATURE_COLUMNS, build_features
from .manifest import sha256_file

RANDOM_SEED = 42


def _runtime_versions() -> dict[str, Any]:
    packages: dict[str, str] = {}
    for package in ("numpy", "pandas", "scikit-learn", "joblib", "xgboost"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            continue
    return {"python": platform.python_version(), "packages": packages}


@dataclass(frozen=True, slots=True)
class TemporalSplit:
    train: np.ndarray
    tuning: np.ndarray
    calibration: np.ndarray
    test: np.ndarray
    train_through: str
    tuning_from: str
    tuning_through: str
    calibration_from: str
    calibration_through: str
    test_from: str
    test_through: str


@dataclass(frozen=True, slots=True)
class CandidateScore:
    name: str
    validation: dict[str, float]
    params: dict[str, Any]


@dataclass(slots=True)
class TrainingResult:
    bundle: dict[str, Any]
    evaluation: dict[str, Any]
    promoted: bool
    candidate_path: Path | None = None


def load_training_frame(path: Path) -> pd.DataFrame:
    if path.is_dir() or path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False)


def _target(frame: pd.DataFrame) -> np.ndarray:
    values = frame["SHOT_MADE_FLAG"].replace(
        {"Made": 1, "Missed": 0, "made": 1, "missed": 0}
    )
    numeric = pd.to_numeric(values, errors="raise").to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or not np.isin(numeric, [0.0, 1.0]).all():
        raise ValueError("SHOT_MADE_FLAG must be binary")
    return numeric.astype(int)


def temporal_split(frame: pd.DataFrame, *, train_fraction: float = 0.60) -> TemporalSplit:
    """Split whole date/game groups chronologically; a game can never cross folds."""
    if not 0.5 <= train_fraction <= 0.7:
        raise ValueError("train_fraction must be between 0.5 and 0.7")
    dates = pd.to_datetime(frame["GAME_DATE"].astype(str), format="%Y%m%d", errors="raise")
    group = dates.dt.strftime("%Y%m%d")
    ordered = pd.Series(sorted(group.unique()))
    if len(ordered) < 10:
        raise ValueError("At least ten distinct game dates are required for temporal evaluation")
    train_end = max(1, int(len(ordered) * train_fraction))
    tuning_end = max(train_end + 1, int(len(ordered) * 0.75))
    calibration_end = max(tuning_end + 1, int(len(ordered) * 0.85))
    calibration_end = min(calibration_end, len(ordered) - 1)
    train_groups = set(ordered.iloc[:train_end])
    tuning_groups = set(ordered.iloc[train_end:tuning_end])
    calibration_groups = set(ordered.iloc[tuning_end:calibration_end])
    test_groups = set(ordered.iloc[calibration_end:])
    group_values = group.to_numpy()

    def indices(values: set[str]) -> np.ndarray:
        return np.flatnonzero(np.isin(group_values, list(values)))

    return TemporalSplit(
        train=indices(train_groups),
        tuning=indices(tuning_groups),
        calibration=indices(calibration_groups),
        test=indices(test_groups),
        train_through=pd.Timestamp(ordered.iloc[train_end - 1]).date().isoformat(),
        tuning_from=pd.Timestamp(ordered.iloc[train_end]).date().isoformat(),
        tuning_through=pd.Timestamp(ordered.iloc[tuning_end - 1]).date().isoformat(),
        calibration_from=pd.Timestamp(ordered.iloc[tuning_end]).date().isoformat(),
        calibration_through=pd.Timestamp(ordered.iloc[calibration_end - 1]).date().isoformat(),
        test_from=pd.Timestamp(ordered.iloc[calibration_end]).date().isoformat(),
        test_through=pd.Timestamp(ordered.iloc[-1]).date().isoformat(),
    )


def expected_calibration_error(
    y: np.ndarray,
    probability: np.ndarray,
    bins: int = 15,
    *,
    sample_weight: np.ndarray | None = None,
) -> float:
    boundaries = np.linspace(0, 1, bins + 1)
    bucket = np.minimum(np.digitize(probability, boundaries[1:-1]), bins - 1)
    weights = np.ones(len(y), dtype=float) if sample_weight is None else sample_weight
    total_weight = float(weights.sum())
    if total_weight <= 0:
        raise ValueError("sample weights must have positive total weight")
    error = 0.0
    for index in range(bins):
        mask = bucket == index
        bucket_weight = float(weights[mask].sum())
        if bucket_weight > 0:
            predicted = float(np.average(probability[mask], weights=weights[mask]))
            actual = float(np.average(y[mask], weights=weights[mask]))
            error += bucket_weight / total_weight * abs(predicted - actual)
    return error


def classification_metrics(
    y: np.ndarray,
    probability: np.ndarray,
    *,
    sample_weight: np.ndarray | None = None,
) -> dict[str, float]:
    return {
        "brier": float(brier_score_loss(y, probability, sample_weight=sample_weight)),
        "log_loss": float(log_loss(y, probability, labels=[0, 1], sample_weight=sample_weight)),
        "auc": float(roc_auc_score(y, probability, sample_weight=sample_weight)),
        "average_precision": float(
            average_precision_score(y, probability, sample_weight=sample_weight)
        ),
        "ece": float(
            expected_calibration_error(y, probability, sample_weight=sample_weight)
        ),
    }


def _confidence_interval(values: list[float]) -> dict[str, float]:
    return {
        "lower": float(np.quantile(values, 0.025)),
        "upper": float(np.quantile(values, 0.975)),
    }


def cluster_bootstrap_intervals(
    y: np.ndarray,
    probability: np.ndarray,
    groups: np.ndarray,
    *,
    iterations: int = 300,
    seed: int = RANDOM_SEED,
) -> dict[str, dict[str, float]]:
    """Bootstrap whole games, preserving within-game correlation."""
    unique = np.unique(groups)
    if len(unique) < 2 or iterations < 2:
        return {}
    rng = np.random.default_rng(seed)
    estimates: dict[str, list[float]] = {key: [] for key in classification_metrics(y, probability)}
    for _ in range(iterations):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        sampled_groups, multiplicity = np.unique(sampled, return_counts=True)
        weights = np.zeros(len(y), dtype=float)
        for group, count in zip(sampled_groups, multiplicity, strict=True):
            weights[groups == group] = count
        included = weights > 0
        if np.unique(y[included]).size < 2:
            continue
        metrics = classification_metrics(y, probability, sample_weight=weights)
        for key, value in metrics.items():
            estimates[key].append(value)
    return {key: _confidence_interval(values) for key, values in estimates.items() if values}


def calibration_curve_rows(
    y: np.ndarray, probability: np.ndarray, *, bins: int = 10
) -> list[dict[str, float | int | str]]:
    quantiles = np.unique(np.quantile(probability, np.linspace(0, 1, bins + 1)))
    if len(quantiles) < 2:
        return []
    bucket = np.clip(np.digitize(probability, quantiles[1:-1]), 0, len(quantiles) - 2)
    rows: list[dict[str, float | int | str]] = []
    for index in range(len(quantiles) - 1):
        mask = bucket == index
        if mask.any():
            rows.append({
                "bucket": f"Q{index + 1}",
                "predicted": round(float(probability[mask].mean()), 4),
                "actual": round(float(y[mask].mean()), 4),
                "shots": int(mask.sum()),
            })
    return rows


def population_stability_index(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population stability index using training-derived quantile boundaries."""
    boundaries = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(boundaries) < 3:
        return 0.0
    expected_bucket = np.clip(np.digitize(expected, boundaries[1:-1]), 0, len(boundaries) - 2)
    actual_bucket = np.clip(np.digitize(actual, boundaries[1:-1]), 0, len(boundaries) - 2)
    score = 0.0
    for index in range(len(boundaries) - 1):
        expected_share = max(float((expected_bucket == index).mean()), 1e-6)
        actual_share = max(float((actual_bucket == index).mean()), 1e-6)
        score += (actual_share - expected_share) * math.log(actual_share / expected_share)
    return float(score)


def drift_report(train: pd.DataFrame, test: pd.DataFrame) -> list[dict[str, float | str]]:
    result = []
    for feature in ("distance", "angle", "seconds_left_period", "is_three", "is_home"):
        score = population_stability_index(
            train[feature].to_numpy(), test[feature].to_numpy()
        )
        status = "alert" if score >= 0.25 else "watch" if score >= 0.1 else "stable"
        result.append({"feature": feature, "psi": score, "status": status})
    return result


def sliced_metrics(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    y: np.ndarray,
    probability: np.ndarray,
) -> list[dict[str, Any]]:
    distance = features["distance"].to_numpy()
    seconds = features["seconds_left_period"].to_numpy()
    masks: dict[str, np.ndarray] = {
        "all": np.ones(len(frame), dtype=bool),
        "rim_0_4ft": distance < 4,
        "midrange_10_24ft": (distance >= 10) & (distance < 24),
        "three_point": features["is_three"].to_numpy() == 1,
        "heave_30ft_last_6s": (distance >= 30) & (seconds <= 6),
        "home": features["is_home"].to_numpy() == 1,
        "away": features["is_home"].to_numpy() == 0,
    }
    for season in sorted(frame["SEASON"].astype(str).unique()):
        masks[f"season_{season}"] = frame["SEASON"].astype(str).to_numpy() == season
    result = []
    for name, mask in masks.items():
        if mask.sum() < 20 or np.unique(y[mask]).size < 2:
            continue
        result.append({"slice": name, "shots": int(mask.sum()), **classification_metrics(
            y[mask], probability[mask]
        )})
    return result


def context_calibration_rows(
    features: pd.DataFrame,
    y: np.ndarray,
    probability: np.ndarray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    distance = features["distance"].to_numpy()
    seconds = features["seconds_left_period"].to_numpy()

    def row(label: str, mask: np.ndarray) -> dict[str, Any] | None:
        if mask.sum() < 20:
            return None
        return {
            "bucket": label,
            "predicted": round(float(probability[mask].mean()), 4),
            "actual": round(float(y[mask].mean()), 4),
            "shots": int(mask.sum()),
        }

    distance_rows = [
        row(f"{lower}-{upper} ft", (distance >= lower) & (distance < upper))
        for lower, upper in ((0, 4), (4, 10), (10, 16), (16, 24), (24, 31), (31, 100))
    ]
    heave = (distance >= 30) & (seconds <= 6)
    time_rows = [row("Last 6s, 30+ ft", heave), row("All other shots", ~heave)]
    return (
        [item for item in distance_rows if item is not None],
        [item for item in time_rows if item is not None],
    )


def _candidate_models(include_xgboost: bool) -> list[tuple[str, Any, dict[str, Any]]]:
    candidates: list[tuple[str, Any, dict[str, Any]]] = [
        (
            "logistic",
            make_pipeline(
                StandardScaler(),
                LogisticRegression(C=1.0, max_iter=500, random_state=RANDOM_SEED),
            ),
            {"C": 1.0},
        ),
        (
            "hist_gradient_boosting",
            HistGradientBoostingClassifier(
                learning_rate=0.08,
                max_iter=300,
                max_leaf_nodes=31,
                min_samples_leaf=50,
                early_stopping=False,
                random_state=RANDOM_SEED,
            ),
            {"learning_rate": 0.08, "max_leaf_nodes": 31, "min_samples_leaf": 50},
        ),
        (
            "hist_gradient_boosting_regularized",
            HistGradientBoostingClassifier(
                learning_rate=0.05,
                max_iter=400,
                max_leaf_nodes=63,
                min_samples_leaf=100,
                l2_regularization=1.0,
                early_stopping=False,
                random_state=RANDOM_SEED,
            ),
            {
                "learning_rate": 0.05,
                "max_leaf_nodes": 63,
                "min_samples_leaf": 100,
                "l2_regularization": 1.0,
            },
        ),
    ]
    if include_xgboost:
        try:
            from xgboost import XGBClassifier
        except ImportError as exc:
            raise RuntimeError("Install the 'ml' extra to enable XGBoost") from exc
        candidates.append((
            "xgboost",
            XGBClassifier(
                n_estimators=700,
                learning_rate=0.05,
                max_depth=7,
                min_child_weight=20,
                subsample=0.8,
                colsample_bytree=0.8,
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=RANDOM_SEED,
                n_jobs=-1,
            ),
            {"n_estimators": 700, "learning_rate": 0.05, "max_depth": 7},
        ))
    return candidates


def _player_distribution(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    y: np.ndarray,
    probability: np.ndarray,
    *,
    minimum_shots: int = 100,
) -> tuple[list[float], float, float, float, list[dict[str, Any]]]:
    weights = 1 + 0.5 * features["is_three"].to_numpy()
    grouping = (
        frame["PLAYER_ID"].astype(str)
        if "PLAYER_ID" in frame.columns
        else frame.get("PLAYER_NAME", pd.Series("unknown", index=frame.index)).astype(str)
    )
    table = pd.DataFrame({
        "player": grouping.to_numpy(),
        "season": frame["SEASON"].astype(str).to_numpy(),
        "actual": y * weights,
        "expected": probability * weights,
        "variance": weights**2 * probability * (1 - probability),
    })
    rows: list[dict[str, Any]] = []
    for (player, season), group in table.groupby(["player", "season"]):
        if len(group) < minimum_shots:
            continue
        raw = float((group["actual"] - group["expected"]).mean())
        measurement = float(group["variance"].sum() / len(group) ** 2)
        rows.append({
            "player": player,
            "season": season,
            "shots": len(group),
            "raw_delta": raw,
            "measurement_variance": measurement,
        })
    if not rows:
        return [], 0.0, 0.0025, 0.25, []
    raw_deltas = np.array([row["raw_delta"] for row in rows], dtype=float)
    measurement_variances = np.array(
        [row["measurement_variance"] for row in rows], dtype=float
    )
    prior_mean = float(np.mean(raw_deltas))
    between_variance = (
        float(np.var(raw_deltas, ddof=1)) if len(raw_deltas) >= 2 else 0.0025
    )
    prior_variance = max(between_variance - float(measurement_variances.mean()), 0.0001)
    if not math.isfinite(prior_variance):
        prior_variance = 0.0025
    residual_variance = float(np.mean(probability * (1 - probability)))
    distribution = []
    for row in rows:
        measurement_variance = max(row["measurement_variance"], 1e-9)
        posterior_variance = 1 / (
            1 / prior_variance + 1 / measurement_variance
        )
        posterior = posterior_variance * (
            prior_mean / prior_variance
            + row["raw_delta"] / measurement_variance
        )
        row["shrunk_delta"] = posterior
        row["ci_95"] = [
            posterior - 1.96 * math.sqrt(posterior_variance),
            posterior + 1.96 * math.sqrt(posterior_variance),
        ]
        distribution.append(round(float(posterior), 6))
    return sorted(distribution), prior_mean, prior_variance, residual_variance, rows


def _feature_importance(
    model: Any,
    features: pd.DataFrame,
    y: np.ndarray,
) -> list[dict[str, float | str]]:
    if len(features) > 10_000:
        rng = np.random.default_rng(RANDOM_SEED)
        index = rng.choice(len(features), 10_000, replace=False)
        features = features.iloc[index]
        y = y[index]
    importance = permutation_importance(
        model,
        features,
        y,
        scoring="neg_brier_score",
        n_repeats=3,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    order = np.argsort(importance.importances_mean)[::-1][:15]
    return [
        {"feature": str(features.columns[index]), "importance": float(
            importance.importances_mean[index]
        )}
        for index in order
    ]


def _safe_incumbent_probability(
    bundle: dict[str, Any] | None,
    frame: pd.DataFrame,
    *,
    test_from: str,
) -> np.ndarray | None:
    if not bundle or "model" not in bundle:
        return None
    training_through = bundle.get("meta", {}).get("training_data_through")
    if not training_through or str(training_through) >= test_from:
        return None
    try:
        columns = bundle.get("feature_columns") or FEATURE_COLUMNS
        return bundle["model"].predict_proba(build_features(frame, columns))[:, 1]
    except (KeyError, ValueError, TypeError):
        return None


def rolling_oof_predictions(
    model: Any,
    frame: pd.DataFrame,
    features: pd.DataFrame,
    y: np.ndarray,
    *,
    before: str,
    folds: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate expanding-window predictions without touching the final test period."""
    dates = pd.to_datetime(frame["GAME_DATE"].astype(str), format="%Y%m%d", errors="raise")
    eligible_dates = np.array(sorted(dates[dates < pd.Timestamp(before)].dt.normalize().unique()))
    warmup = max(1, len(eligible_dates) // 2)
    prediction_dates = eligible_dates[warmup:]
    if len(prediction_dates) < folds:
        return np.array([], dtype=int), np.array([], dtype=float)
    predicted_indices: list[np.ndarray] = []
    predicted_probabilities: list[np.ndarray] = []
    for fold_dates in np.array_split(prediction_dates, folds):
        if not len(fold_dates):
            continue
        fold_start = pd.Timestamp(fold_dates[0])
        fit_index = np.flatnonzero((dates < fold_start).to_numpy())
        predict_index = np.flatnonzero(dates.dt.normalize().isin(fold_dates).to_numpy())
        if not len(fit_index) or not len(predict_index) or np.unique(y[fit_index]).size < 2:
            continue
        estimator = clone(model)
        estimator.fit(features.iloc[fit_index], y[fit_index])
        predicted_indices.append(predict_index)
        predicted_probabilities.append(estimator.predict_proba(features.iloc[predict_index])[:, 1])
    if not predicted_indices:
        return np.array([], dtype=int), np.array([], dtype=float)
    return np.concatenate(predicted_indices), np.concatenate(predicted_probabilities)


def paired_bootstrap_deltas(
    y: np.ndarray,
    candidate: np.ndarray,
    baseline: np.ndarray,
    groups: np.ndarray,
    *,
    iterations: int,
) -> dict[str, dict[str, float]]:
    unique = np.unique(groups)
    rng = np.random.default_rng(RANDOM_SEED)
    estimates: dict[str, list[float]] = {key: [] for key in classification_metrics(y, candidate)}
    for _ in range(iterations):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        sampled_groups, multiplicity = np.unique(sampled, return_counts=True)
        weights = np.zeros(len(y), dtype=float)
        for group, count in zip(sampled_groups, multiplicity, strict=True):
            weights[groups == group] = count
        included = weights > 0
        if np.unique(y[included]).size < 2:
            continue
        candidate_metrics = classification_metrics(y, candidate, sample_weight=weights)
        baseline_metrics = classification_metrics(y, baseline, sample_weight=weights)
        for metric in estimates:
            estimates[metric].append(candidate_metrics[metric] - baseline_metrics[metric])
    return {metric: _confidence_interval(values) for metric, values in estimates.items() if values}


def slice_promotion_checks(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    y: np.ndarray,
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> list[dict[str, Any]]:
    distance = features["distance"].to_numpy()
    seconds = features["seconds_left_period"].to_numpy()
    masks = {
        "rim_0_4ft": distance < 4,
        "three_point": features["is_three"].to_numpy() == 1,
        "heave_30ft_last_6s": (distance >= 30) & (seconds <= 6),
        "home": features["is_home"].to_numpy() == 1,
        "away": features["is_home"].to_numpy() == 0,
    }
    rows = []
    for name, mask in masks.items():
        if mask.sum() < 100 or np.unique(y[mask]).size < 2:
            rows.append({"slice": name, "shots": int(mask.sum()), "status": "insufficient"})
            continue
        candidate_metrics = classification_metrics(y[mask], candidate[mask])
        baseline_metrics = classification_metrics(y[mask], baseline[mask])
        passed = (
            candidate_metrics["brier"] <= baseline_metrics["brier"] + 0.005
            and candidate_metrics["ece"] <= baseline_metrics["ece"] + 0.015
        )
        rows.append({
            "slice": name,
            "shots": int(mask.sum()),
            "status": "passed" if passed else "failed",
            "candidate": candidate_metrics,
            "baseline": baseline_metrics,
        })
    return rows


def train_xfg(
    frame: pd.DataFrame,
    *,
    dataset_version: str,
    include_xgboost: bool = False,
    bootstrap_iterations: int = 300,
    incumbent: dict[str, Any] | None = None,
) -> TrainingResult:
    y = _target(frame)
    features = build_features(frame, FEATURE_COLUMNS, strict=True).reset_index(drop=True)
    frame = frame.reset_index(drop=True)
    split = temporal_split(frame)
    for name, index in (
        ("train", split.train), ("tuning", split.tuning),
        ("calibration", split.calibration), ("test", split.test),
    ):
        if np.unique(y[index]).size < 2:
            raise ValueError(f"Temporal {name} fold must contain both target classes")
    candidates: list[CandidateScore] = []
    fitted: dict[str, Any] = {}
    for name, model, params in _candidate_models(include_xgboost):
        model.fit(features.iloc[split.train], y[split.train])
        probability = model.predict_proba(features.iloc[split.tuning])[:, 1]
        score = CandidateScore(name, classification_metrics(y[split.tuning], probability), params)
        candidates.append(score)
        fitted[name] = model

    winner = min(candidates, key=lambda item: (item.validation["brier"], item.validation["ece"]))
    development_index = np.concatenate([split.train, split.tuning])
    selected_model = clone(fitted[winner.name])
    selected_model.fit(features.iloc[development_index], y[development_index])
    calibrated = CalibratedClassifierCV(FrozenEstimator(selected_model), method="sigmoid")
    calibrated.fit(features.iloc[split.calibration], y[split.calibration])
    test_probability = calibrated.predict_proba(features.iloc[split.test])[:, 1]
    test_y = y[split.test]
    test_frame = frame.iloc[split.test].reset_index(drop=True)
    test_features = features.iloc[split.test].reset_index(drop=True)
    metrics = classification_metrics(test_y, test_probability)
    groups = (
        test_frame["GAME_ID"].astype(str).to_numpy()
        if "GAME_ID" in test_frame.columns
        else test_frame["GAME_DATE"].astype(str).to_numpy()
    )
    confidence = cluster_bootstrap_intervals(
        test_y,
        test_probability,
        groups,
        iterations=bootstrap_iterations,
    )
    incumbent_probability = _safe_incumbent_probability(
        incumbent, test_frame, test_from=split.test_from
    )
    naive_probability = np.full(len(test_y), y[split.train].mean())
    naive_metrics = classification_metrics(test_y, naive_probability)
    baseline_probability = incumbent_probability if incumbent_probability is not None else naive_probability
    comparison = classification_metrics(test_y, baseline_probability)
    paired = paired_bootstrap_deltas(
        test_y,
        test_probability,
        baseline_probability,
        groups,
        iterations=bootstrap_iterations,
    )
    tolerances = {
        "brier": 0.001,
        "log_loss": 0.003,
        "auc": 0.002,
        "average_precision": 0.002,
        "ece": 0.005,
    }
    lower_is_better = {"brier", "log_loss", "ece"}
    paired_passed = set(paired) == set(tolerances) and all(
        (
            paired[metric]["upper"] <= tolerance
            if metric in lower_is_better
            else paired[metric]["lower"] >= -tolerance
        )
        for metric, tolerance in tolerances.items()
    )
    slice_checks = slice_promotion_checks(
        test_frame, test_features, test_y, test_probability, baseline_probability
    )
    slices_passed = not any(row["status"] == "failed" for row in slice_checks)

    oof_index, oof_probability = rolling_oof_predictions(
        fitted[winner.name], frame, features, y, before=split.test_from
    )
    if len(oof_index):
        distribution, prior_mean, prior_variance, residual_variance, player_rows = (
            _player_distribution(
                frame.iloc[oof_index].reset_index(drop=True),
                features.iloc[oof_index].reset_index(drop=True),
                y[oof_index],
                oof_probability,
            )
        )
    else:
        distribution, prior_mean, prior_variance, residual_variance, player_rows = (
            [], 0.0, 0.0025, 0.25, []
        )
    promoted = paired_passed and slices_passed
    evaluation: dict[str, Any] = {
        "schema_version": "xfg-evaluation-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_version": dataset_version,
        "split": asdict(split) | {
            "train": len(split.train),
            "tuning": len(split.tuning),
            "calibration": len(split.calibration),
            "test": len(split.test),
        },
        "winner": winner.name,
        "candidates": [asdict(candidate) for candidate in candidates],
        "test": metrics,
        "confidence_intervals_95": confidence,
        "paired_metric_delta_intervals_95": paired,
        "baseline": comparison,
        "baseline_kind": "eligible_incumbent" if incumbent_probability is not None else "constant_train_rate",
        "promotion": {
            "passed": promoted,
            "paired_metrics_passed": paired_passed,
            "critical_slices_passed": slices_passed,
            "rules": tolerances,
            "slice_checks": slice_checks,
        },
        "calibration": calibration_curve_rows(test_y, test_probability),
        "slices": sliced_metrics(test_frame, test_features, test_y, test_probability),
        "feature_importance": _feature_importance(calibrated, test_features, test_y),
        "drift": drift_report(features.iloc[split.train], test_features),
        "player_season_estimates": player_rows[:500],
        "player_prior_source": "expanding-window out-of-fold predictions before final test",
    }
    calibration_by_distance, calibration_by_time = context_calibration_rows(
        test_features, test_y, test_probability
    )
    meta = {
        "model_version": 3,
        "dataset_version": dataset_version,
        "n_shots": len(frame),
        "n_test": len(test_y),
        "seasons": sorted(frame["SEASON"].astype(str).unique().tolist()),
        "trained_at": datetime.now(UTC).isoformat(),
        "selected_model": winner.name,
        "runtime": _runtime_versions(),
        "training_data_through": split.calibration_through,
        "test_data_from": split.test_from,
        **metrics,
        "brier_naive": naive_metrics["brier"],
        "baseline": comparison,
        "calibration_by_distance": calibration_by_distance,
        "calibration_by_time": calibration_by_time,
        "prior_mean": prior_mean,
        "prior_variance": prior_variance,
        "residual_variance": residual_variance,
        "promotion": evaluation["promotion"],
    }
    bundle = {
        "model": calibrated,
        "feature_columns": FEATURE_COLUMNS,
        "delta_distribution": distribution,
        "meta": meta,
        "evaluation": evaluation,
    }
    return TrainingResult(bundle=bundle, evaluation=evaluation, promoted=promoted)


def save_candidate(result: TrainingResult, model_path: Path, report_path: Path) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    model_descriptor, model_tmp_name = tempfile.mkstemp(
        prefix=f".{model_path.name}.", suffix=".tmp", dir=model_path.parent
    )
    os.close(model_descriptor)
    model_tmp = Path(model_tmp_name)
    report_descriptor, report_tmp_name = tempfile.mkstemp(
        prefix=f".{report_path.name}.", suffix=".tmp", dir=report_path.parent
    )
    os.close(report_descriptor)
    report_tmp = Path(report_tmp_name)
    try:
        joblib.dump(result.bundle, model_tmp)
        with report_tmp.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(result.evaluation, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        report_tmp.replace(report_path)
        model_tmp.replace(model_path)
    finally:
        model_tmp.unlink(missing_ok=True)
        report_tmp.unlink(missing_ok=True)
    result.candidate_path = model_path


def promote_candidate(
    candidate: Path,
    production: Path,
    *,
    force: bool = False,
    expected_sha256: str | None = None,
) -> str:
    candidate_sha256 = sha256_file(candidate)
    if expected_sha256 is not None and candidate_sha256 != expected_sha256:
        raise RuntimeError("Candidate checksum does not match the expected SHA-256")
    bundle = joblib.load(candidate)
    passed = bool(bundle.get("meta", {}).get("promotion", {}).get("passed"))
    if not passed and not force:
        raise RuntimeError("Candidate failed the recorded quality gate; use --force to override")
    production.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{production.name}.", suffix=".promoting", dir=production.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(candidate, temporary)
        if candidate_sha256 != sha256_file(temporary):
            raise RuntimeError("Candidate checksum changed during promotion")
        temporary.replace(production)
    finally:
        temporary.unlink(missing_ok=True)
    return sha256_file(production)


def _mlflow_metric_key(prefix: str, name: str) -> str:
    """Build an MLflow-safe metric key (alphanumerics, underscore, dash, dot, slash)."""
    return f"{prefix}{name}".replace(" ", "_")


def log_mlflow(
    result: TrainingResult,
    *,
    experiment: str = "nba-xfg",
    register: bool = True,
    registered_model_name: str = "xfg",
) -> bool:
    """Record a browsable, file-backed MLflow run for the training result.

    Logs run parameters, per-candidate tuning metrics, final test metrics,
    baseline comparison, and clustered-bootstrap interval widths; attaches the
    evaluation report, calibration, drift, and slice artifacts; and, when the
    recorded promotion gate passes, registers the candidate in the local model
    registry tagged with its dataset and model version. Returns False when the
    optional MLflow extra is not installed so callers stay dependency-light.
    """
    try:
        import mlflow
    except ImportError:
        return False

    evaluation = result.evaluation
    meta = result.bundle.get("meta", {})
    mlflow.set_experiment(experiment)
    with mlflow.start_run() as run:
        mlflow.set_tags({
            "model_version": meta.get("model_version"),
            "dataset_version": evaluation.get("dataset_version"),
            "winner": evaluation.get("winner"),
            "baseline_kind": evaluation.get("baseline_kind"),
            "promotion_gate": "passed" if result.promoted else "failed",
            "schema_version": evaluation.get("schema_version"),
        })
        mlflow.log_params({
            "winner": evaluation.get("winner"),
            "dataset_version": evaluation.get("dataset_version"),
            "seasons": ",".join(meta.get("seasons", [])),
            "n_shots": meta.get("n_shots"),
            "n_test": meta.get("n_test"),
            "train_through": evaluation.get("split", {}).get("train_through"),
            "test_from": evaluation.get("split", {}).get("test_from"),
            "baseline_kind": evaluation.get("baseline_kind"),
        })

        # Final calibrated test metrics.
        mlflow.log_metrics(evaluation["test"])
        # Baseline comparison, so a reviewer sees candidate-vs-baseline in one place.
        mlflow.log_metrics({
            _mlflow_metric_key("baseline_", key): value
            for key, value in evaluation.get("baseline", {}).items()
        })
        # Per-candidate tuning metrics selected on during model choice.
        for candidate in evaluation.get("candidates", []):
            name = candidate["name"]
            mlflow.log_metrics({
                _mlflow_metric_key(f"tuning_{name}_", key): value
                for key, value in candidate.get("validation", {}).items()
            })
        # Clustered-bootstrap 95% interval widths quantify test uncertainty.
        for metric, interval in evaluation.get("confidence_intervals_95", {}).items():
            width = float(interval["upper"]) - float(interval["lower"])
            mlflow.log_metric(_mlflow_metric_key("ci95_width_", metric), width)

        # Rich artifacts for offline inspection.
        mlflow.log_dict(evaluation, "evaluation.json")
        mlflow.log_dict({"calibration": evaluation.get("calibration", [])}, "calibration.json")
        mlflow.log_dict({"drift": evaluation.get("drift", [])}, "drift.json")
        mlflow.log_dict({"slices": evaluation.get("slices", [])}, "slices.json")
        mlflow.log_dict(evaluation.get("promotion", {}), "promotion.json")

        # Register only a gate-passing candidate; a failed gate is still logged
        # for history but never promoted into the registry.
        if register and result.promoted:
            try:
                model = result.bundle.get("model")
                if model is not None:
                    # Log a real sklearn MLmodel so the registry version can reach
                    # READY on the local file store, then register that artifact.
                    import mlflow.sklearn

                    mlflow.sklearn.log_model(
                        model,
                        name="model",
                        registered_model_name=registered_model_name,
                    )
                    latest = mlflow.tracking.MlflowClient().search_model_versions(
                        f"name='{registered_model_name}'"
                    )
                    if latest:
                        newest = max(latest, key=lambda version: int(version.version))
                        mlflow.tracking.MlflowClient().set_tag(
                            run.info.run_id,
                            "registered_model_version",
                            str(newest.version),
                        )
            except Exception as error:
                mlflow.tracking.MlflowClient().set_tag(
                    run.info.run_id, "registry_error", type(error).__name__
                )
    return True
