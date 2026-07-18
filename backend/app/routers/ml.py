"""Endpoints for the shot-quality (xFG) model itself: metadata for the
frontend's "The Model" page and a download of the training dataset CSV."""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..services import ml

router = APIRouter(prefix="/api/ml", tags=["ml"])

CSV_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "shots_export.csv"))


@router.get("/model-info")
def model_info():
    bundle = ml.load_model()
    if bundle is None:
        return {"available": False,
                "reason": ("Model not trained yet. Run "
                           "backend/scripts/train_models.py once.")}
    meta = bundle.get("meta", {})
    csv_exists = os.path.isfile(CSV_PATH)
    return {
        "available": True,
        "model_version": meta.get("model_version", 1),
        "n_shots": meta.get("n_shots"),
        "seasons": meta.get("seasons", []),
        "trained_at": meta.get("trained_at"),
        "metrics": {
            "brier": meta.get("brier"),
            "brier_naive": meta.get("brier_naive"),
            "auc": meta.get("auc"),
            "n_test": meta.get("n_test"),
        },
        "baseline": meta.get("baseline"),
        "calibration_by_distance": meta.get("calibration_by_distance", []),
        "calibration_by_time": meta.get("calibration_by_time", []),
        "delta_distribution": bundle.get("delta_distribution", []),
        "feature_count": len(bundle.get("feature_columns")
                             or ml.FEATURE_COLUMNS),
        "dataset": {
            "available": csv_exists,
            "size_bytes": os.path.getsize(CSV_PATH) if csv_exists else 0,
            "url": "/api/ml/dataset.csv",
        },
    }


@router.get("/dataset.csv")
def dataset_csv():
    if not os.path.isfile(CSV_PATH):
        raise HTTPException(
            status_code=404,
            detail=("Dataset not exported yet. Run "
                    "backend/scripts/export_shots_csv.py."))
    return FileResponse(CSV_PATH, media_type="text/csv",
                        filename="nba_shots_training_data.csv")
