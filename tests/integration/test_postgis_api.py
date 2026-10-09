"""Hand-built fixture geometry only, never asserted to be a real city dataset."""

import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, box, mapping
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ecotwin.api.main import app
from ecotwin.auth.dev_tokens import issue_token
from ecotwin.config import get_settings
from ecotwin.db.models import (
    City,
    DatasetRevision,
    LandcoverCell,
    SimulationJob,
    SimulationResult,
    WeatherHour,
)
from ecotwin.db.session import session_factory
from ecotwin.simulation.command import canonical_digest
from ecotwin.simulation.orchestrator import execute
from ecotwin.spatial.city_snapshot import publish_snapshot
from ecotwin.spatial.geometry import analysis_srid, project
from ecotwin.storage.base import file_digest
from ecotwin.storage.local import LocalObjectStore

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    if os.environ.get("RUN_POSTGIS_TESTS") != "1":
        pytest.skip("Set RUN_POSTGIS_TESTS=1 with a migrated isolated PostGIS database")
    monkeypatch.setenv("ECOTWIN_LOCAL_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    session_factory.cache_clear()
    settings = get_settings()
    geom = box(79, 21, 79.001, 21.001)
    with session_factory()() as session:
        city = City(
            slug="fixture-" + uuid4().hex,
            display_name="Hand-built test area",
            boundary=from_shape(MultiPolygon([geom]), 4326),
            analysis_srid=analysis_srid(geom),
            timezone="UTC",
        )
        session.add(city)
        session.flush()
        revisions = []
        for kind in ["osm", "worldcover", "weather"]:
            path = tmp_path / (kind + ".json")
            path.write_text(json.dumps({"fixture": True, "kind": kind, "nonce": city.slug}))
            digest = file_digest(path)
            key = f"raw/test/{kind}/{digest}/source.json"
            LocalObjectStore(tmp_path).put_file(key, path, digest)
            revision = DatasetRevision(
                city_id=city.id,
                kind=kind,
                provider="hand-built-test-fixture",
                source_url="https://example.org/test-only",
                object_key=key,
                sha256=digest,
                byte_size=path.stat().st_size,
                source_license="CC0-test-fixture",
                attribution="Hand-built geometry, not municipal data",
                acquired_at=datetime.now(UTC),
                native_crs="EPSG:4326",
                status="READY",
                quality_json={"test_fixture": True},
            )
            session.add(revision)
            session.flush()
            revisions.append(revision)
            if kind == "worldcover":
                session.add(
                    LandcoverCell(
                        city_id=city.id,
                        revision_id=revision.id,
                        cell_x=0,
                        cell_y=0,
                        class_code=10,
                        area_m2=project(geom, city.analysis_srid).area,
                        geom=from_shape(geom, 4326),
                    )
                )
            if kind == "weather":
                for index in range(2):
                    session.add(
                        WeatherHour(
                            city_id=city.id,
                            revision_id=revision.id,
                            valid_at=datetime(2026, 10, 9, index, tzinfo=UTC),
                            issued_at=datetime.now(UTC),
                            temperature_c=25,
                            rain_mm=10,
                            humidity_pct=50,
                            wind_mps=1,
                            ghi_w_m2=500,
                            model_name="test-fixture",
                            source_lat=21,
                            source_lon=79,
                        )
                    )
        session.flush()
        snapshot = publish_snapshot(session, city)
        session.commit()
        yield settings, city.id, snapshot.id, mapping(geom)
    get_settings.cache_clear()
    session_factory.cache_clear()


def auth(settings, subject):
    return {"Authorization": "Bearer " + issue_token(settings, subject)}


def test_end_to_end_isolation_idempotency_and_runoff(seeded):
    settings, city_id, snapshot_id, geom = seeded
    with TestClient(app) as client:
        headers = auth(settings, "alice")
        assert client.get("/readyz").status_code == 200
        assert (
            client.post(
                "/v1/scenarios",
                json={"city_id": str(city_id), "snapshot_id": str(snapshot_id), "name": "no auth"},
            ).status_code
            == 401
        )
        first = client.post(
            "/v1/scenarios",
            headers=headers,
            json={"city_id": str(city_id), "snapshot_id": str(snapshot_id), "name": "first"},
        )
        assert first.status_code == 201, first.text
        sid = first.json()["id"]
        other = client.post(
            "/v1/scenarios",
            headers=headers,
            json={"city_id": str(city_id), "snapshot_id": str(snapshot_id), "name": "second"},
        ).json()["id"]
        assert client.get("/v1/scenarios/" + sid, headers=auth(settings, "bob")).status_code == 404
        edit = {
            "edit_type": "LAND_COVER_RECLASSIFY",
            "polygon_geojson": geom,
            "from_class_code": 10,
            "to_class_code": 50,
            "fraction": 1,
        }
        changed = client.put(
            f"/v1/scenarios/{sid}/edits",
            headers={**headers, "If-Match": '"1"'},
            json={"edits": [edit]},
        )
        assert changed.status_code == 200, changed.text
        assert (
            client.put(
                f"/v1/scenarios/{sid}/edits",
                headers={**headers, "If-Match": '"1"'},
                json={"edits": [edit]},
            ).status_code
            == 409
        )
        assert client.get("/v1/scenarios/" + other, headers=headers).json()["edits"] == []
        payload = {
            "requested_models": ["landcover_summary", "runoff_screen"],
            "event_rainfall_mm": 50,
        }
        key = uuid4().hex
        submit_headers = {**headers, "Idempotency-Key": key}
        accepted = client.post(
            f"/v1/scenarios/{sid}/simulate", headers=submit_headers, json=payload
        )
        assert accepted.status_code == 202, accepted.text
        identifier = accepted.json()["job_id"]
        assert (
            client.post(
                f"/v1/scenarios/{sid}/simulate", headers=submit_headers, json=payload
            ).json()["job_id"]
            == identifier
        )
        assert (
            client.post(
                f"/v1/scenarios/{sid}/simulate",
                headers=submit_headers,
                json={**payload, "event_rainfall_mm": 60},
            ).status_code
            == 409
        )
        with session_factory()() as session:
            job = session.get(SimulationJob, identifier)
            report = execute(session, job.frozen_input)
            runoff = next(m for m in report["metrics"] if m["name"] == "event_runoff_volume")
            assert runoff["absolute_delta"] > 0
            assert execute(session, job.frozen_input) == report
            result = SimulationResult(
                job_id=job.id,
                input_digest=report["input_digest"],
                output_digest=canonical_digest(report),
                model_versions=report["model_versions"],
                metrics=report["metrics"],
                warnings=report["warnings"],
                evidence=report["evidence"],
            )
            session.add(result)
            session.flush()
            job.state = "SUCCEEDED"
            job.result_id = result.id
            session.commit()
            rid = str(result.id)
        assert client.get("/v1/results/" + rid, headers=headers).status_code == 200
        assert client.get("/v1/results/" + rid, headers=auth(settings, "bob")).status_code == 404
        assert (
            client.get("/v1/cities/" + str(city_id) + "/landcover").json()["class_areas_m2"]["10"]
            > 0
        )
        assert (
            client.post(
                f"/v1/scenarios/{sid}/simulate",
                headers={**headers, "Idempotency-Key": uuid4().hex},
                json={"requested_models": ["pm25_delta"]},
            ).json()["code"]
            == "MODEL_NOT_AVAILABLE"
        )


def test_snapshot_immutability_and_spatial_index(seeded):
    _, city_id, snapshot_id, _ = seeded
    with session_factory()() as session:
        indexes = session.scalars(
            text("SELECT indexdef FROM pg_indexes WHERE tablename='landcover_cells'")
        ).all()
        assert any("gist" in index.lower() for index in indexes)
        with pytest.raises(DBAPIError):
            session.execute(
                text("UPDATE city_snapshots SET status='CHANGED' WHERE id=:id"), {"id": snapshot_id}
            )
            session.commit()
        session.rollback()
        with pytest.raises(DBAPIError):
            session.execute(
                text("UPDATE landcover_cells SET class_code=50 WHERE city_id=:city"),
                {"city": city_id},
            )
            session.commit()
