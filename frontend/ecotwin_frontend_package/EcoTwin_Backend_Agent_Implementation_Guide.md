# EcoTwin Backend — Agent Implementation Specification

**Status:** Build contract / reference architecture • **Edition:** 9 October 2026  
**Audience:** Autonomous coding agent and human reviewer • **Deliverable:** Fully executable, production-oriented backend, infrastructure code, tests, and a minimal frontend integration contract.  
**Project:** `EnvironmentHacks / EcoTwin` • **Primary language:** Python 3.12 • **Deployment:** OCI Docker images → Amazon ECR → Amazon ECS Fargate.

> **Execution rule:** Implement and test every function and endpoint declared *in the required scope* below. No `TODO`, `pass`, `NotImplementedError`, hardcoded scientific outcome, dummy response, fabricated dataset, or placeholder endpoint may be shipped. External API tokens, AWS account resources, TLS domain, and actual licensed datasets are operator-provided prerequisites, **not** values a coding agent can manufacture. If a required upstream input is unavailable, return a typed and actionable error rather than inventing output. An external dependency that cannot be tested must be reported honestly, not declared working.

## 0. Operating instructions for the coding agent

1. Before editing, inspect the repository, README, test suite, dependency definitions, commit status, and Python package layout. The supplied README reports a working mass-balance, forecasting, routing optimizer and 49 tests, but **verify this against the actual checkout**. Preserve public APIs and scientific invariants that tests establish; never overwrite functioning domain code with a new toy implementation.
2. Record the existing baseline: `git status --short`, `python -m unittest discover tests` and a dependency scan. Add equivalent `pytest` checks for new modules. If the baseline test suite fails before changes, capture that separately; do not mask it.
3. Implement changes incrementally, with real migrations, typed request/response models, reproducible model parameter files, and integration tests. Commit coherent changes; do not use generated sample results in actual production API responses.
4. Treat geography, measurement, model outputs, and illustrations as separate categories. Map geometry comes from licensed data, measurements from recorded sources, outputs from declared formulas, and artistic sprites solely from the frontend.
5. The implementation **must run offline** with previously imported local data and a local PostGIS database. External API ingestion is an explicit, separate command and must not occur during every user simulation request.
6. Use pinned dependency versions via a committed lockfile and immutable Docker image digest in deployment. Confirm compatibility using tests; versions suggested in this document are minimum major-version choices, not an assertion that future/latest versions are safe.
7. Never expose raw AWS keys, OpenAQ keys, connection strings, or developer auth secrets in code, images, logs, or browser bundles. Do not commit `.env`, `data/raw`, or exports containing sensitive or proprietary records.
8. End with a machine-readable implementation report listing commands executed, tests passed/failed, endpoints verified, provenance of test datasets, deployment result, remaining external prerequisites, and any unavailable simulation domains. A green build is not proof of real-city scientific calibration.

### 0.1 Definition of “complete”

**Mandatory finished features:** one or more configurable city study areas; OSM geographic ingestion; WorldCover land-cover ingestion; Open-Meteo forecast ingestion; OpenAQ observation ingestion when credentials/coverage are available; source/version manifest; PostGIS persistence; local and S3 object-storage adapters; baseline snapshots; scenario editing and isolation; rainfall-runoff volume screening model; vegetation-area delta; solar PV potential model under explicit user parameters; adapter to the verified existing EcoTwin waste/energy model; asynchronous jobs; results/provenance; authentication for mutable resources; observability; Docker Compose; AWS ECS/ECR/RDS/S3/SQS deployment IaC; API integration tests; failure-mode tests.

**Functionally supported but strictly observational:** station-level air pollution, provided weather conditions, Landsat surface temperature when ingested. These support mapped overlays or contextual explanations, **not automatic causal temperature/air-quality deltas after tree removal**. Detailed urban CFD, animal mortality, species population change, health incidence, network-level flood hydraulics, unseen city infrastructure, and grid power flow without utility topology are **out of scope**. API responses for requested unsupported metrics must use `MODEL_NOT_AVAILABLE` or `INSUFFICIENT_INPUT_DATA` with reasons; do not create fake engines. Full scalability across arbitrary global cities depends on per-city dataset coverage and license/access conditions.

### 0.2 Production qualities and acceptance targets

- Determinism: identical dataset digests, model version, parameters, and request yield identical result digests (excluding job metadata/timestamps).
- Geographic correctness: WGS84 input in GeoJSON, meter-based area calculations in suitable projected CRS; never compute square meters from unprojected longitude/latitude.
- Isolation: scenarios do not mutate city baseline features or other users' scenarios; all writes are transactionally committed.
- Integrity: checksum on imported objects, input ranges, unit normalization, source timestamp and license recorded for all datasets.
- Reliability: at-least-once-safe job execution with idempotent submission, retries only for transient failures, cancellation, timeout, error details and dead-letter handling.
- Security: authenticated mutation APIs, authorization by owner, bounded upload/query size, query parameterization, HTTPS in production, least-privilege IAM, pinned images and non-root containers.
- Observability: JSON logs with request/job IDs, health/readiness endpoints, ingest outcome counts, data staleness metrics, worker lag, alerts.
- Performance acceptance for a **bounded study area** (max 25 km², max 250,000 vector features, max 2 million land-cover cells): cached city tile/viewport query p95 under 1.5 s on representative deployment; short deterministic runoff model target under 15 s; long jobs accepted with HTTP 202 and progress polling. Benchmark on actual hardware and publish outcomes; do not claim targets were met if untested.

## 1. Reference architecture and service boundaries

![EcoTwin production backend architecture](assets/ecotwin-backend-architecture.png)

**Services / tasks:**

- `ecotwin-api`: FastAPI + SQLAlchemy 2 + Pydantic 2. Stateless application exposing `/v1/*`, `/livez`, `/readyz`, and OpenAPI. Runs as an ECS service behind an HTTPS Application Load Balancer; local port `8000`.
- `ecotwin-worker`: independent worker process built from the **same versioned application image**. Consumes database-backed jobs locally or SQS message hints on AWS, executes simulations, stores immutable reports, and writes job statuses. Runs as ECS service without a public listener.
- `ecotwin-ingest`: CLI entry point in the **same Docker image**, run on demand or as a scheduled ECS one-off task for source ingestion and refresh. Do not run expensive data imports in API startup events.
- `postgres`: PostGIS 16 locally and matching supported Amazon RDS PostgreSQL major release in AWS. Source of truth for relational/geometric records, jobs and scenario metadata.
- `object storage`: local protected filesystem in development; S3 in cloud; content-addressed immutable large raw files and derived rasters. Files are never fetched from AWS by the simulation domain modules directly.
- `external inputs`: OpenStreetMap/Geofabrik, ESA WorldCover, Open-Meteo and OpenAQ. Optional NASA POWER, Landsat, municipality datasets require explicit integration and provenance.

**Data path:** Importers download → normalize → validate → register immutable dataset revision → persist geographic/measurement records → create immutable city baseline → user constructs scenario → backend validates geometry/parameters → job queued → worker reconstructs exact inputs → executes only supported models → validates physical/domain invariants → saves result and source references → API returns result to minimal frontend.

**No new microservice per scientific model.** Modules are isolated Python packages executed by worker processes; split to dedicated independently deployable services only after load profiling or distinct runtime/security requirements justify it. One image, three ECS task definitions, and two always-on services are sufficient initially.

## 2. Complete repository structure (required target)

```text
EnvironmentHacks/
├── README.md
├── LICENSE
├── pyproject.toml                  # Python project and CLI entry points
├── uv.lock                         # Resolved dependency lockfile
├── .python-version                 # 3.12
├── .env.example                    # Explained safe local defaults
├── .gitignore
├── .dockerignore
├── Dockerfile                      # Multi-stage image; non-root runtime
├── compose.yaml                    # api, worker, postgis; local datasets mounted RO
├── Makefile                        # Explicit dev/test/ingest/build commands
├── alembic.ini
├── migrations/
│   ├── env.py
│   └── versions/                    # Actual schema migrations
├── ecotwin/                        # Preserve pre-existing domain modules
│   ├── __init__.py
│   ├── units.py
│   ├── categories.py
│   ├── stream.py
│   ├── facility.py
│   ├── routing.py
│   ├── balance.py
│   ├── scenario.py
│   ├── synthetic.py
│   ├── forecasting.py
│   ├── optimization.py
│   ├── exceptions.py
│   ├── config.py                  # Pydantic Settings; fail-fast validation
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   ├── models.py
│   │   └── repositories/            # city, datasets, readings, scenarios, jobs
│   ├── storage/
│   │   ├── base.py                # Streaming object interface
│   │   ├── local.py
│   │   ├── s3.py
│   │   ├── checked_fallback.py
│   │   └── manifest.py
│   ├── ingestion/
│   │   ├── cli.py
│   │   ├── downloader.py          # retries/timeouts/checksums
│   │   ├── osm.py
│   │   ├── worldcover.py
│   │   ├── open_meteo.py
│   │   ├── openaq.py
│   │   ├── landsat.py             # optional ingest, never dummy readings
│   │   ├── waste_import.py
│   │   └── catalog.py
│   ├── spatial/
│   │   ├── geometry.py
│   │   ├── cover_grid.py
│   │   ├── spatial_queries.py
│   │   └── city_snapshot.py
│   ├── models/
│   │   ├── types.py               # Quantity types, evidence classes
│   │   ├── landcover.py           # Vegetation/impervious deltas
│   │   ├── runoff.py              # Screening runoff volume
│   │   ├── solar_pv.py            # Assumption-based generation model
│   │   ├── waste_adapter.py       # Connects existing engine
│   │   └── registry.py            # Required input contracts
│   ├── simulation/
│   │   ├── command.py
│   │   ├── validation.py
│   │   ├── orchestrator.py
│   │   ├── comparison.py
│   │   ├── evidence.py
│   │   └── reports.py
│   ├── jobs/
│   │   ├── queue.py
│   │   ├── db_queue.py
│   │   ├── sqs_queue.py
│   │   ├── processor.py
│   │   └── worker.py
│   ├── auth/
│   │   ├── jwt.py
│   │   ├── permissions.py
│   │   └── dev_tokens.py
│   ├── api/
│   │   ├── main.py
│   │   ├── dependencies.py
│   │   ├── error_handlers.py
│   │   ├── schemas.py
│   │   └── routes/                # cities, datasets, observations, scenarios,
│   │                              # simulations, jobs, results, health
│   └── telemetry/
│       ├── logging.py
│       └── metrics.py
├── data/
│   ├── raw/                       # Git-ignored real downloads
│   ├── processed/                 # Git-ignored derived files
│   └── manifests/                 # Checked-in schemas, not bulk source data
├── model_parameters/
│   ├── runoff_coefficients.v1.yaml
│   ├── solar_defaults.v1.yaml
│   └── units.yaml
├── tests/
│   ├── unit/                      # math, units, config, storage, scenario
│   ├── integration/               # PostGIS migrations, jobs, API, importers
│   ├── contracts/                 # OpenAQ/Open-Meteo recorded response shapes
│   ├── property/                  # invariants and reproducibility
│   ├── load/                      # locust/k6 benchmark definitions
│   └── fixtures/                  # tiny openly sourced or hand-built geometry
├── scripts/
│   ├── check_data_licenses.py
│   ├── smoke_local.sh
│   ├── backup_restore_check.sh
│   └── generate_openapi.py
├── infra/
│   └── terraform/
│       ├── versions.tf
│       ├── providers.tf
│       ├── variables.tf
│       ├── networking.tf
│       ├── security.tf
│       ├── storage.tf
│       ├── database.tf
│       ├── messaging.tf
│       ├── compute.tf
│       ├── alb_tls.tf
│       ├── observability.tf
│       ├── outputs.tf
│       ├── terraform.tfvars.example
│       └── README.md
├── .github/workflows/
│   ├── ci.yml
│   └── deploy-aws.yml
└── frontend/
    ├── README.md                  # Minimal client instructions only
    ├── package.json
    ├── tsconfig.json
    ├── .env.example               # NEXT_PUBLIC_API_BASE_URL only
    └── src/lib/api-types.ts       # Types generated from OpenAPI
```

