from ecotwin.config import Settings
from ecotwin.storage.local import LocalObjectStore


def object_store(settings: Settings, digests=None):
    local = LocalObjectStore(settings.ecotwin_local_data_dir)
    if settings.ecotwin_storage_mode == "local":
        return local
    from ecotwin.storage.s3 import S3ObjectStore

    cloud = S3ObjectStore(
        settings.ecotwin_s3_bucket,
        settings.aws_region,
        settings.ecotwin_cache_dir,
        settings.ecotwin_s3_prefix,
        settings.ecotwin_cache_quota_bytes,
    )
    if settings.ecotwin_storage_mode == "s3":
        return cloud
    from ecotwin.storage.checked_fallback import CheckedFallbackObjectStore

    return CheckedFallbackObjectStore(cloud, local, digests or {})
