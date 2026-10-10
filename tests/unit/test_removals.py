import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from geoalchemy2.shape import from_shape
from pydantic import ValidationError
from shapely.geometry import LineString, MultiPolygon, box, mapping

from ecotwin.api.routes import removals
from ecotwin.api.routes.removals import live_weather, resolve_geometry
from ecotwin.errors import TwinError
from ecotwin.models.removal import (
    RemovalRequest,
    carbon_stock,
    evaluate_removal,
    rain_events,
    runoff_depth,
)


def request(kind="tree", **kwargs):
    return RemovalRequest(kind=kind, geometry={}, location=(8.54, 47.38), **kwargs)


def samples(rain=0, ghi=500):
    return [
        {"valid_at": "2026-10-11T12:00:00+00:00", "rain_mm": rain, "ghi_w_m2": ghi}
        for _ in range(24)
    ]


def test_nrcs_published_equation_and_zero_storm():
    # Independently expanded equation for a 100 mm storm on CN 98.
    assert runoff_depth(100, 98) == pytest.approx(94.037597, rel=1e-7)
    assert runoff_depth(0, 98) == 0
    assert runoff_depth(5, 61) == 0
    with pytest.raises(TwinError):
        runoff_depth(float("nan"), 61)


def test_removed_building_on_grass_reduces_runoff_for_every_soil_group():
    metrics, _, _ = evaluate_removal(request("building", rainfall_mm=100), 200, samples())
    runoff = next(metric for metric in metrics if metric.key == "runoff")
    assert runoff.after < runoff.before
    assert runoff.low <= runoff.delta <= runoff.high < 0
    assert runoff.delta == pytest.approx(runoff.after - runoff.before)


def test_tree_removal_does_not_turn_tree_canopy_into_ground_runoff():
    metrics, findings, hourly = evaluate_removal(request(replacement="unchanged"), 50, samples(10))
    assert next(metric for metric in metrics if metric.key == "runoff").delta == 0
    assert any(finding["id"] == "interception" for finding in findings)
    solar = next(metric for metric in metrics if metric.key == "solar_exposure")
    assert solar.delta == pytest.approx(sum(row["delta_kwh"] for row in hourly))
    assert next(metric for metric in metrics if metric.key == "carbon").high < 0
    assert carbon_stock(50) > carbon_stock(20)


def test_missing_weather_does_not_produce_fake_zero_predictions():
    metrics, _, _ = evaluate_removal(request("building"), 200, [])
    assert {metric.key for metric in metrics} == {"footprint"}
    metrics, _, _ = evaluate_removal(request("building", rainfall_mm=50), 200, [])
    assert {metric.key for metric in metrics} == {"footprint", "runoff"}


def test_zero_roof_availability_and_no_sunlight():
    metrics, _, _ = evaluate_removal(request("building", roof_usable_fraction=0), 200, samples())
    assert next(metric for metric in metrics if metric.key == "roof_solar").before == 0
    metrics, _, _ = evaluate_removal(request(), 50, samples(ghi=0))
    assert next(metric for metric in metrics if metric.key == "solar_exposure").delta == 0


def test_road_footprint_is_labeled_as_assumed_not_surveyed():
    metrics, _, _ = evaluate_removal(request("road"), 300, [])
    assert metrics[0].key == "footprint"
    assert metrics[0].evidence == "ASSUMED_INPUT"
    assert "width" in metrics[0].method


def test_storms_are_split_after_six_dry_hours():
    assert rain_events([{"rain_mm": rain} for rain in [2, 3, 0, 0, 0, 0, 0, 0, 4]]) == [5, 4]
    assert rain_events([{"rain_mm": rain} for rain in [2, 0, 0, 4]]) == [6]


def test_strict_inputs_and_parameter_bounds():
    for kwargs in [
        {"rainfall_mm": float("nan")},
        {"crown_diameter_m": -1},
        {"shade_fraction": 1.1},
        {"forecast_hours": 100},
        {"made_up": True},
    ]:
        with pytest.raises(ValidationError):
            request(**kwargs)