**Repository migration rule:** The current codebase may already have `examples/`, `tests/test_*.py` and `ecotwin/*`. Keep those files working and introduce new directories without breaking imports. Preserve the existing tests in addition to the new target layout. `frontend/` is only a minimal OpenAPI consumer scaffold: **do not build the interactive frontend under this assignment**.

## 3. Explicit technology decisions and responsibility

| Technology | Required responsibility | Not used for |
|---|---|---|
| Python 3.12; uv lockfile | Application and scientific runtime; reproducible install | Browser rendering |
| FastAPI + Pydantic v2 | Validation, JSON API, OpenAPI 3 schema, typed errors | Heavy synchronous raster import inside requests |
| SQLAlchemy 2 + Alembic + psycopg 3 | Transactional persistence, migrations, connection pooling | Geometry math without PostGIS |
| PostgreSQL 16 + PostGIS | City polygons, spatial joins/indexes, scenarios, observations, job state | Multi-GB raw rasters |
| GeoPandas, Shapely, pyproj, Rasterio, NumPy | Geometric conversion, raster clipping, spatial-area model | Drawing cartoon sprites |
| httpx + tenacity | Upstream HTTP clients, timeout, retry/backoff | Unlimited blind scraping |
| boto3 | S3 object storage, SQS cloud messaging | Simulation calculation APIs |
| scipy / existing optimizer | Proven optimization and numerical routines | Invented AI-only impact scores |
| pytest, hypothesis, testcontainers | Unit, property and real PostGIS integration validation | Replacing production source observations with synthetic data |
| structlog + Prometheus-compatible metrics | Correlated structured logs and counters | Logging API keys or raw identity tokens |
| Docker / Compose | Same runtime locally and on ECS | Embedding data/secrets into images |
| Terraform + GitHub Actions OIDC | Reproducible AWS creation and release automation | Storing AWS user access keys in GitHub secrets |

Pin and resolve exact compatible package versions at implementation time into `uv.lock`; CI must use `uv sync --frozen`. Upgrade deliberately via PR with tests. Do not specify floating `latest` image tags in deployments.

## 4. Data catalog: official access links, coverage, refresh and intended usage

| Dataset / endpoint | Mandatory? | Transport & official link | Implementation use / critical caveat |
|---|---|---|---|
| OpenStreetMap via Geofabrik | Yes | `.osm.pbf` country/regional extracts: https://download.geofabrik.de/ ; index: https://download.geofabrik.de/index-v1.json | Road/building/park/water geometry. For a small development bbox, a rate-limited Overpass query via OSMnx is permitted. ODbL attribution and share-alike conditions apply to relevant derived databases. |
| ESA WorldCover 2021 v200 | Yes | Public COG tiles: https://esa-worldcover.org/en/data-access ; `s3://esa-worldcover/v200/2021/map` (unsigned reads); catalog: https://registry.opendata.aws/esa-worldcover/ | Approximately 10 m cells; classes 10 tree cover, 30 grassland, 50 built-up, 80 water, etc. **2021 baseline**, not a current individual-tree inventory. CC BY 4.0 attribution. |
| Open-Meteo Weather Forecast | Yes | `https://api.open-meteo.com/v1/forecast` ; docs: https://open-meteo.com/en/docs | Hourly `temperature_2m`, `relative_humidity_2m`, `precipitation`, `wind_speed_10m`, `shortwave_radiation`; model-based grid weather. Noncommercial free-tier licensing/limits; use paid access if required. |
| Open-Meteo Historical | Optional for long baseline | `https://archive-api.open-meteo.com/v1/archive` ; docs: https://open-meteo.com/en/docs/historical-weather-api | Historical modeled weather for calibration/background only; not street sensor observations. |
| OpenAQ API v3 | Conditional (air-quality layer requires key/data) | `https://api.openaq.org/v3/locations`, `/v3/sensors/{sensor_id}/hours` ; https://docs.openaq.org/ ; key guide: https://docs.openaq.org/using-the-api/api-key | Point/station pollutant observations with explicit species/units/timestamps; may have no stations in area. `X-API-Key` required. Do not make maps look street-exact. |
| Landsat Collection 2 Level-2 ST | Optional | https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature ; search/download: https://earthexplorer.usgs.gov/ | Earth surface temperature (Kelvin after specified scale conversion), for overlay and external calibration; cloud masking; **not 2 m air temperature**. Account/scene-specific access may be required. |
| NASA POWER daily | Optional solar cross-check | https://power.larc.nasa.gov/docs/services/api/temporal/daily/ | `ALLSKY_SFC_SW_DWN` daily solar input (check response units); coarse gridded resource suitable for screening, not roof shading. |
| Municipal waste and facility records | Conditional for real-city waste simulation | Relevant city open-data portal; India catalog https://www.data.gov.in/ ; World Bank overview https://datatopics.worldbank.org/what-a-waste/ | Real facility throughput and composition required for city-specific results. Country averages may be used **only as declared assumptions**, never reported as local measurements. |
| SRTM elevation | Optional | https://www.earthdata.nasa.gov/data/instruments/srtm | Terrain context; **not enough for drainage-network flood forecasting**. |

**Baseline demonstration region:** configure a bounded area from command flags or an explicitly supplied GeoJSON polygon; the system must never hard-code one city's identity into its models. For quick smoke tests a bbox can be specified as `--bbox 79.05,21.10,79.15,21.20 --city-id nagpur-demo --name 'Nagpur demo area'` (coordinates WGS84, `min_lon,min_lat,max_lon,max_lat`). This is an illustration of input shape and not an assertion of municipal boundaries.

### 4.1 Provider refresh contract

| Source | Normal cadence | Stale policy | Failure behavior |
|---|---|---|---|
| OSM vector snapshot | Manual or weekly | display ingestion timestamp | retain prior revision, log warning |
| WorldCover 2021 | immutable year/version | always label reference year | no replacement without explicit version change |
| Open-Meteo forecast | every 3 hours, bounded by API terms | warn after 6 h, prohibit “current” label after 12 h | retain cached records with age indicator |
| OpenAQ station measurements | every 1–3 hours, API-rate-aware | mark stale after 6 h, never extrapolate to street truth | air-quality overlay `unavailable` if missing |
| Optional Landsat imagery | on explicit user ingestion request | show image acquisition date and cloud mask | hide layer if absent |
| Municipal waste data | source-dependent | keep effective dates per facility | refuse empirical claims if insufficient |

**All ingest clients:** HTTP connect timeout 5 s, read timeout 30 s (configurable), 3 attempts for network errors/429/5xx with exponential backoff and jitter honoring `Retry-After`, bounded pages, domain allowlist, source attribution, explicit API error mapping, and request metrics. Do not retry 401/403, corrupt payloads, or unlicensed distribution. Downloads to `.part` then atomic rename only after checksum, parsing and metadata checks. Each run records successes, failures and completeness.

## 5. Environment and secrets: concrete `.env.example` contract

The coding agent must create this documented file. Values shown are safe **local developer defaults**; `OPENAQ_API_KEY` is deliberately omitted until the developer registers. No real secrets belong in the example. In cloud, load sensitive values from AWS Secrets Manager and ordinary configuration from task environment. Use Pydantic Settings to reject invalid combinations at startup.

