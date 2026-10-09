import hashlib

import pytest
from pydantic import ValidationError
from shapely.geometry import box, mapping

from ecotwin.auth.dev_tokens import issue_token
from ecotwin.auth.jwt import verify_token
from ecotwin.config import Settings
from ecotwin.errors import TwinError
from ecotwin.models.landcover import CoverPiece, class_areas, reclassify
from ecotwin.models.runoff import COEFFICIENTS, runoff_volume
from ecotwin.models.solar_pv import solar_energy
from ecotwin.simulation.command import canonical_digest
from ecotwin.spatial.geometry import analysis_srid, bbox_geometry, geometry, project
from ecotwin.storage.checked_fallback import CheckedFallbackObjectStore
from ecotwin.storage.local import LocalObjectStore


@pytest.mark.parametrize(
    "areas,rain,expected",
    [
        ({10: 1000}, 50, 7.5),
        ({50: 1000}, 50, 42.5),
        ({80: 1000}, 50, 0),
        ({10: 1000}, 0, 0),
        ({10: 500, 50: 500}, 100, 50),
    ],
)
def test_runoff_golden(areas, rain, expected):
    assert runoff_volume(areas, rain, COEFFICIENTS) == pytest.approx(expected)


@pytest.mark.parametrize("rain", [-1, float("nan"), float("inf")])
def test_invalid_rain(rain):
    with pytest.raises(TwinError):
        runoff_volume({10: 1}, rain, COEFFICIENTS)


@pytest.mark.parametrize("ghi,expected", [([1000, 500], 11.25), ([0, 0], 0)])
def test_solar_golden(ghi, expected):
    assert solar_energy(10, ghi) == expected


def test_tilt_rejected():
    with pytest.raises(TwinError, match="Tilted"):
        solar_energy(10, [1000], tilt=10)


def test_projected_area_and_holes():
    geo = geometry(mapping(box(79, 21, 79.001, 21.001)))
    assert 10000 < project(geo, analysis_srid(geo)).area < 13000
    assert analysis_srid(box(-75, -20, -74.99, -19.99)) == 32718


@pytest.mark.parametrize("bbox", ["0,0,0,1", "nan,0,1,1", "180,0,181,1", "0,0,1"])
def test_bad_bbox(bbox):
    with pytest.raises(TwinError):
        bbox_geometry(bbox)


def test_fractional_reclassify_and_conflict():
    geo = box(79, 21, 79.001, 21.001)
    srid = analysis_srid(geo)
    pieces = [CoverPiece(project(geo, srid), 10)]
    edit = {
        "polygon_geojson": mapping(geo),
        "from_class_code": 10,
        "to_class_code": 50,
        "fraction": 0.25,
    }
    changed, realized = reclassify(pieces, edit, srid)
    areas = class_areas(changed)
    assert sum(areas.values()) == pytest.approx(pieces[0].geom.area)
    assert realized == pytest.approx(pieces[0].geom.area * 0.25)
    with pytest.raises(TwinError):
        reclassify(changed, edit, srid)


def test_local_storage_integrity_and_traversal(tmp_path):
    store = LocalObjectStore(tmp_path / "store")
    source = tmp_path / "source"
    source.write_bytes(b"real-source-bytes")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    store.put_file("raw/test/source", source, digest)
    assert store.materialize("raw/test/source", digest).read_bytes() == source.read_bytes()
    with pytest.raises(TwinError):
        store.materialize("raw/test/source", "a" * 64)
    for key in ["../source", "raw/../source", "/raw/source", "raw//source", "raw/./source"]:
        with pytest.raises(TwinError):
            store.exists(key)
    (tmp_path / "store" / "raw" / "escape").symlink_to(tmp_path)
    with pytest.raises(TwinError):
        store.exists("raw/escape/source")


def test_fallback_only_unavailable(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"cache")
    digest = hashlib.sha256(b"cache").hexdigest()
    local = LocalObjectStore(tmp_path / "local")
    local.put_file("raw/source", source, digest)

    class Broken:
        code = "STORAGE_UNAVAILABLE"

        def materialize(self, *args):
            raise TwinError(self.code, "fail")

    primary = Broken()
    store = CheckedFallbackObjectStore(primary, local, {"raw/source": digest})
    assert store.materialize("raw/source", digest).read_bytes() == b"cache"
    for code in ["STORAGE_PERMISSION_DENIED", "DATASET_NOT_FOUND", "DATASET_CHECKSUM_MISMATCH"]:
        primary.code = code
        with pytest.raises(TwinError):
            store.materialize("raw/source", digest)


def test_dev_tokens_and_production_rejection():
    settings = Settings(_env_file=None)
    token = issue_token(settings, "alice")
    assert verify_token(token, settings) == "alice"
    with pytest.raises(TwinError):
        verify_token(token + "bad", settings)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production")


def test_canonical_hash():
    assert canonical_digest({"b": 2, "a": 1}) == canonical_digest({"a": 1, "b": 2})
    with pytest.raises(ValueError):
        canonical_digest({"a": float("nan")})
