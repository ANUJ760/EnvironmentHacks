import pytest
from pyproj import Transformer
from shapely.geometry import Point, box

from ecotwin.ingestion.municipal_trees import deduplicate_trees, parse_trees
from ecotwin.spatial.geometry import project


def document(coordinates=None, crown=8):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "id": "baumkataster_baumstandorte.1",
                "geometry": {"type": "Point", "coordinates": coordinates or [8.54, 47.38]},
                "properties": {"kronendurchmesser": crown, "baumnamelat": "Acer platanoides"},
            }
        ],
    }


def test_register_retains_species_but_does_not_claim_a_measured_crown():
    rows, rejected = parse_trees(document(), box(8.53, 47.37, 8.55, 47.39))
    assert rejected == 0 and len(rows) == 1
    assert rows[0]["tags"]["species"] == "Acer platanoides"
    assert rows[0]["tags"]["crown_diameter_m"] == 8
    assert "fallback" in rows[0]["tags"]["crown_note"]
    assert "trunk_diameter_cm" not in rows[0]["tags"]


@pytest.mark.parametrize("coordinates", [[47.38, 8.54], [8.54, float("nan")], [0, 0]])
def test_wrong_crs_and_invalid_coordinates_are_rejected(coordinates):
    rows, rejected = parse_trees(document(coordinates), box(8.53, 47.37, 8.55, 47.39))
    assert rows == [] and rejected == 1


@pytest.mark.parametrize("crown", [None, 0, 100, float("inf")])
def test_missing_or_invalid_crown_does_not_become_a_measurement(crown):
    rows, _ = parse_trees(document(crown=crown), box(8.53, 47.37, 8.55, 47.39))
    assert rows[0]["tags"]["crown_diameter_m"] is None


def test_cross_source_matching_does_not_merge_two_nearby_registered_trees():
    origin = project(Point(8.54, 47.38), 32632)
    inverse = Transformer.from_crs(32632, 4326, always_xy=True)

    def row(offset, register=False):
        return {
            "geom": Point(*inverse.transform(origin.x + offset, origin.y)),
            "tags": {"register_id": str(offset)} if register else {},
        }

    municipal, adjacent, duplicate, distant = row(0, True), row(0.5, True), row(1), row(4)
    rows, suppressed = deduplicate_trees([duplicate, municipal, adjacent, distant])
    assert suppressed == 1
    assert rows == [municipal, adjacent, distant]
