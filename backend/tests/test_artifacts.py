from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from app.pipeline.artifacts import (
    ArtifactVerificationError,
    download_verified,
    publish_local,
    upload_s3_compatible,
)


class FakeResponse:
    def __init__(self, *, payload=None, content: bytes = b"", error: Exception | None = None):
        self.payload = payload
        self.content = content
        self.error = error

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error

    def json(self):
        return self.payload

    def iter_content(self, _size: int):
        midpoint = max(1, len(self.content) // 2)
        yield self.content[:midpoint]
        yield self.content[midpoint:]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _index(content: bytes, **patch) -> dict:
    result = {
        "schema_version": "model-artifact-v1",
        "version": "v3-test",
        "filename": "xfg.joblib",
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
        "metadata": {"dataset_version": "fixture"},
    }
    result.update(patch)
    return result


def _mock_download(monkeypatch, index: dict, content: bytes) -> None:
    def get(url: str, **_kwargs):
        return (
            FakeResponse(content=json.dumps(index).encode())
            if url.endswith("index.json")
            else FakeResponse(content=content)
        )

    monkeypatch.setattr("app.pipeline.artifacts.requests.get", get)


def test_verified_download_is_streamed_and_atomic(tmp_path: Path, monkeypatch):
    content = b"verified model bytes"
    index = _index(content)
    _mock_download(monkeypatch, index, content)

    result = download_verified(
        "https://objects.example/releases/v3",
        tmp_path,
        expected_sha256=index["sha256"],
    )

    assert result.read_bytes() == content
    assert not list(tmp_path.glob("*.download"))


@pytest.mark.parametrize(
    ("patch", "expected"),
    [
        ({"schema_version": "future"}, "schema"),
        ({"sha256": "not-a-digest"}, "SHA-256"),
        ({"filename": "../unsafe.joblib"}, "filename"),
        ({"size_bytes": 0}, "size"),
    ],
)
def test_download_rejects_untrusted_index(tmp_path: Path, monkeypatch, patch, expected):
    content = b"model"
    _mock_download(monkeypatch, _index(content, **patch), content)
    with pytest.raises(ArtifactVerificationError, match=expected):
        download_verified("https://objects.example/v3", tmp_path)


def test_download_rejects_pin_size_and_content_mismatch(tmp_path: Path, monkeypatch):
    content = b"model"
    index = _index(content)
    _mock_download(monkeypatch, index, content)
    with pytest.raises(ArtifactVerificationError, match="pinned"):
        download_verified(
            "https://objects.example/v3",
            tmp_path,
            expected_sha256="0" * 64,
        )

    _mock_download(monkeypatch, _index(content, size_bytes=2), content)
    with pytest.raises(ArtifactVerificationError, match="exceeded"):
        download_verified("https://objects.example/v3", tmp_path)

    _mock_download(monkeypatch, _index(content), b"tampered")
    with pytest.raises(ArtifactVerificationError, match=r"exceeded|size mismatch|checksum"):
        download_verified("https://objects.example/v3", tmp_path)


def test_download_propagates_http_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.artifacts.requests.get",
        lambda *_args, **_kwargs: FakeResponse(error=requests.HTTPError("not found")),
    )
    with pytest.raises(requests.HTTPError):
        download_verified("https://objects.example/missing", tmp_path)


def test_local_overwrite_is_staged(tmp_path: Path):
    model = tmp_path / "xfg.joblib"
    model.write_bytes(b"first")
    destination = tmp_path / "releases"
    publish_local(model, destination, version="v3", metadata={})
    model.write_bytes(b"second")

    release = publish_local(model, destination, version="v3", metadata={}, overwrite=True)

    assert (release / "xfg.joblib").read_bytes() == b"second"
    assert json.loads((release / "index.json").read_text())["size_bytes"] == 6
    assert not (destination / ".v3.previous").exists()


def test_s3_upload_verifies_each_object_and_publishes_index_last(
    tmp_path: Path, monkeypatch
):
    release = tmp_path / "v3-test"
    release.mkdir()
    (release / "xfg.joblib").write_bytes(b"model")
    (release / "index.json").write_text("{}")
    uploaded: list[str] = []
    remote: dict[str, tuple[int, str]] = {}

    class FakeClient:
        def upload_file(self, source, _bucket, key, ExtraArgs):
            uploaded.append(key)
            remote[key] = (Path(source).stat().st_size, ExtraArgs["Metadata"]["sha256"])

        def head_object(self, *, Bucket, Key):
            size, digest = remote[Key]
            return {"ContentLength": size, "Metadata": {"sha256": digest}}

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *_a, **_k: FakeClient()))
    upload_s3_compatible(release, bucket="models", prefix="nba/models")

    assert uploaded == [
        "nba/models/v3-test/xfg.joblib",
        "nba/models/v3-test/index.json",
    ]
