"""Offline performance snapshot for release evidence and regression triage."""

from __future__ import annotations

import gzip
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.nba import cache  # noqa: E402
from app.services import ml  # noqa: E402


def timed(call):
    started = time.perf_counter()
    result = call()
    return result, round((time.perf_counter() - started) * 1000, 2)


def frontend_bundles() -> list[dict[str, object]]:
    assets = ROOT / "frontend" / "dist" / "assets"
    if not assets.exists():
        return []
    rows = []
    for path in sorted(assets.glob("*.js")):
        content = path.read_bytes()
        rows.append({
            "file": path.name,
            "bytes": len(content),
            "gzip_bytes": len(gzip.compress(content, compresslevel=9)),
        })
    return rows


def feature_matrix_benchmark(rows: int = 100_000) -> dict[str, object]:
    rng = np.random.default_rng(42)
    source = pd.DataFrame({
        "SHOT_DISTANCE": rng.integers(0, 40, rows),
        "LOC_X": rng.integers(-250, 251, rows),
        "LOC_Y": rng.integers(-20, 400, rows),
        "PERIOD": rng.integers(1, 6, rows),
        "MINUTES_REMAINING": rng.integers(0, 12, rows),
        "SECONDS_REMAINING": rng.integers(0, 60, rows),
        "SHOT_TYPE": np.where(rng.random(rows) < 0.4, "3PT Field Goal", "2PT Field Goal"),
        "SHOT_ZONE_BASIC": np.where(
            rng.random(rows) < 0.4, "Above the Break 3", "Restricted Area"
        ),
        "SHOT_ZONE_AREA": np.where(
            rng.random(rows) < 0.5, "Center(C)", "Right Side Center(RC)"
        ),
        "ACTION_TYPE": np.where(rng.random(rows) < 0.5, "Jump Shot", "Driving Layup Shot"),
        "TEAM_ID": np.full(rows, 1610612761),
        "HTM": np.full(rows, "TOR"),
    })
    matrix, elapsed_ms = timed(lambda: ml.build_features(source, strict=True))
    return {
        "rows": rows,
        "elapsed_ms": elapsed_ms,
        "rows_per_second": round(rows / max(elapsed_ms / 1000, 1e-9)),
        "matrix_mib": round(matrix.memory_usage(deep=True).sum() / 1024**2, 2),
        "dtype": str(matrix.dtypes.iloc[0]),
    }


def main() -> None:
    bundle, load_ms = timed(ml.load_model)
    warmed, warm_ms = timed(lambda: ml.warm_model(bundle))
    report = {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "model": {
            "available": bundle is not None,
            "load_ms": load_ms,
            "warmup_ms": warm_ms,
            "warmed": warmed,
            "identity": ml.model_status(),
        },
        "cache": cache.stats(),
        "feature_matrix": feature_matrix_benchmark(),
        "frontend_bundles": frontend_bundles(),
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
