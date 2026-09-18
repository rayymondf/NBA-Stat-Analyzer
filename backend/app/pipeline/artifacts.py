"""Verified local and S3-compatible model artifact transport."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from .manifest import sha256_file


class ArtifactVerificationError(RuntimeError):
    pass


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
MAX_INDEX_BYTES = 1024 * 1024


def artifact_index(model_path: Path, *, version: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "model-artifact-v1",
        "version": version,
        "filename": model_path.name,
        "sha256": sha256_file(model_path),
        "size_bytes": model_path.stat().st_size,
        "metadata": metadata,
    }


def publish_local(
    model_path: Path,
    destination: Path,
    *,
    version: str,
    metadata: dict[str, Any],
    overwrite: bool = False,
) -> Path:
    release = destination / version
    if release.exists() and not overwrite:
        raise FileExistsError(f"Immutable artifact release already exists: {release}")
    destination.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{version}.", dir=destination))
    target = stage / model_path.name
    try:
        shutil.copy2(model_path, target)
        index = artifact_index(target, version=version, metadata=metadata)
        (stage / "index.json").write_text(
            json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if release.exists():
            backup = destination / f".{version}.previous"
            if backup.exists():
                shutil.rmtree(backup)
            release.replace(backup)
            try:
                stage.replace(release)
            except Exception:
                backup.replace(release)
                raise
            shutil.rmtree(backup)
        else:
            stage.replace(release)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return release


def download_verified(
    base_url: str,
    destination: Path,
    *,
    expected_sha256: str | None = None,
    max_size_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
    timeout: float = 60,
) -> Path:
    """Download an index + model from a public/presigned R2/S3 HTTP prefix."""
    base = base_url.rstrip("/")
    with requests.get(f"{base}/index.json", timeout=timeout, stream=True) as index_response:
        index_response.raise_for_status()
        index_chunks: list[bytes] = []
        index_bytes = 0
        for chunk in index_response.iter_content(64 * 1024):
            if chunk:
                index_bytes += len(chunk)
                if index_bytes > MAX_INDEX_BYTES:
                    raise ArtifactVerificationError("Artifact index exceeds the size limit")
                index_chunks.append(chunk)
    try:
        index = json.loads(b"".join(index_chunks))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactVerificationError("Artifact index is not valid JSON") from exc
    if not isinstance(index, dict) or index.get("schema_version") != "model-artifact-v1":
        raise ArtifactVerificationError("Artifact index has an unsupported schema")
    digest = index.get("sha256")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise ArtifactVerificationError("Artifact index has an invalid SHA-256")
    if expected_sha256 and index.get("sha256") != expected_sha256:
        raise ArtifactVerificationError("Artifact index does not match the pinned SHA-256")
    if expected_sha256 and not SHA256_PATTERN.fullmatch(expected_sha256):
        raise ArtifactVerificationError("Pinned artifact SHA-256 is invalid")
    declared_filename = index.get("filename")
    if not isinstance(declared_filename, str) or not declared_filename:
        raise ArtifactVerificationError("Artifact filename is missing or invalid")
    filename = Path(declared_filename).name
    if filename != declared_filename:
        raise ArtifactVerificationError("Artifact filename is not safe")

    declared_size = index.get("size_bytes")
    if not isinstance(declared_size, int) or not 0 < declared_size <= max_size_bytes:
        raise ArtifactVerificationError("Artifact size is invalid or exceeds the configured limit")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / filename
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{filename}.", suffix=".download", dir=destination
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        downloaded = 0
        with requests.get(f"{base}/{quote(filename)}", timeout=timeout, stream=True) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        downloaded += len(chunk)
                        if downloaded > declared_size or downloaded > max_size_bytes:
                            raise ArtifactVerificationError("Artifact exceeded its declared size")
                        handle.write(chunk)
        if downloaded != declared_size:
            raise ArtifactVerificationError(
                f"Artifact size mismatch: expected {declared_size}, found {downloaded}"
            )
        actual = sha256_file(temporary)
        if actual != digest:
            raise ArtifactVerificationError(
                f"Artifact checksum mismatch: expected {digest}, found {actual}"
            )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def upload_s3_compatible(
    release_dir: Path,
    *,
    bucket: str,
    prefix: str,
    endpoint_url: str | None = None,
) -> None:
    """Upload a release to AWS S3, Cloudflare R2, or another S3-compatible store."""
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - optional production path
        raise RuntimeError("Install the 'pipeline' extra to upload artifacts") from exc
    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    paths = sorted(path for path in release_dir.iterdir() if path.is_file())
    paths.sort(key=lambda path: path.name == "index.json")
    for path in paths:
        if path.is_file():
            key = "/".join(part.strip("/") for part in (prefix, release_dir.name, path.name))
            checksum = sha256_file(path)
            client.upload_file(
                str(path), bucket, key, ExtraArgs={"Metadata": {"sha256": checksum}}
            )
            remote = client.head_object(Bucket=bucket, Key=key)
            if (
                int(remote.get("ContentLength", -1)) != path.stat().st_size
                or remote.get("Metadata", {}).get("sha256") != checksum
            ):
                raise ArtifactVerificationError(f"Remote verification failed for s3://{bucket}/{key}")
