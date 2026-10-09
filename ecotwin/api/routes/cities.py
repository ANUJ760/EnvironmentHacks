from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import mapping
from sqlalchemy import func, select

from ecotwin.api.schemas import (
    AirView,
    CityView,
    DatasetView,
    FeatureCollection,
    LandcoverView,
    WeatherView,
)
from ecotwin.db.models import (
    AirObservation,
    AirStation,
    City,
    CitySnapshot,
    DatasetRevision,
    GeoFeature,
    WeatherHour,
)
from ecotwin.db.session import session_dependency
from ecotwin.errors import TwinError
from ecotwin.models.landcover import class_areas
from ecotwin.models.registry import MODELS, UNSUPPORTED
from ecotwin.spatial.geometry import bbox_geometry, validate_area
from ecotwin.spatial.spatial_queries import load_cover

router = APIRouter(prefix="/v1", tags=["cities"])


def city_row(session, identifier):
    row = session.get(City, identifier)
    if not row:
        raise TwinError("CITY_NOT_FOUND", "City not found", 404)
    return row


def active_snapshot(session, city_id):
    row = session.scalar(
        select(CitySnapshot)
        .where(CitySnapshot.city_id == city_id, CitySnapshot.status == "PUBLISHED")
        .order_by(CitySnapshot.created_at.desc())
        .limit(1)
    )
    if not row:
        raise TwinError("DATASET_NOT_READY", "Publish a verified city snapshot first")
    return row


def city_document(session, row):
    snapshot = session.scalar(
        select(CitySnapshot)
        .where(CitySnapshot.city_id == row.id, CitySnapshot.status == "PUBLISHED")
        .order_by(CitySnapshot.created_at.desc())
        .limit(1)
    )
    return {
        "id": str(row.id),
        "slug": row.slug,
        "display_name": row.display_name,
        "boundary": mapping(to_shape(row.boundary)),
        "analysis_srid": row.analysis_srid,
        "timezone": row.timezone,
        "status": row.status,
        "active_snapshot_id": str(snapshot.id) if snapshot else None,
        "capabilities": snapshot.baseline_summary["capabilities"] if snapshot else [],
    }


@router.get("/cities", response_model=list[CityView])
def cities(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: UUID | None = None,
    session=Depends(session_dependency),
):
    query = select(City).order_by(City.id)
    if cursor:
        query = query.where(City.id > cursor)
    return [city_document(session, row) for row in session.scalars(query.limit(limit))]


@router.get("/cities/{identifier}", response_model=CityView)
def get_city(identifier: UUID, session=Depends(session_dependency)):
    return city_document(session, city_row(session, identifier))


@router.get("/cities/{identifier}/features", response_model=FeatureCollection)
def features(
    identifier: UUID,
    bbox: str,
    category: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    cursor: UUID | None = None,
    session=Depends(session_dependency),
):
    city = city_row(session, identifier)
    snapshot = active_snapshot(session, identifier)
    viewport = bbox_geometry(bbox)
    validate_area(viewport, city.analysis_srid)
    query = (
        select(GeoFeature)
        .where(
            GeoFeature.city_id == identifier,
            GeoFeature.revision_id.in_(snapshot.dataset_revision_ids),
            func.ST_Intersects(GeoFeature.geom, from_shape(viewport, srid=4326)),
        )
        .order_by(GeoFeature.id)
    )
    if category:
        query = query.where(GeoFeature.category == category)
    if cursor:
        query = query.where(GeoFeature.id > cursor)
    rows = list(session.scalars(query.limit(limit)))
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": str(row.id),
                "geometry": mapping(to_shape(row.geom)),
                "properties": {
                    "provider_feature_id": row.provider_feature_id,
                    "category": row.category,
                    "tags": row.tags,
                    "source_revision_id": str(row.revision_id),
                    "area_m2": float(row.area_m2) if row.area_m2 is not None else None,
                },
            }
            for row in rows
        ],
        "next_cursor": str(rows[-1].id) if len(rows) == limit else None,
    }


@router.get("/cities/{identifier}/landcover", response_model=LandcoverView)
def landcover(identifier: UUID, session=Depends(session_dependency)):
    city = city_row(session, identifier)
    snapshot = active_snapshot(session, identifier)
    areas = class_areas(load_cover(session, snapshot, city))
    total = sum(areas.values())
    return {
        "reference_year": 2021,
        "class_areas_m2": areas,
        "class_percentages": {key: value / total * 100 for key, value in areas.items()},
        "covered_area_m2": total,
        "city_area_m2": validate_area(to_shape(city.boundary), city.analysis_srid),
        "source_revision_ids": [str(value) for value in snapshot.dataset_revision_ids],
        "limitations": ["classification_not_tree_inventory", "2021_reference"],
    }


