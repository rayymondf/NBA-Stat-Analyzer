"""Train the shot-quality (xFG) model on league-wide NBA shots.

Run once (and optionally re-run each season for fresh data):

    backend\\venv\\Scripts\\python.exe backend\\scripts\\train_models.py

What it does, in plain English:
1. Downloads every shot taken in the last three seasons from NBA.com,
   30 cached requests per season, so re-runs are instant.
2. Turns each shot into numbers a model can learn from: distance, court
   location and angle, shot type, quarter, seconds left in the quarter,
   home or away.
3. Trains a gradient-boosted classifier to predict the chance a shot goes in,
   picking its settings on a validation slice.
4. Compares the new model (B) against the previous design (A) on the exact
   same held-out shots, and only saves B if it wins.
5. Saves the model to backend/data/models/xfg.joblib, plus the distribution of
   player skill deltas and calibration tables for the app's Model page.

No external datasets, GPUs, or accounts needed. Everything is free and local.
"""
import os
import sys
from datetime import datetime, timezone
from itertools import product

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import joblib
import numpy as np
import pandas as pd
from nba_api.stats.static import teams as static_teams
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split

from app.nba import api  # noqa: E402
from app.nba.seasons import current_season, previous_season  # noqa: E402
from app.services.ml import (MODEL_PATH, MODEL_VERSION,  # noqa: E402
                             FEATURE_COLUMNS, FEATURE_COLUMNS_V1,
                             build_features)

MIN_SHOTS_FOR_DISTRIBUTION = 200
NUM_SEASONS = 3

DIST_BUCKETS = [(0, 4), (4, 10), (10, 16), (16, 24), (24, 31)]


def train_seasons() -> list[str]:
    seasons = [current_season()]
    while len(seasons) < NUM_SEASONS:
        seasons.append(previous_season(seasons[-1]))
    return seasons


def collect_shots(seasons: list[str]) -> pd.DataFrame:
    frames = []
    team_ids = [t["id"] for t in static_teams.get_teams()]
    for season in seasons:
        for i, team_id in enumerate(team_ids, 1):
            rows = api.team_shot_chart(team_id, season)
            df = pd.DataFrame(rows)
            df["SEASON"] = season
            frames.append(df)
            print(f"  {season}: team {i:>2}/30 -> {len(rows):>5} shots")
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["SHOT_DISTANCE", "LOC_X", "LOC_Y", "SHOT_MADE_FLAG"])
    return df


def _calibration_rows(x_test: pd.DataFrame, y_test: np.ndarray,
                      p_test: np.ndarray) -> tuple[list[dict], list[dict]]:
    dist = x_test["distance"].to_numpy()
    by_distance = []
    for lo, hi in DIST_BUCKETS:
        m = (dist >= lo) & (dist < hi)
        if m.sum() > 100:
            by_distance.append({
                "bucket": f"{lo}-{hi} ft", "lo": lo, "hi": hi,
                "predicted": round(float(p_test[m].mean()), 3),
                "actual": round(float(y_test[m].mean()), 3),
                "shots": int(m.sum()),
            })
    secs = x_test["seconds_left_period"].to_numpy()
    heave = (secs <= 6) & (dist >= 30)
    by_time = []
    for label, m in [("Last 6s of a quarter, 30+ ft", heave),
                     ("All other shots", ~heave)]:
        if m.sum() > 20:
            by_time.append({
                "bucket": label,
                "predicted": round(float(p_test[m].mean()), 3),
                "actual": round(float(y_test[m].mean()), 3),
                "shots": int(m.sum()),
            })
    return by_distance, by_time


def _report(name: str, y_test: np.ndarray, p_test: np.ndarray) -> tuple[float, float]:
    brier = brier_score_loss(y_test, p_test)
    auc = roc_auc_score(y_test, p_test)
    print(f"  {name}: Brier {brier:.4f}   AUC {auc:.3f}")
    return float(brier), float(auc)


