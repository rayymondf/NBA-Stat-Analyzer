"""Shot-quality (xFG) model, the app's first *trained* ML component.

A gradient-boosted classifier is trained on league-wide shots (see
backend/scripts/train_models.py) to estimate each shot's make probability from
where and how it was taken (location, distance, angle, shot type, quarter,
clock, home or away). Comparing a player's ACTUAL makes with what the model
EXPECTED from those same locations isolates shot-making skill from shot
selection.

The model uses shot location and context data only, never video or images.
"""
import os
import threading

import numpy as np
import pandas as pd

from ..nba import api
from ..nba.seasons import current_season

MODEL_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "models", "xfg.joblib"))

MODEL_VERSION = 2

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
                   columns: list[str] | None = None) -> pd.DataFrame:
    """Numeric feature matrix from raw Shot_Chart_Detail rows.

    Shared by training and inference so both always agree. `columns` selects
    which feature set to return; a saved model bundle carries its own list so
    inference always matches what that model was trained on.
    """
    out = pd.DataFrame(index=shots.index)
    out["distance"] = shots["SHOT_DISTANCE"].astype(float)
    out["abs_x"] = shots["LOC_X"].abs().astype(float)
    out["loc_y"] = shots["LOC_Y"].astype(float)
    # Angle from the hoop in degrees: 0 = straight on, +/-90 = the baselines.
    out["angle"] = np.degrees(np.arctan2(
        shots["LOC_X"].astype(float), shots["LOC_Y"].astype(float)))
    out["period"] = shots["PERIOD"].clip(upper=5).astype(float)
    # Seconds left in the period: separates normal shots from end-of-quarter
    # heaves, the single biggest calibration fix in v2.
    if "MINUTES_REMAINING" in shots.columns and "SECONDS_REMAINING" in shots.columns:
        secs = (shots["MINUTES_REMAINING"].astype(float) * 60
                + shots["SECONDS_REMAINING"].astype(float))
        out["seconds_left_period"] = secs.clip(0, 720)
    else:
        out["seconds_left_period"] = 360.0
    out["is_three"] = shots["SHOT_TYPE"].astype(str).str.contains("3PT").astype(float)
    if "HTM" in shots.columns and "TEAM_ID" in shots.columns:
        abbr = shots["TEAM_ID"].map(_team_abbr())
        out["is_home"] = (abbr == shots["HTM"]).astype(float)
    else:
        out["is_home"] = 0.0
    for z in ZONES:
        out[f"zone_{z}"] = (shots["SHOT_ZONE_BASIC"] == z).astype(float)
    if "SHOT_ZONE_AREA" in shots.columns:
        for a in ZONE_AREAS:
            out[f"area_{a}"] = (shots["SHOT_ZONE_AREA"] == a).astype(float)
    else:
        for a in ZONE_AREAS:
            out[f"area_{a}"] = 0.0
    groups = shots["ACTION_TYPE"].map(action_group)
    for a in ACTION_GROUPS:
        out[f"action_{a}"] = (groups == a).astype(float)
    return out[columns or FEATURE_COLUMNS]


def load_model() -> dict | None:
    """Lazy-load the trained bundle {model, meta, delta_distribution}."""
    global _model_bundle
    if _model_bundle is not None:
        return _model_bundle
    with _model_lock:
        if _model_bundle is None and os.path.isfile(MODEL_PATH):
            import joblib
            _model_bundle = joblib.load(MODEL_PATH)
    return _model_bundle


def _delta_percentile(delta: float, distribution: list[float]) -> int | None:
    if not distribution:
        return None
    arr = np.asarray(distribution)
    return int(round((arr < delta).mean() * 100))


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
    x = build_features(shots, cols)
    xfg = model.predict_proba(x)[:, 1]

    made = shots["SHOT_MADE_FLAG"].astype(float).to_numpy()
    is3 = x["is_three"].to_numpy()
    weight = 1 + 0.5 * is3  # eFG weighting: threes count 1.5x

    n = len(shots)
    expected_efg = float((xfg * weight).sum() / n)
    actual_efg = float((made * weight).sum() / n)
    delta = actual_efg - expected_efg

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

    meta = bundle.get("meta", {})
    return {
        "available": True,
        "season": season,
        "season_type": season_type,
        "shots": n,
        "expected_efg": round(expected_efg, 3),
        "actual_efg": round(actual_efg, 3),
        "delta": round(delta, 3),
        "delta_per_100_shots": round(delta * 2 * 100, 1),  # extra points per 100 FGA
        "percentile": _delta_percentile(delta, bundle.get("delta_distribution", [])),
        "zones": zones,
        "model": {
            "trained_on_shots": meta.get("n_shots"),
            "seasons": meta.get("seasons"),
            "brier": meta.get("brier"),
            "auc": meta.get("auc"),
            "trained_at": meta.get("trained_at"),
            "model_version": meta.get("model_version", 1),
        },
        "explanation": (
            "Expected eFG% (xFG) is what an average NBA player would shoot "
            "from this player's exact shot locations and types, estimated by "
            "a model trained on real NBA shots. A positive delta means the "
            "player makes more than those shots usually yield: shot-making "
            "skill beyond shot selection. This is a model estimate built from "
            "shot locations and types only, never video."),
    }
