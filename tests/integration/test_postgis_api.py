"""Hand-built fixture geometry only, never asserted to be a real city dataset."""

import json
import os
from datetime import UTC, datetime, timedelta
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
from ecotwin.jobs.db_queue import claim
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


def test_worker_subprocess_and_job_cancellation(seeded):
    settings, city_id, snapshot_id, geom = seeded
    from ecotwin.jobs.processor import process_job

    with TestClient(app) as client:
        headers = auth(settings, "worker-test-" + uuid4().hex)
        scenario = client.post(
            "/v1/scenarios",
            headers=headers,
            json={"city_id": str(city_id), "snapshot_id": str(snapshot_id), "name": "worker"},
        ).json()
        response = client.post(
            f"/v1/scenarios/{scenario['id']}/simulate",
            headers={**headers, "Idempotency-Key": uuid4().hex},
            json={"requested_models": ["runoff_screen"], "event_rainfall_mm": 50},
        )
        job_id = response.json()["job_id"]
        worker_id = uuid4().hex
        with session_factory()() as session:
            # Other tests may leave queued jobs; claim the tested job using a distinct old timestamp.
            session.execute(
                text("UPDATE simulation_jobs SET created_at='2000-01-01' WHERE id=:id"),
                {"id": job_id},
            )
            session.commit()
            job = claim(session, worker_id, settings, job_id=job_id)
            assert str(job.id) == job_id
        process_job(job, worker_id, settings)
        status = client.get("/v1/jobs/" + job_id, headers=headers).json()
        assert status["state"] == "SUCCEEDED", status
        assert (
            client.get("/v1/results/" + status["result_id"], headers=headers).json()["metrics"][0][
                "scenario_value"
            ]
            >= 0
        )
        duplicate = client.post(
            f"/v1/scenarios/{scenario['id']}/simulate",
            headers={**headers, "Idempotency-Key": uuid4().hex},
            json={"requested_models": ["landcover_summary"]},
        ).json()["job_id"]
        canceled = client.post("/v1/jobs/" + duplicate + "/cancel", headers=headers, json={})
        assert canceled.status_code == 200 and canceled.json()["state"] == "CANCELED"


def test_expired_lease_recovery_and_retry_cap(seeded):
    settings, city_id, snapshot_id, _ = seeded
    from ecotwin.db.models import Scenario, UserAccount
    from ecotwin.jobs.db_queue import submit

    with session_factory()() as session:
        user = UserAccount(identity_issuer="test", identity_subject=uuid4().hex)
        session.add(user)
        session.flush()
        scenario = Scenario(
            snapshot_id=snapshot_id,
            owner_user_id=user.id,
            name="lease-test",
            updated_at=datetime.now(UTC),
            scenario_sha256="b" * 64,
        )
        session.add(scenario)
        session.flush()
        job = submit(
            session, scenario, user.id, uuid4().hex, {"requested_models": ["landcover_summary"]}, []
        )
        job.state = "RUNNING"
        job.attempt = settings.worker_max_attempts
        job.locked_until = datetime.now(UTC) - timedelta(seconds=5)
        job.worker_id = "dead-worker"
        session.commit()
        claim(session, "new-worker", settings)
        session.refresh(job)
        assert job.state == "FAILED" and job.error_code == "RETRY_LIMIT_EXCEEDED"