@router.get("/cities/{identifier}/datasets", response_model=list[DatasetView])
def datasets(
    identifier: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: UUID | None = None,
    session=Depends(session_dependency),
):
    city_row(session, identifier)
    query = (
        select(DatasetRevision)
        .where(DatasetRevision.city_id == identifier)
        .order_by(DatasetRevision.id)
    )
    if cursor:
        query = query.where(DatasetRevision.id > cursor)
    return [
        {
            "id": str(row.id),
            "kind": row.kind,
            "provider": row.provider,
            "source_url": row.source_url,
            "sha256": row.sha256,
            "byte_size": row.byte_size,
            "source_license": row.source_license,
            "attribution": row.attribution,
            "acquired_at": row.acquired_at,
            "coverage": mapping(to_shape(row.coverage)) if row.coverage is not None else None,
            "status": row.status,
            "quality": row.quality_json,
        }
        for row in session.scalars(query.limit(limit))
    ]


@router.get("/cities/{identifier}/observations/weather", response_model=WeatherView)
def weather(
    identifier: UUID,
    start: datetime | None = None,
    end: datetime | None = None,
    session=Depends(session_dependency),
):
    city_row(session, identifier)
    snapshot = active_snapshot(session, identifier)
    if start and (not start.tzinfo or not end or not end.tzinfo or end <= start):
        raise TwinError("INVALID_REQUEST", "Timezone-aware increasing start/end required")
    query = (
        select(WeatherHour)
        .where(
            WeatherHour.city_id == identifier,
            WeatherHour.revision_id.in_(snapshot.dataset_revision_ids),
        )
        .order_by(WeatherHour.valid_at)
        .limit(384)
    )
    if start:
        query = query.where(WeatherHour.valid_at >= start, WeatherHour.valid_at < end)
    rows = list(session.scalars(query))
    if not rows:
        return {"status": "UNAVAILABLE", "reason_code": "INSUFFICIENT_INPUT_DATA", "series": []}
    age = (datetime.now(UTC) - rows[0].issued_at).total_seconds() / 3600
    return {
        "evidence_class": "SCREENING_ESTIMATE",
        "spatial_scope": "coarse_forecast_grid",
        "age_hours": age,
        "stale": age > 6,
        "current": age <= 12,
        "series": [
            {
                key: getattr(row, key)
                for key in [
                    "valid_at",
                    "issued_at",
                    "temperature_c",
                    "rain_mm",
                    "humidity_pct",
                    "wind_mps",
                    "ghi_w_m2",
                    "model_name",
                    "source_lat",
                    "source_lon",
                ]
            }
            for row in rows
        ],
    }


@router.get("/cities/{identifier}/observations/air", response_model=AirView)
def air(
    identifier: UUID,
    parameter: str = "pm25",
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    session=Depends(session_dependency),
):
    city = city_row(session, identifier)
    snapshot = active_snapshot(session, identifier)
    rows = session.execute(
        select(AirObservation, AirStation)
        .join(AirStation, AirObservation.station_id == AirStation.id)
        .where(
            AirObservation.revision_id.in_(snapshot.dataset_revision_ids),
            AirObservation.parameter == parameter,
            func.ST_Intersects(AirStation.location, city.boundary),
        )
        .order_by(AirObservation.measured_at.desc())
        .limit(limit)
    ).all()
    readings = [
        {
            "station_id": str(station.id),
            "station_name": station.name,
            "location": mapping(to_shape(station.location)),
            "parameter": row.parameter,
            "value": row.value,
            "unit": row.unit,
            "measured_at": row.measured_at,
            "source_url": row.source_url,
            "revision_id": str(row.revision_id),
            "stale": (datetime.now(UTC) - row.measured_at).total_seconds() > 21600,
            "distance_from_city_centroid_m": float(
                session.scalar(
                    select(
                        func.ST_Distance(
                            func.ST_Transform(station.location, city.analysis_srid),
                            func.ST_Transform(func.ST_Centroid(city.boundary), city.analysis_srid),
                        )
                    )
                )
            ),
        }
        for row, station in rows
    ]
    return {
        "evidence_class": "OBSERVED" if readings else "UNAVAILABLE",
        "reason_code": None if readings else "INSUFFICIENT_INPUT_DATA",
        "spatial_scope": "station_only",
        "readings": readings,
    }


@router.get("/models", response_model=dict)
def models(city_id: UUID | None = None, session=Depends(session_dependency)):
    kinds = set()
    if city_id:
        city_row(session, city_id)
        snapshot = active_snapshot(session, city_id)
        kinds = set(snapshot.baseline_summary["capabilities"])
    return {
        "models": [
            {
                "id": name,
                **contract,
                "available": all(
                    k in kinds
                    for k in contract["required_inputs"]
                    if k in {"worldcover", "weather", "waste"}
                ),
                "additional_user_inputs": [
                    k
                    for k in contract["required_inputs"]
                    if k not in {"worldcover", "weather", "waste"}
                ],
            }
            for name, contract in MODELS.items()
        ],
        "unavailable_models": [
            {"id": name, "reason_code": "MODEL_NOT_AVAILABLE"} for name in UNSUPPORTED
        ],
    }
