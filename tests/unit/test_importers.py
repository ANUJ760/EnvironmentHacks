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


def test_optional_landsat_qa_mask(tmp_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    from ecotwin.ingestion.landsat import surface_temperature

    profile = {
        "driver": "GTiff",
        "height": 2,
        "width": 2,
        "count": 1,
        "dtype": "uint16",
        "crs": "EPSG:4326",
        "transform": from_origin(79, 21.002, 0.001, 0.001),
    }
    for name, values in [
        ("ST.tif", np.full((2, 2), 45000, dtype="uint16")),
        ("QA.tif", np.array([[0, 8], [0, 0]], dtype="uint16")),
    ]:
        with rasterio.open(tmp_path / name, "w", **profile) as destination:
            destination.write(values, 1)
    metadata = {
        "scene_id": "TEST_ONLY",
        "acquired_at": "2026-10-09T00:00:00+00:00",
        "st_band": "ST.tif",
        "qa_pixel_band": "QA.tif",
        "scale_factor": 0.00341802,
        "add_offset": 149,
        "source_url": "https://example.org/test",
        "source_license": "CC0-test",
        "attribution": "Hand-built test bands",
    }
    values, _, _ = surface_temperature(tmp_path, metadata, box(79, 21, 79.002, 21.002))
    assert values.count() == 3 and values[0, 0] == pytest.approx(45000 * 0.00341802 + 149)
    with pytest.raises(TwinError):
        surface_temperature(tmp_path, {}, box(79, 21, 79.002, 21.002))


def test_osm_xml_bulk_geometry_keeps_underlying_way_identity(tmp_path):
    from ecotwin.ingestion.osm import parse_geojson, pbf_geojson

    path = tmp_path / "tiny.osm"
    path.write_text("""<?xml version="1.0"?><osm version="0.6" generator="hand-built-test">
    <node id="1" lat="21" lon="79"/><node id="2" lat="21" lon="79.001"/>
    <node id="3" lat="21.001" lon="79.001"/><node id="4" lat="21.001" lon="79"/>
    <node id="5" lat="21.0005" lon="79.0005"><tag k="natural" v="tree"/></node>
    <way id="12"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/><tag k="building" v="yes"/></way>
    <way id="13"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/></way>
    </osm>""")
    document = pbf_geojson(path)
    rows, _ = parse_geojson(document, box(78.999, 20.999, 79.002, 21.002))
    assert {row["provider_feature_id"] for row in rows} == {
        "osm:node/5",
        "osm:way/12",
        "osm:way/13",
    }
    assert any("Polygon" in row["geom"].geom_type for row in rows)
    assert any(row["geom"].geom_type == "LineString" for row in rows)


def test_osm_rejects_bad_identity_topology_and_clips_outside():
    from ecotwin.ingestion.osm import parse_geojson

    boundary = box(79, 21, 79.001, 21.001)
    bad = {"type": "Feature", "id": "untagged-id", "properties": {}, "geometry": mapping(boundary)}
    with pytest.raises(TwinError):
        parse_geojson({"type": "FeatureCollection", "features": [bad]}, boundary)
    invalid = {
        "type": "Feature",
        "id": "osm:way/1",
        "properties": {"building": "yes"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[79, 21], [79.001, 21.001], [79, 21.001], [79.001, 21], [79, 21]]],
        },
    }
    outside = {
        "type": "Feature",
        "id": "osm:way/2",
        "properties": {"building": "yes"},
        "geometry": mapping(box(80, 22, 80.001, 22.001)),
    }
    rows, rejected = parse_geojson(
        {"type": "FeatureCollection", "features": [invalid, outside]}, boundary
    )
    assert rows == [] and rejected == 1


def test_worldcover_missing_coverage_nodata_and_size_limits(raster):
    with pytest.raises(TwinError):
        raster_cells(raster, box(80, 22, 80.002, 22.002), 32644)
    with pytest.raises(TwinError):
        raster_cells(raster, box(79, 21, 79.002, 21.002), 32644, limit=1)
    with rasterio.open(raster, "r+") as dataset:
        dataset.write(np.zeros((2, 2), dtype="uint8"), 1)
    with pytest.raises(TwinError) as error:
        raster_cells(raster, box(79, 21, 79.002, 21.002), 32644)
    assert error.value.code == "INSUFFICIENT_INPUT_DATA"
