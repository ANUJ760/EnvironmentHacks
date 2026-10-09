FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.12
COPY pyproject.toml uv.lock ./
COPY ecotwin ./ecotwin
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ARG GIT_REVISION=unknown
ARG BUILD_TIMESTAMP=unknown
LABEL org.opencontainers.image.revision=$GIT_REVISION org.opencontainers.image.created=$BUILD_TIMESTAMP
RUN groupadd --gid 10001 ecotwin && useradd --uid 10001 --gid 10001 --create-home ecotwin
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /app/.venv ./.venv
COPY ecotwin ./ecotwin
COPY model_parameters ./model_parameters
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/livez', timeout=3)"
ENTRYPOINT ["entrypoint"]
CMD ["uvicorn", "ecotwin.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
