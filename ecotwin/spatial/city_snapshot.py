from pathlib import Path

from sqlalchemy import select

from ecotwin.config import get_settings
from ecotwin.db.models import CitySnapshot, DatasetRevision
from ecotwin.errors import TwinError
from ecotwin.simulation.command import canonical_digest
from ecotwin.storage.factory import object_store


def parameter_documents():
    import yaml

    package = Path(__file__).resolve().parents[1]
    root = package / "model_parameters"
    if not root.is_dir():
        root = package.parent / "model_parameters"
    if not root.is_dir():
        raise TwinError("DATASET_NOT_READY", "Installed model parameter resources are missing")
    return {p.name: yaml.safe_load(p.read_text()) for p in sorted(root.glob("*.yaml"))}


def publish_snapshot(session, city):
    revisions = list(
        session.scalars(
            select(DatasetRevision)
            .where(DatasetRevision.city_id == city.id, DatasetRevision.status == "READY")
            .order_by(DatasetRevision.acquired_at.desc(), DatasetRevision.id)
        )
    )
    latest = {}
    for revision in revisions:
        latest.setdefault(revision.kind, revision)
    if not {"osm", "worldcover", "weather"} <= latest.keys():
        raise TwinError(
            "INSUFFICIENT_INPUT_DATA",
            "Import OSM, WorldCover and weather before publishing",
            missing_inputs=sorted({"osm", "worldcover", "weather"} - latest.keys()),
        )
    selected = sorted(latest.values(), key=lambda r: r.kind)
    store = object_store(get_settings(), {r.object_key: r.sha256 for r in selected})
    for revision in selected:
        store.materialize(revision.object_key, revision.sha256)
    parameters = parameter_documents()
    from geoalchemy2.shape import to_shape
    from shapely.geometry import mapping

    snapshot = CitySnapshot(
        city_id=city.id,
        dataset_revision_ids=[r.id for r in selected],
        composite_input_sha256=canonical_digest(
            {
                "city_id": str(city.id),
                "boundary": mapping(to_shape(city.boundary)),
                "analysis_srid": city.analysis_srid,
                "processing_version": "ingest-v1",
                "datasets": [{"kind": r.kind, "sha256": r.sha256} for r in selected],
            }
        ),
        model_config_sha256=canonical_digest(parameters),
        baseline_summary={
            "schema_version": 1,
            "parameters": parameters,
            "capabilities": list(latest),
            "reference_year": 2021,
        },
        status="PUBLISHED",
    )
    session.add(snapshot)
    session.flush()
    return snapshot
