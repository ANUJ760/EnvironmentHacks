# Local and AWS deployment

## Fresh clone: local

Prerequisites: Git, Python 3.10+ for the stdlib launcher, Docker Engine/Desktop with
Compose v2, internet access, and several GB of free disk space. Docker supplies
Python 3.12, Node 22, PostGIS and all application dependencies; host npm/uv is not
required. Linux users must be allowed to access Docker. Run from the repository:

```bash
git switch backend
python3 scripts/local.py up
```

Open http://localhost:3000. The launcher preserves existing `.env`, creates it on
first use, downloads and validates source files, migrates PostGIS, imports missing
revisions, publishes a city snapshot, generates trees, builds the frontend, and
waits for service health. This is a real Zurich study, not a synthetic dataset.
First ingestion can take several minutes. Repeat the same command after pulling
updates; already imported hashes are skipped. Do not run two bootstraps concurrently.

```bash
python3 scripts/local.py download             # downloads only, no database needed
python3 scripts/local.py up --with-ollama     # optional CPU Ollama + Qwen model
python3 scripts/local.py status
python3 scripts/local.py refresh              # explicitly re-download static sources
python3 scripts/local.py down                 # preserves data and named volumes
```

Ollama is an external service, **not a Python dependency**. The optional `ai` Compose
profile pins its container and pulls `qwen2.5:1.5b` (~1 GB). It is used only for
explanations of computed findings; numerical impacts work without it. Change
`OLLAMA_MODEL` only to a model your machine can support. No GPU or 3-D renderer is
required. Runtime Python packages and hashes are exported in `requirements.txt`
from `uv.lock`; Docker uses the frozen lock. For a native Python environment use
Python 3.12, `pip install -r requirements.txt`, then `pip install --no-deps -e .`.
Native frontend packages are locked in `frontend/package-lock.json` (`npm ci`).
Native Linux ingestion also needs the OS Expat library (`libexpat1` on Debian);
the Docker image installs it and CI verifies native geospatial imports.

If ports are occupied, set `ECOTWIN_DB_PORT`, `ECOTWIN_API_PORT`, and
`ECOTWIN_FRONTEND_PORT` in the launch environment. Do not delete existing Docker
volumes to fix a port conflict. `up --offline` reuses downloaded scientific inputs;
new imagery/tiles, Docker images, or model weights still require internet unless
already cached. Browser appearance is not guaranteed fully offline.

## Data placement and provenance

`config/datasets/zurich.json` is the version-controlled download recipe. Data bytes,
model weights and secrets are ignored by Git. Downloads are bounded, validated and
atomically installed; receipts record source URLs, licenses and SHA256 hashes.

| Input | Local placement | Acquisition |
| --- | --- | --- |
| OSM city and study extract | `data/raw/osm/*.osm.pbf` | BBBike Zurich, then local crop; ODbL |
| Municipal tree register | `data/raw/zurich-municipal-trees.geojson` | Zurich open data; source license in recipe |
| ESA WorldCover 2021 | `data/raw/worldcover/zurich-center.tif` | Native-resolution ranged crop, not full global tiles |
| Weather and regional air forecasts | `data/raw/weather/`, `data/raw/air/` | Open-Meteo weather/CAMS; three-hour refresh cache |
| Research reference PDFs | `data/raw/research/` | USDA/IPCC/NRCS references in recipe |
| Generated tree visualization | `frontend/public/maps/zurich-trees.geojson` | Municipal/OSM reconciliation |
| Vector tiles, Swiss aerial imagery, glyphs | `data/cache/maps/` | Automatically downloaded on demand through restricted proxy |
| Ingested immutable source objects/snapshots | `data/raw/`, `data/processed/`, `data/manifests/` | Backend local object store |
| Download receipts/checkpoints | `data/bootstrap/` | Bootstrap harness |

Streamed visualization cache is capped at 1 GB and records source/hash metadata;
it is not an all-zoom offline city archive. Refreshing forecasts publishes a new
snapshot; old snapshots remain reproducible. PostGIS geometry/revisions live in
the `pgdata` Docker volume, not Git. Ollama weights live in `ollama_models`.
OpenAQ station ingestion needs `OPENAQ_API_KEY` and explicit bootstrap
`--with-openaq`; municipal waste/material/operator records require genuine supplied
measurements. These are not silently substituted with fabricated observations.
Landsat is not an input to the current primary planner. See [datasets](DATASETS.md)
and [architecture](ARCHITECTURE.md) for coverage and scientific limitations.
The visual city is wider than the calibrated/imported study extent. Regional air
forecasts do not establish street-level pollution, oxygen or river chemistry.

## AWS storage and deployment harness

### AWS-provided CloudFront hostname

For an account without a custom domain, set `use_cloudfront=true` in the ignored
Terraform variables file. Generate a random `origin_verify_secret` of at least
32 characters and protect it like a credential. `domain_name`, `zone_id`, and
`allowed_cors_origin` can remain empty: the public URL and CORS origin come from
the new CloudFront distribution. The default custom-domain configuration remains
available when `use_cloudfront=false`.

CloudFront redirects visitors to HTTPS and disables caching for application/API
responses. Its load-balancer origin uses HTTP because an AWS load-balancer name
cannot use a customer ACM certificate. Origin ingress is restricted to AWS's
CloudFront prefix list; listener rules also require the generated secret header.
Use a custom domain with ACM for HTTPS on both network legs when required.

