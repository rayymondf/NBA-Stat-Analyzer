"""Shot-quality (xFG) model, the app's first *trained* ML component.

A gradient-boosted classifier is trained on league-wide shots (see
backend/scripts/train_models.py) to estimate each shot's make probability from
where and how it was taken (location, distance, angle, shot type, quarter,
clock, home or away). Comparing a player's ACTUAL makes with what the model
EXPECTED from those same locations isolates shot-making skill from shot
selection.

The model uses shot location and context data only, never video or images.
"""
import logging
import math
import threading
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from ..config import get_settings
from ..nba import api
from ..nba.seasons import current_season
from ..pipeline.artifacts import ArtifactVerificationError, download_verified
from ..pipeline.manifest import sha256_file

MODEL_PATH = str(get_settings().data_dir / "models" / "xfg.joblib")

MODEL_VERSION = 3

ZONES = ["Restricted Area", "In The Paint (Non-RA)", "Mid-Range",
         "Left Corner 3", "Right Corner 3", "Above the Break 3", "Backcourt"]

ZONE_AREAS = ["Left Side(L)", "Left Side Center(LC)", "Center(C)",
              "Right Side Center(RC)", "Right Side(R)", "Back Court(BC)"]

ACTION_GROUPS = ["dunk", "layup", "tip", "alley", "hook", "floater",
                 "pullup", "stepback", "turnaround", "fadeaway", "bank",
                 "driving", "cutting", "running", "jump"]

# v1 feature set (kept so a pre-v2 saved model still gets the exact matrix
# it was trained on).
FEATURE_COLUMNS_V1 = (
    ["distance", "abs_x", "loc_y", "period", "is_three"]
    + [f"zone_{z}" for z in ZONES]
    + [f"action_{a}" for a in ACTION_GROUPS]
)

FEATURE_COLUMNS = (
    ["distance", "abs_x", "loc_y", "angle", "period", "seconds_left_period",
     "is_three", "is_home"]
    + [f"zone_{z}" for z in ZONES]
    + [f"area_{a}" for a in ZONE_AREAS]
    + [f"action_{a}" for a in ACTION_GROUPS]
)

_TEAM_ABBR: dict[int, str] | None = None


def _team_abbr() -> dict[int, str]:
    global _TEAM_ABBR
    if _TEAM_ABBR is None:
        from nba_api.stats.static import teams as static_teams
        _TEAM_ABBR = {t["id"]: t["abbreviation"]
                      for t in static_teams.get_teams()}
    return _TEAM_ABBR

_model_lock = threading.Lock()
_model_bundle: dict | None = None
_model_load_attempted = False
_model_load_error: str | None = None
log = logging.getLogger(__name__)


def action_group(action: str) -> str:
    a = (action or "").lower()
    for key in ("dunk", "layup", "tip", "alley", "hook", "floater"):
        if key in a:
            return key
    if "pull" in a:
        return "pullup"
    if "step" in a:
        return "stepback"
    for key in ("turnaround", "fadeaway", "bank", "driving", "cutting",
                "running"):
        if key in a:
            return key
    return "jump"


