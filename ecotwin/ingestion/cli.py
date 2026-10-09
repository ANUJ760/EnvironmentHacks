"""Explicit operator commands; imports never run in API request handlers."""

import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPolygon, Point
from sqlalchemy import select, text

from ecotwin.config import get_settings
from ecotwin.db.models import (
    AirObservation,
    AirStation,
    City,
    DatasetRevision,
    FacilityProfile,
    GeoFeature,
    LandcoverCell,
    WeatherHour,
)
from ecotwin.db.session import session_factory
from ecotwin.errors import TwinError
from ecotwin.ingestion.catalog import register_object, successful_run
from ecotwin.ingestion.downloader import ProviderClient
from ecotwin.spatial.city_snapshot import publish_snapshot
from ecotwin.spatial.geometry import analysis_srid, bbox_geometry, project, validate_area
from ecotwin.spatial.spatial_queries import city_by_slug

app = typer.Typer(no_args_is_help=True)
db = typer.Typer()
city = typer.Typer()
ingest = typer.Typer()
datasets = typer.Typer()
models = typer.Typer()
jobs = typer.Typer()
auth = typer.Typer()
for name, group in [
    ("db", db),
    ("city", city),
    ("ingest", ingest),
    ("datasets", datasets),
    ("models", models),
    ("jobs", jobs),
    ("auth", auth),
]:
    app.add_typer(group, name=name)


def write_cache(document, name):
    import tempfile

    root = get_settings().ecotwin_cache_dir
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix="-" + name, dir=root, delete=False) as file:
        json.dump(document, file, allow_nan=False)
        return Path(file.name)


def output(value):
    typer.echo(json.dumps(value, default=str))


@db.command("check")
def db_check():
    with session_factory()() as session:
        output(
            {
                "postgis": session.scalar(text("SELECT PostGIS_Version()")),
                "migration": session.scalar(text("SELECT version_num FROM alembic_version")),
            }
        )


@city.command("create")
def city_create(
    city_id: str = typer.Option(...),
    name: str = typer.Option(...),
    bbox: str = typer.Option(...),
    timezone_name: str = typer.Option("UTC", "--timezone"),
):
    import re

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", city_id):
        raise TwinError("INVALID_CITY", "Use a lowercase city slug")
    ZoneInfo(timezone_name)
    boundary = bbox_geometry(bbox)
    srid = analysis_srid(boundary)
    validate_area(boundary, srid, get_settings().max_study_area_km2)
    with session_factory()() as session:
        row = session.scalar(select(City).where(City.slug == city_id))
        if row:
            if not to_shape(row.boundary).equals(boundary):
                raise TwinError("CITY_CONFLICT", "City slug already has a different boundary", 409)
        else:
            row = City(
                slug=city_id,
                display_name=name,
                boundary=from_shape(MultiPolygon([boundary]), srid=4326),
                analysis_srid=srid,
                timezone=timezone_name,
            )
            session.add(row)
            session.commit()
        output({"id": row.id, "slug": row.slug, "analysis_srid": row.analysis_srid})


@city.command("snapshot")
def snapshot(city: str = typer.Option(...)):
    with session_factory()() as session:
        row = publish_snapshot(session, city_by_slug(session, city))
        session.commit()
        output({"snapshot_id": row.id, "input_digest": row.composite_input_sha256})


@ingest.command("osm")
def osm(
    city: str = typer.Option(...),
    file: Path | None = typer.Option(None),
    method: str = typer.Option("cached"),
):
    from ecotwin.ingestion.osm import URL, fetch_osm, parse_geojson, pbf_geojson

    with session_factory()() as session:
        area = city_by_slug(session, city)
        boundary = to_shape(area.boundary)
        if file:
            document = pbf_geojson(file) if file.suffix == ".pbf" else json.loads(file.read_text())
        elif method == "overpass":
            client = ProviderClient()
            try:
                document = fetch_osm(client, boundary)
            finally:
                client.close()
            file = write_cache(document, "osm.geojson")
        else:
            raise TwinError(
                "INSUFFICIENT_INPUT_DATA",
                "Download a city-cropped OSM PBF/GeoJSON to data/raw and pass --file, or select --method overpass",
            )
        rows, rejected = parse_geojson(document, boundary)
        revision, created = register_object(
            session,
            area,
            "osm",
            file,
            boundary,
            {"crs": "EPSG:4326", "rejected": rejected},
            URL if method == "overpass" else None,
        )
        if created:
            for row in rows:
                geom = row.pop("geom")
                metric = project(geom, area.analysis_srid)
                session.add(
                    GeoFeature(
                        city_id=area.id,
                        revision_id=revision.id,
                        geom=from_shape(geom, srid=4326),
                        area_m2=metric.area if "Polygon" in geom.geom_type else None,
                        length_m=metric.length if "Line" in geom.geom_type else None,
                        **row,
                    )
                )
            successful_run(session, revision, len(rows), rejected)
        session.commit()
        output({"revision_id": revision.id, "features": len(rows), "rejected": rejected})