def main() -> None:
    seasons = train_seasons()
    print(f"Collecting league-wide shots for {seasons} …")
    shots = collect_shots(seasons)
    print(f"Total shots: {len(shots):,}")
    print("SHOT_ZONE_AREA values:", sorted(shots["SHOT_ZONE_AREA"].dropna().unique()))

    y_all = shots["SHOT_MADE_FLAG"].astype(int).to_numpy()

    # Frozen, shared test set drawn from the two most recent seasons: both the
    # old design (A) and the new one (B) are judged on these identical rows.
    recent_mask = shots["SEASON"].isin(seasons[:2]).to_numpy()
    recent_idx = np.where(recent_mask)[0]
    train_recent_idx, test_idx = train_test_split(
        recent_idx, test_size=0.2, random_state=42,
        stratify=y_all[recent_idx])
    test_shots = shots.iloc[test_idx]
    y_test = y_all[test_idx]

    # Training pools. A trains exactly like the shipped v1 (2 recent seasons);
    # B gets all seasons minus the frozen test rows.
    b_train_idx = np.setdiff1d(np.arange(len(shots)), test_idx)

    print("\nModel A (previous design: v1 features, fixed settings) …")
    xa_train = build_features(shots.iloc[train_recent_idx], FEATURE_COLUMNS_V1)
    xa_test = build_features(test_shots, FEATURE_COLUMNS_V1)
    model_a = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_depth=None,
        min_samples_leaf=50, random_state=42)
    model_a.fit(xa_train, y_all[train_recent_idx])
    pa = model_a.predict_proba(xa_test)[:, 1]
    brier_a, auc_a = _report("A", y_test, pa)

    print("\nModel B (v2 features, 3 seasons, tuned settings) …")
    xb_pool = build_features(shots.iloc[b_train_idx], FEATURE_COLUMNS)
    yb_pool = y_all[b_train_idx]
    xb_test = build_features(test_shots, FEATURE_COLUMNS)

    fit_idx, val_idx = train_test_split(
        np.arange(len(yb_pool)), test_size=0.1, random_state=7,
        stratify=yb_pool)
    best = None
    for lr, leaves, leaf_min in product([0.05, 0.08], [31, 63], [20, 50]):
        cand = HistGradientBoostingClassifier(
            max_iter=1000, learning_rate=lr, max_leaf_nodes=leaves,
            min_samples_leaf=leaf_min, early_stopping=True,
            validation_fraction=0.1, n_iter_no_change=20, random_state=42)
        cand.fit(xb_pool.iloc[fit_idx], yb_pool[fit_idx])
        pv = cand.predict_proba(xb_pool.iloc[val_idx])[:, 1]
        score = brier_score_loss(yb_pool[val_idx], pv)
        print(f"  lr={lr} leaves={leaves} min_leaf={leaf_min} "
              f"-> val Brier {score:.4f} ({cand.n_iter_} iters)")
        if best is None or score < best[0]:
            best = (score, {"learning_rate": lr, "max_leaf_nodes": leaves,
                            "min_samples_leaf": leaf_min})
    params = best[1]
    print(f"  Winner: {params}; refitting on the full training pool …")
    model_b = HistGradientBoostingClassifier(
        max_iter=1000, early_stopping=True, validation_fraction=0.1,
        n_iter_no_change=20, random_state=42, **params)
    model_b.fit(xb_pool, yb_pool)
    pb = model_b.predict_proba(xb_test)[:, 1]
    brier_b, auc_b = _report("B", y_test, pb)

    naive = np.full_like(pb, yb_pool.mean())
    brier_naive = float(brier_score_loss(y_test, naive))

    print(f"\nHead-to-head on the same {len(y_test):,} held-out shots:")
    print(f"  Brier (lower=better): A {brier_a:.4f}  B {brier_b:.4f}  "
          f"naive {brier_naive:.4f}")
    print(f"  AUC   (higher=better): A {auc_a:.3f}  B {auc_b:.3f}")
    cal_dist, cal_time = _calibration_rows(xb_test, y_test, pb)
    print("  B calibration by distance (predicted vs actual):")
    for row in cal_dist:
        print(f"    {row['bucket']:>9}: predicted {row['predicted']:.3f}  "
              f"actual {row['actual']:.3f}  ({row['shots']:,} shots)")
    print("  B calibration, end-of-quarter heaves vs everything else:")
    for row in cal_time:
        print(f"    {row['bucket']}: predicted {row['predicted']:.3f}  "
              f"actual {row['actual']:.3f}  ({row['shots']:,} shots)")

    # Ship gate: B must beat A on Brier without giving up real AUC.
    if not (brier_b < brier_a and auc_b >= auc_a - 0.002):
        print("\nNew model did NOT beat the previous design on the shared "
              "test set. Keeping the existing saved model; nothing written.")
        return

    print("\nComputing league delta distribution …")
    x_full = build_features(shots, FEATURE_COLUMNS)
    p_all = model_b.predict_proba(x_full)[:, 1]
    is3 = x_full["is_three"].to_numpy()
    weight = 1 + 0.5 * is3
    per = pd.DataFrame({
        "player": shots["PLAYER_ID"].to_numpy(),
        "expected": p_all * weight,
        "actual": shots["SHOT_MADE_FLAG"].astype(float).to_numpy() * weight,
    })
    grouped = per.groupby("player").agg(n=("actual", "size"),
                                        expected=("expected", "mean"),
                                        actual=("actual", "mean"))
    qualified = grouped[grouped["n"] >= MIN_SHOTS_FOR_DISTRIBUTION]
    deltas = (qualified["actual"] - qualified["expected"]).round(4).tolist()
    print(f"  {len(deltas)} players with >= {MIN_SHOTS_FOR_DISTRIBUTION} shots")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump({
        "model": model_b,
        "feature_columns": FEATURE_COLUMNS,
        "delta_distribution": sorted(deltas),
        "meta": {
            "model_version": MODEL_VERSION,
            "n_shots": int(len(shots)),
            "n_test": int(len(y_test)),
            "seasons": seasons,
            "brier": round(brier_b, 4),
            "brier_naive": round(brier_naive, 4),
            "auc": round(auc_b, 3),
            "baseline": {"brier": round(brier_a, 4), "auc": round(auc_a, 3)},
            "calibration_by_distance": cal_dist,
            "calibration_by_time": cal_time,
            "params": params,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        },
    }, MODEL_PATH)
    print(f"\nSaved model v{MODEL_VERSION} -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
