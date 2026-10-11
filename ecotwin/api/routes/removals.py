"""Read-only hypothetical removal previews; immutable scenarios stay unchanged."""

import threading
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from geoalchemy2.shape import from_shape, to_shape
from pyproj import Transformer
from shapely import transform
from shapely.geometry import mapping
from shapely.ops import substring
from sqlalchemy import func, select

from ecotwin.api.routes.cities import active_snapshot, city_row
from ecotwin.config import get_settings
from ecotwin.db.models import GeoFeature, WeatherHour
from ecotwin.db.session import session_dependency
from ecotwin.errors import TwinError
from ecotwin.ingestion.downloader import ProviderClient
from ecotwin.ingestion.open_meteo import fetch_weather, parse_weather
from ecotwin.models.removal import SOURCES, RemovalReport, RemovalRequest, evaluate_removal
from ecotwin.spatial.geometry import geometry, project

router = APIRouter(prefix="/v1/cities", tags=["removal previews"])
_weather_cache = {}
_weather_lock = threading.Lock()


def live_weather(city, session, snapshot, hours):
    now = datetime.now(UTC)
    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=hours)
    center = to_shape(city.boundary).centroid
    cache_key = str(city.id)
    source, failure = "live_forecast", None
    with _weather_lock:
        cached = _weather_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < 300:
            rows, acquired = cached[1:]
        else:
            rows, acquired = [], now
            if get_settings().open_meteo_enabled:
                client = ProviderClient(
                    httpx.Client(timeout=httpx.Timeout(4, connect=2)), sleep=lambda delay: None
                )
                try:
                    rows = parse_weather(fetch_weather(client, center.y, center.x, 73), now)
                    _weather_cache[cache_key] = (time.monotonic(), rows, now)
                except (TwinError, httpx.HTTPError):
                    failure = "Live provider unavailable; using the published forecast if it covers this period."
                finally:
                    client.close()
            else:
                failure = "Live provider disabled; using the published forecast."
    if not rows:
        source = "pinned_forecast"
        saved = list(
            session.scalars(
                select(WeatherHour)
                .where(
                    WeatherHour.city_id == city.id,
                    WeatherHour.revision_id.in_(snapshot.dataset_revision_ids),
                    WeatherHour.valid_at > start,
                    WeatherHour.valid_at <= end,
                )
                .order_by(WeatherHour.valid_at)
            )
        )
        rows = [
            {
                key: getattr(row, key)
                for key in [
                    "valid_at",
                    "issued_at",
                    "rain_mm",
                    "ghi_w_m2",
                    "temperature_c",
                    "humidity_pct",
                    "wind_mps",
                    "source_lat",
                    "source_lon",
                ]
            }
            for row in saved
        ]
        acquired = min((row["issued_at"] for row in rows), default=now)
    selected = [row for row in rows if start < row["valid_at"] <= end]
    complete = len(selected) == hours
    age = max(0, (now - acquired).total_seconds() / 3600)
    serialized = [
        {**row, "valid_at": row["valid_at"].isoformat(), "issued_at": row["issued_at"].isoformat()}
        for row in selected
    ]
    weather = {
        "source": source if selected else "unavailable",
        "fetched_at": acquired.isoformat(),
        "age_hours": age,
        "stale": age > 6,
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "hours_available": len(selected),
        "complete": complete,
        "rainfall_mm": sum(row["rain_mm"] for row in selected)
        if complete and all(row["rain_mm"] is not None for row in selected)
        else None,
        "spatial_scope": "city-center coarse weather-model grid",
        "source_lat": selected[0]["source_lat"] if selected else None,
        "source_lon": selected[0]["source_lon"] if selected else None,
        "notice": failure,
    }
    return weather, serialized if complete else []


