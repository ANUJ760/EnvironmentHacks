import structlog
from ecotwin.errors import TwinError
from ecotwin.storage.base import ObjectStore

class CheckedFallbackObjectStore:
    def __init__(self,primary: ObjectStore,local: ObjectStore,digests: dict[str,str]):
        self.primary,self.local,self.digests=primary,local,digests
        self.data_served_from='s3'
    def materialize(self,key,expected_sha256):
        if self.digests.get(key) != expected_sha256:
            raise TwinError('DATASET_CHECKSUM_MISMATCH','Fallback requires pinned manifest digest')
        try:
            return self.primary.materialize(key,expected_sha256)
        except TwinError as exc:
            if exc.code != 'STORAGE_UNAVAILABLE':
                raise
            path=self.local.materialize(key,expected_sha256)
            self.data_served_from='local_verified_cache'
            structlog.get_logger().warning('storage_fallback',key=key,data_served_from=self.data_served_from)
            return path
    def open_read(self,key):
        if key not in self.digests:
            raise TwinError('DATASET_NOT_READY','Manifest digest required')
        return self.materialize(key,self.digests[key]).open('rb')
    def exists(self,key):
        try:
            self.materialize(key,self.digests[key])
            return True
        except TwinError as exc:
            if exc.code == 'DATASET_NOT_FOUND':
                return False
            raise
    def put_file(self,key,source_path,sha256):
        self.primary.put_file(key,source_path,sha256)
