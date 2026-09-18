"""Single command-line entrypoint for reproducible data/ML operations."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import joblib

from ..nba import cache
from ..nba.seasons import current_season, previous_season
from .artifacts import download_verified, publish_local, upload_s3_compatible
from .dataset import build_parquet, inspect_dataset, query_parquet
from .ingest import combine_raw, ingest_shots
from .manifest import DatasetManifest, sha256_file
from .training import (
    load_training_frame,
    log_mlflow,
    promote_candidate,
    save_candidate,
    train_xfg,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nba-pipeline")
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest = subcommands.add_parser("ingest", help="resumably fetch league-wide NBA shots")
    season_source = ingest.add_mutually_exclusive_group(required=True)
    season_source.add_argument("--season", action="append", dest="seasons")
    season_source.add_argument(
        "--recent-seasons",
        type=int,
        metavar="COUNT",
        help="ingest the current season and COUNT-1 preceding seasons",
    )
    ingest.add_argument("--raw-dir", type=Path, default=Path("data/raw/shots"))
    ingest.add_argument("--combined", type=Path)
    ingest.add_argument("--force", action="store_true")
    ingest.add_argument(
        "--current-max-age-hours",
        type=float,
        default=24,
        help="refresh current-season partitions older than this many hours",
    )

    validate = subcommands.add_parser("validate", help="validate a shot CSV or Parquet file")
    validate.add_argument("input", type=Path)
    validate.add_argument("--sample-rows", type=int)

    build = subcommands.add_parser("build", help="build partitioned Parquet and a manifest")
    build.add_argument("input", type=Path)
    build.add_argument("--output", type=Path, default=Path("data/processed/shots"))
    build.add_argument("--manifest", type=Path, default=Path("data/manifests/shots.json"))

    verify = subcommands.add_parser("verify", help="verify a dataset against its manifest")
    verify.add_argument("input", type=Path)
    verify.add_argument("manifest", type=Path)

    query = subcommands.add_parser("query", help="run read-only SQL against Parquet shots")
    query.add_argument("dataset", type=Path)
    query.add_argument("sql")

    pull = subcommands.add_parser("artifact-pull", help="download and checksum a model")
    pull.add_argument("url")
    pull.add_argument("--sha256", required=True)
    pull.add_argument("--output", type=Path, default=Path("data/models"))

    publish = subcommands.add_parser("artifact-publish", help="stage a versioned model release")
    publish.add_argument("model", type=Path)
    publish.add_argument("--destination", type=Path, default=Path("data/artifacts"))
    publish.add_argument("--version", required=True)
    publish.add_argument("--dataset-version", required=True)
    publish.add_argument("--bucket")
    publish.add_argument("--prefix", default="nba-stat-analyzer/models")
    publish.add_argument("--endpoint-url")
    publish.add_argument("--overwrite", action="store_true")

    train = subcommands.add_parser("train", help="train and evaluate an xFG v3 candidate")
    train.add_argument("input", type=Path)
    train.add_argument("--dataset-version", required=True)
    train.add_argument("--output", type=Path, default=Path("data/models/xfg-v3-candidate.joblib"))
    train.add_argument("--report", type=Path, default=Path("data/models/xfg-v3-evaluation.json"))
    train.add_argument("--incumbent", type=Path, default=Path("data/models/xfg.joblib"))
    train.add_argument("--incumbent-sha256")
    train.add_argument("--bootstrap-iterations", type=int, default=300)
    train.add_argument("--xgboost", action="store_true")
    train.add_argument("--mlflow", action="store_true")

    evaluate = subcommands.add_parser("evaluate", help="print a candidate's saved evaluation")
    evaluate.add_argument("model", type=Path)

    promote = subcommands.add_parser("promote", help="atomically promote a gated candidate")
    promote.add_argument("candidate", type=Path)
    promote.add_argument("--production", type=Path, default=Path("data/models/xfg.joblib"))
    promote.add_argument("--sha256", help="verify the candidate before deserializing it")
    promote.add_argument("--force", action="store_true")

    cache_prune = subcommands.add_parser(
        "cache-prune-pipeline",
        help="inspect or remove legacy team-season shot payloads from the runtime cache",
    )
    cache_prune.add_argument("--apply", action="store_true")
    cache_prune.add_argument("--vacuum", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if args.command == "ingest":
        seasons = args.seasons
        if args.recent_seasons is not None:
            if not 1 <= args.recent_seasons <= 10:
                raise ValueError("--recent-seasons must be between 1 and 10")
            newest = current_season()
            seasons = [newest]
            for _ in range(args.recent_seasons - 1):
                seasons.append(previous_season(seasons[-1]))
        ingestion_result = ingest_shots(
            seasons,
            args.raw_dir,
            force=args.force,
            refresh_current_after_hours=args.current_max_age_hours,
        )
        if args.combined:
            combine_raw(ingestion_result.paths, args.combined)
        print(json.dumps({
            "rows": ingestion_result.rows,
            "fetched_partitions": ingestion_result.fetched_partitions,
            "reused_partitions": ingestion_result.reused_partitions,
        }, indent=2))
    elif args.command == "validate":
        print(json.dumps(inspect_dataset(args.input, sample_rows=args.sample_rows).as_dict(), indent=2))
    elif args.command == "build":
        manifest = build_parquet(args.input, args.output, manifest_path=args.manifest)
        print(json.dumps({"dataset_version": manifest.dataset_version, "rows": manifest.rows}, indent=2))
    elif args.command == "verify":
        DatasetManifest.read(args.manifest).verify(args.input)
        print("Dataset checksum verified")
    elif args.command == "query":
        print(query_parquet(args.dataset, args.sql).to_string(index=False))
    elif args.command == "artifact-pull":
        print(download_verified(args.url, args.output, expected_sha256=args.sha256))
    elif args.command == "artifact-publish":
        release = publish_local(
            args.model,
            args.destination,
            version=args.version,
            metadata={"dataset_version": args.dataset_version},
            overwrite=args.overwrite,
        )
        if args.bucket:
            upload_s3_compatible(
                release,
                bucket=args.bucket,
                prefix=args.prefix,
                endpoint_url=args.endpoint_url,
            )
        print(release)
    elif args.command == "train":
        incumbent = None
        if args.incumbent.exists():
            if (
                args.incumbent_sha256
                and sha256_file(args.incumbent) != args.incumbent_sha256
            ):
                raise RuntimeError("Incumbent checksum does not match the expected SHA-256")
            incumbent = joblib.load(args.incumbent)
        training_result = train_xfg(
            load_training_frame(args.input),
            dataset_version=args.dataset_version,
            include_xgboost=args.xgboost,
            bootstrap_iterations=args.bootstrap_iterations,
            incumbent=incumbent,
        )
        save_candidate(training_result, args.output, args.report)
        if args.mlflow:
            log_mlflow(training_result)
        print(json.dumps({
            "candidate": str(args.output),
            "winner": training_result.evaluation["winner"],
            "metrics": training_result.evaluation["test"],
            "promotion_gate_passed": training_result.promoted,
        }, indent=2))
    elif args.command == "evaluate":
        bundle = joblib.load(args.model)
        print(json.dumps(bundle.get("evaluation", bundle.get("meta", {})), indent=2))
    elif args.command == "promote":
        checksum = promote_candidate(
            args.candidate,
            args.production,
            force=args.force,
            expected_sha256=args.sha256,
        )
        print(json.dumps({"production": str(args.production), "sha256": checksum}, indent=2))
    elif args.command == "cache-prune-pipeline":
        before = (
            cache.prune_pipeline_payloads(vacuum=args.vacuum)
            if args.apply
            else cache.pipeline_payload_stats()
        )
        print(json.dumps({
            "applied": args.apply,
            "removed_or_removable": before,
            "cache": cache.stats(),
        }, indent=2))


if __name__ == "__main__":
    main()
