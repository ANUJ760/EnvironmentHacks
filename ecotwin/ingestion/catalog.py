from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from geoalchemy2.shape import from_shape
from sqlalchemy import select

from ecotwin.config import get_settings
from ecotwin.db.models import DatasetRevision, ImportRun
from ecotwin.storage.base import file_digest
from ecotwin.storage.factory import object_store
from ecotwin.storage.manifest import DatasetManifest

current_import_run = ContextVar("current_import_run", default=None)

SOURCES = {
    "municipal_trees": (
        "City of Zurich",
        "CC0-1.0",
        "Grün Stadt Zürich · Baumkataster",
        "https://data.stadt-zuerich.ch/dataset/geo_baumkataster",
    ),
    "air_forecast": (
        "Open-Meteo CAMS",
        "Provider terms; CAMS attribution; review commercial use",
        "CAMS ENSEMBLE / CAMS GHG via Open-Meteo",
        "https://open-meteo.com/en/docs/air-quality-api",
    ),
    "osm": (
        "OpenStreetMap",
        "ODbL-1.0",
        "© OpenStreetMap contributors",
        "https://www.openstreetmap.org/copyright",
    ),
    "worldcover": (
        "ESA WorldCover",
        "CC-BY-4.0",
        "ESA WorldCover 2021 v200",
        "https://esa-worldcover.org/en/data-access",
    ),
    "weather": (
        "Open-Meteo",
        "Provider terms; review intended commercial use",
        "Open-Meteo weather-model forecast",
        "https://open-meteo.com/en/terms",
    ),
    "air": (
        "OpenAQ",
        "Per-provider terms retained in station metadata",
        "OpenAQ and original observation providers",
        "https://docs.openaq.org",
    ),
}


def register_object(
    session, city, kind, path, coverage, quality, source_url=None, license_info=None
):
    digest = file_digest(path)
    existing = session.scalar(
        select(DatasetRevision).where(
            DatasetRevision.city_id == city.id,
            DatasetRevision.kind == kind,
            DatasetRevision.sha256 == digest,
        )
    )
    if existing:
        return existing, False
    provider, license_name, attribution, url = license_info or SOURCES[kind]
    captured = datetime.now(UTC)
    key = f"raw/{provider.lower().replace(' ', '-')}/{kind}/{digest}/{path.name}"
    store = object_store(get_settings())
    store.put_file(key, path, digest)
    revision = DatasetRevision(
        city_id=city.id,
        kind=kind,
        provider=provider,
        source_url=source_url or url,
        object_key=key,
        sha256=digest,
        byte_size=path.stat().st_size,
        source_license=license_name,
        attribution=attribution,
        acquired_at=captured,
        native_crs=quality.get("crs", "EPSG:4326"),
        resolution_m=quality.get("resolution_m"),
        coverage=from_shape(coverage, srid=4326) if coverage is not None else None,
        status="READY",
        quality_json=quality,
    )
    session.add(revision)
    session.flush()
    from shapely.geometry import mapping

    manifest = DatasetManifest(
        city_id=str(city.id),
        source_url=revision.source_url,
        sha256=digest,
        byte_size=revision.byte_size,
        media_type="application/octet-stream",
        crs=revision.native_crs,
        coverage=dict(mapping(coverage)) if coverage is not None else None,
        native_units=quality.get("native_units", {}),
        normalized_units=quality.get("normalized_units", {}),
        captured_at=captured,
        source_license=license_name,
        attribution=attribution,
        processing_version="ingest-v1",
        upstream_revision=quality.get("version", "source-bytes"),
    )
    import tempfile

    get_settings().ecotwin_cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, dir=get_settings().ecotwin_cache_dir
    ) as temporary:
        temporary.write(manifest.model_dump_json())
        manifest_path = Path(temporary.name)
    try:
        store.put_file(f"manifests/{revision.id}.json", manifest_path, file_digest(manifest_path))
    finally:
        manifest_path.unlink(missing_ok=True)
    return revision, True


def successful_run(session, revision, count, rejected=0):
    now = datetime.now(UTC)
    identifier = current_import_run.get()
    run = session.get(ImportRun, identifier) if identifier else None
    if run is None:
        run = ImportRun(started_at=now, details_json={})
        session.add(run)
    run.dataset_revision_id = revision.id
    run.status = "SUCCEEDED"
    run.finished_at = now
    run.rows_read = count + rejected
    run.rows_imported = count
    run.rows_rejected = rejected
    run.details_json = {"complete": rejected == 0}