def build_features(shots: pd.DataFrame,
                   columns: list[str] | None = None,
                   *, strict: bool = False) -> pd.DataFrame:
    """Numeric feature matrix from raw Shot_Chart_Detail rows.

    Shared by training and inference so both always agree. `columns` selects
    which feature set to return; a saved model bundle carries its own list so
    inference always matches what that model was trained on.
    """
    if strict:
        required = {
            "SHOT_DISTANCE", "LOC_X", "LOC_Y", "PERIOD", "MINUTES_REMAINING",
            "SECONDS_REMAINING", "SHOT_TYPE", "SHOT_ZONE_BASIC", "SHOT_ZONE_AREA",
            "ACTION_TYPE", "TEAM_ID", "HTM",
        }
        missing = sorted(required.difference(shots.columns))
        if missing:
            raise ValueError(f"v3 features require columns: {', '.join(missing)}")
        if shots[list(required)].isna().any().any():
            raise ValueError("v3 feature columns must not contain null values")
    distance = pd.to_numeric(shots["SHOT_DISTANCE"], errors="coerce").to_numpy(dtype=np.float32)
    loc_x = pd.to_numeric(shots["LOC_X"], errors="coerce").to_numpy(dtype=np.float32)
    loc_y = pd.to_numeric(shots["LOC_Y"], errors="coerce").to_numpy(dtype=np.float32)
    period = np.minimum(
        pd.to_numeric(shots["PERIOD"], errors="coerce").to_numpy(dtype=np.float32), 5
    )
    data: dict[str, np.ndarray] = {
        "distance": distance,
        "abs_x": np.abs(loc_x),
        "loc_y": loc_y,
        "angle": np.degrees(np.arctan2(loc_x, loc_y)).astype(np.float32),
        "period": period,
    }
    # Angle from the hoop in degrees: 0 = straight on, +/-90 = the baselines.
    # Seconds left in the period: separates normal shots from end-of-quarter
    # heaves, the single biggest calibration fix in v2.
    if "MINUTES_REMAINING" in shots.columns and "SECONDS_REMAINING" in shots.columns:
        minutes = pd.to_numeric(shots["MINUTES_REMAINING"], errors="coerce").to_numpy(
            dtype=np.float32
        )
        seconds = pd.to_numeric(shots["SECONDS_REMAINING"], errors="coerce").to_numpy(
            dtype=np.float32
        )
        data["seconds_left_period"] = np.clip(minutes * 60 + seconds, 0, 720)
    else:
        data["seconds_left_period"] = np.full(len(shots), 360, dtype=np.float32)
    data["is_three"] = shots["SHOT_TYPE"].astype(str).str.contains("3PT").to_numpy(
        dtype=np.float32
    )
    if "HTM" in shots.columns and "TEAM_ID" in shots.columns:
        team_ids = pd.to_numeric(shots["TEAM_ID"], errors="coerce").astype("Int64")
        abbr = team_ids.map(_team_abbr())
        if strict and abbr.isna().any():
            raise ValueError("TEAM_ID could not be mapped to an NBA team")
        data["is_home"] = (abbr == shots["HTM"]).to_numpy(dtype=np.float32)
    else:
        data["is_home"] = np.zeros(len(shots), dtype=np.float32)
    for z in ZONES:
        data[f"zone_{z}"] = (shots["SHOT_ZONE_BASIC"] == z).to_numpy(dtype=np.float32)
    if "SHOT_ZONE_AREA" in shots.columns:
        for a in ZONE_AREAS:
            data[f"area_{a}"] = (shots["SHOT_ZONE_AREA"] == a).to_numpy(dtype=np.float32)
    else:
        for a in ZONE_AREAS:
            data[f"area_{a}"] = np.zeros(len(shots), dtype=np.float32)
    groups = shots["ACTION_TYPE"].map(action_group)
    for a in ACTION_GROUPS:
        data[f"action_{a}"] = (groups == a).to_numpy(dtype=np.float32)
    out = pd.DataFrame(data, index=shots.index, dtype=np.float32)
    return out[columns or FEATURE_COLUMNS]


