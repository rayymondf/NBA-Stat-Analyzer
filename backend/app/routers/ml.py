"""Endpoints for the shot-quality (xFG) model itself: metadata for the
frontend's "The Model" page and a download of the training dataset CSV."""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from ..config import get_settings
from ..routing import PlayerId, Season, SeasonType
from ..schemas import ModelInfoResponse, ShotExplainerResponse
from ..services import ml

router = APIRouter(prefix="/ml", tags=["ml"])

CSV_PATH = str(get_settings().data_dir / "shots_export.csv")


@router.get("/players/{player_id}/shot-explainer", response_model=ShotExplainerResponse)
def shot_explainer(
    player_id: PlayerId,
    season: Season | None = None,
    season_type: SeasonType = SeasonType.REGULAR,
):
    """Which shot-context features most drive the model's make-probability estimate."""
    return ml.shot_difficulty_explainer(player_id, season, str(season_type))


@router.get("/model-info", response_model=ModelInfoResponse)
def model_info():
    settings = get_settings()
    bundle = ml.load_model()
    if bundle is None:
        return {"available": False,
                "reason": ("Model not trained yet. Run "
                           "nba-pipeline train --help.")}
    meta = bundle.get("meta", {})
    csv_exists = os.path.isfile(CSV_PATH)
    return {
        "available": True,
        "model_version": meta.get("model_version", 1),
        "dataset_version": meta.get("dataset_version"),
        "n_shots": meta.get("n_shots"),
        "seasons": meta.get("seasons", []),
        "trained_at": meta.get("trained_at"),
        "metrics": {
            "brier": meta.get("brier"),
            "brier_naive": meta.get("brier_naive"),
            "auc": meta.get("auc"),
            "n_test": meta.get("n_test"),
            "log_loss": meta.get("log_loss"),
            "average_precision": meta.get("average_precision"),
            "ece": meta.get("ece"),
        },
        "baseline": meta.get("baseline"),
        "calibration_by_distance": meta.get("calibration_by_distance", []),
        "calibration_by_time": meta.get("calibration_by_time", []),
        "delta_distribution": bundle.get("delta_distribution", []),
        "feature_count": len(bundle.get("feature_columns")
                             or ml.FEATURE_COLUMNS),
        "selected_model": bundle.get("evaluation", {}).get("winner", "legacy gradient boosting"),
        "feature_importance": bundle.get("evaluation", {}).get("feature_importance", []),
        "drift": bundle.get("evaluation", {}).get("drift", []),
        "confidence_intervals_95": bundle.get("evaluation", {}).get(
            "confidence_intervals_95", {}
        ),
        "evaluation": bundle.get("evaluation", {}),
        "dataset": {
            "available": csv_exists or bool(settings.dataset_public_url),
            "size_bytes": os.path.getsize(CSV_PATH) if csv_exists else 0,
            "url": "/api/v1/ml/dataset.csv",
            "usage_note": (
                "Derived from NBA.com statistics. Review NBA.com terms before "
                "redistributing or using the dataset commercially."
            ),
        },
    }


@router.get(
    "/dataset.csv",
    response_class=FileResponse,
    responses={
        200: {
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
            "description": "Versioned shot-training data export",
        }
    },
)
def dataset_csv():
    public_url = get_settings().dataset_public_url
    if public_url:
        return RedirectResponse(public_url, status_code=307)
    if not os.path.isfile(CSV_PATH):
        raise HTTPException(
            status_code=404,
            detail=("Dataset not exported yet. Run "
                    "backend/scripts/export_shots_csv.py."))
    return FileResponse(CSV_PATH, media_type="text/csv",
                        filename="nba_shots_training_data.csv")
