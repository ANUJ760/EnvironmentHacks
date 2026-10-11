from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from geoalchemy2.shape import from_shape, to_shape
from sqlalchemy import delete, select

from ecotwin.api.dependencies import current_user
from ecotwin.api.schemas import (
    EditsReplace,
    JobAccepted,
    JobView,
    ResultView,
    ScenarioCreate,
    ScenarioView,
    SimulationRequest,
)
from ecotwin.auth.permissions import owned_job, owned_result, owned_scenario
from ecotwin.db.models import (
    AuditEvent,
    City,
    CitySnapshot,
    Scenario,
    ScenarioEdit,
    SimulationJob,
    SimulationResult,
)
from ecotwin.db.session import session_dependency
from ecotwin.errors import TwinError
from ecotwin.jobs.db_queue import cancel, submit
from ecotwin.jobs.queue import publish_hint
from ecotwin.models.registry import MODELS
from ecotwin.simulation.command import canonical_digest
from ecotwin.simulation.validation import validate_edits
from ecotwin.spatial.geometry import geometry
from ecotwin.spatial.spatial_queries import load_cover, snapshot_buildings, snapshot_inputs

router = APIRouter(prefix="/v1", tags=["scenarios"])


def edits_for(session, scenario):
    return [
        row.parameters
        for row in session.scalars(
            select(ScenarioEdit)
            .where(ScenarioEdit.scenario_id == scenario.id)
            .order_by(ScenarioEdit.ordinal)
        )
    ]


def scenario_view(session, row):
    return ScenarioView(
        id=row.id,
        snapshot_id=row.snapshot_id,
        name=row.name,
        version=row.version,
        scenario_sha256=row.scenario_sha256,
        edits=edits_for(session, row),
    )


@router.post("/scenarios", response_model=ScenarioView, status_code=201)
def create(
    body: ScenarioCreate,
    response: Response,
    session=Depends(session_dependency),
    user=Depends(current_user),
):
    snapshot = session.scalar(
        select(CitySnapshot).where(
            CitySnapshot.id == body.snapshot_id,
            CitySnapshot.city_id == body.city_id,
            CitySnapshot.status == "PUBLISHED",
        )
    )
    if not snapshot:
        raise TwinError("DATASET_NOT_READY", "Published same-city snapshot required")
    row = Scenario(
        snapshot_id=snapshot.id,
        owner_user_id=user.id,
        name=body.name,
        updated_at=datetime.now(UTC),
        scenario_sha256=canonical_digest({"snapshot_id": str(snapshot.id), "edits": []}),
    )
    session.add(row)
    session.flush()
    session.add(
        AuditEvent(
            actor_id=user.id, action="scenario_created", resource_id=row.id, details={"version": 1}
        )
    )
    session.commit()
    response.headers["ETag"] = f'"{row.version}"'
    return scenario_view(session, row)


@router.get("/scenarios/{identifier}", response_model=ScenarioView)
def get_scenario(
    identifier: UUID,
    response: Response,
    session=Depends(session_dependency),
    user=Depends(current_user),
):
    row = owned_scenario(session, identifier, user.id)
    response.headers["ETag"] = f'"{row.version}"'
    return scenario_view(session, row)


