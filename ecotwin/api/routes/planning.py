"""Read-only, bounded planning previews with pinned geographic provenance."""

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import mapping
from sqlalchemy import func, select

from ecotwin.api.routes.cities import active_snapshot, city_row
from ecotwin.api.routes.removals import live_weather, resolve_geometry
from ecotwin.config import get_settings
from ecotwin.db.models import DatasetRevision, GeoFeature, LandcoverCell
from ecotwin.db.session import session_dependency
from ecotwin.errors import TwinError
from ecotwin.ingestion.air_forecast import FIELDS, URL, fetch_air_forecast, parse_air_forecast
from ecotwin.ingestion.downloader import ProviderClient
from ecotwin.models.planning import (
    CLASS_NAMES,
    PlanningReport,
    PlanningRequest,
    calculate_planning,
    planning_digest,
)
from ecotwin.models.removal import SOURCES, RemovalRequest
from ecotwin.simulation.command import canonical_digest
from ecotwin.spatial.geometry import geometry, project
from ecotwin.storage.factory import object_store

router = APIRouter(prefix="/v1/cities", tags=["planning previews"])
_air_cache = {}
_air_lock = threading.Lock()


def regional_air(city, snapshot, session, hours):
    now = datetime.now(UTC)
    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=hours)
    center = to_shape(city.boundary).centroid
    key = str(city.id)
    parsed, provenance, notice = None, {}, None
    source = "live_regional_forecast"
    with _air_lock:
        cached = _air_cache.get(key)
        if cached and time.monotonic() - cached[0] < 900:
            parsed, provenance = cached[1:]
        elif get_settings().open_meteo_enabled:
            client = ProviderClient(
                httpx.Client(timeout=httpx.Timeout(3, connect=2)), sleep=lambda delay: None
            )
            try:
                document = fetch_air_forecast(client, center.y, center.x)
                document["_ecotwin_issued_at"] = now.isoformat()
                parsed = parse_air_forecast(document)
                if (
                    abs(parsed["source_lat"] - center.y) > 2
                    or abs(parsed["source_lon"] - center.x) > 2
                ):
                    raise TwinError("UPSTREAM_PAYLOAD_INVALID", "Regional grid outside city")
                provenance = {"source_url": URL, "payload_sha256": canonical_digest(document)}
                _air_cache[key] = (time.monotonic(), parsed, provenance)
            except (TwinError, httpx.HTTPError):
                notice = "Live air provider unavailable. Published forecast used if available."
            finally:
                client.close()
    if parsed is None:
        revision = session.scalar(
            select(DatasetRevision).where(
                DatasetRevision.id.in_(snapshot.dataset_revision_ids),
                DatasetRevision.kind == "air_forecast",
            )
        )
        if revision:
            store = object_store(get_settings(), {revision.object_key: revision.sha256})
            try:
                parsed = parse_air_forecast(
                    json.loads(store.materialize(revision.object_key, revision.sha256).read_text())
                )
                provenance = {
                    "source_url": revision.source_url,
                    "revision_id": str(revision.id),
                    "object_key": revision.object_key,
                    "sha256": revision.sha256,
                }
                source = "pinned_regional_forecast"
            except (TwinError, OSError, ValueError):
                notice = "Published air forecast unavailable or failed validation."
    if parsed is None:
        return {
            "status": "UNAVAILABLE",
            "source": "unavailable",
            "notice": notice,
            "series": [],
            "current": {},
            "units": FIELDS,
        }, []
    series = [
        row for row in parsed["series"] if start < datetime.fromisoformat(row["valid_at"]) <= end
    ]
    age = max(0, (now - datetime.fromisoformat(parsed["fetched_at"])).total_seconds() / 3600)
    nearest = min(
        parsed["series"],
        key=lambda row: abs((datetime.fromisoformat(row["valid_at"]) - now).total_seconds()),
    )
    complete = len(series) == hours
    return {
        **{key: value for key, value in parsed.items() if key != "series"},
        "status": "AVAILABLE",
        "source": source,
        "series": series,
        "current": nearest,
        "complete": complete,
        "age_hours": age,
        "stale": age > 6,
        "spatial_scope": "regional model grid (~11 km European air / greenhouse gas products; not a street measurement)",
        "notice": notice,
        "provenance": provenance,
    }, series if complete and age <= 6 else []