def load_model() -> dict | None:
    """Lazy-load the trained bundle {model, meta, delta_distribution}."""
    global _model_bundle, _model_load_attempted, _model_load_error
    if _model_bundle is not None:
        return _model_bundle
    if _model_load_attempted:
        return None
    with _model_lock:
        if _model_bundle is not None:
            return _model_bundle
        if _model_load_attempted:
            return None
        _model_load_attempted = True
        path = Path(MODEL_PATH)
        settings = get_settings()
        if not path.is_file() and settings.artifact_base_url:
            if not settings.artifact_expected_sha256:
                _model_load_error = "artifact_pin_required"
                log.error("ARTIFACT_BASE_URL requires a pinned SHA-256")
                return None
            try:
                downloaded = download_verified(
                    settings.artifact_base_url,
                    path.parent,
                    expected_sha256=settings.artifact_expected_sha256,
                )
                if downloaded != path:
                    downloaded.replace(path)
            except (OSError, ValueError, ArtifactVerificationError, requests.RequestException) as exc:
                _model_load_error = "artifact_bootstrap_failed"
                log.error(
                    "Unable to bootstrap verified xFG artifact (%s)",
                    type(exc).__name__,
                )
                return None
        if path.is_file():
            import joblib

            if (
                settings.environment.lower() == "production"
                and not settings.artifact_expected_sha256
            ):
                _model_load_error = "artifact_pin_required"
                log.error("Production model load requires ARTIFACT_EXPECTED_SHA256")
                return None
            if (
                settings.artifact_expected_sha256
                and sha256_file(path) != settings.artifact_expected_sha256
            ):
                _model_load_error = "artifact_checksum_mismatch"
                log.error("Local artifact checksum does not match the configured pin")
                return None
            try:
                candidate = joblib.load(path)
            except Exception as exc:
                _model_load_error = "artifact_deserialization_failed"
                log.error("Unable to load xFG artifact (%s)", type(exc).__name__)
                return None
            if (
                not isinstance(candidate, dict)
                or not callable(getattr(candidate.get("model"), "predict_proba", None))
                or not isinstance(candidate.get("feature_columns"), list)
                or not isinstance(candidate.get("meta"), dict)
            ):
                _model_load_error = "artifact_contract_invalid"
                log.error("Artifact does not match the xFG bundle contract")
                return None
            _model_bundle = candidate
            _model_load_error = None
        elif not path.is_file():
            _model_load_error = "artifact_not_found"
    return _model_bundle


def reload_model() -> dict | None:
    """Clear the in-process model cache after an atomic artifact promotion."""
    global _model_bundle, _model_load_attempted, _model_load_error
    with _model_lock:
        _model_bundle = None
        _model_load_attempted = False
        _model_load_error = None
    return load_model()


def model_status() -> dict[str, object]:
    bundle = _model_bundle
    return {
        "available": bundle is not None,
        "attempted": _model_load_attempted,
        "error": _model_load_error,
        "version": bundle.get("meta", {}).get("model_version") if bundle else None,
        "dataset_version": bundle.get("meta", {}).get("dataset_version") if bundle else None,
    }


def warm_model(bundle: dict | None = None) -> bool:
    """Pay native-library/model initialization cost before the first visitor."""
    bundle = bundle or _model_bundle
    if not bundle:
        return False
    columns = bundle.get("feature_columns") or FEATURE_COLUMNS
    sample = pd.DataFrame(np.zeros((1, len(columns)), dtype=np.float32), columns=columns)
    bundle["model"].predict_proba(sample)
    return True


def _delta_percentile(delta: float, distribution: list[float]) -> int | None:
    if not distribution:
        return None
    arr = np.asarray(distribution)
    return round((arr < delta).mean() * 100)


def _base_estimator(model: object) -> object:
    """Unwrap a CalibratedClassifierCV / FrozenEstimator to the fitted tree model.

    SHAP's fast TreeExplainer needs the underlying gradient-boosted estimator; a
    calibrated wrapper is not a tree. We best-effort unwrap and fall back to the
    given model if the structure is unfamiliar.
    """
    calibrated = getattr(model, "calibrated_classifiers_", None)
    if calibrated:
        inner = getattr(calibrated[0], "estimator", None)
        if inner is not None:
            return getattr(inner, "estimator", inner)
    return getattr(model, "estimator", model)


# Human-readable labels for the model's feature groups, used by the explainer.
_FEATURE_LABELS = {
    "distance": "Shot distance",
    "abs_x": "Horizontal court position",
    "loc_y": "Distance up the court",
    "angle": "Angle to the hoop",
    "period": "Quarter",
    "seconds_left_period": "Time left in period",
    "is_three": "Three-point attempt",
    "is_home": "Home court",
}