For initial RDS setup, run `scripts/bootstrap_aws_database.py` as a one-off ECS
task in the private application subnets. Give that temporary task permission to
read the RDS administrator secret and write the four runtime database secrets.
Supply `DB_ADMIN_SECRET_ARN`, `DB_HOST`, and the JSON mapping
`DB_RUNTIME_SECRET_ARNS`. Run it first to create PostGIS and distinct database
roles, run the migration with the migration role, then run it with `--grants`.
Remove the temporary administrator IAM permissions afterward. Passwords are
generated in memory and stored in Secrets Manager; no password enters Terraform
variables or command output.

No cloud resources are created by local setup. AWS deployment is an explicit,
paid operator action requiring AWS CLI/SSO credentials, Terraform 1.11+, Docker,
an owned Route53 domain, and a private encrypted/versioned Terraform state bucket.
Read [the infrastructure runbook](../infra/terraform/README.md), especially DB role
bootstrap and budgets, before applying anything.

Persistent scientific data belong in the **private encrypted S3 dataset bucket**
created by Terraform, under `ecotwin/raw/`, `ecotwin/processed/`,
`ecotwin/manifests/` and `ecotwin/results/`. Preserve immutable content-addressed
keys; never upload `.env`, credentials, model weights or local DB volumes.
Private RDS/PostGIS stores geometry and revision metadata. ECS/Fargate disk is
temporary: it is only download/compute staging. The API/worker retrieve verified
objects from S3 using task roles. Keep S3 versioning/backups and RDS backups.
The generated tree asset is included in the frontend image at build time; an
optional licensed public CDN URL can replace it. Map proxy cache is disposable
task-local disk in AWS; do not expose the scientific bucket to browsers.

The helpers below are dry-run by default; `--apply` explicitly enables S3 writes,
image pushes, or one-off paid tasks. They do not call `terraform apply`.

1. Download locally using `scripts/local.py download`, commit source changes, and
   configure ignored `infra/terraform/terraform.tfvars` using its example. Initialize
   the remote state backend. Apply a reviewed initial plan with `enable_tasks=false`
   and `enable_services=false` to create networking, S3, ECR and RDS.
2. Capture identifiers (not credentials):

   ```bash
   terraform -chdir=infra/terraform output -json > deployment-outputs.json
   uv sync --frozen
   uv run python scripts/aws_deploy.py images --outputs deployment-outputs.json
   uv run python scripts/aws_deploy.py images --outputs deployment-outputs.json --apply
   ```

   Set both printed immutable `image_uri` and `frontend_image_uri` in tfvars. The
   images are separate: never use the backend image for the frontend task.
3. Bootstrap PostGIS and least-privilege DB users with the runbook's SQL template;
   install their TLS connection URIs in Secrets Manager. Set `database_secret_arns`,
   `enable_tasks=true`, services still false; review/apply and refresh outputs.
4. Optional reproducible seed transfer (bucket name comes from Terraform outputs):

   ```bash
   uv run python scripts/dataset_bundle.py upload --bucket YOUR_DATASET_BUCKET --region YOUR_REGION
   uv run python scripts/dataset_bundle.py upload --bucket YOUR_DATASET_BUCKET --region YOUR_REGION --apply
   ```

   This prints an immutable `manifests/bundles/HASH.json` index. It transfers raw
   inputs, receipts, processed objects and the tree asset, not DB rows or map cache.
   Without a seed index, the AWS bootstrap downloads the same registered sources
   using NAT egress. With a seed, it verifies/restores files from S3 first.
5. Run migrations, then ingestion; the helper waits and requires exit code zero:

   ```bash
   uv run python scripts/aws_deploy.py migrate --outputs deployment-outputs.json --apply
   uv run python scripts/aws_deploy.py bootstrap --outputs deployment-outputs.json --bundle-index manifests/bundles/HASH.json --apply
   ```

   The bootstrap publishes source objects/snapshot to S3 and imports geometry into
   RDS. Register `ingest_city_slug="zurich-center"` only once the city exists.
6. Set `enable_services=true`; review/apply the service stage. Wait for API,
   worker and frontend ECS services to stabilize; check HTTPS `/readyz`,
   `/v1/cities`, `/api/health` and the interactive map/removal preview. Frontend
   calls API through private Cloud Map DNS, not localhost or public port 8000.
   Inspect CloudWatch failures, DLQ, alarms and missing-source states.

Terraform does not provision Ollama on Fargate. Keep cloud explanations optional,
or operate a separately secured CPU/GPU Ollama service and configure its internal
URL/model using `ollama_base_url`, `ollama_model` and the explicit
`ollama_allowed_hosts` Terraform hostname allowlist. Never expose unauthenticated
Ollama to the internet. The frontend has no credentials for scientific S3 inputs.
The manual GitHub release workflow requires pre-registered task definitions, both
image digests and a protected production environment with least-privilege OIDC.
Rollback to compatible image/task digests; do not automatically downgrade schemas.
Local tests and Terraform validation are not evidence of a live AWS deployment.

## Agent handoff

Use [this copy-and-paste prompt](LOCAL_AGENT_PROMPT.md) for a fresh checkout.