@ingest.command("worldcover")
def worldcover(
    city: str = typer.Option(...),
    file: Path | None = typer.Option(None),
    year: int = typer.Option(2021),
):
    from ecotwin.ingestion.worldcover import raster_cells, tile_urls

    if year != 2021:
        raise TwinError("MODEL_INPUT_UNSUPPORTED", "Only WorldCover 2021 v200 is configured")
    with session_factory()() as session:
        area = city_by_slug(session, city)
        boundary = to_shape(area.boundary)
        if not file:
            output(
                {
                    "required_downloads": tile_urls(boundary),
                    "destination": "data/raw/worldcover/",
                    "next": "ecotwin ingest worldcover --city " + city + " --file PATH",
                }
            )
            raise typer.Exit(2)
        rows, coverage, quality = raster_cells(file, boundary, area.analysis_srid)
        revision, created = register_object(
            session, area, "worldcover", file, coverage, {**quality, "resolution_m": 10}
        )
        if created:
            for row in rows:
                row["geom"] = from_shape(row["geom"], srid=4326)
                session.add(LandcoverCell(city_id=area.id, revision_id=revision.id, **row))
            successful_run(session, revision, len(rows))
        session.commit()
        output({"revision_id": revision.id, "cells": len(rows), "quality": quality})


@ingest.command("weather")
def weather(
    city: str = typer.Option(...),
    file: Path | None = typer.Option(None),
    forecast_hours: int = typer.Option(72),
    issued_at: str | None = typer.Option(None),
):
    from ecotwin.ingestion.open_meteo import URL, fetch_weather, parse_weather

    with session_factory()() as session:
        area = city_by_slug(session, city)
        center = to_shape(area.boundary).centroid
        if file:
            document = json.loads(file.read_text())
            timestamp = issued_at or document.get("_ecotwin_issued_at")
            if not timestamp:
                raise TwinError(
                    "INSUFFICIENT_INPUT_DATA",
                    "Cached weather requires original --issued-at UTC timestamp",
                )
            issue = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            if not get_settings().open_meteo_enabled:
                raise TwinError("LAYER_UNAVAILABLE", "Weather connector disabled")
            issue = datetime.now(UTC)
            client = ProviderClient()
            try:
                document = fetch_weather(client, center.y, center.x, forecast_hours)
            finally:
                client.close()
            document["_ecotwin_issued_at"] = issue.isoformat()
            file = write_cache(document, "weather.json")
        if not issue.tzinfo:
            raise TwinError("UPSTREAM_PAYLOAD_INVALID", "Issue time must be timezone-aware")
        rows = parse_weather(document, issue)
        revision, created = register_object(
            session,
            area,
            "weather",
            file,
            None,
            {
                "crs": "EPSG:4326",
                "issued_at": issue.isoformat(),
                "coverage": "coarse_grid",
                "native_units": document["hourly_units"],
            },
            URL,
        )
        if created:
            for row in rows:
                session.add(WeatherHour(city_id=area.id, revision_id=revision.id, **row))
            successful_run(session, revision, len(rows))
        session.commit()
        output({"revision_id": revision.id, "hours": len(rows)})


