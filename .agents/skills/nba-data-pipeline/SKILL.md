---
name: nba-data-pipeline
description: Build, validate, inspect, or publish the NBA shot dataset and its Parquet, DuckDB, manifest, or object-storage artifacts. Use for ingestion, dataset refreshes, lineage, schema failures, and artifact transport; not for model selection or UI work.
---

# NBA data pipeline

Work from `backend` and use `nba-pipeline` rather than one-off notebooks or untracked transformations.

1. Identify the exact source seasons and whether the run may call NBA.com. Do not infer permission for a large live refresh from a read-only analysis request.
2. Ingest to resumable team-season partitions with `nba-pipeline ingest --season <YYYY-YY>`. Preserve raw partitions; do not rewrite them during feature experiments.
3. Validate before deriving data. Treat missing required fields, invalid targets, out-of-range coordinates/clock values, and checksum mismatch as hard failures.
4. Build the Hive-partitioned Parquet dataset and manifest with `nba-pipeline build`. Carry the resulting `dataset_version` into every training run and artifact index.
5. Use `nba-pipeline query <dataset> <sql>` for read-only profiling. Keep SQL to `SELECT` or CTE queries.
6. For artifact publication, stage locally first. Verify SHA-256 after transport. Never load an unverified remote joblib file.

Return row and partition counts, seasons, dataset version, checksum status, validation findings, and exact output paths. Note NBA.com usage/redistribution constraints when publishing data.
