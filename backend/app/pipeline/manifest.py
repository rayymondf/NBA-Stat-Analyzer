"""Content-addressed manifests for datasets and deployable model artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def directory_inventory(path: Path) -> tuple[list[dict[str, Any]], str]:
    files = []
    for item in sorted(path.rglob("*.parquet")):
        files.append({
            "path": item.relative_to(path).as_posix(),
            "size_bytes": item.stat().st_size,
            "sha256": sha256_file(item),
        })
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return files, hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    schema_version: str
    dataset_version: str
    created_at: str
    sha256: str
    rows: int
    seasons: list[str]
    columns: list[str]
    source: str
    partitions: list[str] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    processed_sha256: str | None = None
    files: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        source_path: Path,
        *,
        rows: int,
        seasons: list[str],
        columns: list[str],
        source: str,
        partitions: list[str] | None = None,
        validation: dict[str, Any] | None = None,
        processed_dir: Path | None = None,
        schema_version: str = "shots-v1",
    ) -> DatasetManifest:
        checksum = sha256_file(source_path)
        files, processed_sha256 = (
            directory_inventory(processed_dir) if processed_dir else ([], None)
        )
        return cls(
            schema_version=schema_version,
            dataset_version=f"{schema_version}-{checksum[:12]}",
            created_at=datetime.now(UTC).isoformat(),
            sha256=checksum,
            rows=rows,
            seasons=sorted(seasons),
            columns=columns,
            source=source,
            partitions=partitions or [],
            validation=validation or {},
            processed_sha256=processed_sha256,
            files=files,
        )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def read(cls, path: Path) -> DatasetManifest:
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    def verify(self, source_path: Path) -> None:
        actual = sha256_file(source_path)
        if actual != self.sha256:
            raise ValueError(
                f"Dataset checksum mismatch: expected {self.sha256}, found {actual}"
            )

    def verify_processed(self, dataset_dir: Path) -> None:
        files, checksum = directory_inventory(dataset_dir)
        if not self.processed_sha256 or checksum != self.processed_sha256:
            raise ValueError(
                "Processed dataset checksum mismatch: "
                f"expected {self.processed_sha256}, found {checksum}"
            )
        if files != self.files:
            raise ValueError("Processed dataset inventory does not match its manifest")