class EmptySession:
    def scalars(self, query):
        return []


def test_projected_tree_crown_and_bounded_road_segment():
    city = SimpleNamespace(
        id=uuid4(),
        analysis_srid=32632,
        boundary=from_shape(MultiPolygon([box(8.53, 47.37, 8.55, 47.39)]), srid=4326),
    )
    snapshot = SimpleNamespace(dataset_revision_ids=[uuid4()])
    tree = request()
    tree.geometry = {"type": "Point", "coordinates": tree.location}
    _, area, _, inside = resolve_geometry(tree, city, snapshot, EmptySession())
    assert area == pytest.approx(50.2655, rel=0.001)
    assert inside
    road = request("road")
    road.geometry = mapping(LineString([(8.539, 47.38), (8.541, 47.38)]))
    _, area, _, _ = resolve_geometry(road, city, snapshot, EmptySession())
    assert area == pytest.approx(300, rel=0.001)
    tree.location = (999, 999)
    with pytest.raises(TwinError):
        resolve_geometry(tree, city, snapshot, EmptySession())


def weather_context():
    city = SimpleNamespace(
        id=uuid4(), boundary=from_shape(MultiPolygon([box(8.53, 47.37, 8.55, 47.39)]), srid=4326)
    )
    return city, SimpleNamespace(dataset_revision_ids=[uuid4()])


def forecast_rows():
    now = datetime.now(UTC)
    start = now.replace(minute=0, second=0, microsecond=0)
    return now, [
        {
            "valid_at": start + timedelta(hours=hour),
            "issued_at": now,
            "rain_mm": 1,
            "ghi_w_m2": 500,
            "temperature_c": 15,
            "humidity_pct": 60,
            "wind_mps": 2,
            "source_lat": 47.38,
            "source_lon": 8.54,
        }
        for hour in range(73)
    ]


@pytest.mark.parametrize("hours", [24, 72])
def test_live_cache_covers_complete_future_window(monkeypatch, hours):
    city, snapshot = weather_context()
    acquired, rows = forecast_rows()
    monkeypatch.setattr(
        removals, "_weather_cache", {str(city.id): (time.monotonic(), rows, acquired)}
    )
    metadata, samples = live_weather(city, EmptySession(), snapshot, hours)
    assert metadata["source"] == "live_forecast"
    assert metadata["complete"]
    assert len(samples) == hours
    assert metadata["rainfall_mm"] == hours
    assert not metadata["stale"]


def test_incomplete_forecast_is_not_used_as_complete_weather(monkeypatch):
    city, snapshot = weather_context()
    acquired, rows = forecast_rows()
    monkeypatch.setattr(
        removals, "_weather_cache", {str(city.id): (time.monotonic(), rows[:10], acquired)}
    )
    metadata, samples = live_weather(city, EmptySession(), snapshot, 24)
    assert not metadata["complete"]
    assert metadata["rainfall_mm"] is None
    assert samples == []


def test_unavailable_and_stale_published_weather_are_explicit(monkeypatch):
    city, snapshot = weather_context()
    monkeypatch.setattr(removals, "_weather_cache", {})
    monkeypatch.setattr(removals, "get_settings", lambda: SimpleNamespace(open_meteo_enabled=False))
    metadata, samples = live_weather(city, EmptySession(), snapshot, 24)
    assert metadata["source"] == "unavailable"
    assert samples == []
    now, rows = forecast_rows()
    saved = [
        SimpleNamespace(**{**row, "issued_at": now - timedelta(hours=7)}) for row in rows[1:25]
    ]
    session = SimpleNamespace(scalars=lambda query: saved)
    metadata, samples = live_weather(city, session, snapshot, 24)
    assert metadata["source"] == "pinned_forecast"
    assert metadata["complete"] and metadata["stale"]
    assert len(samples) == 24
