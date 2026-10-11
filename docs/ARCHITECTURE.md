# EcoTwin: lightweight city-planning simulator

## Purpose and implemented scope

Compare the energy, waste, water and environmental consequences of changing a
real city. Click mapped features or any ground location, or draw a polygon. Choose
removal/clearing, filling/raising ground, or conversion to grass. Results compare
baseline and intervention **under identical weather and air conditions**.

The current release is an evidence-backed **screening simulator**, not a calibrated
city-wide pollution, heat or hydraulic model. Its principal outputs are:

- Clipped OSM inventory and WorldCover land-cover composition.
- NRCS storm runoff and soil-group sensitivity, where cover and rainfall support it.
- On-site and displacement-adjusted building energy and operational waste proxies.
- One-time demolition material, recovery and residual mass balance.
- Fill volume/material from mapped area and editable depth/height/density assumptions.
- Vegetation/standing-carbon loss, hourly solar effects and a gross PM₂.₅ deposition
  capacity proxy. Deposition is **not** a street-concentration change.
- Current regional CAMS pollutant/CO₂/methane context and Open-Meteo weather.
- JSON research export containing inputs, model version, dataset references,
  actual weather/air samples, limitations and SHA256 digests.

Water chemistry, atmospheric oxygen, flood depth, landfill hazards and causal
street temperature/pollution changes remain explicitly unavailable. Water/forest
changes have evidence-backed qualitative findings alongside supported quantities.
Intensity defaults are adjustable scenario assumptions, not locally measured values.
Future calibration requires independent local measurements.

## Components

```text
Browser: Next.js / React + MapLibre flat 2D
  ├─ OSM/OpenFreeMap tiles, swisstopo aerial imagery, mapped tree asset
  └─ Same-origin Next.js gateway
       └─ FastAPI
            ├─ PostGIS: cities, pinned revisions, geometry, scenarios, jobs
            ├─ Planning engine: bounded geometry + deterministic calculations
            ├─ Provider adapters: live weather / regional air + pinned fallback
            └─ ObjectStore: local files now; private S3 via IAM in AWS

Explicit ingestion CLI → verified raw objects + manifests → PostGIS snapshot
Existing saved-scenario jobs → database/SQS queue → worker → stored reports
Optional Ollama → ranks existing verified findings only; never computes impacts
```

Key files: `ecotwin/models/planning.py`, `ecotwin/api/routes/planning.py`,
`ecotwin/ingestion/air_forecast.py`, `ecotwin/storage/`,
`frontend/src/components/map/PlanningPanel.tsx`, `CityMap.tsx`.

## Data and reproducibility

Zurich has a downloaded OSM extract, native-resolution WorldCover 2021 study crop,
weather imports and a newly downloaded **73-hour CAMS/Open-Meteo air forecast**.
Raw data stay ignored by Git. Import metadata include source, acquisition time,
license, content hash and storage-independent object key.

```bash
# Run on the host with DATABASE_URL pointing at localhost and a writable local data directory.
ecotwin ingest air-forecast --city zurich-center
ecotwin ingest weather --city zurich-center --forecast-hours 72
ecotwin datasets verify --city zurich-center
ecotwin city snapshot --city zurich-center
```

An offline air import uses `--file PATH`, with original `_ecotwin_issued_at` retained.
No provider data are imported during an API request. Live previews cache weather
for five minutes and regional air for fifteen minutes; exported samples freeze
each calculation. Only a valid, sufficiently complete and fresh forecast drives
weather-dependent proxies. Missing data are never replaced with fabricated zeros.
Full-city visuals exceed the smaller verified scientific study boundary: geographic
gaps are exposed, not extrapolated. Register and import additional studies (at most
25 km² each) to extend coverage. Whole-city scientific coverage requires tiled
datasets and validation; this release does not claim that the full-city visual map
already has complete scientific measurements.

## Lightweight operation and test

No new rendering or ML dependency is required. The map stays flat, with bounded
pixel ratio, workers and tile cache. Drawing is native GeoJSON, capped at 100 points.
Planning requests are capped at 1 km², 5 km extent and 5,000 intersecting mapped
objects. Inputs debounce by 400 ms; panels refresh once per minute. Scrollable
inspectors do not increase canvas dimensions. AI runs only on explicit request.

```bash
docker compose up -d --build api worker
cd frontend && npm ci && npm run dev
# In separate terminals:
.venv/bin/pytest -q tests/unit tests/contracts
cd frontend && npm run test && npm run typecheck && npm run lint
RUN_LIVE_MAP_TESTS=1 npm run test:e2e -- tests/e2e/planning.test.ts
```

The live smoke test covers real building energy/displacement and material balance,
custom-area drawing, filling, before/after map reuse, regional air and JSON export.
Validated locally on 2026-10-11: 126 backend unit/contract tests, 38 frontend tests,
four live map/planning checks against both development and the Docker frontend,
TypeScript, lint, production builds and an actual exported-report replay passed.
The optional Gemma explanation was also checked against the host Ollama service.
The complete backend regression suite additionally passed: 177 tests, with 13
opt-in integration tests skipped. Production dependencies have no known findings
in `npm audit --omit=dev`; development-tool advisories remain separate release work.
Replay an exported report without network access or a database:

```bash
.venv/bin/python scripts/replay_planning_report.py PATH_TO_EXPORTED_REPORT.json
```

Replay validates both hashes and recalculates all metrics from the captured inputs.
Metric comparison allows 1e-12 relative / 1e-9 absolute floating-point tolerance
across Python runtimes. Hashes are unsigned integrity checks, not proof of origin.
This verifies internal reproducibility, not local scientific calibration.

## Docker → AWS handoff

Backend and frontend have separate Dockerfiles. `compose.yaml` runs PostGIS,
migrations, API, worker and optional frontend; the existing Terraform runbook covers
the backend AWS infrastructure. New planning code uses the existing ObjectStore
contract—no workstation path is required in production.

Use `ECOTWIN_STORAGE_MODE=s3`, `ECOTWIN_S3_BUCKET`, `ECOTWIN_S3_PREFIX=ecotwin/`
and `AWS_REGION`; use IAM task roles, never baked-in AWS credentials. Transfer
registered raw/processed/manifest objects **preserving their exact object keys and
hashes**, or re-ingest with the S3 configuration. PostGIS remains the query store
(RDS PostgreSQL with PostGIS); S3 is the object store, not a spatial database.
Existing production validation requires Cognito, S3, SQS and no local fallback.

Recommended deployment: ECR images → ECS/Fargate services; RDS/PostGIS; private
S3; SQS worker queue; ALB HTTPS; Secrets Manager and CloudWatch. Run migrations
and ingestion as explicit tasks. No AWS resources are created by this change.

For public visualization assets, use CloudFront with a private S3 origin. Build the
frontend with `--build-arg NEXT_PUBLIC_MAP_ASSET_BASE_URL=https://YOUR_CDN` and
provide `maps/zurich-trees.geojson` there, with appropriate CORS. Empty uses the
bundled local asset. Scientific datasets remain private and are never exposed by
this CDN setting. External map/provider connectivity is required for uncached data.

Ollama is optional; an AWS release can disable it or connect a separately hosted
local service. It is not bundled into either application image. Add gateway/WAF
rate limits, provider quotas and monitoring before a public release. Review
Open-Meteo/CAMS and imagery license/commercial-use terms before deployment.