def selected_area(request, city, snapshot, session):
    if request.selection_type in {"tree", "building", "road", "park"}:
        supplied = geometry(request.geometry, polygon=False)
        location = request.location or tuple(supplied.representative_point().coords[0])
        old = RemovalRequest(
            kind=request.selection_type,
            geometry=request.geometry,
            location=location,
            crown_diameter_m=request.crown_diameter_m,
            trunk_diameter_cm=request.trunk_diameter_cm,
            road_width_m=request.road_width_m,
            road_length_m=request.road_length_m,
        )
        shape, area, source, inside = resolve_geometry(old, city, snapshot, session)
        return shape, area, source, inside
    supplied = geometry(request.geometry)
    metric = project(supplied, city.analysis_srid)
    west, south, east, north = metric.bounds
    if east - west > 5000 or north - south > 5000:
        raise TwinError("INVALID_GEOMETRY", "Selection must span at most 5 km per axis", 422)
    if (
        not 1 <= metric.area <= 1_000_000
        or metric.distance(project(to_shape(city.boundary), city.analysis_srid)) > 15000
    ):
        raise TwinError(
            "INVALID_GEOMETRY", "Select 1 m²–1 km² within 15 km of the city study area", 422
        )
    return (
        supplied,
        metric.area,
        "User-selected area intersected with published OSM and WorldCover",
        to_shape(city.boundary).covers(supplied),
    )


def intersect_inventory(session, city, snapshot, selected, request):
    metric = project(selected, city.analysis_srid)
    sql_shape = from_shape(selected, srid=4326)
    cover_rows = session.execute(
        select(
            LandcoverCell.class_code,
            func.sum(
                func.ST_Area(
                    func.ST_Transform(
                        func.ST_Intersection(LandcoverCell.geom, sql_shape), city.analysis_srid
                    )
                )
            ),
        )
        .where(
            LandcoverCell.revision_id.in_(snapshot.dataset_revision_ids),
            func.ST_Intersects(LandcoverCell.geom, sql_shape),
        )
        .group_by(LandcoverCell.class_code)
    ).all()
    cover = {code: float(value) for code, value in cover_rows if value and value > 0}
    rows = list(
        session.scalars(
            select(GeoFeature)
            .where(
                GeoFeature.city_id == city.id,
                GeoFeature.revision_id.in_(snapshot.dataset_revision_ids),
                func.ST_Intersects(GeoFeature.geom, sql_shape),
            )
            .limit(5001)
        )
    )
    if len(rows) > 5000:
        raise TwinError("INVALID_GEOMETRY", "Too many mapped objects; select a smaller area", 422)
    counts, building_shapes, floor, assumed_levels = {}, [], 0, 0
    for row in rows:
        piece = project(to_shape(row.geom), city.analysis_srid).intersection(metric)
        if piece.is_empty or ("Polygon" in to_shape(row.geom).geom_type and piece.area < 0.01):
            continue
        counts[row.category] = counts.get(row.category, 0) + 1
        if row.category != "building":
            continue
        building_shapes.append(piece)
        try:
            levels = float(row.tags.get("building:levels", ""))
            if not 1 <= levels <= 60:
                raise ValueError("Invalid levels")
        except (ValueError, TypeError):
            levels = request.building_levels
            assumed_levels += 1
        floor += piece.area * levels
    from shapely.ops import unary_union

    buildings = unary_union(building_shapes).area if building_shapes else 0
    # De-duplicate overlapping mapped outlines for the gross-floor proxy.
    if building_shapes and sum(piece.area for piece in building_shapes) > buildings:
        floor *= buildings / sum(piece.area for piece in building_shapes)
    inventory = {
        "counts": counts,
        "buildings_count": counts.get("building", 0),
        "roads_count": counts.get("road", 0),
        "mapped_trees_count": counts.get("mapped_tree", 0),
        "building_area_m2": buildings,
        "floor_area_m2": floor,
        "buildings_with_assumed_levels": assumed_levels,
        "tree_inventory_complete": False,
    }
    return inventory, cover