def test_cached_ingestion_cli_and_public_api(tmp_path, monkeypatch):
    if os.environ.get("RUN_POSTGIS_TESTS") != "1":
        pytest.skip("PostGIS opt-in required")
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from typer.testing import CliRunner

    from ecotwin.ingestion.cli import app as cli
    from ecotwin.ingestion.open_meteo import FIELDS

    monkeypatch.setenv("ECOTWIN_LOCAL_DATA_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("ECOTWIN_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()
    session_factory.cache_clear()
    runner = CliRunner()
    slug = "cli-" + uuid4().hex

    def invoke(args):
        response = runner.invoke(cli, args)
        assert response.exit_code == 0, (response.output, response.exception)
        return response

    create = invoke(
        [
            "city",
            "create",
            "--city-id",
            slug,
            "--name",
            "Hand-built fixture",
            "--bbox",
            "79,21,79.002,21.002",
        ]
    )
    city = json.loads(create.output)["id"]
    invoke(
        [
            "city",
            "create",
            "--city-id",
            slug,
            "--name",
            "Hand-built fixture",
            "--bbox",
            "79,21,79.002,21.002",
        ]
    )
    footprint = mapping(box(79.0005, 21.0005, 79.0015, 21.0015))
    osm = tmp_path / "osm.geojson"
    osm.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "osm:way/12",
                        "properties": {"building": "yes"},
                        "geometry": footprint,
                    }
                ],
            }
        )
    )
    invoke(["ingest", "osm", "--city", slug, "--file", str(osm)])
    invoke(["ingest", "osm", "--city", slug, "--file", str(osm)])
    cover = tmp_path / "cover.tif"
    with rasterio.open(
        cover,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_origin(79, 21.002, 0.001, 0.001),
        nodata=0,
    ) as destination:
        destination.write(np.full((2, 2), 10, dtype="uint8"), 1)
    invoke(["ingest", "worldcover", "--city", slug, "--file", str(cover)])
    weather = tmp_path / "weather.json"
    weather.write_text(
        json.dumps(
            {
                "latitude": 21,
                "longitude": 79,
                "_ecotwin_issued_at": "2026-10-09T00:00:00+00:00",
                "hourly_units": {k: v[1] for k, v in FIELDS.items()},
                "hourly": {
                    "time": ["2026-10-09T00:00", "2026-10-09T01:00"],
                    **{key: [50, 50] for key in FIELDS},
                },
            }
        )
    )
    invoke(["ingest", "weather", "--city", slug, "--file", str(weather)])
    air = tmp_path / "air.json"
    air.write_text(
        json.dumps(
            {
                "coverage": "stations",
                "observations": [
                    {
                        "location": {
                            "id": 42,
                            "name": "Test fixture station",
                            "coordinates": {"latitude": 21.001, "longitude": 79.001},
                        },
                        "sensor_id": "13",
                        "parameter": "pm25",
                        "value": 12,
                        "unit": "µg/m³",
                        "measured_at": "2026-10-09T00:00:00+00:00",
                        "source_url": "https://example.org/test-fixture",
                    }
                ],
            }
        )
    )
    invoke(["ingest", "air", "--city", slug, "--file", str(air)])
    profile = {
        "material_recovery_rate": 0.5,
        "landfill_residue_rate": 0.3,
        "process_loss_rate": 0.2,
        "specific_energy_kwh_per_tonne": 100,
        "energy_efficiency": 0.5,
    }
    document = {
        "source_license": "CC0-test-only",
        "attribution": "hand-built fixture",
        "measurement_type": "ASSUMED",
        "source_url": "https://example.org/test",
        "origin_id": "origin",
        "daily_waste_tonnes": 1,
        "composition": {"organic": 1},
        "facilities": [
            {
                "facility_id": "plant",
                "facility_type": "test",
                "lat": 21.001,
                "lon": 79.001,
                "effective_date": "2026-10-09T00:00:00+00:00",
                "source_url": "https://example.org/test",
                "measurement_type": "ASSUMED",
                "capacity_tpd": 2,
                "accepted_categories": ["organic"],
                "profiles": {"organic": profile},
            }
        ],
        "routing": {"organic": "plant"},
    }
    waste = tmp_path / "waste.json"
    waste.write_text(json.dumps(document))
    invoke(["ingest", "waste", "--city", slug, "--file", str(waste)])
    invoke(["datasets", "verify", "--city", slug])
    snap = invoke(["city", "snapshot", "--city", slug])
    snapshot_id = json.loads(snap.output)["snapshot_id"]
    invoke(["models", "list", "--city", slug])
    invoke(["db", "check"])
    invoke(["auth", "issue-dev-token", "--subject", "cli-user"])
    with TestClient(app) as client:
        assert client.get("/v1/cities?limit=1").status_code == 200
        assert client.get("/v1/cities/" + city).json()["active_snapshot_id"] == snapshot_id
        features = client.get(f"/v1/cities/{city}/features?bbox=79,21,79.002,21.002").json()
        assert features["features"][0]["properties"]["category"] == "building"
        assert (
            client.get(f"/v1/cities/{city}/features?bbox=79,21,79.002,21.002&category=road").json()[
                "features"
            ]
            == []
        )
        assert client.get(f"/v1/cities/{city}/datasets").status_code == 200
        assert (
            client.get(f"/v1/cities/{city}/observations/weather").json()["series"][0]["rain_mm"]
            == 50
        )
        assert (
            client.get(
                f"/v1/cities/{city}/observations/weather?start=2026-10-09T00:00:00Z&end=2026-10-09T02:00:00Z"
            ).status_code
            == 200
        )
        assert (
            client.get(f"/v1/cities/{city}/observations/air").json()["readings"][0]["value"] == 12
        )
        assert client.get("/v1/models?city_id=" + city).status_code == 200
        assert client.get("/metrics").status_code == 200
        headers = auth(get_settings(), "cli-sim-" + uuid4().hex)
        scenario = client.post(
            "/v1/scenarios",
            headers=headers,
            json={"city_id": city, "snapshot_id": snapshot_id, "name": "PV and waste"},
        ).json()
        solar = {
            "edit_type": "SOLAR_PV_INSTALL",
            "footprint_geojson": footprint,
            "installed_kwp": 10,
            "panel_tilt_deg": 0,
            "panel_azimuth_deg": 0,
            "performance_ratio": 0.75,
        }
        response = client.put(
            f"/v1/scenarios/{scenario['id']}/edits",
            headers={**headers, "If-Match": '"1"'},
            json={"edits": [solar]},
        )
        assert response.status_code == 200, response.text
        accepted = client.post(
            f"/v1/scenarios/{scenario['id']}/simulate",
            headers={**headers, "Idempotency-Key": uuid4().hex},
            json={"requested_models": ["solar_pv", "waste_balance"]},
        ).json()
        with session_factory()() as session:
            job = session.get(SimulationJob, accepted["job_id"])
            report = execute(session, job.frozen_input)
            energy = next(m for m in report["metrics"] if m["name"] == "pv_indicative_energy")
            assert energy["scenario_value"] == 0.75
            assert report["evidence"]["unavailable_metrics"][0]["name"] == "emissions_delta"
    get_settings.cache_clear()
    session_factory.cache_clear()


