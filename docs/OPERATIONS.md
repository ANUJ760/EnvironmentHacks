# Local operation and release gates

Python 3.12, uv, Docker/Compose and Node 22 (client generation only) are required.
`make setup` installs the frozen Python lock and generates a protected untracked `.env`.
`make up` starts database, one-shot migration, API and independent worker.
API: http://localhost:8000/docs ; `/livez`, `/readyz`, `/metrics`.
`make down` preserves the database volume. API/worker see read-only datasets.
Run explicit ingestion through `docker compose run --rm ingest ecotwin ...`.

Follow `docs/DATASETS.md` to populate real download slots. If using host Python,
set `DATABASE_URL=postgresql+psycopg://ecotwin:ecotwin_local_only@localhost:5432/ecotwin`
and `ECOTWIN_LOCAL_DATA_DIR=./data`; keep the generated secret in `.env`.
Issue a local token with `ecotwin auth issue-dev-token --subject local-developer`.
Cognito access tokens are mandatory in cloud. The local database password is only
for the loopback Compose service; use independent generated roles/passwords in AWS.

`make test` runs legacy and new unit/property/contract tests; real integration is
opt-in with `RUN_POSTGIS_TESTS=1`, using a dedicated migrated database. Do not run
integration fixtures in production. `make contracts` generates both OpenAPI and
TypeScript. ETag is a quoted integer; editing requires the current `If-Match`.
Supply `Idempotency-Key` when submitting; same key with changed input is a 409.
Cancellation is idempotent and the worker kills its numerical subprocess at deadline.
DB job rows are authoritative; SQS hints are reconciled by DB polling after publish failure.

## Scientific scope

`landcover-v1`: exact mapped class-area changes; WorldCover 2021, not tree counts.
`runoff-coeff-v1`: volume screening with explicit analyst coefficient assumptions;
no hydraulic flood depths, soil group, drainage or calibration.
`solar-screen-v1`: horizontal/unshaded nameplate yield using pinned hourly GHI;
no tilted calculation without plane-of-array input, no shading/structural approval.
`legacy-waste-v1`: verified existing mass/energy engine; real city records or explicit
analyst assumptions required. Legacy forecasts remain a library API and are not
misrepresented as calibrated spatial city forecasts.
Air measurements and optional Landsat ST are observational overlays only. Heat,
street pollution deltas, wildlife mortality, health outcomes and grid flows are unavailable.

## Operational evidence

See `docs/implementation-report.json` for actual executed checks and external blockers.
AWS apply/push, live Cognito/S3/SQS tests, real-city calibration, load targets and a cloud
restore drill require operator inputs. Passing tests does not certify those gates.
Terraform setup and exact staged release commands are in `infra/terraform/README.md`.
Do not deploy if security scans, migrations, contracts or live smoke fail.
Run `scripts/backup_restore_check.sh` only with distinct source and isolated restore DB
URIs; record actual recovery duration, object checksums and geometry validation.

For worker shutdown use SIGTERM; it releases/retries work, with expired leases reclaimed.
Deterministic input errors are terminal; transport errors retry up to WORKER_MAX_ATTEMPTS.
Retain previous immutable image digest for compatible rollback; no automatic schema downgrade.
Refreshes create revisions but do not alter snapshots or reports. Publish a new snapshot
only after checking coverage, provenance and licenses. Keep source originals for audit.