def resolve_geometry(request, city, snapshot, session):
    supplied = geometry(request.geometry, polygon=request.kind in {"park", "building"})
    click = geometry({"type": "Point", "coordinates": request.location}, polygon=False)
    projected_click = project(click, city.analysis_srid)
    boundary = to_shape(city.boundary)
    if projected_click.distance(project(boundary.centroid, city.analysis_srid)) > 15000:
        raise TwinError(
            "INVALID_GEOMETRY", "Select a feature within 15 km of this city study area", 422
        )
    if project(supplied, city.analysis_srid).distance(projected_click) > 50:
        raise TwinError(
            "INVALID_GEOMETRY", "Selected feature must be near the clicked location", 422
        )
    expected = {
        "tree": {"Point"},
        "road": {"LineString", "MultiLineString"},
        "park": {"Polygon", "MultiPolygon"},
        "building": {"Polygon", "MultiPolygon"},
    }
    if supplied.geom_type not in expected[request.kind]:
        raise TwinError("INVALID_GEOMETRY", "Unsupported geometry for this feature type", 422)
    category = {"tree": "mapped_tree", "road": "road", "building": "building", "park": "park"}[
        request.kind
    ]
    query = select(GeoFeature).where(
        GeoFeature.city_id == city.id,
        GeoFeature.revision_id.in_(snapshot.dataset_revision_ids),
        GeoFeature.category == category,
    )
    if request.kind == "tree":
        query = query.where(
            func.ST_DWithin(
                func.ST_Transform(GeoFeature.geom, city.analysis_srid),
                from_shape(projected_click, srid=city.analysis_srid),
                5,
            )
        )
    else:
        query = query.where(
            func.ST_Intersects(GeoFeature.geom, from_shape(click.buffer(0.00002), srid=4326))
        )
    rows = list(session.scalars(query.limit(10)))
    candidates = [row for row in rows if to_shape(row.geom).geom_type in expected[request.kind]]
    authoritative = min(
        candidates,
        key=lambda row: project(to_shape(row.geom), city.analysis_srid).distance(projected_click),
        default=None,
    )
    chosen = to_shape(authoritative.geom) if authoritative else supplied
    metric = project(chosen, city.analysis_srid)
    source = (
        (
            "Published municipal tree revision "
            if authoritative.tags.get("register_id")
            else "Published OSM revision "
        )
        + str(authoritative.revision_id)
        if authoritative
        else "Unverified supplied map geometry (outside published coverage or no matching feature)"
    )
    if request.kind == "tree":
        metric = metric.buffer(request.crown_diameter_m / 2, quad_segs=24)
        source += "; circular crown diameter is user-assumed"
    elif request.kind == "road":
        if metric.geom_type == "MultiLineString":
            metric = min(metric.geoms, key=lambda line: line.distance(projected_click))
        along = metric.project(projected_click)
        metric = substring(
            metric,
            max(0, along - request.road_length_m / 2),
            min(metric.length, along + request.road_length_m / 2),
        ).buffer(request.road_width_m / 2, cap_style="flat")
        source += "; segment length and road width are user-assumed"
    if not 0 < metric.area <= 1_000_000:
        raise TwinError("INVALID_GEOMETRY", "Preview supports positive footprints up to 1 km²", 422)
    inverse = Transformer.from_crs(city.analysis_srid, 4326, always_xy=True)
    affected = transform(metric, inverse.transform, interleaved=False)
    return affected, metric.area, source, boundary.covers(affected)


@router.post("/{identifier}/removal-preview", response_model=RemovalReport)
def preview(identifier: UUID, request: RemovalRequest, session=Depends(session_dependency)):
    city = city_row(session, identifier)
    snapshot = active_snapshot(session, identifier)
    affected, area, source, inside = resolve_geometry(request, city, snapshot, session)
    weather, samples = live_weather(city, session, snapshot, request.forecast_hours)
    metrics, findings, hourly = evaluate_removal(request, area, samples)
    limitations = [
        "Hypothetical read-only preview; the published city and stored scenarios are unchanged.",
        "Weather is a coarse forecast grid, not a sensor at this feature.",
        "No calibrated street temperature, pollution, flood depth, species loss or traffic prediction.",
        "Parameter ranges show sensitivity, not statistical confidence.",
    ]
    if not inside:
        limitations.append(
            "This feature is outside the verified analysis area. Geometry and assumed surfaces support exploration, not a full-city calibrated simulation."
        )
    if not weather["complete"]:
        limitations.append(
            "Forecast coverage is incomplete; weather-dependent metrics are omitted unless a design storm is supplied."
        )
    if weather["stale"]:
        limitations.append(
            "The available forecast is stale. Check its acquisition time before using weather-dependent estimates."
        )
    return RemovalReport(
        computed_at=datetime.now(UTC).isoformat(),
        kind=request.kind,
        affected_geometry=mapping(affected),
        area_m2=area,
        geometry_source=source,
        within_analysis_area=inside,
        weather=weather,
        inputs=request.model_dump(exclude={"geometry", "location"}),
        metrics=metrics,
        hourly=hourly,
        findings=findings,
        limitations=limitations,
        sources=SOURCES,
    )