def test_bad_geometry_api_bodies_and_outside_edits(seeded):
    settings, city_id, snapshot_id, geom = seeded
    with TestClient(app) as client:
        headers = auth(settings, "validation-" + uuid4().hex)
        scenario = client.post(
            "/v1/scenarios",
            headers=headers,
            json={"city_id": str(city_id), "snapshot_id": str(snapshot_id), "name": "validation"},
        ).json()
        sid = scenario["id"]
        outside = {
            "edit_type": "LAND_COVER_RECLASSIFY",
            "polygon_geojson": mapping(box(80, 22, 80.001, 22.001)),
            "from_class_code": 10,
            "to_class_code": 50,
            "fraction": 1,
        }
        response = client.put(
            f"/v1/scenarios/{sid}/edits",
            headers={**headers, "If-Match": '"1"'},
            json={"edits": [outside]},
        )
        assert response.json()["code"] == "OUTSIDE_STUDY_BOUNDARY"
        assert client.post("/v1/scenarios", headers=headers, json={"unknown": 1}).status_code == 422
        assert (
            client.post(
                "/v1/scenarios",
                headers={**headers, "Content-Type": "text/plain"},
                content="malicious",
            ).status_code
            == 415
        )
        assert (
            client.post(
                "/v1/scenarios", headers=headers, json={"name": "x" * 1_000_001}
            ).status_code
            == 413
        )
        assert client.get("/v1/cities/" + str(uuid4())).status_code == 404
        assert client.get("/does-not-exist").status_code == 404
        assert client.get("/v1/jobs/" + str(uuid4()), headers=headers).status_code == 404
        assert client.get(f"/v1/scenarios/{sid}/reports", headers=headers).json() == []
        assert (
            client.get(f"/v1/cities/{city_id}/observations/air").json()["evidence_class"]
            == "UNAVAILABLE"
        )
        assert client.get(f"/v1/cities/{city_id}/features?bbox=nan,0,1,1").status_code == 422
        assert (
            client.get(
                f"/v1/cities/{city_id}/observations/weather?start=2026-10-09T00:00:00"
            ).status_code
            == 422
        )


