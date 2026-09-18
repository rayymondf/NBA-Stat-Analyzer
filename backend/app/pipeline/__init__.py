"""Reproducible data/ML workflows with lazy imports for fast API startup."""

from __future__ import annotations

from typing import Any

__all__ = [
    "DatasetManifest",
    "DatasetValidationError",
    "build_parquet",
    "inspect_dataset",
    "validate_shots",
]


def __getattr__(name: str) -> Any:
    if name == "DatasetManifest":
        from .manifest import DatasetManifest

        return DatasetManifest
    if name in {"DatasetValidationError", "build_parquet", "inspect_dataset", "validate_shots"}:
        from . import dataset

        return getattr(dataset, name)
    raise AttributeError(name)
