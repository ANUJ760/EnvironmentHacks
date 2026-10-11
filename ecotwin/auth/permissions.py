from sqlalchemy import select

from ecotwin.db.models import Scenario, SimulationJob, SimulationResult
from ecotwin.errors import TwinError


def owned_scenario(session, identifier, user_id, lock=False):
    query = select(Scenario).where(Scenario.id == identifier, Scenario.owner_user_id == user_id)
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if not row:
        raise TwinError("SCENARIO_NOT_FOUND", "Scenario not found", 404)
    return row


def owned_job(session, identifier, user_id, lock=False):
    query = select(SimulationJob).where(
        SimulationJob.id == identifier, SimulationJob.requested_by == user_id
    )
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if not row:
        raise TwinError("JOB_NOT_FOUND", "Job not found", 404)
    return row


def owned_result(session, identifier, user_id):
    row = session.scalar(
        select(SimulationResult)
        .join(SimulationJob, SimulationResult.job_id == SimulationJob.id)
        .where(SimulationResult.id == identifier, SimulationJob.requested_by == user_id)
    )
    if not row:
        raise TwinError("RESULT_NOT_FOUND", "Result not found", 404)
    return row
