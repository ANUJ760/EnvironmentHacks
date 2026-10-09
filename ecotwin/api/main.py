import re
import time
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from ecotwin.api.error_handlers import problem, register_handlers
from ecotwin.api.routes import cities, scenarios
from ecotwin.config import get_settings
from ecotwin.db.session import session_dependency
from ecotwin.errors import TwinError
from ecotwin.telemetry.logging import configure
from ecotwin.telemetry.metrics import LATENCY, REQUESTS


@asynccontextmanager
async def lifespan(app):
    settings = get_settings()
    configure(settings.log_level)
    yield


app = FastAPI(title="EcoTwin Backend", version="0.2.0", lifespan=lifespan)
register_handlers(app)


# Validation intentionally occurs on startup and when CLI executes, not module import.
# Explicit origins are configured once by the app factory below.
def configure_cors(application):
    import os

    from dotenv import dotenv_values

    origin_setting = (
        os.environ.get("CORS_ALLOWED_ORIGINS")
        or dotenv_values(".env").get("CORS_ALLOWED_ORIGINS")
        or "http://localhost:3000"
    )
    origins = origin_setting.split(",")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "If-Match",
            "Idempotency-Key",
            "X-Request-ID",
        ],
        expose_headers=["ETag", "X-Request-ID"],
    )


configure_cors(app)


@app.middleware("http")
async def request_context(request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request.state.request_id = (
        supplied if re.fullmatch(r"[A-Za-z0-9-]{1,64}", supplied) else str(uuid4())
    )
    structlog.contextvars.bind_contextvars(request_id=request.state.request_id, service="api")
    started = time.monotonic()
    if request.method in {"POST", "PUT", "PATCH"}:
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return problem(request, "UNSUPPORTED_MEDIA_TYPE", "JSON request required", 415)
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 1_000_000:
                return problem(request, "REQUEST_TOO_LARGE", "JSON body exceeds 1 MB", 413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    try:
        response = await call_next(request)
    except Exception:
        structlog.get_logger().error("request_failed", error_code="INTERNAL_ERROR")
        response = problem(
            request, "INTERNAL_ERROR", "Request failed; inspect correlated server logs", 500
        )
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    route = getattr(request.scope.get("route"), "path", "unmatched")
    duration = time.monotonic() - started
    REQUESTS.labels(request.method, route, str(response.status_code)).inc()
    LATENCY.labels(route).observe(duration)
    structlog.get_logger().info(
        "http_request",
        route=route,
        status=response.status_code,
        duration_ms=round(duration * 1000, 2),
    )
    structlog.contextvars.clear_contextvars()
    return response


@app.get("/livez", tags=["health"], response_model=dict)
def livez():
    return {"status": "alive"}


@app.get("/readyz", tags=["health"], response_model=dict)
def readyz(session=Depends(session_dependency)):
    try:
        session.execute(text("SELECT 1"))
        version = session.scalar(text("SELECT version_num FROM alembic_version"))
        if version != "0002":
            raise TwinError("DATABASE_NOT_READY", "Migration head is not current", 503)
        return {"status": "ready", "migration": version}
    except TwinError:
        raise
    except Exception as exc:
        raise TwinError("DATABASE_NOT_READY", "Database or schema unavailable", 503) from exc


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(cities.router)
app.include_router(scenarios.router)
