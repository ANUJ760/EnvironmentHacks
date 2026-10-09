"""Streaming storage contract and strict keys."""

import hashlib
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

from ecotwin.errors import TwinError


def safe_key(key: str) -> str:
    path = PurePosixPath(key)
    if (
        not key
        or key.startswith("/")
        or "\\" in key
        or any(p in {".", "..", ""} for p in key.split("/"))
        or path.parts[0] not in {"raw", "processed", "results", "manifests"}
    ):
        raise TwinError(
            "INVALID_OBJECT_KEY", "Object key must be relative under an approved prefix"
        )
    return key


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    if len(expected) != 64 or file_digest(path) != expected:
        raise TwinError("DATASET_CHECKSUM_MISMATCH", "Object differs from its pinned SHA256")


class ObjectStore(Protocol):
    def open_read(self, key: str) -> BinaryIO: ...
    def put_file(self, key: str, source_path: Path, sha256: str) -> None: ...
    def materialize(self, key: str, expected_sha256: str) -> Path: ...
    def exists(self, key: str) -> bool: ...