```dotenv
# === Runtime ===
APP_ENV=development              # development | test | production
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
CORS_ALLOWED_ORIGINS=http://localhost:3000
MAX_STUDY_AREA_KM2=25
MAX_FEATURES_PER_VIEW=5000
MAX_SCENARIO_EDITS=100

# === Database ===
# Compose hostname is db; if running Python on host use localhost instead.
DATABASE_URL=postgresql+psycopg://ecotwin:ecotwin_local_only@db:5432/ecotwin
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# === Dataset/object storage ===
# local: always filesystem; s3: S3 only; auto: S3 then verified immutable local copy
ECOTWIN_STORAGE_MODE=local
ECOTWIN_LOCAL_DATA_DIR=/app/data
ECOTWIN_ALLOW_LOCAL_FALLBACK=false
ECOTWIN_S3_BUCKET=              # required when storage mode is s3 or auto
ECOTWIN_S3_PREFIX=ecotwin/
AWS_REGION=ap-south-1
VERIFY_DATASET_SHA256=true

# === Workers ===
ECOTWIN_QUEUE_BACKEND=database   # database | sqs
ECOTWIN_SQS_QUEUE_URL=          # required only when queue backend is sqs
WORKER_POLL_SECONDS=2
WORKER_LEASE_SECONDS=180
WORKER_MAX_ATTEMPTS=3
SIMULATION_TIMEOUT_SECONDS=120

# === External data ===
OPEN_METEO_ENABLED=true
OPEN_METEO_BASE_URL=https://api.open-meteo.com
OPENAQ_ENABLED=false            # set true only after obtaining an API key
OPENAQ_BASE_URL=https://api.openaq.org/v3
OPENAQ_API_KEY=                 # obtain from https://explore.openaq.org/register
OPENAQ_MAX_STATION_RADIUS_M=25000
HTTP_CONNECT_TIMEOUT_SECONDS=5
HTTP_READ_TIMEOUT_SECONDS=30

# === Authentication ===
# dev: signed development JWT on localhost only; cognito: validated remote JWTs
AUTH_MODE=dev
DEV_JWT_SECRET=                # generate: openssl rand -hex 32; never commit .env
COGNITO_USER_POOL_ID=          # required with AUTH_MODE=cognito
COGNITO_CLIENT_ID=             # required with AUTH_MODE=cognito
COGNITO_AWS_REGION=ap-south-1

# === Model version and provenance ===
RUNOFF_MODEL_VERSION=runoff-coeff-v1
SOLAR_MODEL_VERSION=solar-screen-v1
ENABLE_UNCALIBRATED_HEAT_PREDICTION=false
```

**Local onboarding:** `cp .env.example .env`, execute `openssl rand -hex 32` and place the output in `DEV_JWT_SECRET` in the untracked `.env`; run `docker compose --env-file .env up --build -d`. In production `AUTH_MODE=cognito`, `ECOTWIN_STORAGE_MODE=s3`, `ECOTWIN_QUEUE_BACKEND=sqs`, fallback disabled and credentials from secrets; enforce those conditions in settings validation. For a local agent performing automated integration tests, test-mode auth must use an isolated generated secret, not bypass authorization logic.

## 6. Relational schema and versioned dataset contract

**Migration discipline:** implement the following with Alembic, PostgreSQL foreign keys, CHECK constraints, uniqueness constraints and GiST spatial indexes; include an upgrade and downgrade migration, migration tests, and seed **configuration** (not fabricated city measurements). Use UTC `TIMESTAMPTZ` and `UUID` IDs, `NUMERIC` for physically conserved quantities and `DOUBLE PRECISION` for statistical/geospatial sensor values with explicit units. Use a `schema_version` integer on serialized scientific documents and `model_version` string in every report.

| Table | Required columns / constraints | Indexes / reason |
|---|---|---|
| `cities` | `id uuid pk`, `slug unique`, `display_name`, `boundary geometry(MultiPolygon,4326)`, `analysis_srid int`, `timezone text`, `created_at`, `status enum` | GiST boundary; choose projected equal-area/local metric CRS per city; reject invalid boundary |
| `dataset_revisions` | `id uuid pk`, `city_id fk`, `kind enum`, `provider`, `source_url`, `object_key`, `sha256 char(64)`, `byte_size bigint`, `source_license`, `attribution`, `acquired_at`, `valid_from`, `valid_to`, `native_crs`, `resolution_m`, `coverage geometry`, `status enum`, `quality_json jsonb` | unique `(city_id,kind,sha256)`; no updates after published; immutable assets |
| `import_runs` | `id`, `dataset_revision_id`, `status`, `started_at`, `finished_at`, `rows_read`, `rows_imported`, `rows_rejected`, `error_code`, `details_json` | troubleshooting and audit trail |
| `geo_features` | `id uuid`, `city_id`, `revision_id`, `provider_feature_id`, `category`, `tags jsonb`, `geom geometry(Geometry,4326)`, `area_m2 numeric null`, `length_m numeric null`, `effective_at` | unique `(revision_id,provider_feature_id,category)`; GiST geom; btree `(city_id,category)` |
| `landcover_cells` | `id`, `city_id`, `revision_id`, `cell_x`, `cell_y`, `class_code smallint`, `area_m2 numeric(16,4)`, `geom geometry(Polygon,4326)` | unique `(revision_id,cell_x,cell_y)`; GiST geom; optional partition by city; clipped edge-cell area correctly computed |
| `weather_hours` | `id`, `city_id`, `revision_id`, `valid_at timestamptz`, `issued_at timestamptz`, `temperature_c`, `rain_mm`, `humidity_pct`, `wind_mps`, `ghi_w_m2`, `model_name`, `source_lat`, `source_lon` | unique `(city_id,revision_id,valid_at)`; distinct issued vs valid times |
| `air_stations` | `id`, `provider_station_id`, `source`, `location geometry(Point,4326)`, `name`, `metadata jsonb` | unique `(source,provider_station_id)`; GiST location |
| `air_observations` | `id`, `station_id`, `sensor_id`, `parameter`, `value`, `unit`, `measured_at`, `source_url`, `revision_id` | unique `(source station,sensor_id,measured_at,parameter)` enforced using station foreign key; index timestamp/parameter |
| `facility_profiles` | `id`, `city_id`, `revision_id`, `facility_kind`, `geom Point`, `capacity_tpd numeric`, `accepted_categories jsonb`, `efficiency_profile jsonb`, `parameter_source`, `effective_at` | explicitly distinguish observed capacity vs assumed profile |
| `city_snapshots` | `id uuid`, `city_id`, `created_at`, `dataset_revision_ids uuid[]`, `composite_input_sha256`, `model_config_sha256`, `baseline_summary jsonb`, `status` | snapshot immutable after published; compound digest from sorted source revision digests |
| `user_accounts` | `id uuid`, `identity_issuer`, `identity_subject`, `created_at` | unique `(identity_issuer,identity_subject)` |
| `scenarios` | `id uuid`, `snapshot_id`, `owner_user_id`, `name`, `status`, `created_at`, `updated_at`, `version int`, `scenario_sha256` | optimistic concurrency via version; `owner_user_id` required |
| `scenario_edits` | `id`, `scenario_id`, `ordinal`, `edit_type`, `target geometry(Geometry,4326)`, `parameters jsonb`, `sha256`, `created_at` | unique `(scenario_id,ordinal)`; GiST optional target; controlled edit enums |
| `simulation_jobs` | `id uuid`, `scenario_id`, `requested_by`, `idempotency_key`, `state enum`, `attempt int`, `not_before`, `locked_until`, `worker_id`, `progress_pct`, `error_code`, `error_message`, `created_at`, `started_at`, `finished_at`, `result_id nullable` | unique `(requested_by,idempotency_key)`, queue index `(state,not_before)`; no mutable input after submission |
| `simulation_results` | `id uuid`, `job_id unique`, `report_schema_version`, `input_digest`, `model_versions jsonb`, `metrics jsonb`, `warnings jsonb`, `evidence jsonb`, `object_key nullable`, `created_at` | immutable result; output SHA256 stored on object artifacts |

**Core data rules:**

- Dataset revision status is `DOWNLOADING → VALIDATING → READY` or `FAILED`; a city snapshot may reference `READY` revisions only. Publishing snapshot is a single database transaction.
- Source geometry is always EPSG:4326 in DB; reproject to the city's validated `analysis_srid` to compute area/length and to clip rasters. For a large city crossing UTM zones use a fit-for-purpose local equal-area projection selected at onboarding; do not hard-code zone 43N for all cities.
- OSM points, lines and polygons are distinct feature shapes. A park polygon is not proof that every pixel is tree canopy. A `natural=tree` point is an individual *mapped* tree only, not an inventory of all actual trees.
- Revisions are immutable even when providers change a file at the same URL. Snapshot references must include source SHA256, URL/license, capture time and transformation version.
- `dataset_revisions.coverage` must represent downloaded/cropped actual coverage, not the city's full boundary by assumption.
- Geometry must pass `ST_IsValid`, SRID validation, area and bbox bounds checks; repair (`ST_MakeValid`) only if the repair is logged and original retained.
- Prevent overlapping scenario edit areas from double-consuming land cover: apply edits sequentially against each evolving clipped land-cover grid, and reject any edit whose declared source category disagrees with the current state.
- For weather/air-quality missing null measurements, store null/reason only when protocol allows; never encode missing as zero. Convert provider source units to canonical units while retaining raw unit metadata.

### 6.1 Dataset manifest and cache keys

Every imported object is stored under `raw/{source}/{dataset_kind}/{sha256}/{original_filename}` and transformed objects under `processed/{city_slug}/{revision_uuid}/{artifact_filename}`. The manifest JSON contains `schema_version`, city ID, source URL, `sha256`, exact byte length, media type, CRS, coverage polygon, native and normalized units, capture time, measurement window, license, attribution, processing algorithm version, and upstream revision identifiers.

Use an immutable `sha256` of file bytes. Simulations pin the exact manifest records. Cache keys include `(snapshot_digest, scenario_edit_digest, model_id, model_version, parameters_digest, weather_revision)`, not just city name or current calendar date.

## 7. Object storage: local, S3 and verified fallback

**One interface for both stores:**

The `ObjectStore` interface must expose four methods with fixed signatures and fully tested concrete implementations: `open_read(key: str) -> BinaryIO` (streamed read), `put_file(key: str, source_path: Path, sha256: str) -> None` (atomic verified upload), `materialize(key: str, expected_sha256: str) -> Path` (checksum-verified local cached file), and `exists(key: str) -> bool` (object lookup). Implement `LocalObjectStore`, `S3ObjectStore` and `CheckedFallbackObjectStore` with no unimplemented methods.

A concrete implementation must provide these exact methods. `materialize` should stream to a checksum-verified disk cache with atomic rename and bounded disk quota, because multi-GB GeoTIFF downloads cannot be loaded into Python RAM with `read()`. `open_read` streams data; close resources deterministically. Set S3 and network operation timeouts, SDK retry mode and multipart transfer thresholds. All input keys are generated from validated database records; reject absolute paths, `..` traversal, symlinks escaping the root, unexpected object prefixes and duplicate paths.

**Selection:**

