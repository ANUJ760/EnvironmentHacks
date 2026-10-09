import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box, mapping

from ecotwin.errors import TwinError
from ecotwin.ingestion.osm import parse_geojson
from ecotwin.ingestion.worldcover import raster_cells, tile_urls
from ecotwin.models.waste_adapter import build_scenario, waste_metrics
from ecotwin.spatial.geometry import analysis_srid, project


@pytest.fixture
def raster(tmp_path):
    path = tmp_path / "cover.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_origin(79, 21.002, 0.001, 0.001),
        nodata=0,
    ) as dataset:
        dataset.write(np.array([[10, 50], [30, 0]], dtype="uint8"), 1)
    return path


def test_worldcover_clipped_area_and_nodata(raster):
    boundary = box(79, 21, 79.002, 21.002)
    srid = analysis_srid(boundary)
    rows, coverage, quality = raster_cells(raster, boundary, srid)
    assert len(rows) == 3 and {r["class_code"] for r in rows} == {10, 50, 30}
    assert sum(row["area_m2"] for row in rows) == pytest.approx(
        project(coverage, srid).area, rel=0.005
    )
    assert quality["nodata_area_m2"] > 0 and quality["reference_year"] == 2021
    assert "N21E078" in tile_urls(boundary)[0]


def test_worldcover_unknown_class(raster):
    with rasterio.open(raster, "r+") as dataset:
        dataset.write(np.full((2, 2), 9, dtype="uint8"), 1)
    with pytest.raises(TwinError):
        raster_cells(raster, box(79, 21, 79.002, 21.002), 32644)


def test_osm_types_duplicates_holes_and_clipping():
    outer = [(79, 21), (79.002, 21), (79.002, 21.002), (79, 21.002), (79, 21)]
    inner = [
        (79.0005, 21.0005),
        (79.001, 21.0005),
        (79.001, 21.001),
        (79.0005, 21.001),
        (79.0005, 21.0005),
    ]
    feature = {
        "type": "Feature",
        "id": "osm:relation/42",
        "properties": {"building": "yes"},
        "geometry": mapping(Polygon(outer, [inner])),
    }
    rows, rejected = parse_geojson(
        {"type": "FeatureCollection", "features": [feature, feature]}, box(79, 21, 79.002, 21.002)
    )
    assert len(rows) == 1 and len(rows[0]["geom"].interiors) == 1 and not rejected


def test_waste_adapter_mass_closure():
    profile = {
        "material_recovery_rate": 0.5,
        "landfill_residue_rate": 0.3,
        "process_loss_rate": 0.2,
        "specific_energy_kwh_per_tonne": 100,
        "energy_efficiency": 0.5,
    }
    document = {
        "measurement_type": "ASSUMED",
        "source_url": "https://example.org/analyst",
        "origin_id": "test-origin",
        "daily_waste_tonnes": 1,
        "composition": {"organic": 1},
        "facilities": [
            {
                "facility_id": "plant",
                "effective_date": "2026-10-09T00:00:00+00:00",
                "source_url": "https://example.org/analyst",
                "measurement_type": "ASSUMED",
                "capacity_tpd": 2,
                "accepted_categories": ["organic"],
                "profiles": {"organic": profile},
            }
        ],
        "routing": {"organic": "plant"},
    }
    result = waste_metrics(build_scenario(document))
    assert (
        result["mass_balance_error_kg"] == 0
        and result["material_recovered_kg"] == 500
        and result["energy_recovered_kwh"] == 50
    )
    document["synthetic"] = True
    with pytest.raises(TwinError):
        build_scenario(document)
