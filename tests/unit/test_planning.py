import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from geoalchemy2.shape import from_shape
from pydantic import ValidationError
from shapely.geometry import box

from ecotwin.api.routes import planning
from ecotwin.errors import TwinError
from ecotwin.ingestion.air_forecast import FIELDS, parse_air_forecast
from ecotwin.models.planning import PlanningRequest, calculate_planning


def evaluate(**kwargs):
    request = PlanningRequest(geometry={}, **kwargs)
    inventory = {"floor_area_m2": 300, "building_area_m2": 100, "roads_count": 1}
    weather = [{"valid_at": "2026-10-11T12:00:00+00:00", "rain_mm": 50, "ghi_w_m2": 500}]
    metrics, findings, hourly, limitations = calculate_planning(
        request, inventory, {10: 100, 50: 100}, 200, weather, [{"pm2_5": 10}], 1
    )
    return {metric.key: metric for metric in metrics}, findings, hourly, limitations


def test_energy_and_waste_preserve_displaced_activity_by_default():
    metrics, _, _, _ = evaluate()
    assert metrics["energy_local"].delta == -30000
    assert metrics["energy_system"].delta == 0
    assert metrics["waste_system"].delta == 0
    metrics, _, _, _ = evaluate(displaced_fraction=0.5)
    assert metrics["energy_system"].delta == -15000
    assert metrics["waste_system"].after == metrics["waste_local"].before * 0.5


def test_demolition_material_is_conserved_and_not_mixed_with_daily_waste():
    metrics, _, _, _ = evaluate()
    assert metrics["demolition"].after == pytest.approx(240)
    assert metrics["demolition"].after == pytest.approx(
        metrics["recovered"].after + metrics["residual"].after
    )
    assert metrics["demolition"].unit == "t"
    assert metrics["waste_local"].unit == "kg/day"


def test_tree_selection_does_not_demolish_adjacent_buildings():
    metrics, _, _, _ = evaluate(selection_type="tree", replacement="unchanged")
    assert "demolition" not in metrics
    assert "energy_local" not in metrics
    assert metrics["runoff"].delta == 0
    assert metrics["carbon"].delta < 0
    assert metrics["pm_deposition"].delta < 0
    assert "pm25_delta" not in metrics


def test_forested_area_to_sealed_ground_increases_runoff():
    metrics, _, _, _ = evaluate(replacement="impervious")
    assert metrics["runoff"].delta > 0
    assert metrics["runoff"].low <= metrics["runoff"].delta <= metrics["runoff"].high


def test_water_fill_reports_materials_without_fake_flood_or_chemistry_changes():
    request = PlanningRequest(geometry={}, action="fill", water_depth_m=2, fill_height_m=1)
    inventory = {"floor_area_m2": 0, "building_area_m2": 0}
    metrics, findings, _, limitations = calculate_planning(
        request, inventory, {80: 100, 30: 50}, 150, [], [], 1
    )
    values = {metric.key: metric for metric in metrics}
    assert values["fill_volume"].after == 250
    assert values["fill_material"].after == 400
    assert "runoff" not in values
    assert any(finding["id"] == "water" for finding in findings)
    assert any("chemistry" in value for value in limitations)


def test_missing_coverage_and_weather_do_not_become_zero_predictions():
    request = PlanningRequest(geometry={})
    inventory = {"floor_area_m2": 0, "building_area_m2": 0}
    metrics, _, _, _ = calculate_planning(request, inventory, {}, 100, [], [], 0)
    assert metrics == []
    for value in [float("nan"), -1, 11]:
        with pytest.raises(ValidationError):
            PlanningRequest(geometry={}, waste_kg_person_day=value)


def test_regional_air_validates_units_times_and_missing_gases():
    document = {
        "_ecotwin_issued_at": datetime.now(UTC).isoformat(),
        "latitude": 47.38,
        "longitude": 8.54,
        "hourly": {"time": ["2026-10-11T12:00", "2026-10-11T13:00"], "pm2_5": [10, None]},
        "hourly_units": {"pm2_5": FIELDS["pm2_5"]},
    }
    result = parse_air_forecast(document)
    assert result["series"][0]["pm2_5"] == 10
    assert result["series"][0]["carbon_dioxide"] is None
    assert result["series"][1]["pm2_5"] is None
    document["hourly_units"]["pm2_5"] = "ppm"
    with pytest.raises(TwinError, match="Valid hourly"):
        parse_air_forecast(document)


def test_published_air_fallback_reads_verified_object_store_not_local_assumptions(
    tmp_path, monkeypatch
):
    now = datetime.now(UTC)
    start = now.replace(minute=0, second=0, microsecond=0)
    document = {
        "_ecotwin_issued_at": now.isoformat(),
        "latitude": 47.38,
        "longitude": 8.54,
        "hourly": {
            "time": [(start + timedelta(hours=hour)).isoformat() for hour in range(25)],
            "pm2_5": [10] * 25,
        },
        "hourly_units": {"pm2_5": FIELDS["pm2_5"]},
    }
    path = tmp_path / "air.json"
    path.write_text(json.dumps(document))
    revision = SimpleNamespace(
        id=uuid4(),
        object_key="raw/forecast/source.json",
        sha256="a" * 64,
        source_url="https://open-meteo.com",
    )
    called = []

    def materialize(key, sha):
        called.append((key, sha))
        return path

    monkeypatch.setattr(planning, "_air_cache", {})
    monkeypatch.setattr(planning, "get_settings", lambda: SimpleNamespace(open_meteo_enabled=False))
    monkeypatch.setattr(
        planning, "object_store", lambda settings, digests: SimpleNamespace(materialize=materialize)
    )
    city = SimpleNamespace(
        id=uuid4(), boundary=from_shape(box(8.53, 47.37, 8.55, 47.39), srid=4326)
    )
    snapshot = SimpleNamespace(dataset_revision_ids=[revision.id])
    session = SimpleNamespace(scalar=lambda query: revision)
    metadata, samples = planning.regional_air(city, snapshot, session, 24)
    assert metadata["source"] == "pinned_regional_forecast"
    assert metadata["complete"]
    assert len(samples) == 24
    assert called == [(revision.object_key, revision.sha256)]


def test_wide_sliver_cannot_bypass_bounded_selection_area():
    city = SimpleNamespace(
        id=uuid4(),
        analysis_srid=32632,
        boundary=from_shape(box(8.53, 47.37, 8.55, 47.39), srid=4326),
    )
    request = PlanningRequest(
        geometry={
            "type": "Polygon",
            "coordinates": [
                [[8.5, 47.38], [8.8, 47.38], [8.8, 47.38001], [8.5, 47.38001], [8.5, 47.38]]
            ],
        }
    )
    with pytest.raises(TwinError, match="5 km"):
        planning.selected_area(request, city, None, None)