1. `local`: only local store. Do not instantiate boto3 or attempt AWS discovery; failure of local file raises `DATASET_NOT_FOUND`.
2. `s3`: only cloud store; require bucket and region. S3 404 returns `DATASET_NOT_FOUND`, access denied returns `STORAGE_PERMISSION_DENIED`, timeout returns `STORAGE_UNAVAILABLE`. No silent fallback.
3. `auto`: require an S3 bucket and explicit `ECOTWIN_ALLOW_LOCAL_FALLBACK=true`. On **network/service unavailability** only, permit local cached object if SHA256 equals the manifest's pinned digest. Never fall back on S3 403/401, invalid credentials, checksum mismatch, or missing manifest. Emit a structured `storage_fallback` event and include `data_served_from=local_verified_cache` in response metadata.
4. In production, settings validator requires `s3`, `ECOTWIN_ALLOW_LOCAL_FALLBACK=false`, server-side encryption, IAM task roles, and no ambient long-lived credentials. The agent must test these start-up invariants.

**Database selection is independent of object storage:** `DATABASE_URL` points to local Compose PostGIS or private RDS. Implement migrations once. Do not automatically replace an unavailable production RDS with a different local DB because doing so would create conflicting mutable records.

## 8. Data ingestion: executable command behavior and acceptance

Expose a Typer CLI installed as `ecotwin`. Required commands:

```bash
ecotwin db check
ecotwin city create --city-id nagpur-demo --name 'Nagpur demo area' --bbox 79.05,21.10,79.15,21.20 --timezone Asia/Kolkata
ecotwin ingest osm --city nagpur-demo --method overpass
ecotwin ingest worldcover --city nagpur-demo --year 2021
ecotwin ingest weather --city nagpur-demo --forecast-hours 72
ecotwin ingest air --city nagpur-demo --lookback-hours 48
ecotwin city snapshot --city nagpur-demo
ecotwin datasets verify --city nagpur-demo
ecotwin models list --city nagpur-demo
ecotwin jobs work --once
```

The command `ingest air` must stop with a clear `OPENAQ_CREDENTIAL_REQUIRED` unless `OPENAQ_ENABLED=true` and a valid key exists. Because station availability varies, `0 relevant stations` is a **successful ingestion with coverage=none** and an unavailable air overlay, not an excuse to synthesize readings. `city snapshot` requires OSM and WorldCover revisions READY, and at least one usable weather revision for weather-dependent models; optional data are reflected in capability flags.

### 8.1 OSM vector pipeline

- **Production bulk mode:** retrieve correct Geofabrik extract from the indexed regional source using `.osm.pbf` and record the snapshot date; crop via `osmium extract` to city polygon/bbox before parsing. Do **not** download and parse the planet-sized country extract per user request. A country extract may be large; store once per refresh in the bulk-ingestion pipeline.
- **Bounded developer mode:** use OSMnx 2.x or a query builder to request selected keys via Overpass for a maximum 25 km² bbox: `building`, `highway`, `leisure=park|garden`, `natural=water|wood|tree`, `waterway`, `landuse`, `amenity=recycling|waste_disposal`, `power` where tagged. Use Overpass fair-use and backoff. Return OSM feature ID, raw tags, geometry and type; normalize to controlled categories.
- Remove duplicate OSM type/id combinations; parse multipolygons, hole rings, LineStrings and Points; preserve `osm:node/way/relation` in `provider_feature_id` to avoid collision.
- Clip to study boundary in metric-safe geometry operations, validate topology, project for `area_m2/length_m`, insert using staging tables then promote on successful validation. Persist counts of valid/invalid and coverage.
- Index geometries; provide viewport queries with `ST_Intersects(geom, ST_MakeEnvelope(:west,:south,:east,:north,4326))`, bound bbox area and feature count, return paginated GeoJSON FeatureCollection. Optionally precompute zoom-dependent simplifications; never simplify scientific geometry before running area calculations.

### 8.2 ESA WorldCover raster pipeline

- Download only tiles intersecting selected polygon from 2021 v200 public S3 using unsigned access; do **not** `aws s3 sync` all ~global tiles. Use the official tile index/grid to identify matching tiles and the public bucket for COG reads. Record original GeoTIFF checksum and version.
- Clip/mosaic selected COGs to boundary with Rasterio; reproject to a documented local projected equal-area CRS for cell area; preserve WorldCover 2021 integer category values and nodata handling. Accept class codes `{10,20,30,40,50,60,70,80,90,95,100}` and explicit nodata; reject unknown classes until mapped.
- Create the scenario analysis grid: native-resolution polygon cells clipped to city boundary, each with exact `area_m2` and `class_code`; for large areas use a raster-backed analysis representation plus aggregated DB tiles, not unrestricted millions of database polygon inserts. The `landcover_cells` schema is mandatory for bounded reference regions, and the implementation may store heavier analysis tiles in object storage with metadata in DB.
- Compute class areas and percentages from cell areas, not counts alone; assert non-overlap and sum of classified cell areas matches valid covered city area within numerical tolerance of 0.5%. Report unmapped/nodata area separately.
- Interpretation: code 10 = **tree cover class**, not a count of trees; 50 = built-up; 80 = permanent water; 90/95 wetlands/mangroves. 2021 data must always be labeled as 2021 reference even if imported in 2026.

### 8.3 Open-Meteo weather pipeline