def _feature_label(column: str) -> str:
    if column in _FEATURE_LABELS:
        return _FEATURE_LABELS[column]
    if column.startswith("zone_"):
        return f"Zone: {column[5:]}"
    if column.startswith("area_"):
        return f"Court area: {column[5:]}"
    if column.startswith("action_"):
        return f"Shot type: {column[7:]}"
    return column


def shot_difficulty_explainer(
    player_id: int,
    season: str | None = None,
    season_type: str = "Regular Season",
    *,
    max_shots: int = 400,
    top_k: int = 8,
) -> dict:
    """Explain which shot-context features most drive the model's xFG estimate.

    Returns mean absolute SHAP contributions per feature over a sample of the
    player's shots. This attributes the *model's* difficulty estimate to inputs;
    it is not a causal or pure-talent measure and never observes defenders,
    contest, or video.
    """
    bundle = load_model()
    if bundle is None:
        return {"available": False,
                "reason": "Model not trained yet. Run nba-pipeline train --help."}
    try:
        import shap
    except ImportError:
        return {"available": False,
                "reason": "SHAP is not installed. Install the 'ml' extra to enable explanations."}

    season = season or current_season()
    data = api.shot_chart(player_id, season, season_type)
    shots = pd.DataFrame(data.get("Shot_Chart_Detail", []))
    if shots.empty:
        return {"available": False, "reason": f"No shots for this player in {season}."}

    model = bundle["model"]
    columns = bundle.get("feature_columns") or FEATURE_COLUMNS
    meta = bundle.get("meta", {})
    model_version = int(meta.get("model_version", 1))
    try:
        features = build_features(shots, columns, strict=model_version >= 3)
    except ValueError as exc:
        return {"available": False, "reason": f"Shot context is incomplete: {exc}"}

    if len(features) > max_shots:
        features = features.sample(max_shots, random_state=42)

    estimator = _base_estimator(model)
    try:
        explainer = shap.TreeExplainer(estimator)
        shap_values = explainer.shap_values(features)
    except Exception as exc:
        log.warning("SHAP explanation failed (%s)", type(exc).__name__)
        return {"available": False,
                "reason": "Explanations are unavailable for the current model artifact."}

    values = np.asarray(shap_values)
    # Binary classifiers may return a per-class list/3D array; take the positive class.
    if values.ndim == 3:
        values = values[:, :, -1]
    mean_abs = np.abs(values).mean(axis=0)
    mean_signed = values.mean(axis=0)
    order = np.argsort(mean_abs)[::-1][:top_k]
    contributions = [
        {
            "feature": str(features.columns[i]),
            "label": _feature_label(str(features.columns[i])),
            "mean_abs_impact": round(float(mean_abs[i]), 5),
            "mean_signed_impact": round(float(mean_signed[i]), 5),
            "direction": "raises make probability" if mean_signed[i] >= 0 else "lowers make probability",
        }
        for i in order
        if mean_abs[i] > 0
    ]
    return {
        "available": True,
        "season": season,
        "season_type": season_type,
        "shots_explained": len(features),
        "model_version": model_version,
        "contributions": contributions,
        "explanation": (
            "Each value is the average magnitude of a feature's contribution to "
            "the model's per-shot make-probability estimate (SHAP). It attributes "
            "the model's difficulty estimate to its inputs; it is not a causal or "
            "pure-talent measure and never sees defenders, contest quality, or video."
        ),
    }



def _shrunken_delta(
    raw_delta: float,
    probabilities: np.ndarray,
    weights: np.ndarray,
    prior_variance: float,
    prior_mean: float = 0.0,
) -> tuple[float, tuple[float, float]]:
    """Empirical-Bayes estimate and interval for a player's weighted FG delta."""
    n = len(probabilities)
    measurement_variance = float(
        np.sum(weights**2 * probabilities * (1 - probabilities)) / n**2
    )
    measurement_variance = max(measurement_variance, 1e-9)
    prior_variance = max(prior_variance, 1e-9)
    posterior_variance = 1 / (1 / prior_variance + 1 / measurement_variance)
    posterior = posterior_variance * (
        prior_mean / prior_variance + raw_delta / measurement_variance
    )
    margin = 1.96 * math.sqrt(posterior_variance)
    return float(posterior), (float(posterior - margin), float(posterior + margin))


