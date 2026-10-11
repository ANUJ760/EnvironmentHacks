<p align="center">
  <img src="ecotwin.png" alt="EcoTwin city planning banner" width="100%" />
</p>

# EcoTwin

**An evidence-backed city planner for exploring environmental changes.** EcoTwin
uses real mapped features and published datasets to help users examine the
potential consequences of interventions such as removing a building, tree, road,
or park area, or changing the ground cover in a drawn area.

EcoTwin is a screening and learning tool—not a substitute for site surveys,
engineering design, environmental assessment, or locally calibrated models. It
shows its data sources, assumptions, coverage gaps, and unavailable outputs so
users can judge what a result does and does not mean.

## What you can do

- Explore the registered Zurich study area on a map and inspect mapped buildings,
  trees, roads, parks, and other features.
- Preview a feature removal or draw a bounded area to compare selected changes.
- Review supported estimates such as mapped land-cover area, runoff screening,
  building energy and waste proxies, demolition material balance, vegetation
  indicators, and indicative solar potential when the required inputs are present.
- See forecast and regional-air context with acquisition times, freshness, sample
  coverage, and provenance.
- Export a JSON report containing the request, assumptions, model/data references,
  results, limitations, and integrity hashes. Exported reports can be replayed
  offline with the included validation script.
- Optionally ask a locally run Ollama model to organize verified findings. The
  model does not calculate impact numbers or add unsupported claims.

Results depend on the selected geometry and the available source data. Missing
data are reported as missing; they are not replaced with invented measurements.

## Practical real-world use cases

These examples show how a planner, facilities team, researcher, or community
group could use EcoTwin to structure an early-stage conversation. They are
illustrative workflows, not claims that EcoTwin has been deployed for these
decisions or that its screening output is sufficient for approval or design.

### 1. Review a proposed tree or building removal

Before discussing a small redevelopment or maintenance proposal, select a mapped
tree or building and inspect the removal preview. Compare the existing feature
with the stated ground-replacement assumption. The report can show supported
runoff and vegetation indicators, a roof-solar opportunity proxy for a building,
and qualitative findings where evidence is not sufficient for a number.

**Useful for:** preparing questions for a site visit, identifying missing
measurements, and making trade-offs visible in a community or project meeting.

**Follow-up needed:** confirm the asset, size, condition, ownership, and local
rules on site. A mapped feature is not proof of current condition or removal
permission.

### 2. Compare paved and greener surfaces for a small site

Draw a bounded area such as a courtyard, parking area, or campus plot. Compare the
baseline cover with an explicitly chosen grass or other supported intervention
and review runoff screening across soil-group assumptions. Use the result to
identify whether drainage capacity, soil infiltration, or a surveyed design storm
needs further investigation.

**Useful for:** early conversations about permeable landscaping, rain gardens, or
site retrofit options.

**Follow-up needed:** obtain a site survey, local rainfall/design-storm criteria,
soil tests, and drainage plans. EcoTwin does not model sewer networks, flood depth,
or detailed hydraulic performance.

### 3. Screen a roof for solar follow-up

Select a mapped building and review the indicative rooftop-solar opportunity
under the report's stated usable-area and performance assumptions. Compare the
screening result with the building's approximate footprint and the available
solar-weather inputs; use it to decide whether a detailed roof assessment is
worth commissioning.

**Useful for:** prioritizing roofs for a qualified solar installer or facilities
survey.

**Follow-up needed:** verify roof geometry, orientation, shading, structural
capacity, electrical connection, permits, and actual installed equipment. The
screen is not an energy-yield guarantee or structural approval.

### 4. Prepare a neighborhood greening or redevelopment discussion

Use the map to inspect what is actually represented in the registered study
area, then compare a small set of bounded intervention previews. Share the JSON
reports so participants can see the selected geometry, assumptions, source
coverage, and limitations rather than only a headline number.

**Useful for:** scoping alternatives, explaining data gaps, and agreeing on what
should be measured before a formal plan is prepared.

**Follow-up needed:** bring in local residents, relevant city departments, and
measured inventories. Regional air context and literature-based vegetation
proxies do not establish local health or biodiversity impacts.

### 5. Prioritize campus or municipal field surveys

Use an existing map and its coverage warnings to identify which features,
land-cover classes, or weather inputs are missing or uncertain. A team can use
that list to plan tree inventories, roof inspections, soil sampling, or source
data updates before attempting a more detailed comparison.

**Useful for:** turning an initial desktop review into a practical data-collection
plan.

**Follow-up needed:** replace proxy assumptions with verified local observations
where the decision requires them, then re-import and publish a new data snapshot.

Across these cases, EcoTwin is best used to ask **“what should we verify next?”**
and to compare transparent screening assumptions—not to make a final engineering,
permitting, health, or investment decision on its own.

## Run locally