- HTTP `GET https://api.open-meteo.com/v1/forecast` with `latitude`/`longitude` from city centroid, `hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,shortwave_radiation`, `timezone=UTC`, `forecast_hours=72`, explicit `wind_speed_unit=ms`, `temperature_unit=celsius`, `precipitation_unit=mm` (verify against provider's supported values), and source model metadata if returned.
- Confirm equal length arrays and strictly monotonic time axis. Reject NaN, 200-with-`error:true`, unsupported units, future timestamp regression or impossible ranges (`humidity_pct` outside 0–100; rain < 0; solar < 0). Do not discard merely unusually hot/cold but physically plausible readings; flag quality.
- Persist issued-at separately from forecast valid-at and store source lat/lon and model name; attach to region as **coarse forecast context** rather than street sensors. `rain_mm` is depth accumulated over the provider hourly interval; do not treat hourly records as instantaneous rainfall rate.
- If weather is outdated, expose stale age. Scenario models depending on future weather must pin a forecast issue time so baseline and modified scenario use exactly the same weather input.

### 8.4 OpenAQ station measurement pipeline

- Authenticate with `X-API-Key` read only from backend secret settings. Discover nearby stations using `GET /v3/locations` with bbox/country/location filters as supported by the API. Respect pagination, provider quota and radius; store only locations that truly fall within the configured area or an explicitly disclosed nearby search radius.
- Read sensors from the returned location metadata or documented location-specific sensor endpoint; call `GET /v3/sensors/{sensor_id}/hours` for bounded lookback window. Use parameter IDs/names and units returned by the sensor rather than guessing pollutants from positional ordering.
- Normalize timestamps to UTC, preserve source units, retain raw numeric value, deduplicate `(station,sensor,parameter,time)` and record provider station coordinates. If source units need conversion, use parameter-specific defined conversions; avoid generic conversion from ppm to µg/m³ without temperature/pressure/gas molar mass.
- The air-quality API endpoint returns available station series plus observation timestamps and distance from query center. Do not return street-level interpolated predictions unless a separately validated spatial interpolation algorithm and quality diagnostics exist.

### 8.5 Optional historical, Landsat, waste, solar and municipal imports

- **Landsat:** implement an actual dataset import command accepting downloaded Collection 2 Level-2 scene directory/manifest and cloud-mask metadata; read official scale factors, valid pixel mask and Kelvin units from product metadata; spatially clip and store acquisition date. If an authenticated USGS search/download API is enabled, follow its official contract; do not pretend anonymous Scene API works. Missing scenes result in `LAYER_UNAVAILABLE`.
- **NASA POWER:** optional API client requests `ALLSKY_SFC_SW_DWN` for given location/dates using `https://power.larc.nasa.gov/api/temporal/daily/point`; validate returned units and spatial resolution before comparing with Open-Meteo irradiance.
- **Waste facilities:** accept municipality-issued CSV/JSON with required `facility_id,lat,lon,capacity_tpd,facility_type,accepted_streams,effective_date,source_url,measurement_type`; validate capacities >= 0 and waste-category mapping; records with missing empirical capacity cannot be silently assumed as observed.
- Provide a domain-parameter import workflow for analyst-supplied waste recovery profiles and grid limits. Every such input is tagged `ASSUMED` or `MEASURED`. Use current synthetic-city support only in the **test/sandbox namespace**, never as a real city's default input.

## 9. Simulation engine: supported operations, math and explicit limits

### 9.1 Scenario command types

Expose exactly these mutable edit types initially:

1. `LAND_COVER_RECLASSIFY`: fields `{polygon_geojson, from_class_code, to_class_code, fraction}` where `fraction` is in `(0,1]`, geometry must be within study-area boundary, affected valid classified area > 0, source class must exist. Fraction applies to area intersection in a deterministic raster-cell order and records its realized reclassified area; never change whole-cell coverage in excess of requested area without reporting quantization/partial-cell handling. Use fractional cell-area accounting if necessary.
2. `SOLAR_PV_INSTALL`: fields `{footprint_geojson, installed_kwp, performance_ratio, panel_tilt_deg, panel_azimuth_deg}`; `installed_kwp > 0`, `performance_ratio` between 0 and 1; restrict location to defined land/building feature as intended by user and disallow duplicate allocation on identical area. Model result is **indicative energy** with no shadow/structural approval claim.
3. `WASTE_ROUTING_OVERRIDE`: fields `{stream_category, origin_id, facility_id, allocation_fraction}` with per-category fractions summing to 1 within numerical tolerance and compatibility/capacity validation delegated to existing EcoTwin modules. Enabled only if city facility profiles and non-synthetic waste stream observations/explicit user assumptions exist.

Store edits as canonical normalized documents and hash them. Reject unknown types with HTTP 422. Scenario creation and edit mutation require `If-Match` version / optimistic lock to prevent concurrent updates. Freeze the scenario (version and digest) once a job is accepted; subsequent edits produce a new version and a different digest, not retrospective mutation of queued job inputs.

### 9.2 Land-cover and vegetation changes (always supported with WorldCover)

For each class `k`, baseline area `A_k = Σ_i area(i,k)`, scenario area `A'_k` after ordered interventions, and delta `ΔA_k=A'_k-A_k`; report in m², ha and percent of city valid land-cover area. Set `tree_cover_area_m2=A_10`. Percentage change in tree cover is `(A'_10−A_10)/A_10 × 100` **only if A_10 > 0**; otherwise percentage is null with explanation. Surface-water cells (code 80) are not treated as permeable land for stormwater calculations.

**Invariant:** `Σ_k A'_k` equals `Σ_k A_k` for land-cover reclassification across the same valid analysis area; no negative area, no new class beyond mapping, no edit outside region. Report unchanged classified area, unknown/nodata coverage and model resolution. A reduction in tree-cover area **does not equal** a count of individual trees removed unless independently inventoried.

### 9.3 Event rainfall runoff: defined, runnable screening-level model

Use a transparent **land-use runoff coefficient** model, not a claim of validated hydraulic flood prediction. Inputs: event rainfall depth `P_mm` (explicit user event rainfall or sum of a specified contiguous weather hourly interval), per-class run-off coefficients `C_k`, cell areas in m² and class IDs. Formula:

`V_m3 = Σ_{land cells i} [ (P_mm / 1000) × area_m2(i) × C_class(i) ]`.

Store a versioned, editable YAML parameter table for initial **screening assumptions** (not universal empirical constants): tree=0.15, shrub=0.20, grass=0.25, crop=0.30, built-up=0.85, bare=0.65. Snow/ice, surface water, wetlands and mangroves are **excluded** from this simplistic terrestrial comparison unless the analyst supplies a separate justified model; return `INCOMPLETE_COVERAGE` if excluded area exceeds 10% of **the intervention target area** and never silently label the total as full-watershed runoff. Parameter values must be displayed in result metadata, labeled analyst assumptions and configurable through approved model config revision. This is an area-based excess-runoff screening indicator and **not flood inundation, drainage load or runoff hydrograph**.

For both baseline and scenario use identical `P_mm`, identical boundaries and same parameter version. `ΔV = V_scenario − V_baseline`, `%Δ = ΔV / V_baseline × 100` only if baseline > 0. Reject negative precipitation, invalid coefficient, negative area or unsuitable requested period. Report model status `SCREENING_ESTIMATE`; report at least limitations `{no_soil_group,no_drainage_network,no_calibration,uniform_rainfall_assumption}`. Where watershed-grade runoff is requested, use the USDA NRCS curve-number method **only if** soils (hydrologic group), cover-specific curve numbers, antecedent moisture assumptions and rainfall event assumptions are supplied; never assign universal CN just from WorldCover. See https://directives.nrcs.usda.gov/sites/default/files2/1712930818/31754.pdf .

### 9.4 Solar PV indicative yield (runnable under assumptions)

Input `installed_kwp` and hourly weather `shortwave_radiation` as W/m² from a pinned weather forecast revision; `performance_ratio` defaults to 0.75 from `solar_defaults.v1.yaml` and must be flagged `ASSUMED`. For horizontal, unshaded first-order screening, hourly energy:

`E_hour_kwh = installed_kwp × (GHI_W_m2 / 1000 W_m2) × performance_ratio × 1 hour`.

Sum hourly energy over selected period. For nonzero roof tilt, do **not** silently use horizontal GHI as plane-of-array irradiance. Either request `global_tilted_irradiance` with the provider's tilt/azimuth parameters and record exact returned units, or reject unsupported tilted calculations with `MODEL_INPUT_UNSUPPORTED`. Account for radiation units (hourly mean W/m² vs energy per interval). Return energy in kWh, model horizon and assumptions; **do not** equate nameplate `kWp` to DC-to-AC real output without explicit losses. A building polygon cannot prove structural, shading or usable-roof feasibility. Grid emission savings require a separate verified grid emission factor and time-varying displacement assumptions; otherwise mark `emissions_delta` unavailable.

### 9.5 Existing waste and energy models: adapter with verified domain constraints

- Inspect actual `ecotwin/scenario.py`, `balance.py`, `optimization.py`, `facility.py` and existing tests. Expose a `WasteRoutingModel` adapter mapping actual input classes to typed, city-tagged `FacilityProfile`, `WasteStream` and `RouteSplit` objects without rewriting existing solvers.
- Preserve category sum-to-one, facility compatibility, processing capacity, mass balance `input = recovered + residue + physical loss`, nonnegative energy, and internal unit consistency. Capacity and efficiency assumptions must trace to a revision (or explicit user-supplied config), never fabricated municipality facts.
- For electricity-related simulations, **only** execute grid/transformer/battery models when the repository contains verified implementation and supplied electrical topology/transformer ratings. The README describes phases 5–8 as planned; do not mark these as completed solely from the README.
- Optimizer must report `optimal/infeasible/unbounded/timeout` status, constraints and objective weights; never present an infeasible candidate as feasible. Run baseline and intervention through exactly the same model version and input unit normalization.

### 9.6 Environmental observations and unsupported causal predictions

- OpenAQ observations: map point sensors and nearby distances. No edit to park should alter pollutant readings, because they are measured data. If user asks `PM2.5 change from tree removal`, return `MODEL_NOT_AVAILABLE` unless an explicitly configured validated causal/dispersion model exists.
- Open-Meteo temperature: provide forecast context. Do **not** change a weather forecast after removing trees. A land-surface-temperature overlay from Landsat is an observation of surface conditions at acquisition time, not a prediction of an edit.
- Wildlife metrics: provide baseline *land-cover/habitat proxy* only when category mappings are declared. Do not predict species deaths, abundance or biodiversity changes from canopy area alone.
- For heatwaves/cold weather: forecast and threshold-based **informational** advisory may be generated using documented health-authority thresholds if jurisdiction-specific sources are integrated; otherwise show weather values and generic safety context without claiming clinical outcomes.

### 9.7 Report schema and evidence labels

Every result metric has:

`{name, baseline_value, scenario_value, absolute_delta, percentage_delta, unit, spatial_scope, start_at, end_at, evidence_class, model_id, model_version, source_revision_ids, parameter_digest, confidence_interval, limitations}`.

`evidence_class ∈ {OBSERVED, DETERMINISTIC_CALCULATION, SCREENING_ESTIMATE, CALIBRATED_PREDICTION, ASSUMED_INPUT, UNAVAILABLE}`. `confidence_interval` is null unless an actual quantified method exists; do not attach arbitrary ±10%. `UNAVAILABLE` must include stable `reason_code` and missing data/model names. Return positives and negatives as metric deltas, not one unvalidated composite eco-score. Report numeric precision according to source resolution and model accuracy, not 8 decimal places of false certainty.

## 10. End-to-end execution and dependency graph

1. Validate bearer token, city and ownership; parse versioned scenario schema, area limits and model support; fetch immutable snapshot and edits.
2. Compute canonical scenario digest (sorted keys, defined numeric precision, CRS-normalized coordinates, stable edit order) and simulation key `(scenario digest, snapshot digest, time inputs digest, model config digest)`.
3. Deduplicate request using `Idempotency-Key`. If same user/key and identical payload already exists, return same job; identical key/different payload is HTTP 409 `IDEMPOTENCY_CONFLICT`.
4. Mark scenario frozen for job input or store immutable scenario revision by ID. Insert job in DB with `QUEUED`, commit; then publish SQS message `{job_id}` if configured. Failed publish is reconciled by sweeper polling DB queued jobs (outbox pattern recommended).
5. Worker claims job with transaction and lease; verifies exact dataset revisions and SHA256 through `DatasetManager`, loads spatial features and weather, and applies edits to a copy of analysis state.
6. Select affected model DAG: `LAND_COVER_RECLASSIFY → landcover_summary → runoff_screen`; `SOLAR_PV_INSTALL → solar_pv`; `WASTE_ROUTING_OVERRIDE → existing waste balance → optimizer (if requested)`. Execute models in topological order, with valid shared inputs.
7. Run baseline and scenario calculations with identical exogenous conditions; assert conservation and nonnegative outputs; evaluate direct and derived results; add evidence/limitations.
8. Store immutable result transactionally, set job `SUCCEEDED`, emit `simulation_duration_seconds`; on domain error set `FAILED` with stable code and no fabricated metrics.
9. API polls `GET /v1/jobs/{id}`. When ready, `GET /v1/results/{id}` returns provenance and metrics; JSON can optionally be exported to S3 with checksum.

**Timeout and recovery:** each worker task has hard deadline; lease renewal heartbeat; expired lease is reclaimable; job attempts max 3 for transient errors with exponential backoff. Deterministic domain failures (`INSUFFICIENT_INPUT_DATA`, invalid geometry, unsupported model, infeasible optimization) are terminal and not retried. SQS message duplicate delivery must not duplicate result creation. Implement an SQS DLQ, `maxReceiveCount` policy, and an operator requeue command with audit trail. Cancellation sets `CANCEL_REQUESTED` and worker checks between model steps; long-running numerical subprocesses must be terminated cleanly. Termination or SIGTERM in ECS should drain gracefully and release leases.

## 11. REST API contract (OpenAPI-generated; `/v1` prefix)

**Response format:** Pydantic v2 models with UTF-8 JSON, ISO-8601 UTC datetimes, decimal quantities serialized deterministically, and GeoJSON coordinates in `[longitude,latitude]` WGS84. Add `X-Request-ID` to responses and structured logs. List endpoints have bound `limit<=100`, cursor pagination where appropriate and bounded geospatial bbox queries. Use ETag/`If-Match` on editable scenarios.

| Endpoint | Method | Auth | Behavior |
|---|---|---|---|
| `/livez` | GET | none | process alive; no remote dependency calls |
| `/readyz` | GET | none/internal ALB | readiness: successful DB ping and migrations current; avoid external API checks |
| `/v1/cities` | GET | optional public | page available cities and data coverage |
| `/v1/cities/{city_id}` | GET | optional public | boundary, analysis CRS, active snapshot ID, supported capabilities |
| `/v1/cities/{city_id}/features?bbox=...&category=...&limit=...` | GET | optional public | validated viewport GeoJSON FeatureCollection + source references |
| `/v1/cities/{city_id}/landcover` | GET | optional public | class areas, % coverage, reference year and quality |
| `/v1/cities/{city_id}/observations/weather?start=...&end=...` | GET | optional public | typed forecast series, issued and valid times |
| `/v1/cities/{city_id}/observations/air?parameter=pm25` | GET | optional public | stations plus real measurements, no interpolated street values |
| `/v1/cities/{city_id}/datasets` | GET | optional public | revisions, licenses, coverage, freshness and capability flags |
| `/v1/models` | GET | optional public | runnable models, required inputs and reasons disabled per city |
| `/v1/scenarios` | POST | bearer | create scenario from snapshot; return UUID/version/ETag |
| `/v1/scenarios/{id}` | GET | owner | immutable/reference scenario details |
| `/v1/scenarios/{id}/edits` | PUT | owner + If-Match | replace ordered edits atomically, revalidate target areas; new version |
| `/v1/scenarios/{id}/simulate` | POST | owner + Idempotency-Key | accept frozen job; 202 plus `job_id`, `status_url` |
| `/v1/jobs/{job_id}` | GET | owner | queued/running/succeeded/failed/canceled, progress and error details |
| `/v1/jobs/{job_id}/cancel` | POST | owner | request cancellation; idempotent |
| `/v1/results/{result_id}` | GET | owner | typed baseline/scenario results, caveats, complete provenance |
| `/v1/scenarios/{id}/reports` | GET | owner | paginate past completed result versions |

**Error representation** uses problem JSON (`application/problem+json`) with `type`, `title`, `status`, `detail`, `code`, `request_id`, `missing_inputs` (when applicable); never return stack traces, SQL or secret values. Stable codes: `CITY_NOT_FOUND`, `DATASET_NOT_READY`, `DATASET_CHECKSUM_MISMATCH`, `STORAGE_UNAVAILABLE`, `STORAGE_PERMISSION_DENIED`, `STALE_WEATHER`, `OPENAQ_CREDENTIAL_REQUIRED`, `INVALID_GEOMETRY`, `OUTSIDE_STUDY_BOUNDARY`, `SCENARIO_VERSION_CONFLICT`, `IDEMPOTENCY_CONFLICT`, `MODEL_NOT_AVAILABLE`, `MODEL_INPUT_UNSUPPORTED`, `INSUFFICIENT_INPUT_DATA`, `OPTIMIZATION_INFEASIBLE`, `SIMULATION_FAILED`. Treat `MODEL_NOT_AVAILABLE` as a valid machine-readable capability result, not success with a fabricated 0.0 metric.

### 11.1 Request/response examples for integration tests

**Create scenario:**

```http
POST /v1/scenarios
Authorization: Bearer <user-issued-authentication-token>
Content-Type: application/json

{"city_id":"<registered-city-uuid>","snapshot_id":"<published-snapshot-uuid>","name":"Park replacement test"}
```

These angle-bracket identifiers in HTTP examples represent **runtime-issued opaque IDs**, not source-code placeholders. Implementation must supply real IDs from create/ingest APIs during tests and must not hardcode example UUIDs into the application.

**Run a scenario:**

```http
POST /v1/scenarios/{id}/simulate
Authorization: Bearer <user-issued-authentication-token>
Idempotency-Key: 0cddcaf9-9b5b-41b9-8624-4013c108f7d2
Content-Type: application/json

{"requested_models":["landcover_summary","runoff_screen"],"event_rainfall_mm":50.0,"report_schema_version":1}
```

**Success result properties:** `job_id`, `snapshot_id`, `scenario_revision`, `inputs.sha256`, `metrics[]` with raw numeric fields and units, `data_provenance[]`, `model_parameters[]`, `warnings[]`, `unavailable_metrics[]` and `created_at`. Generate a committed OpenAPI JSON snapshot and test that `frontend/src/lib/api-types.ts` is generated from it, not manually guessed. The backend must not depend on Next.js.

## 12. Auth, authorization, validation and privacy

- **Production identity:** Cognito user-pool JWT authorization; validate token signature via issuer JWKS, `iss`, `aud`/`client_id` as applicable to token type, expected `token_use=access` and `exp`, with cached rotation of JWKS; reject malformed/expired/wrong-pool tokens. `sub` is the stable identity. Distinguish access tokens from ID tokens correctly.
- **Development identity:** `AUTH_MODE=dev` issues short-lived local JWTs only through CLI `ecotwin auth issue-dev-token --subject local-developer --minutes 60`, signed with a generated secret. CLI prints token to console; never ship an unauthenticated HTTP token-mint endpoint. Refuse `dev` mode if `APP_ENV=production`.
- **Authorization:** the API verifies scenario and job/result ownership on every read/write; queries apply owner filters **in SQL**, not just after DB retrieval. City baseline read endpoints may be public, subject to rate limiting and cost controls.
- **Geometry/API protection:** enforce bbox bounds and at most 25 km² study area, maximum 100 edits, maximum 5000 features per viewport call, maximum 1 MB JSON request body, polygon vertex and nesting limits, no uncontrolled user-provided remote URL fetches (SSRF), allowed content types, safe JSON serialization, CORS allowlist, secure security headers, and redacted logs.
- **Database:** migrations run with schema-owner role, API/workers use separate least-privilege DB roles, statement timeout, transaction timeout where supported, pool pre-ping and bounded max connections. No table-wipe migration on production data.
- **Audit:** record creation/change actor, scenario version, simulation digest, data source versions and failed authorization attempts. Avoid storing personal geolocation tracking if not needed.

## 13. Local Docker development: executable setup specification

**Required root Dockerfile:** multi-stage build based on `python:3.12-slim` pinned by digest at lock/release time; install locked wheel dependencies including GDAL/GEOS/PROJ system runtime compatible with Rasterio/GeoPandas; create unprivileged `ecotwin` UID; `COPY` package/model configs/migrations; include `HEALTHCHECK` for API service; use `exec` entrypoint and no root in runtime. Never bake datasets or `.env` into image. Build once, run `ecotwin-api`, `ecotwin-worker`, and `ecotwin-ingest` with overridden commands.

**Required Compose:**

| Service | Image/command | Volumes/network/health |
|---|---|---|
| `db` | pinned compatible `postgis/postgis:16-3.4` digest | named persistent PG volume, health `pg_isready`, localhost-only binding if host access needed |
| `api` | local application image, `uvicorn ecotwin.api.main:app --host 0.0.0.0 --port 8000` | `data:/app/data` read-only except temporary cache path; `8000:8000`; depends on healthy DB |
| `worker` | same image, `ecotwin jobs work` | same dataset read-only mount plus dedicated writable tmp/cache; DB and worker leases |
| `migrate` | same image, `alembic upgrade head`, one-shot | run before serving API; exit nonzero blocks dependent tasks |

No always-on importer service: `docker compose run --rm api ecotwin ingest ...` invokes ingestion on demand with explicitly writable import/cache volume or separate ingestion service profile. For local mode, both API and worker may read finalized artifacts, while only ingestor writes raw/processed immutable revisions. Restrict writable mounts to ingestor and controlled worker result-cache directories; avoid permissive chmod 777. Define `make` tasks:

```bash
make setup          # create .env if absent and print secret-generation instruction
make up             # docker compose up --build -d; migration must complete first
make migrate        # explicit one-shot Alembic migration
make ingest-demo    # exactly: city create, osm, worldcover, weather, optional air, snapshot
make test           # uv run pytest -q including contract and storage tests
make integration    # live local PostGIS/API integration fixtures
make smoke          # call /readyz, cities, features, scenario, simulate, job, results
make down           # stop containers; preserve database volume
```

`make ingest-demo` must refuse to invent missing datasets and print specific required provider access or errors. **It must not auto-download a huge India extract**; bounded OSMnx Overpass mode and WorldCover tile-only downloads suffice. For offline repeatability, allow ingesting previously cached real download artifacts without network.

### 13.1 Required local smoke test

1. `docker compose config` succeeds; `docker compose up --build -d` leaves DB, API and worker healthy; `alembic current` equals head.
2. `GET /readyz` is 200; `GET /v1/cities` does not require external network.
3. `ecotwin city create` validates bbox; run OSM import and WorldCover import from real cached/downloaded objects; inspect staging and published rows, spatial index and manifest SHA256. Fetch Open-Meteo forecast and pin revision.
4. Create two scenarios from same snapshot; modify first scenario's classified land-cover area; verify second scenario and baseline unchanged after commit and after worker retry.
5. Simulate event rainfall in both; verify area conservation, nonnegative runoff, expected sign of delta for tree-to-built conversion under documented runoff coefficient assumptions, and no errors in legacy conservation tests.
6. Repeat same idempotent request and verify exactly one job/result. Repeat with changed payload under same key: HTTP 409.
7. Stop and restart worker mid-job, verify recovery/lease/duplicate resistance. Remove required dataset and verify a typed error, **not** a numerical zero.
8. Restart all containers disconnected from internet; previously imported city, weather and completed scenarios must still be available. External ingestion jobs may report upstream unavailable without impacting cached read endpoints.

## 14. Test matrix and release acceptance gates

| Test group | Minimum assertions | Gate |
|---|---|---|
| Legacy domain regression | Existing 49 tests or actual suite; zero introduced regressions | Required |
| Geometry/unit tests | WGS84 normalization, projected area correctness, polygon holes, invalid/multipolygon handling, bbox limits, land-cover total preservation | Required |
| Data/import tests | Valid real-source fixture parse, unit/range checks, checksum reject, provider 429/5xx retry, malformed response handling, pagination, no invented station readings | Required |
| Storage tests | local-only never calls AWS; S3 no fallback on 403; verified local cache on service timeout in explicit auto mode; wrong digest rejected; traversal rejected; streamed large file | Required |
| Hydrology/solar math | hand-computed golden cases, zero rainfall, zero baseline percentage null, mass/area invariants, expected scenario sign, solar zero irradiance result zero | Required |
| Waste adapter | input categories compatible, mass closure retained, route fractions sum to 1, infeasible optimizer status reported | Required when existing engine verified |
| Database migrations | fresh PostGIS init, upgrade twice safe, non-destructive downgrade policy, real spatial index, foreign-key enforcement | Required |
| Auth/ownership | unauthorized 401, wrong owner 403/404 according to policy, expired token, wrong issuer/audience, dev prohibited in prod, malicious CORS/geometry rejected | Required |
| API contract | OpenAPI schema matches live response; 422 typed input errors; source/provenance; pagination; concurrency version conflict | Required |
| Queue/recovery | duplicate jobs idempotent, SQS at-least-once safe, worker crash/lease expiry, DLQ behavior and retry cap, cancellation, job timeout | Required |
| Integration | Docker Compose PostGIS + ingestion fixture + scenario + job + results, no internet required for cached dataset run | Required |
| Security scan | dependency audit, container vulnerability scan, no hard-coded credential, no elevated root runtime | Required |
| Operational | `/readyz`, structured logs, metric counters, restart, backup/restore drill, graceful deploy and rollback procedure | Required |
| Load smoke | 50 concurrent reads + 5 queued simulations with measured p95, error rate, memory and queue latency | Report measurements; tune before production |

**Property-based assertions:** cumulative class area conserved for all valid reclassification edits; all `area_m2 >= 0`; runoff in `[0, P_m × modeled_land_area]` for C∈[0,1]; zero precipitation gives zero runoff; PV energy nonnegative for irradiance >= 0; scenario never alters baseline digests; duplicate job processing yields exactly one immutable result; diff of same input digest yields exact normalized result match.

**Minimum automation:** PR workflow runs `ruff check`, formatter check, `mypy` for typed business modules, `pytest -q` with PostGIS service, checks Alembic drift, generates `openapi.json`, scans dependencies and builds Docker image. Merge and release are blocked on failed required checks. `coverage` should report branch coverage and enforce >=85% for new application modules; scientific mathematical core and auth/access-control modules should be >=95% branch coverage. Report actual percentage, not just a threshold assertion.

## 15. Frontend integration: required setup only

Create `frontend/README.md`, minimal `package.json` for Next.js/TypeScript and `src/lib/api-types.ts` generated automatically from `backend/openapi.json`, plus `.env.example`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Provide exact fetch contracts for `cities`, `features`, `observations`, `scenarios`, `jobs` and `results`; describe `Authorization`, `If-Match`, `Idempotency-Key`, expected CORS origin and GeoJSON WGS84 coordinates. API provides viewport-filtered GeoJSON features that a later PixiJS/MapLibre frontend can render. **Do not** implement login screens, 2D tile/sprite rendering, dashboards, or aesthetic interfaces as part of this backend-only assignment. Do not expose OpenAQ/AWS credentials in `NEXT_PUBLIC_*` variables.

---

# Part II — AWS deployment (Docker images → ECR → ECS Fargate)

## 16. Deployment decisions and account prerequisites

Target a single AWS region initially, e.g. `ap-south-1` for an India-focused demonstration. User/operator must supply an AWS account with appropriate permissions, budget, DNS domain for HTTPS, OpenAQ key if air layer is enabled, and access to datasets under each provider's terms. **No instruction can truthfully manufacture AWS account IDs, DNS ownership or private API credentials.** Terraform variables and CLI environment variables below are populated from actual AWS outputs and operator secrets at deployment time; no fake identifiers may be committed.

**Services:** ECR (immutable OCI images), ECS Fargate (API and worker services plus scheduled ingestion tasks), RDS PostgreSQL+PostGIS, S3 (source/dataset object store and result exports), SQS + DLQ, ALB/ACM/Route 53 for HTTPS, VPC/networking, Secrets Manager, CloudWatch/alarms, EventBridge Scheduler, IAM/OIDC and optional AWS Budgets. Avoid EKS, SageMaker, Bedrock and Lambda unless additional distinct use cases justify them. A single image used by distinct ECS task definitions minimizes runtime drift.

### 16.1 Terraform infrastructure acceptance contract

Implement `infra/terraform` as runnable Terraform 1.x with AWS provider constraints and remote encrypted state backend documented in `infra/terraform/README.md`. Add resources:

1. **Network:** VPC spanning at least two AZs; two public subnets for ALB, two private application subnets for ECS tasks, two isolated/private database subnets; egress via properly budgeted NAT or explicitly enumerated endpoints and approved outbound proxy. Fargate tasks need to reach external Open-Meteo/OpenAQ/OSM endpoints when ingestion runs, while ECR/S3/CloudWatch/SQS private access can use VPC endpoints. Database never receives a public IP.
2. **Security groups:** ALB receives 443 from internet; ECS API accepts container port 8000 only from ALB; worker accepts no inbound internet; database port 5432 only from API/worker/ingest security groups. Egress scoped to required destinations where practical; never open DB 5432 worldwide.
3. **ECR:** one private repository `ecotwin-backend`; scanning enabled; immutable tags; lifecycle retention; IAM pull for execution role. Release identifies image by digest or immutable SHA tag.
4. **S3:** dedicated private bucket, versioning, default SSE (SSE-S3 or approved KMS), block-public-access all true, TLS-only bucket policy, lifecycle policies for caches/temporary objects, retention for protected originals/results, role-scoped prefixes.
5. **RDS:** supported PostgreSQL 16 and matching PostGIS extension available; encrypted, private, `backup_retention_period >= 7`, deletion protection on production, automatic minor version upgrade policy, Multi-AZ preferred for genuine production availability (single-AZ only with explicit nonproduction cost trade-off), restricted security group. Create PostGIS via privileged database-bootstrap/migration procedure, not ordinary app user.
6. **SQS:** standard main queue with encrypted messages and DLQ; main visibility timeout exceeds worker's maximum single-attempt processing/heartbeat policy; redrive maxReceiveCount e.g. 5; CloudWatch alarm for age, queue backlog and DLQ count. Messages contain **job UUID only**, not complete data or secrets.
7. **ECS:** cluster, API service desired count >= 2 across two AZs (unless explicitly hackathon/nonproduction), worker desired count >= 1, autoscaling policy keyed to CPU/queue backlog, separate API/worker/ingest task definitions, non-root container runtime, defined CPU/memory, separate task and execution roles, health checks, log groups with retention. Task IAM roles grant API read-only necessary S3/database network and queue send, worker read/write scoped S3/SQS and optional permissions, ingest only allowed import prefixes/providers.
8. **TLS and DNS:** ACM certificate validated for operator-owned hostname, ALB HTTPS 443 listener, redirect HTTP 80 to HTTPS 443, target group health `/readyz`, DNS alias record through Route 53 if domain managed there. Fail the production Terraform apply if there is no valid cert or hostname; do not call an HTTP-only endpoint production-grade.
9. **Identity:** Cognito user pool/app client with appropriate audience/issuer; output pool ID, client ID and region for backend settings. JWT validation remains in API; ALB is not a substitute for per-scenario ownership authorization.
10. **Secrets:** RDS app password/connection URI, optional OpenAQ key and runtime auth settings via Secrets Manager. ECS task definitions reference secret ARNs; no plaintext terraform outputs or GitHub log disclosure. Use IAM task roles, not injected AWS_ACCESS_KEY_ID/SECRET_ACCESS_KEY.
11. **Metrics/budgets:** CloudWatch logs for API/worker/ingest, metric filters/custom application alarms for job errors, bad ingestion, DB connections, queue age, API 5xx and ALB target health; create budget alerts to a confirmed operator address or report inability if it is not provided.
12. **Scheduled ingest:** EventBridge Scheduler invokes one-off ECS tasks for weather/air refresh. OSM/WorldCover ingest scheduled less frequently or on demand. Only deploy enabled connectors and obey API licensing/rate constraints.

**Infrastructure outputs (required):** `aws_region`, `ecr_repository_url`, `ecs_cluster_name`, `api_service_name`, `worker_service_name`, `api_task_definition_arn`, `ingest_task_definition_arn`, `s3_bucket_name`, `sqs_queue_url`, `rds_endpoint`, `cognito_user_pool_id`, `cognito_client_id`, `api_https_url`. Outputs must exclude passwords/keys.

## 17. Step-by-step AWS build and release runbook

### 17.1 Verify tools and identity

Install Docker with Buildx, AWS CLI v2, Terraform and `jq`; authenticate with AWS Identity Center/SSO or short-lived IAM role, **not long-lived access keys**. Execute:

```bash
aws sts get-caller-identity
aws configure get region
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -out=deployment.tfplan
```

The agent must create a real `terraform.tfvars` from `terraform.tfvars.example` based on operator-supplied `environment`, `aws_region`, `domain_name`, `zone_id`, `db_instance_class`, `budget_email`, `allowed_cors_origin` and initial ECS sizing. Provision certificate and DNS verification; run `terraform apply deployment.tfplan` only after the operator reviews cost/region/DNS and explicitly authorizes infrastructure creation. Terraform should create ECR and dependent infrastructure without needing any app container image in ECR by using a documented two-stage apply (bootstrap resources first, then services with actual image digest), or a properly separated bootstrap module; no nonexistent image placeholders in running ECS tasks.

### 17.2 Build, test and push the immutable Docker image

The following commands use **real output values** retrieved dynamically at runtime, rather than hardcoded account IDs:

```bash
set -euo pipefail
export AWS_REGION="$(terraform -chdir=infra/terraform output -raw aws_region)"
export ECR_REPO="$(terraform -chdir=infra/terraform output -raw ecr_repository_url)"
export IMAGE_TAG="$(git rev-parse --short=12 HEAD)"
export ECR_REGISTRY="${ECR_REPO%/*}"

uv sync --frozen
uv run pytest -q
docker buildx build --platform linux/amd64 --pull --tag "${ECR_REPO}:${IMAGE_TAG}" --load .
docker run --rm "${ECR_REPO}:${IMAGE_TAG}" ecotwin --help
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"
docker push "${ECR_REPO}:${IMAGE_TAG}"
export IMAGE_DIGEST="$(aws ecr describe-images --repository-name ecotwin-backend \
  --image-ids imageTag="$IMAGE_TAG" --query 'imageDetails[0].imageDigest' --output text)"
export IMAGE_URI="${ECR_REPO}@${IMAGE_DIGEST}"
printf '%s\n' "$IMAGE_URI"
```

The Docker CLI invocation `docker run IMAGE ecotwin --help` assumes the Dockerfile's default ENTRYPOINT executes the supplied command; if the image uses the `ecotwin` command itself as `ENTRYPOINT`, run `docker run IMAGE --help` instead and update CI smoke accordingly. **Choose one consistent ENTRYPOINT/command contract, implement it, and test it.** `IMAGE_URI` must be used in ECS task definitions; a mutable `latest` tag is forbidden. If deploying on ARM Fargate, build and test an arm64 image and set ECS runtimePlatform consistently instead.

### 17.3 Register task definitions and perform migrations

- Update Terraform `image_uri` variable to the pushed immutable `IMAGE_URI`; apply the service-stage Terraform plan, creating task definitions with correct commands and secrets. API command: `uvicorn ecotwin.api.main:app --host 0.0.0.0 --port 8000`. Worker command: `ecotwin jobs work`. Ingestion command: `ecotwin ingest weather ...` or `ecotwin ingest air ...` via EventBridge task override.
- **One-off schema task before API traffic:** `alembic upgrade head` using the migration task definition in a private subnet with DB reachability. If PostGIS extension creation privileges are needed, complete RDS PostGIS bootstrap with controlled administrator role before running app migrations.
- A migration failure **blocks** service rollout. Backward-compatible expand/contract changes: deploy additive migration, new service, later destructive migration after old tasks drain. Backup snapshot before high-risk migration.
- Ensure task execution role has ECR pull, CloudWatch logs and Secrets Manager reference permissions; task role grants only application resources. AWS distinguishes execution and task roles; do not confuse them.
- Verify task role access to S3 paths and SQS; the API has no generic `s3:*` permission or permission to list every account bucket.

### 17.4 One-time city import to cloud

From a trusted workstation or dedicated data-prep container, import verified local immutable objects to S3 using `aws s3 cp` and checksum manifest, or run ECS ingest task directly using provider downloads. Do **not** copy `data/raw` blindly without source licensing/manifest verification. Example with already-validated artifact:

```bash
aws s3 cp ./data/processed/ \
  "s3://$(terraform -chdir=infra/terraform output -raw s3_bucket_name)/ecotwin/processed/" \
  --recursive --sse AES256
```

This uploads only files already generated under that directory; the corresponding manifest and `dataset_revisions` rows must be imported/published consistently through CLI tooling. The production city snapshot must be created after verifying dataset revisions in RDS. For bulk data, prefer ECS ingestion tasks whose runtime has sufficient storage/time and use checksummed artifacts. Keep local developer DB records separate from production data by explicit import/export workflows; do not `pg_restore` local user accounts/secrets into production.

### 17.5 Roll out ECS services and perform smoke tests

```bash
export CLUSTER="$(terraform -chdir=infra/terraform output -raw ecs_cluster_name)"
export API_SERVICE="$(terraform -chdir=infra/terraform output -raw api_service_name)"
export WORKER_SERVICE="$(terraform -chdir=infra/terraform output -raw worker_service_name)"
export API_URL="$(terraform -chdir=infra/terraform output -raw api_https_url)"

aws ecs update-service --cluster "$CLUSTER" --service "$API_SERVICE" --force-new-deployment
aws ecs update-service --cluster "$CLUSTER" --service "$WORKER_SERVICE" --force-new-deployment
aws ecs wait services-stable --cluster "$CLUSTER" --services "$API_SERVICE" "$WORKER_SERVICE"
curl --fail --show-error --silent "${API_URL}/livez"
curl --fail --show-error --silent "${API_URL}/readyz"
curl --fail --show-error --silent "${API_URL}/v1/cities"
```

Then execute an authenticated create/edit/run/poll/report test against a **dedicated test city and test user** in staging; validate result digest and source metadata. Confirm no AWS credentials or DB passwords appear in application logs or API responses. Confirm stale weather data are labeled and unavailable pollution data not fabricated. Set alarms before public release. If migrations or smoke fail, stop rollout and use the prior stable image digest; any schema rollback must be a reviewed migration/restore operation, not automatic destructive downgrade.

### 17.6 GitHub Actions CI/CD (required)

- Workflow `ci.yml`: on PR, use immutable tool versions/actions pinned to commit SHA when feasible; install uv; verify lock; lint/type-check; run PostGIS service-based tests; generate and diff OpenAPI; build image; scan image and dependencies.
- Workflow `deploy-aws.yml`: on protected main release, require GitHub environment approval. GitHub OIDC (`permissions: id-token: write, contents: read`) assumes an IAM role restricted to this exact repo/ref/environment; no permanent AWS credentials in GitHub Secrets. Build once; push immutable image to ECR; capture digest; prepare/apply compatible Terraform revision; one-off migrate; ECS rolling update; health and smoke; notify deployment status.
- Restrict deployment IAM role to allowed ECR/ECS/PassRole/CloudWatch/Terraform state resources. Protect `main`, require review and successful CI. Container images should carry git revision and build timestamp labels.
- Maintain an artifact with resolved image digest, migration head, test report, OpenAPI digest and dataset/source manifest versions for release traceability.

## 18. Production operations, maintenance and failure recovery

**Health and monitoring:** `/livez` is cheap process check; `/readyz` tests DB connectivity/migration state and worker-ready dependency separately; ALB checks `/readyz`. Define standard log event keys `{timestamp, level, service, request_id, job_id, city_id, dataset_revision_id, source, error_code, duration_ms}` with access-token/API-key scrubbing. Metrics include ingest success/staleness, bad-checksum counts, forecast age, request latency by route, 5xx, `simulation_job_duration`, `simulation_jobs_failed_total`, active leases, queue oldest age, DLQ count, DB pool saturation, S3 fallback count.

**Backups:** RDS automated backups retention >=7 days and daily checks; monthly restore drill to isolated test RDS and PostGIS geometry/query validation. S3 versioning, protected original source revisions and object checksums; separate backup/replication policy for irreplaceable artifacts. Record actual RPO/RTO test measurements, not unverified SLO claims.

**Rollbacks:** store at least the last two deployable image digests and migration compatibility notes. Prefer backward-compatible DB schema deployment. Revert ECS task definition to earlier digest when safe; if an irreversible schema change took place, restore from reviewed backup with downtime plan and explicit data-loss assessment. Never run `alembic downgrade -1` automatically in production.

**Cost control:** AWS Budgets notifications; tags `project=ecotwin`, `env`, `owner`; cap Fargate tasks/queued jobs/ingestion frequency; use S3 lifecycle for temporary files and avoid unbounded raster copies; measure NAT/ALB/RDS costs (often dominant at small scale). A production-grade two-AZ RDS+ALB+NAT+Fargate system is not necessarily free-tier-priced.

**Data compliance:** retain OSM attribution/ODbL conditions, WorldCover CC BY 4.0 attribution and Open-Meteo account/usage terms; document OpenAQ per-record/provider rights where available. Display `observed`, `modeled`, `screening`, `assumed`, and `unavailable` labels consistently. Do not treat publicity of a public dataset as permission to evade rate limits or redistribute proprietary layers.

## 19. Agent delivery checklist: report as PASS / FAIL / BLOCKED, never invented

- [ ] Existing EcoTwin APIs and tests still work; all new source modules have real implementations.
- [ ] Documented `.env.example`, settings validation and safe local boot, no hardcoded cloud secrets.
- [ ] Real PostGIS schema, migrations, indexes, checks and non-destructive revision strategy.
- [ ] Local/S3 data-access unit and integration tests, checksum and fallback test matrix.
- [ ] Actual OSM and WorldCover bounded-city imports; honest provider metadata and source credits.
- [ ] Weather/OpenAQ clients with pagination/timeouts/retries/staleness/missing-data logic.
- [ ] Immutable city snapshot and full scenario CRUD/edit/concurrency isolation.
- [ ] Working vegetation-area, runoff and solar calculations with explicit assumption labels.
- [ ] Existing waste/optimization adapter validated against legacy tests and supplied data.
- [ ] Job state machine, duplicate suppression, leases, retries, cancellation and errors.
- [ ] Auth ownership, injection/path protection and error schema tests.
- [ ] Fully generated and validated OpenAPI + only required frontend client scaffolding.
- [ ] Docker Compose migration/startup/smoke and offline cached-data run.
- [ ] Terraform `validate/plan`, ECR image build/push, ECS/RDS/S3/SQS/task role setup.
- [ ] AWS live deployment/smoke **only if account, domain and credentials were actually provided and authorized**; otherwise mark as `BLOCKED_BY_EXTERNAL_PREREQUISITE`, supplying exact commands and Terraform plan.
- [ ] Source licenses, limitations, setup/operations runbook and reproducibility manifest.

**Final response from coding agent must contain:** files changed, features implemented and not supported; exact setup/deployment commands; tests executed with actual counts; output of Docker smoke; actual cloud resources deployed or external blockers; model versions and scientific limitations; known defects requiring follow-up. **Do not say “production-ready” until actual cloud smoke, security checks, and restore drill are completed and documented.**

## 20. Official source reference register

The following links are the authoritative references for the datasets, model limitations and AWS procedures used above. Review terms at deployment time, as provider policies and API schemas can change.

1. Geofabrik OSM extracts and machine-readable index — https://download.geofabrik.de/ ; https://download.geofabrik.de/index-v1.json
2. OpenStreetMap ODbL license and attribution — https://www.openstreetmap.org/copyright
3. ESA WorldCover products, v200/2021, access options and attribution — https://esa-worldcover.org/en/data-access ; https://registry.opendata.aws/esa-worldcover/
4. ESA WorldCover class codes — https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200
5. Open-Meteo API / forecasts — https://open-meteo.com/en/docs ; https://open-meteo.com/en/terms
6. OpenAQ API v3 and authentication — https://docs.openaq.org/ ; https://docs.openaq.org/using-the-api/api-key ; https://docs.openaq.org/resources/measurements
7. NASA POWER daily API — https://power.larc.nasa.gov/docs/services/api/temporal/daily/
8. USGS Landsat Collection 2 land-surface-temperature product — https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature
9. USDA NRCS runoff model and assumptions — https://directives.nrcs.usda.gov/sites/default/files2/1712930818/31754.pdf
10. RDS PostgreSQL PostGIS extension — https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.PostGIS.html
11. Amazon ECR Docker push — https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html
12. Amazon ECS task and execution IAM roles — https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-iam-role-overview.html ; https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html
13. Amazon ECS Secrets Manager — https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data-tutorial.html
14. Amazon SQS dead-letter queues — https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
15. AWS RDS backup and restore — https://docs.aws.amazon.com/AmazonRDS/latest/gettingstartedguide/managing-backup-restore.html
16. GitHub Actions → AWS OIDC — https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
17. GitHub Actions Docker image → ECR pattern — https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/build-and-push-docker-images-to-amazon-ecr-using-github-actions-and-terraform.html

---

**Scope verdict:** This contract produces a working spatial-data backend, scientific **screening** simulators, integration with the verified current EcoTwin domain library, provenance-driven results, and reproducible AWS container deployment. It does **not** assert that arbitrary city-level forecasts, biodiversity outcomes or health impacts can be inferred precisely from public maps without validated models, network inventories and calibration data.