def shot_quality(player_id: int, season: str | None = None,
                 season_type: str = "Regular Season") -> dict:
    bundle = load_model()
    if bundle is None:
        return {"available": False,
                "reason": ("Model not trained yet. Run "
                           "backend/scripts/train_models.py once.")}

    season = season or current_season()
    data = api.shot_chart(player_id, season, season_type)
    shots = pd.DataFrame(data.get("Shot_Chart_Detail", []))
    if shots.empty:
        return {"available": False,
                "reason": f"No shots for this player in {season}."}

    model = bundle["model"]
    cols = bundle.get("feature_columns") or FEATURE_COLUMNS_V1
    meta = bundle.get("meta", {})
    model_version = int(meta.get("model_version", 1))
    try:
        x = build_features(shots, cols, strict=model_version >= 3)
    except ValueError as exc:
        return {"available": False, "reason": f"Shot context is incomplete: {exc}"}
    xfg = model.predict_proba(x)[:, 1]

    made = shots["SHOT_MADE_FLAG"].astype(float).to_numpy()
    is3 = x["is_three"].to_numpy()
    weight = 1 + 0.5 * is3  # eFG weighting: threes count 1.5x

    n = len(shots)
    expected_efg = float((xfg * weight).sum() / n)
    actual_efg = float((made * weight).sum() / n)
    raw_delta = actual_efg - expected_efg

    zones = []
    for z in ZONES:
        mask = (shots["SHOT_ZONE_BASIC"] == z).to_numpy()
        zn = int(mask.sum())
        if zn < 5:
            continue
        zones.append({
            "zone": z,
            "shots": zn,
            "expected_fg": round(float(xfg[mask].mean()), 3),
            "actual_fg": round(float(made[mask].mean()), 3),
            "delta": round(float(made[mask].mean() - xfg[mask].mean()), 3),
        })

    if model_version >= 3:
        delta, confidence_interval = _shrunken_delta(
            raw_delta,
            xfg,
            weight,
            float(meta.get("prior_variance", 0.0025)),
            float(meta.get("prior_mean", 0.0)),
        )
    else:
        delta, confidence_interval = raw_delta, None
    return {
        "available": True,
        "season": season,
        "season_type": season_type,
        "shots": n,
        "expected_efg": round(expected_efg, 3),
        "actual_efg": round(actual_efg, 3),
        "delta": round(delta, 3),
        "raw_delta": round(raw_delta, 3),
        "shrunk_delta": round(delta, 3),
        "confidence_interval_95": (
            [round(confidence_interval[0], 3), round(confidence_interval[1], 3)]
            if confidence_interval else None
        ),
        "delta_per_100_shots": round(delta * 2 * 100, 1),  # extra points per 100 FGA
        "percentile": _delta_percentile(delta, bundle.get("delta_distribution", [])),
        "zones": zones,
        "model": {
            "trained_on_shots": meta.get("n_shots"),
            "seasons": meta.get("seasons"),
            "brier": meta.get("brier"),
            "auc": meta.get("auc"),
            "trained_at": meta.get("trained_at"),
            "model_version": model_version,
            "dataset_version": meta.get("dataset_version"),
        },
        "explanation": (
            "Expected eFG% (xFG) is what an average NBA player would shoot "
            "from this player's exact shot locations and types, estimated by "
            "a model trained on real NBA shots. A positive delta means the "
            "player makes more than those shots usually yield: shot-making "
            "a residual versus the league shot-context benchmark. It is not a "
            "causal or pure-talent measure: contest, defender, play context and "
            "video are not available to this model."),
        "uncertainty_note": (
            "The displayed delta is shrunk toward league average for small samples. "
            "Its 95% interval captures shot-result sampling uncertainty, not every source "
            "of model or tracking-data uncertainty."
        ),
    }
