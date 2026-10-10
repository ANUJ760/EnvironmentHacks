from types import SimpleNamespace
from uuid import uuid4

import pytest
from geoalchemy2.shape import from_shape
from pydantic import ValidationError
from shapely.geometry import LineString, MultiPolygon, box, mapping

from ecotwin.api.routes.removals import resolve_geometry
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