@ingest.command("air")
def air(
    city: str = typer.Option(...),
    file: Path | None = typer.Option(None),
    lookback_hours: int = typer.Option(48),
):
    from ecotwin.ingestion.openaq import URL, fetch_air

    with session_factory()() as session:
        area = city_by_slug(session, city)
        boundary = to_shape(area.boundary)
        if file:
            document = json.loads(file.read_text())
        else:
            client = ProviderClient()
            try:
                document = fetch_air(client, get_settings(), boundary.bounds, lookback_hours)
            finally:
                client.close()
            file = write_cache(document, "air.json")
        revision, created = register_object(
            session,
            area,
            "air",
            file,
            None,
            {"crs": "EPSG:4326", "coverage": document["coverage"]},
            URL,
        )
        if created:
            seen = set()
            for row in document["observations"]:
                location = row["location"]
                coords = location["coordinates"]
                point = Point(coords["longitude"], coords["latitude"])
                if not boundary.covers(point):
                    continue
                station = session.scalar(
                    select(AirStation).where(
                        AirStation.source == "OpenAQ",
                        AirStation.provider_station_id == str(location["id"]),
                    )
                )
                if not station:
                    station = AirStation(
                        provider_station_id=str(location["id"]),
                        source="OpenAQ",
                        name=location["name"],
                        location=from_shape(point, srid=4326),
                        metadata_json=location,
                    )
                    session.add(station)
                    session.flush()
                key = (station.id, row["sensor_id"], row["parameter"], row["measured_at"])
                if key in seen:
                    continue
                seen.add(key)
                from sqlalchemy.dialects.postgresql import insert

                session.execute(
                    insert(AirObservation)
                    .values(
                        station_id=station.id,
                        sensor_id=row["sensor_id"],
                        parameter=row["parameter"],
                        value=row["value"],
                        unit=row["unit"],
                        measured_at=datetime.fromisoformat(row["measured_at"]),
                        source_url=row["source_url"],
                        revision_id=revision.id,
                    )
                    .on_conflict_do_nothing()
                )
            successful_run(session, revision, len(seen))
        session.commit()
        output({"revision_id": revision.id, "coverage": document["coverage"]})


@ingest.command("waste")
def waste(city: str = typer.Option(...), file: Path = typer.Option(...)):
    from ecotwin.models.waste_adapter import build_scenario

    document = json.loads(file.read_text())
    build_scenario(document)
    with session_factory()() as session:
        area = city_by_slug(session, city)
        revision, created = register_object(
            session,
            area,
            "waste",
            file,
            None,
            {"measurement_type": document["measurement_type"], "crs": "EPSG:4326"},
            document["source_url"],
            (
                "Municipal or analyst inputs",
                document["source_license"],
                document["attribution"],
                document["source_url"],
            ),
        )
        if created:
            for row in document["facilities"]:
                session.add(
                    FacilityProfile(
                        city_id=area.id,
                        revision_id=revision.id,
                        facility_kind=row["facility_id"],
                        geom=from_shape(Point(row["lon"], row["lat"]), srid=4326),
                        capacity_tpd=row["capacity_tpd"],
                        accepted_categories=row["accepted_categories"],
                        efficiency_profile=row["profiles"],
                        parameter_source=row["measurement_type"] + ":" + row["source_url"],
                        effective_at=datetime.fromisoformat(row["effective_date"]),
                    )
                )
            successful_run(session, revision, len(document["facilities"]))
        session.commit()
        output({"revision_id": revision.id})


@datasets.command("verify")
def verify_datasets(city: str = typer.Option(...)):
    from ecotwin.storage.factory import object_store

    with session_factory()() as session:
        area = city_by_slug(session, city)
        rows = list(
            session.scalars(select(DatasetRevision).where(DatasetRevision.city_id == area.id))
        )
        store = object_store(get_settings(), {r.object_key: r.sha256 for r in rows})
        for row in rows:
            store.materialize(row.object_key, row.sha256)
        output({"verified": len(rows)})


@models.command("list")
def list_models(city: str | None = typer.Option(None)):
    from ecotwin.models.registry import MODELS, UNSUPPORTED

    output({"models": MODELS, "unsupported": UNSUPPORTED, "city": city})


@auth.command("issue-dev-token")
def token(subject: str = typer.Option(...), minutes: int = typer.Option(60)):
    from ecotwin.auth.dev_tokens import issue_token

    typer.echo(issue_token(get_settings(), subject, minutes))


@jobs.command("work")
def work(once: bool = typer.Option(False)):
    from ecotwin.jobs.worker import run_worker

    run_worker(once=once)
