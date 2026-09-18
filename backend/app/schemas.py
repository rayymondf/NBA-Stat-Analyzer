"""Public response envelopes used to keep OpenAPI responses explicit.

Domain services intentionally return heterogeneous analytics payloads. These
JSON-root models validate that the public boundary remains serializable while
the frontend's richer named interfaces document individual payload shapes.

Explicit DTOs (e.g. ``ModelInfo``) progressively replace the generic roots so
the OpenAPI contract names concrete schemas that the frontend derives types
from. Endpoints not yet migrated continue to use the generic roots below and
stay byte-for-byte compatible on ``/api/v1``.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel


class JsonObject(RootModel[dict[str, JsonValue]]):
    pass


class JsonObjectList(RootModel[list[dict[str, JsonValue]]]):
    pass


class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    request_id: str
    retryable: bool


# --- Explicit xFG model-info DTOs -------------------------------------------
# These describe the /api/v1/ml/model-info payload. Optional fields default to
# None/[] so the schema stays backward compatible with older saved bundles that
# omit newer keys, and so the "unavailable" response validates too.


class ModelMetrics(BaseModel):
    """Held-out classification metrics for the calibrated model."""

    model_config = ConfigDict(extra="allow")

    brier: float | None = None
    brier_naive: float | None = None
    auc: float | None = None
    n_test: int | None = None
    log_loss: float | None = None
    average_precision: float | None = None
    ece: float | None = None


class CalibrationPoint(BaseModel):
    """One row of a predicted-vs-actual calibration table."""

    model_config = ConfigDict(extra="allow")

    bucket: str
    predicted: float
    actual: float
    shots: int


class FeatureImportance(BaseModel):
    feature: str
    importance: float


class DriftEntry(BaseModel):
    feature: str
    psi: float
    status: str


class Interval(BaseModel):
    """A 95% bootstrap confidence interval."""

    lower: float
    upper: float


class DatasetInfo(BaseModel):
    available: bool
    size_bytes: int = 0
    url: str
    usage_note: str


class ModelInfoAvailable(BaseModel):
    """Full metadata for a loaded xFG model, consumed by the "The Model" page."""

    model_config = ConfigDict(extra="allow", protected_namespaces=())

    available: Literal[True] = Field(True, description="True when a model bundle is loaded.")
    model_version: int = 1
    dataset_version: str | None = None
    n_shots: int | None = None
    seasons: list[str] = Field(default_factory=list)
    trained_at: str | None = None
    metrics: ModelMetrics = Field(default_factory=ModelMetrics)
    baseline: dict[str, JsonValue] | None = None
    calibration_by_distance: list[CalibrationPoint] = Field(default_factory=list)
    calibration_by_time: list[CalibrationPoint] = Field(default_factory=list)
    delta_distribution: list[float] = Field(default_factory=list)
    feature_count: int = 0
    selected_model: str | None = None
    feature_importance: list[FeatureImportance] = Field(default_factory=list)
    drift: list[DriftEntry] = Field(default_factory=list)
    confidence_intervals_95: dict[str, Interval] = Field(default_factory=dict)
    evaluation: dict[str, JsonValue] = Field(default_factory=dict)
    dataset: DatasetInfo


class ModelInfoUnavailable(BaseModel):
    """Returned when no model bundle is loaded yet."""

    available: Literal[False] = Field(False)
    reason: str


ModelInfoResponse = ModelInfoAvailable | ModelInfoUnavailable
