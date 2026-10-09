import pytest
from pydantic import ValidationError
from shapely.geometry import box, mapping

from ecotwin.api.schemas import Reclassify, SimulationRequest
from ecotwin.config import Settings
from ecotwin.errors import TwinError
from ecotwin.ingestion.openaq import fetch_air, pages
from ecotwin.models.waste_adapter import build_scenario
from ecotwin.simulation.validation import validate_edits
from ecotwin.spatial.geometry import analysis_srid, geometry


@pytest.mark.parametrize(
    "payload",
    [
        {"requested_models": ["runoff_screen", "runoff_screen"]},
        {"requested_models": ["runoff_screen"], "start_at": "2026-10-09T00:00:00Z"},
        {
            "requested_models": ["runoff_screen"],
            "start_at": "2026-10-09T00:00:00",
            "end_at": "2026-10-09T01:00:00",
        },
        {
            "requested_models": ["runoff_screen"],
            "start_at": "2026-10-09T01:00:00Z",
            "end_at": "2026-10-09T00:00:00Z",
        },
    ],
)
def test_time_and_request_contract(payload):
    with pytest.raises(ValidationError):
        SimulationRequest.model_validate(payload)


def test_invalid_edit_categories_and_bounded_geometry():
    with pytest.raises(ValidationError):
        Reclassify(
            edit_type="LAND_COVER_RECLASSIFY",
            polygon_geojson=mapping(box(0, 0, 0.01, 0.01)),
            from_class_code=10,
            to_class_code=10,
            fraction=1,
        )
    for document in [
        mapping(box(0, 0, 0.001, 0.001)) | {"notes": "x" * 500001},
        mapping(box(-170, 0, 170, 1)),
        {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
    ]:
        with pytest.raises(TwinError):
            geometry(document)
    with pytest.raises(TwinError):
        analysis_srid(box(0, 85, 0.01, 85.01))


def test_pv_geometry_requires_buildings_tilt_and_unique_allocations():
    footprint = mapping(box(79, 21, 79.001, 21.001))
    boundary = box(79, 21, 79.002, 21.002)
    solar = {
        "edit_type": "SOLAR_PV_INSTALL",
        "footprint_geojson": footprint,
        "installed_kwp": 10,
        "performance_ratio": 0.75,
        "panel_tilt_deg": 0,
        "panel_azimuth_deg": 0,
    }
    for edits, buildings in [
        ([solar], []),
        ([solar | {"panel_tilt_deg": 30}], [boundary]),
        ([solar, solar], [boundary]),
    ]:
        with pytest.raises(TwinError):
            validate_edits(boundary, 32644, [], edits, buildings)
    validate_edits(boundary, 32644, [], [{"edit_type": "WASTE_ROUTING_OVERRIDE"}], [])


def test_empty_waste_profiles_rejected():
    document = {
        "measurement_type": "ASSUMED",
        "source_url": "https://example.org/test",
        "daily_waste_tonnes": 1,
        "composition": {"organic": 1},
        "facilities": [
            {
                "facility_id": "plant",
                "effective_date": "2026-10-09T00:00:00Z",
                "source_url": "https://example.org/test",
                "measurement_type": "ASSUMED",
                "capacity_tpd": 2,
                "accepted_categories": ["organic"],
                "profiles": {},
            }
        ],
        "routing": {"organic": "plant"},
    }
    with pytest.raises(TwinError):
        build_scenario(document)


def test_air_payload_structure_and_missing_measurements():
    class Invalid:
        def json(self, *args, **kwargs):
            return {"results": None}

    with pytest.raises(TwinError):
        pages(Invalid(), "/locations", {}, {})
    settings = Settings(_env_file=None, openaq_enabled=True, openaq_api_key="test-only-key")

    class Client:
        def json(self, url, **kwargs):
            if url.endswith("/locations"):
                return {
                    "results": [
                        {
                            "id": 1,
                            "coordinates": {"latitude": 21, "longitude": 79},
                            "sensors": [{"id": 2, "parameter": {"name": "pm25", "units": "µg/m³"}}],
                        }
                    ]
                }
            return {"results": [{"value": None}]}

    assert fetch_air(Client(), settings, (78, 20, 80, 22))["coverage"] == "none"