The quickest route is the included Docker Compose harness. It downloads the
registered public inputs, prepares the local database, imports the Zurich study,
and starts the API, worker, and web app. Data and model files are kept outside Git.

### Requirements

- Git
- Python 3.10 or later (only the standard library is needed on the host for the
  setup launcher)
- Docker Engine or Docker Desktop with Docker Compose v2
- Internet access for initial image and dataset downloads
- Several gigabytes of free disk space for images, source data, database, and
  optional model weights

The containers supply the application runtimes and dependencies. You do not need
to install Python packages, Node.js, PostGIS, or Ollama on the host to use the
standard local setup.

### Start the application

From the repository root, run:

```bash
python3 scripts/local.py up
```

On first run this creates a local `.env` if needed, downloads and validates the
registered inputs, migrates PostGIS, imports missing data, publishes a Zurich
snapshot, builds the application images, and waits for the services to become
healthy. Initial setup can take several minutes. When it is ready, open
[http://localhost:3000](http://localhost:3000).

Useful follow-up commands:

```bash
python3 scripts/local.py status       # show Compose service status
python3 scripts/local.py download     # download inputs without starting services
python3 scripts/local.py refresh      # explicitly refresh static source downloads
python3 scripts/local.py up --offline # reuse downloaded inputs (images/network tiles may still need internet)
python3 scripts/local.py down         # stop services; preserve data and volumes
```

The setup is safe to rerun: already imported content hashes are skipped. Do not
run two bootstrap operations at the same time. `down` intentionally does not
delete the database volume or downloaded data. Do not use `docker compose down
--volumes` unless you explicitly intend to erase the local database and Ollama
model volume.

If the default ports are in use, set these variables before running the launcher:

```bash
ECOTWIN_DB_PORT=5433 ECOTWIN_API_PORT=8001 ECOTWIN_FRONTEND_PORT=3001 \
  python3 scripts/local.py up
```

Then open the printed frontend URL. Configuration and generated secrets are kept
in the ignored `.env`; never commit it.

### Optional local AI explanations

Ollama is optional and is not a Python package or part of the application image.
To start its Compose profile and download the default `qwen2.5:1.5b` model (about
1 GB), run:

```bash
python3 scripts/local.py up --with-ollama
```

This uses additional disk and memory. Core maps, calculations, and reports work
without Ollama. The explanation feature can only organize findings already
computed by EcoTwin; it cannot change numeric results. The model is stored in the
local Docker volume `ollama_models`, not in the repository.

## Data, downloads, and storage

Dataset recipes are versioned in [`config/datasets/zurich.json`](config/datasets/zurich.json).
The setup harness stores downloaded and generated data under ignored local
directories; the actual data files are not committed to this repository.

| Data | Purpose | Local location |
| --- | --- | --- |
| OpenStreetMap extract | Mapped buildings, roads, parks, and other features | `data/raw/osm/` |
| ESA WorldCover 2021 | Land-cover class-area estimates | `data/raw/worldcover/` |
| Zurich municipal tree register | Local mapped tree inventory where available | `data/raw/` |
| Open-Meteo forecast | Hourly weather inputs for supported previews | `data/raw/weather/` |
| Regional air forecast | Regional pollutant and greenhouse-gas context | `data/raw/air/` |
| Source receipts and manifests | Licenses, source references, timestamps, hashes | `data/bootstrap/`, `data/manifests/` |
| Processed scientific objects | Immutable imported source objects | `data/processed/` |
| Map tiles, imagery, and fonts | Disposable on-demand map cache | `data/cache/maps/` |
| PostGIS database | City geometry, revisions, and snapshots | Docker volume `pgdata` |
| Optional Ollama weights | Locally downloaded model files | Docker volume `ollama_models` |

On-demand map tiles are cached as they are used; this is not a complete offline
map archive. Initial downloads and newly requested map areas require internet
access. The downloaded Zurich sample covers a bounded analysis area; the visual
map may show a wider area than the validated scientific data. Coverage limits
are shown in the app rather than extrapolated silently.

Data providers have different licenses and terms. Check the source recipe and
provider terms before redistributing datasets or using them commercially. In
particular, OpenStreetMap data have ODbL attribution and share-alike obligations;
ESA WorldCover is CC BY 4.0. See the [dataset guide](docs/DATASETS.md) for source
details, registering another study area, manual imports, and provenance steps.

## How it works

```text
Web browser (Next.js, React, MapLibre)
              │ same-origin API gateway
              ▼
FastAPI backend ───── PostGIS (city features, source revisions, snapshots)
       │
       ├── deterministic screening models and report export
       ├── provider adapters for weather and regional air
       └── verified object storage (local files in development, private S3 in AWS)

Background worker ─── database queue locally / SQS in the AWS deployment
Optional Ollama ───── local explanation of already-computed findings
```

The web app is in `frontend/`; the Python API, models, ingestion tools, and worker
are in `ecotwin/`; database migrations are in `migrations/`. `compose.yaml`
defines the local services. The API exposes interactive documentation at
[http://localhost:8000/docs](http://localhost:8000/docs) and health endpoints at
`/livez` and `/readyz` while running.

## Scientific scope and limitations

EcoTwin combines mapped data with transparent, deterministic screening methods.
Some features or indicators may be unavailable for a location if its data are
missing or outside the published study coverage. Current models may include:

- **Land cover:** area changes by mapped WorldCover class; the 2021 land-cover
  raster is not a current tree-by-tree inventory.
- **Runoff:** event-volume screening using published curve-number methods and
  explicit soil/cover assumptions. It does not calculate flood depth, drainage
  routing, or storm-sewer capacity.
- **Buildings and energy:** mapped footprint and roof-solar opportunity estimates
  using stated assumptions. Roof tilt, shading, structure, and installed panels
  are not necessarily known.
- **Vegetation:** mapped canopy or tree indicators and literature-based biomass
  proxies. These are not a local tree-health assessment or calibrated carbon
  inventory.
- **Weather and air:** forecast or regional context, not street-level sensors.
  A regional concentration is not a predicted concentration change caused by an
  intervention.
- **Waste and demolition:** supported mass/energy balances and material proxies
  where the required mapped or supplied inputs exist. Assumed values are labeled.

The app does not claim to predict health outcomes, biodiversity change, street
temperature or pollution deltas, flood depths, or river chemistry. See the
[architecture and accuracy notes](docs/ARCHITECTURE.md) and
[interactive preview methodology](docs/REMOVAL_PREVIEWS.md) for formulas, data
coverage, and detailed assumptions.

## Development and verification

Use the Docker harness for a complete local experience. For code development,
the backend targets Python 3.12 and uses `uv`; the frontend targets Node.js 22
and uses the committed npm lockfile.

```bash
# Python dependencies and checks
uv sync --frozen
uv run ruff check .
uv run ruff format --check ecotwin tests scripts migrations
uv run mypy
uv run pytest -q

# Frontend checks
cd frontend
npm ci
npm run api:check
npm run lint
npm run typecheck
npm run test
npm run build
```

PostGIS integration tests require a migrated test database and are opt-in. Do not
point tests at production data. The GitHub Actions workflow runs backend, frontend,
dependency, container-build, and Trivy security checks for pull requests and
pushes to the `backend` branch.

To validate a downloaded report offline:

```bash
uv run python scripts/replay_planning_report.py PATH_TO_EXPORTED_REPORT.json
```

The replay checks report integrity and recalculates outputs from captured inputs;
it does not validate that the inputs represent reality or establish who created
the report. See [operations](docs/OPERATIONS.md) for the local test setup and
release gates.

## Deploy to AWS

The AWS path is explicit and operator-controlled; running locally does not create
cloud resources. The deployment harness uses separate backend and frontend images,
ECS/Fargate, RDS PostgreSQL with PostGIS, a private S3 data bucket, SQS for the
worker, and supporting AWS networking, secrets, and monitoring. Terraform stages
and dry-run-by-default helper scripts are documented in these guides:

- [AWS/local deployment and persistent data placement](docs/DEPLOYMENT.md)
- [Terraform infrastructure and release runbook](infra/terraform/README.md)
- [Dataset source and import guide](docs/DATASETS.md)

In AWS, S3 stores immutable, verified raw/processed datasets, manifests, and
results; RDS/PostGIS stores spatial features and revision metadata. ECS task disk
is temporary and must not be treated as the dataset store. Use private encrypted
S3, IAM task roles, and no long-lived credentials in images. Ollama is not
provisioned by the Terraform deployment; keep explanations optional or operate a
separately secured service. Review AWS costs, provider licenses, security scans,
and the runbook before applying infrastructure.

## Repository map

```text
ecotwin/                 Python API, scientific models, ingestion, worker
frontend/                Next.js planner and map UI
config/datasets/          Registered dataset download recipes
data/                    Local downloads and generated data (ignored by Git)
migrations/              Alembic/PostGIS schema migrations
model_parameters/        Versioned model coefficients and defaults
scripts/local.py         Fresh-clone local setup and service launcher
scripts/bootstrap_data.py Dataset download, validation, and import harness
infra/terraform/         AWS infrastructure
docs/                    Architecture, datasets, deployment, and operations guides
tests/                   Backend tests; frontend tests are under frontend/tests/
```

## Project name and internal identifiers

**EcoTwin** is the project name. Internal identifiers such as the
Python package and command (`ecotwin`), database name, Docker image names, and
`ECOTWIN_*` configuration variables are retained for compatibility with the
existing code and deployment setup.

## License

See [`LICENSE`](LICENSE). Dataset licensing and attribution are separate; consult
the individual source terms before copying or redistributing data.
