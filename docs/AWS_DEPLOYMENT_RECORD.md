# EcoTwin AWS staging deployment

Deployed and verified on 2026-10-11 in AWS account `030933799922`, region
`ap-south-1` (Mumbai).

Public application: **https://dl65r09hy25vj.cloudfront.net**

## Running architecture

- CloudFront distribution `E1906NHR36NVBF` provides the AWS hostname and browser HTTPS.
- Application Load Balancer routes requests to the frontend or backend.
- ECS cluster `ecotwin-staging` runs two API tasks, one worker, and one frontend
  on Fargate in private application subnets.
- Private encrypted RDS PostgreSQL/PostGIS instance `ecotwin-staging` stores spatial
  features, revisions, snapshots, scenarios, and job records. Backups retain seven days.
- Private, versioned, encrypted dataset bucket:
  `ecotwin-staging-data-20261011163745494600000001`.
- SQS job and dead-letter queues, Cognito for protected backend operations,
  Secrets Manager for independent database-role credentials, Cloud Map for private
  API discovery, CloudWatch logs/alarms, and load-balancer WAF rate limiting.
- Two NAT gateways support outbound provider requests from private subnets.
- EventBridge Scheduler imports Zurich weather every three hours. Imports create
  new revisions; publishing a replacement scientific snapshot remains an explicit
  operation. Live previews can retrieve current forecasts independently.

Ollama is optional and is not deployed. Numerical previews and reports work
without it. This is the staging configuration: RDS is single-AZ; the guide's
production Multi-AZ/deletion-protection settings have not been enabled. These
resources incur ongoing AWS charges while running.

## Deployment process used

1. Validated the existing Terraform configuration and verified AWS identity.
   Added the optional CloudFront deployment mode because this account has no
   custom domain or Route53 hosted zone.
2. Created private, encrypted, versioned Terraform state storage in
   `ecotwin-tfstate-030933799922-ap-south-1`, using state key
   `ecotwin/staging.tfstate` and S3 lock files.
3. Applied the infrastructure stage with services/tasks disabled: networking,
   load balancer, CloudFront, RDS, S3, ECR, IAM, queues, Cognito, and monitoring.
4. Built separate `linux/amd64` application images, pushed them to immutable ECR
   tags, and selected their SHA256 digests. Patched the frontend's OS packages and
   removed npm/yarn from its runtime image after its security scan found fixable
   vulnerabilities. Both final images passed the configured Trivy policy:
   fail on HIGH/CRITICAL vulnerabilities with available fixes; unfixed findings
   are excluded.
5. Uploaded the verified local source bundle to private S3, preserving content
   hashes and scientific object keys. No `.env`, credentials, DB volume, map
   cache, or Ollama weights were uploaded.
6. Ran a one-off private ECS database administrator task to install PostGIS,
   generate independent API/worker/ingestion/migration passwords in memory, and
   populate Secrets Manager. Ran Alembic migrations as the migration role, then
   a second administrator task to apply runtime table grants. Removed the
   temporary administrator IAM role and deregistered its task definitions.
7. Registered application task definitions and ran the ingestion harness in a
   private Fargate task. It restored/verified the source bundle, refreshed weather
   and air forecasts, imported source geometry/data into RDS, verified datasets,
   and published the Zurich snapshot. Source objects/manifests are in S3.
8. Enabled the frontend, API, and worker services using immutable image digests,
   fixed the private frontend-to-API security-group rule drift discovered during
   staged applies, and enabled scheduled weather ingestion.
9. Waited for stable ECS deployments and verified the application through the
   public CloudFront hostname, including real browser tests and report replay.

CloudFront's load-balancer connection uses HTTP. Network ingress is restricted
to AWS's CloudFront origin-facing prefix list, and forwarding rules require a
random secret header. Default origin requests are rejected. For TLS on both
network legs, use the custom-domain/ACM deployment option. Application responses
are not cached by CloudFront.

## Release and dataset identifiers

Backend source: `893643c5cc8468dcec0f87532bf0a635944547f4`

```text
030933799922.dkr.ecr.ap-south-1.amazonaws.com/ecotwin-backend@sha256:1562ff2e03f0082f36feb2953c623a4a0c7093de019497d9f6340ddc8f62d74d
```

Frontend source: `c77c2f38858ce59f8cb51279d6ed3bd7d70b1353`

```text
030933799922.dkr.ecr.ap-south-1.amazonaws.com/ecotwin-staging-frontend@sha256:16711adae2172e477745fca8f64fb742b6ddc54e497680fdcbb2f761f76400fd
```

Private seed-bundle index, relative to the `ecotwin/` S3 prefix:

```text
manifests/bundles/14b5475fcb8a1971fe3c77d0a2bbfd73c81dbf61199dda455de5d2c931f046e4.json
```

Published city ID: `c0877c6a-6f4a-4d82-9f70-a5aa18917dca`

Snapshot ID: `35100d23-cf95-4076-b71e-d3bdb5e2e48a`

Imported OSM features: 18,866; WorldCover cells: 57,600; municipal trees: 4,398;
weather samples: 72 hours; air-forecast samples: 73 hours. The study bbox remains
`8.53,47.37,8.55,47.39`; broader visual-map coverage is not broader scientific
coverage.

## Verification evidence

- Database administrator, migration, grants, and ingestion tasks exited zero.
- ECS API, worker, and frontend rollouts reached `COMPLETED`, with no pending tasks.
- Terraform plan reported no infrastructure changes before the final scheduled
  weather-ingestion addition.
- Homepage, `/readyz`, `/livez`, `/api/health`, and city gateway returned HTTP 200.
- `/metrics` returned 403, retired frontend auth/scenario routes returned 410,
  unauthenticated protected backend operations returned 401, and anonymous
  dataset-bucket access returned 403.
- Four Playwright tests passed against the deployed URL: city map navigation and
  layers, public planner access boundaries, municipal-tree selection/provenance,
  and custom-area planning with report export.
- The exported planning report replay verified both integrity hashes and matched
  all calculated metrics.
- Seven onboarding tests passed locally. Terraform validation, formatting, and
  Ruff checks for the database bootstrap helper passed.

Authenticated saved-scenario/queue execution, load testing, and a cloud backup
restore drill were not exercised by this deployment verification.

## Future updates

The ignored `infra/terraform/terraform.tfvars` contains this deployment's settings
and the origin verification secret. Protect it; do not publish it. Terraform state
is stored remotely. `deployment-outputs.json` contains resource identifiers and
is also ignored.

Use [the deployment guide](DEPLOYMENT.md) for image publication, explicit
migrations/imports, and compatible rollbacks. Keep the two image digests distinct.
Review a Terraform plan before applying changes to the running deployment.
Do not delete the RDS instance, dataset bucket, state bucket, or local volumes
when merely stopping or updating application services.
