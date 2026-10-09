import os
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from ecotwin.errors import TwinError
from ecotwin.storage.base import safe_key, verify


class LocalObjectStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        target = self.root / safe_key(key)
        if not target.resolve().is_relative_to(self.root):
            raise TwinError("INVALID_OBJECT_KEY", "Symlink escapes storage root")
        return target

    def open_read(self, key: str) -> BinaryIO:
        try:
            return self.path(key).open("rb")
        except FileNotFoundError as exc:
            raise TwinError(
                "DATASET_NOT_FOUND", "Download and import the pinned dataset", 404
            ) from exc

    def exists(self, key: str) -> bool:
        return self.path(key).is_file()

    def materialize(self, key: str, expected_sha256: str) -> Path:
        target = self.path(key)
        if not target.is_file():
            raise TwinError("DATASET_NOT_FOUND", "Download and import the pinned dataset", 404)
        verify(target, expected_sha256)
        return target

    def put_file(self, key: str, source_path: Path, sha256: str) -> None:
        verify(source_path, sha256)
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            verify(target, sha256)
            return
        fd, name = tempfile.mkstemp(dir=target.parent, suffix=".part")
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as destination, source_path.open("rb") as source:
                shutil.copyfileobj(source, destination, 1024 * 1024)
                destination.flush()
                os.fsync(destination.fileno())
            verify(temporary, sha256)
            try:
                os.link(temporary, target)  # atomic no-overwrite publication
            except FileExistsError:
                verify(target, sha256)
        finally:
            temporary.unlink(missing_ok=True)