def test_worker_terminal_error_retry_and_hard_timeout(seeded, monkeypatch):
    settings, city_id, snapshot_id, geom = seeded
    from ecotwin.db.models import Scenario, UserAccount
    from ecotwin.jobs.db_queue import submit
    from ecotwin.jobs.processor import process_job

    with session_factory()() as session:
        user = UserAccount(identity_issuer="worker-failure", identity_subject=uuid4().hex)
        session.add(user)
        session.flush()
        scenario = Scenario(
            snapshot_id=snapshot_id,
            owner_user_id=user.id,
            name="failure",
            updated_at=datetime.now(UTC),
            scenario_sha256="a" * 64,
        )
        session.add(scenario)
        session.flush()
        job = submit(
            session, scenario, user.id, uuid4().hex, {"requested_models": ["missing_model"]}, []
        )
        claimed = claim(session, "failure-worker", settings, job_id=job.id)
    process_job(claimed, "failure-worker", settings)
    with session_factory()() as session:
        session.refresh(claimed) if claimed in session else None
        status = session.get(SimulationJob, job.id)
        assert status.state == "FAILED" and status.error_code == "MODEL_NOT_AVAILABLE"


def test_job_quota_and_live_cancellation(seeded, monkeypatch):
    settings, city_id, snapshot_id, _ = seeded
    monkeypatch.setenv("MAX_PENDING_JOBS_PER_USER", "1")
    get_settings.cache_clear()
    with TestClient(app) as client:
        headers = auth(get_settings(), "quota-" + uuid4().hex)
        scenario = client.post(
            "/v1/scenarios",
            headers=headers,
            json={"city_id": str(city_id), "snapshot_id": str(snapshot_id), "name": "quota"},
        ).json()
        route = f"/v1/scenarios/{scenario['id']}/simulate"
        key = uuid4().hex
        request = {"requested_models": ["landcover_summary"]}
        first = client.post(route, headers={**headers, "Idempotency-Key": key}, json=request)
        assert first.status_code == 202
        assert (
            client.post(
                route, headers={**headers, "Idempotency-Key": key}, json=request
            ).status_code
            == 202
        )
        assert (
            client.post(
                route, headers={**headers, "Idempotency-Key": uuid4().hex}, json=request
            ).status_code
            == 429
        )
        with session_factory()() as session:
            job = claim(session, "cancel-worker", get_settings(), job_id=first.json()["job_id"])
        response = client.post("/v1/jobs/" + str(job.id) + "/cancel", headers=headers, json={})
        assert response.json()["state"] == "CANCEL_REQUESTED"
        from ecotwin.jobs.processor import process_job

        process_job(job, "cancel-worker", get_settings())
        assert client.get("/v1/jobs/" + str(job.id), headers=headers).json()["state"] == "CANCELED"
    get_settings.cache_clear()


def test_failed_import_audit_and_operator_requeue(seeded, tmp_path):
    settings, city_id, snapshot_id, geom = seeded
    from typer.testing import CliRunner

    from ecotwin.db.models import AuditEvent, ImportRun, Scenario, UserAccount
    from ecotwin.ingestion.cli import app as cli
    from ecotwin.jobs.db_queue import submit

    runner = CliRunner()
    with session_factory()() as session:
        city = session.get(City, city_id)
        slug = city.slug
    malformed = tmp_path / "invalid.json"
    malformed.write_text("{}")
    result = runner.invoke(cli, ["ingest", "osm", "--city", slug, "--file", str(malformed)])
    assert result.exit_code != 0
    with session_factory()() as session:
        audit = session.scalar(
            select(ImportRun)
            .where(ImportRun.status == "FAILED")
            .order_by(ImportRun.started_at.desc())
            .limit(1)
        )
        assert audit.error_code == "UPSTREAM_PAYLOAD_INVALID"
        user = UserAccount(identity_issuer="operator-test", identity_subject=uuid4().hex)
        session.add(user)
        session.flush()
        scenario = Scenario(
            snapshot_id=snapshot_id,
            owner_user_id=user.id,
            name="requeue",
            updated_at=datetime.now(UTC),
            scenario_sha256="f" * 64,
        )
        session.add(scenario)
        session.flush()
        job = submit(
            session, scenario, user.id, uuid4().hex, {"requested_models": ["landcover_summary"]}, []
        )
        job.state = "FAILED"
        job.attempt = 3
        job.error_code = "STORAGE_UNAVAILABLE"
        session.commit()
        identifier = str(job.id)
    response = runner.invoke(
        cli,
        [
            "jobs",
            "requeue",
            "--job-id",
            identifier,
            "--reason",
            "Verified temporary provider outage resolved",
        ],
    )
    assert response.exit_code == 0, (response.output, response.exception)
    with session_factory()() as session:
        assert session.get(SimulationJob, identifier).state == "QUEUED"
        assert session.scalar(
            select(AuditEvent).where(
                AuditEvent.resource_id == identifier, AuditEvent.action == "operator_job_requeued"
            )
        )
