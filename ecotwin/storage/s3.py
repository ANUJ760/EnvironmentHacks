import hashlib
import os
import tempfile
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ecotwin.errors import TwinError
from ecotwin.storage.base import safe_key, verify


class S3ObjectStore:
    def __init__(
        self,
        bucket: str,
        region: str,
        cache: Path,
        prefix: str = "ecotwin/",
        quota: int = 8_000_000_000,
        client=None,
    ):
        self.bucket, self.prefix, self.cache, self.quota = bucket, prefix, cache, quota
        self.client = client or boto3.client(
            "s3",
            region_name=region,
            config=Config(
                connect_timeout=5, read_timeout=30, retries={"max_attempts": 3, "mode": "standard"}
            ),
        )

    def remote_key(self, key):
        return self.prefix + safe_key(key)

    def call(self, method, **kwargs):
        try:
            return getattr(self.client, method)(Bucket=self.bucket, **kwargs)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in {
                "AccessDenied",
                "InvalidAccessKeyId",
                "SignatureDoesNotMatch",
                "ExpiredToken",
            }:
                raise TwinError(
                    "STORAGE_PERMISSION_DENIED", "S3 credentials or permissions rejected", 503
                ) from exc
            if code in {"PreconditionFailed", "412", "ConditionalRequestConflict"}:
                raise TwinError(
                    "OBJECT_ALREADY_EXISTS", "Conditional object write refused", 409
                ) from exc
            if code in {"NoSuchKey", "404", "NotFound"}:
                raise TwinError("DATASET_NOT_FOUND", "Pinned object is missing", 404) from exc
            raise TwinError("STORAGE_UNAVAILABLE", "S3 service unavailable", 503) from exc
        except BotoCoreError as exc:
            raise TwinError("STORAGE_UNAVAILABLE", "S3 transport unavailable", 503) from exc

    def exists(self, key):
        try:
            self.call("head_object", Key=self.remote_key(key))
            return True
        except TwinError as exc:
            if exc.code == "DATASET_NOT_FOUND":
                return False
            raise

    def open_read(self, key):
        return self.call("get_object", Key=self.remote_key(key))["Body"]

    def put_file(self, key, source_path, sha256):
        verify(source_path, sha256)
        # Conditional PUT is atomic, refuses overwrite; input is streamed.
        if source_path.stat().st_size > 5_000_000_000:
            raise TwinError(
                "MODEL_INPUT_UNSUPPORTED", "Split source objects larger than 5 GB before import"
            )
        with source_path.open("rb") as source:
            try:
                self.call(
                    "put_object",
                    Key=self.remote_key(key),
                    Body=source,
                    IfNoneMatch="*",
                    ServerSideEncryption="AES256",
                    Metadata={"sha256": sha256},
                )
            except TwinError as exc:
                if exc.code != "OBJECT_ALREADY_EXISTS":
                    raise
                if not self.exists(key):
                    raise
                # Verify bytes, not solely mutable metadata.
                self.materialize(key, sha256)

    def materialize(self, key, expected_sha256):
        safe_key(key)
        self.cache.mkdir(parents=True, exist_ok=True)
        target = self.cache / hashlib.sha256(key.encode()).hexdigest()
        if target.exists():
            verify(target, expected_sha256)
            return target
        fd, name = tempfile.mkstemp(dir=self.cache, suffix=".part")
        temporary = Path(name)
        try:
            used = sum(p.stat().st_size for p in self.cache.iterdir() if p.is_file())
            body = self.open_read(key)
            with os.fdopen(fd, "wb") as out:
                try:
                    for chunk in iter(lambda: body.read(1024 * 1024), b""):
                        used += len(chunk)
                        if used > self.quota:
                            raise TwinError(
                                "STORAGE_UNAVAILABLE",
                                "Cache quota exceeded; clear unpinned cache",
                                503,
                            )
                        out.write(chunk)
                finally:
                    body.close()
                out.flush()
                os.fsync(out.fileno())
            verify(temporary, expected_sha256)
            os.replace(temporary, target)
            return target
        finally:
            temporary.unlink(missing_ok=True)