@router.post("/{identifier}/planning-preview", response_model=PlanningReport)
def planning_preview(
    identifier: UUID, request: PlanningRequest, session=Depends(session_dependency)
):
    city = city_row(session, identifier)
    snapshot = active_snapshot(session, identifier)
    selected, area, source, inside = selected_area(request, city, snapshot, session)
    inventory, cover = intersect_inventory(session, city, snapshot, selected, request)
    if request.selection_type == "building" and inventory["building_area_m2"] < 0.01:
        # A clicked vector-tile footprint is usable geometry, but its floor count
        # and consumption remain explicit assumptions outside pinned OSM coverage.
        inventory.update(
            buildings_count=1,
            building_area_m2=area,
            floor_area_m2=area * request.building_levels,
            buildings_with_assumed_levels=1,
            footprint_source="supplied_map_outline",
        )
    coverage = min(1, sum(cover.values()) / area)
    weather, weather_samples = live_weather(city, session, snapshot, request.forecast_hours)
    if weather["stale"]:
        weather_samples = []
    air, air_samples = regional_air(city, snapshot, session, request.forecast_hours)
    metrics, findings, hourly, limitations = calculate_planning(
        request, inventory, cover, area, weather_samples, air_samples, coverage
    )
    if not inside:
        limitations.insert(
            0,
            "Outside the verified study boundary; missing geography is not extrapolated. Expand and publish city datasets for full scientific coverage.",
        )
    if coverage < 0.98:
        limitations.insert(
            0,
            f"WorldCover covers {coverage:.1%} of this selection; whole-selection runoff is unavailable.",
        )
    revisions = list(
        session.scalars(
            select(DatasetRevision).where(DatasetRevision.id.in_(snapshot.dataset_revision_ids))
        )
    )
    inputs = request.model_dump(mode="json")
    provenance = {
        "digest_algorithm": "sha256-json-numeric-v1",
        "snapshot_input_sha256": snapshot.composite_input_sha256,
        "analysis_srid": city.analysis_srid,
        "datasets": [
            {
                "id": str(row.id),
                "kind": row.kind,
                "sha256": row.sha256,
                "object_key": row.object_key,
                "source_url": row.source_url,
                "acquired_at": row.acquired_at.isoformat(),
                "license": row.source_license,
            }
            for row in sorted(revisions, key=lambda row: row.kind)
        ],
        "weather_samples": weather_samples,
        "air_samples": air_samples,
        "unavailable": [
            "water_chemistry",
            "atmospheric_oxygen",
            "street_pollution_delta",
            "landfill_hazards",
            "flood_depth",
            "calibrated_heat_delta",
        ],
    }
    sources = SOURCES + [
        {
            "id": "cams",
            "title": "CAMS / Open-Meteo regional air forecast",
            "url": "https://open-meteo.com/en/docs/air-quality-api",
        },
        {
            "id": "woods",
            "title": "NRCS forest curve numbers (National Engineering Handbook)",
            "url": "https://directives.nrcs.usda.gov/sites/default/files2/1712930818/31754.pdf",
        },
        {
            "id": "deposition",
            "title": "i-Tree published deposition methods; screening proxy only",
            "url": "https://www.itreetools.org/support/resources-overview/i-tree-methods-and-files/i-tree-eco-resources",
        },
        {
            "id": "swmm",
            "title": "EPA hydrology / water-quality model requirements",
            "url": "https://www.epa.gov/water-research/storm-water-management-model-swmm",
        },
    ]
    report = {
        "computed_at": datetime.now(UTC).isoformat(),
        "model_version": "planning-screen-v1",
        "city_id": str(city.id),
        "snapshot_id": str(snapshot.id),
        "area_m2": area,
        "affected_geometry": dict(mapping(selected)),
        "geometry_source": source,
        "within_analysis_area": inside,
        "inventory": inventory,
        "landcover": [
            {"class_code": code, "label": CLASS_NAMES[code], "area_m2": value}
            for code, value in sorted(cover.items())
        ],
        "coverage_fraction": coverage,
        "metrics": metrics,
        "findings": findings,
        "limitations": limitations,
        "sources": sources,
        "weather": weather,
        "air": air,
        "hourly": hourly,
        "inputs": inputs,
        "provenance": provenance,
        "input_sha256": planning_digest(
            {"inputs": inputs, "inventory": inventory, "cover": cover, "provenance": provenance}
        ),
    }
    report["result_sha256"] = planning_digest(
        {**report, "metrics": [value.model_dump() for value in metrics]}
    )
    return report


@router.get("/{identifier}/environment-baseline")
def environment_baseline(identifier: UUID, session=Depends(session_dependency)):
    city = city_row(session, identifier)
    snapshot = active_snapshot(session, identifier)
    weather, series = live_weather(city, session, snapshot, 24)
    air, _ = regional_air(city, snapshot, session, 24)
    return {"snapshot_id": str(snapshot.id), "weather": {**weather, "series": series}, "air": air}
