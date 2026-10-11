"""Bounded subprocess execution, heartbeat fencing and transactional completion."""

import multiprocessing
import time
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select

from ecotwin.db.models import SimulationJob, SimulationResult
from ecotwin.db.session import session_factory
from ecotwin.errors import TwinError
from ecotwin.simulation.command import canonical_digest
from ecotwin.simulation.orchestrator import execute

TRANSIENT = {"STORAGE_UNAVAILABLE", "UPSTREAM_UNAVAILABLE", "DATABASE_UNAVAILABLE"}


def child_execute(frozen, pipe):
    try:
        # Spawn creates fresh engine pools and prevents inheriting active DB sockets.
        with session_factory()() as session:
            report = execute(session, frozen, lambda progress: pipe.send(("progress", progress)))
        pipe.send(("result", report))
    except TwinError as exc:
        pipe.send(("error", {"code": exc.code, "detail": exc.detail}))
    except Exception:
        pipe.send(
            (
                "error",
                {
                    "code": "SIMULATION_FAILED",
                    "detail": "Simulation failed validation or execution; inspect correlated worker logs",
                },
            )
        )
    finally:
        pipe.close()


def process_job(job, worker_id, settings, stop=lambda: False):
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=child_execute, args=(job.frozen_input, send))
    process.start()
    send.close()
    deadline = time.monotonic() + settings.simulation_timeout_seconds
    report = None
    error = None
    progress = 1
    last_heartbeat = 0.0
    try:
        while True:
            if receive.poll(0.2):
                try:
                    kind, payload = receive.recv()
                except EOFError:
                    error = {
                        "code": "SIMULATION_FAILED",
                        "detail": "Simulation subprocess ended without a result",
                    }
                    break
                if kind == "progress":
                    progress = payload
                elif kind == "result":
                    report = payload
                    break
                else:
                    error = payload
                    break
            if time.monotonic() > deadline:
                error = {
                    "code": "SIMULATION_TIMEOUT",
                    "detail": "Simulation exceeded its configured hard deadline",
                }
                break
            if stop():
                error = {
                    "code": "STORAGE_UNAVAILABLE",
                    "detail": "Worker shutting down; retry queued",
                }
                break
            if time.monotonic() - last_heartbeat > 1:
                with session_factory()() as session:
                    current = session.scalar(
                        select(SimulationJob).where(SimulationJob.id == job.id).with_for_update()
                    )
                    if current.worker_id != worker_id or current.attempt != job.attempt:
                        return
                    if current.state == "CANCEL_REQUESTED":
                        current.state = "CANCELED"
                        current.finished_at = datetime.now(UTC)
                        current.locked_until = None
                        current.worker_id = None
                        session.commit()
                        return
                    current.progress_pct = progress
                    current.locked_until = datetime.now(UTC) + timedelta(
                        seconds=settings.worker_lease_seconds
                    )
                    session.commit()
                last_heartbeat = time.monotonic()
            if not process.is_alive() and not receive.poll():
                error = {
                    "code": "SIMULATION_FAILED",
                    "detail": "Simulation subprocess exited unexpectedly",
                }
                break
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join()
        receive.close()
    with session_factory()() as session:
        current = session.scalar(
            select(SimulationJob).where(SimulationJob.id == job.id).with_for_update()
        )
        if (
            current.worker_id != worker_id
            or current.attempt != job.attempt
            or current.state not in {"RUNNING", "CANCEL_REQUESTED"}
        ):
            return
        now = datetime.now(UTC)
        if current.state == "CANCEL_REQUESTED":
            current.state = "CANCELED"
            current.finished_at = now
        elif report:
            result = SimulationResult(
                job_id=current.id,
                input_digest=report["input_digest"],
                output_digest=canonical_digest(report),
                model_versions=report["model_versions"],
                metrics=report["metrics"],
                warnings=report["warnings"],
                evidence=report["evidence"],
            )
            session.add(result)
            session.flush()
            current.result_id = result.id
            current.state = "SUCCEEDED"
            current.progress_pct = 100
            current.finished_at = now
        else:
            current.error_code = error["code"]
            current.error_message = error["detail"]
            if error["code"] in TRANSIENT and current.attempt < settings.worker_max_attempts:
                current.state = "RETRY_WAIT"
                current.not_before = now + timedelta(seconds=2**current.attempt)
            else:
                current.state = "FAILED"
                current.finished_at = now
        current.worker_id = None
        current.locked_until = None
        session.commit()

    from ecotwin.telemetry.metrics import JOBS

    JOBS.labels(current.state).inc()
    structlog.get_logger().info(
        "simulation_job_completed",
        job_id=str(job.id),
        state=current.state,
        attempt=current.attempt,
        error_code=current.error_code,
    )