@router.put("/scenarios/{identifier}/edits", response_model=ScenarioView)
def replace_edits(
    identifier: UUID,
    body: EditsReplace,
    response: Response,
    if_match: Annotated[str, Header()],
    session=Depends(session_dependency),
    user=Depends(current_user),
):
    row = owned_scenario(session, identifier, user.id, lock=True)
    if if_match != f'"{row.version}"':
        raise TwinError("SCENARIO_VERSION_CONFLICT", "Use the latest scenario ETag", 409)
    snapshot = session.get(CitySnapshot, row.snapshot_id)
    city = session.get(City, snapshot.city_id)
    documents = [edit.model_dump(mode="json") for edit in body.edits]
    pieces = (
        load_cover(session, snapshot, city)
        if any(e["edit_type"] == "LAND_COVER_RECLASSIFY" for e in documents)
        else []
    )
    validate_edits(
        to_shape(city.boundary),
        city.analysis_srid,
        pieces,
        documents,
        snapshot_buildings(session, snapshot),
    )
    if any(e["edit_type"] == "WASTE_ROUTING_OVERRIDE" for e in documents) and not any(
        r.kind == "waste" for r in snapshot_inputs(session, snapshot)
    ):
        raise TwinError(
            "INSUFFICIENT_INPUT_DATA", "Pinned waste inputs are required for routing edits"
        )
    session.execute(delete(ScenarioEdit).where(ScenarioEdit.scenario_id == row.id))
    for ordinal, document in enumerate(documents):
        target = document.get("polygon_geojson") or document.get("footprint_geojson")
        session.add(
            ScenarioEdit(
                scenario_id=row.id,
                ordinal=ordinal,
                edit_type=document["edit_type"],
                target=from_shape(geometry(target), srid=4326) if target else None,
                parameters=document,
                sha256=canonical_digest(document),
            )
        )
    row.version += 1
    row.updated_at = datetime.now(UTC)
    row.scenario_sha256 = canonical_digest(
        {"snapshot_id": str(row.snapshot_id), "edits": documents}
    )
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="scenario_edits_replaced",
            resource_id=row.id,
            details={"version": row.version, "digest": row.scenario_sha256},
        )
    )
    session.commit()
    response.headers["ETag"] = f'"{row.version}"'
    return scenario_view(session, row)


@router.post("/scenarios/{identifier}/simulate", response_model=JobAccepted, status_code=202)
def simulate(
    identifier: UUID,
    body: SimulationRequest,
    idempotency_key: Annotated[str, Header()],
    session=Depends(session_dependency),
    user=Depends(current_user),
):
    row = owned_scenario(session, identifier, user.id, lock=True)
    if any(model not in MODELS for model in body.requested_models):
        raise TwinError("MODEL_NOT_AVAILABLE", "Requested model has no validated implementation")
    job = submit(
        session,
        row,
        user.id,
        idempotency_key,
        body.model_dump(mode="json"),
        edits_for(session, row),
    )
    publish_hint(job.id)
    return JobAccepted(job_id=job.id, status_url=f"/v1/jobs/{job.id}")


@router.get("/jobs/{identifier}", response_model=JobView)
def get_job(identifier: UUID, session=Depends(session_dependency), user=Depends(current_user)):
    row = owned_job(session, identifier, user.id)
    return JobView.model_validate(row, from_attributes=True)


@router.post("/jobs/{identifier}/cancel", response_model=JobView)
def cancel_job(identifier: UUID, session=Depends(session_dependency), user=Depends(current_user)):
    row = cancel(session, owned_job(session, identifier, user.id, lock=True))
    return JobView.model_validate(row, from_attributes=True)


@router.get("/results/{identifier}", response_model=ResultView)
def result(identifier: UUID, session=Depends(session_dependency), user=Depends(current_user)):
    return ResultView.model_validate(
        owned_result(session, identifier, user.id), from_attributes=True
    )


@router.get("/scenarios/{identifier}/reports", response_model=list[ResultView])
def reports(
    identifier: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: UUID | None = None,
    session=Depends(session_dependency),
    user=Depends(current_user),
):
    owned_scenario(session, identifier, user.id)
    query = (
        select(SimulationResult)
        .join(SimulationJob, SimulationJob.id == SimulationResult.job_id)
        .where(SimulationJob.scenario_id == identifier, SimulationJob.requested_by == user.id)
        .order_by(SimulationResult.id)
    )
    if cursor:
        query = query.where(SimulationResult.id > cursor)
    return [
        ResultView.model_validate(row, from_attributes=True)
        for row in session.scalars(query.limit(limit))
    ]
