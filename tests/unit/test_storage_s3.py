import hashlib
import io

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from ecotwin.errors import TwinError
from ecotwin.storage.s3 import S3ObjectStore


class S3:
    def __init__(self):
        self.objects = {}
        self.error = None

    def fail(self):
        if self.error == "network":
            raise EndpointConnectionError(endpoint_url="https://s3.amazonaws.com")
        if self.error:
            raise ClientError({"Error": {"Code": self.error}}, "GetObject")

    def head_object(self, **kwargs):
        self.fail()
        if kwargs["Key"] not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}

    def get_object(self, **kwargs):
        self.fail()
        if kwargs["Key"] not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[kwargs["Key"]])}

    def put_object(self, **kwargs):
        self.fail()
        assert kwargs["ServerSideEncryption"] == "AES256" and kwargs["IfNoneMatch"] == "*"
        if kwargs["Key"] in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.objects[kwargs["Key"]] = kwargs["Body"].read()
        return {}


def test_s3_streaming_cache_and_conditional_write(tmp_path):
    client = S3()
    store = S3ObjectStore("bucket", "ap-south-1", tmp_path / "cache", client=client)
    source = tmp_path / "input"
    source.write_bytes(b"x" * (3 * 1024 * 1024))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    store.put_file("raw/test", source, digest)
    store.put_file("raw/test", source, digest)
    assert store.exists("raw/test")
    path = store.materialize("raw/test", digest)
    assert path.stat().st_size == source.stat().st_size
    assert store.materialize("raw/test", digest) == path
    assert not store.exists("raw/missing")
    with pytest.raises(TwinError):
        store.materialize("raw/test", "a" * 64)


@pytest.mark.parametrize(
    "error,code",
    [
        ("AccessDenied", "STORAGE_PERMISSION_DENIED"),
        ("ExpiredToken", "STORAGE_PERMISSION_DENIED"),
        ("NoSuchKey", "DATASET_NOT_FOUND"),
        ("network", "STORAGE_UNAVAILABLE"),
        ("InternalError", "STORAGE_UNAVAILABLE"),
    ],
)
def test_s3_error_mapping(tmp_path, error, code):
    client = S3()
    client.error = error
    store = S3ObjectStore("bucket", "ap-south-1", tmp_path, client=client)
    with pytest.raises(TwinError) as exc:
        store.open_read("raw/source")
    assert exc.value.code == code


def test_cache_quota(tmp_path):
    client = S3()
    client.objects["ecotwin/raw/test"] = b"too large"
    store = S3ObjectStore("bucket", "ap-south-1", tmp_path, quota=2, client=client)
    with pytest.raises(TwinError):
        store.materialize("raw/test", hashlib.sha256(b"too large").hexdigest())
    assert not list(tmp_path.glob("*.part"))
