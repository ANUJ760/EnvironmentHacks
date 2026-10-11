"""PostgreSQL source of truth with SKIP LOCKED claims and fenced completion."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from ecotwin.db.models import SimulationJob, UserAccount
from ecotwin.errors import TwinError
from ecotwin.simulation.command import canonical_digest

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELED"}


def submit(session, scenario, user_id, key, request, edits):
    if not key or len(key) > 128:
        raise TwinError("INVALID_IDEMPOTENCY_KEY", "Idempotency-Key must contain 1–128 characters")
    frozen = {
        "snapshot_id": str(scenario.snapshot_id),
        "scenario_id": str(scenario.id),
        "scenario_revision": scenario.version,
        "scenario_digest": scenario.scenario_sha256,
        "edits": edits,
        "request": request,
    }
    digest = canonical_digest(frozen)
    from ecotwin.config import get_settings

    session.scalar(select(UserAccount).where(UserAccount.id == user_id).with_for_update())
    existing = session.scalar(
        select(SimulationJob).where(
            SimulationJob.requested_by == user_id, SimulationJob.idempotency_key == key
        )
    )
    if existing:
        if existing.request_digest != digest:
            raise TwinError(
                "IDEMPOTENCY_CONFLICT", "This key already pins a different request", 409
            )
        session.commit()
        return existing
    pending = session.scalar(
        select(func.count())
        .select_from(SimulationJob)
        .where(
            SimulationJob.requested_by == user_id,
            SimulationJob.state.in_(["QUEUED", "RUNNING", "RETRY_WAIT", "CANCEL_REQUESTED"]),
        )
    )
    if pending >= get_settings().max_pending_jobs_per_user:
        raise TwinError(
            "JOB_QUOTA_EXCEEDED", "Wait for or cancel pending jobs before submitting more", 429
        )
    now = datetime.now(UTC)
    identifier = uuid4()
    session.execute(
        insert(SimulationJob)
        .values(
            id=identifier,
            scenario_id=scenario.id,
            requested_by=user_id,
            idempotency_key=key,
            request_digest=digest,
            frozen_input=frozen,
            state="QUEUED",
            attempt=0,
            not_before=now,
            progress_pct=0,
        )
        .on_conflict_do_nothing(index_elements=["requested_by", "idempotency_key"])
    )
    row = session.scalar(
        select(SimulationJob).where(
            SimulationJob.requested_by == user_id, SimulationJob.idempotency_key == key
        )
    )
    if row.request_digest != digest:
        raise TwinError(
            "IDEMPOTENCY_CONFLICT",
            "This key was used with a different scenario revision or request",
            409,
        )
    session.commit()
    return row


def claim(session, worker_id, settings, job_id=None):
    now = datetime.now(UTC)
    # Sweep interrupted cancellation and exhausted expired leases before claiming.
    expired = list(
        session.scalars(
            select(SimulationJob)
            .where(
                SimulationJob.state.in_(["RUNNING", "CANCEL_REQUESTED"]),
                SimulationJob.locked_until < now,
            )
            .with_for_update(skip_locked=True)
        )
    )
    for job in expired:
        if job.state == "CANCEL_REQUESTED":
            job.state = "CANCELED"
            job.finished_at = now
        elif job.attempt >= settings.worker_max_attempts:
            job.state = "FAILED"
            job.error_code = "RETRY_LIMIT_EXCEEDED"
            job.finished_at = now
        else:
            job.state = "RETRY_WAIT"
            job.not_before = now
        job.locked_until = None
        job.worker_id = None
    session.flush()
    row = session.scalar(
        select(SimulationJob)
        .where(
            SimulationJob.state.in_(["QUEUED", "RETRY_WAIT"]),
            SimulationJob.id == job_id if job_id else True,
            SimulationJob.not_before <= now,
            SimulationJob.attempt < settings.worker_max_attempts,
        )
        .order_by(SimulationJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if row:
        row.state = "RUNNING"
        row.attempt += 1
        row.worker_id = worker_id
        row.locked_until = now + timedelta(seconds=settings.worker_lease_seconds)
        row.started_at = now
        row.progress_pct = 1
    session.commit()
    return row


def cancel(session, job):
    if job.state in TERMINAL:
        return job
    job.state = "CANCEL_REQUESTED" if job.state == "RUNNING" else "CANCELED"
    if job.state == "CANCELED":
        job.finished_at = datetime.now(UTC)
    session.commit()
    return job
