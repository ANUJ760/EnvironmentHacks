# AWS infrastructure and release

Validated Terraform 1.11.4, AWS provider 5.100.0 (committed provider checksum lock).
No AWS resources have been created. Account identity, operator-owned domain/Route53
zone, budget recipient, approved region and release approval are external prerequisites.
Two NAT gateways, ALB, private RDS and ECS incur ongoing cost. Staging RDS is single
AZ; production uses Multi-AZ, deletion protection and seven-day encrypted backups.

1. Authenticate using AWS SSO/short-lived role: `aws sts get-caller-identity`.
2. Configure an independently bootstrapped **encrypted, versioned private state
   bucket**. Run `terraform init -backend-config=bucket=YOUR_STATE_BUCKET
   -backend-config=key=ecotwin/ENV.tfstate -backend-config=region=YOUR_REGION
   -backend-config=use_lockfile=true`. State bucket creation is intentionally separate.
3. Copy `terraform.tfvars.example` to ignored `terraform.tfvars`; supply real
   owner/domain/zone/CORS values and keep `enable_services=false`.
   `terraform fmt -check`; `terraform validate`; `terraform plan -out=bootstrap.tfplan`.
   Review cost/region/DNS, then **explicitly approve** `terraform apply bootstrap.tfplan`.
4. Build once after CI: `docker build --build-arg GIT_REVISION="$(git rev-parse HEAD)"
   --build-arg BUILD_TIMESTAMP="$(date -u +%FT%TZ)" -t ecotwin-backend:release .`.
   Authenticate ECR using `aws ecr get-login-password --region REGION`; tag/push using
   the `ecr_repository_url` output and immutable Git SHA. Resolve ECR SHA256 image digest.
5. Bootstrap PostGIS as RDS schema administrator. Provision independent API,
   worker, ingest and migration DB roles with generated passwords; use the grants
   in `scripts/bootstrap_database.sql` as the least-privilege template. Populate
   Secrets Manager runtime secrets with role-specific full `postgresql+psycopg://`
   URIs using `?sslmode=require`. Terraform never handles password plaintext.
6. Supply `database_secret_arns` mapping, immutable `image_uri`, and set
   `enable_tasks=true`, `enable_services=false`. Apply the reviewed task stage.
   Run the `migration_task_definition_arn` as a one-off Fargate task in the private
   subnets using `migration_security_group_id`; wait and inspect exit code **0**.
   Only after migration passes set `enable_services=true` and apply service stage.
7. Import verified sources using a one-off ingestion task; publish the snapshot.
   Configure `ingest_city_slug` only when the city exists. Weather refresh does not
   automatically change an existing immutable snapshot; publish a new one deliberately.
8. `aws ecs wait services-stable --cluster CLUSTER --services API WORKER`;
   `curl --fail https://HOST/readyz`; run `scripts/smoke_local.py` with the staging
   user access token and `ECOTWIN_API_URL`. Check alarms, DLQ, ownership and source licenses.

Outputs are resource identifiers only, never passwords. The execution role pulls
ECR/logs/secrets; individual task roles access only required bucket prefixes and queues.
External provider HTTPS egress uses NAT; DB has no public route/IP. Runtime JSON logs
and `/metrics` support observability; scrape metrics internally, not through public ALB.
The release workflow requires a protected `production` GitHub environment and OIDC role
trust restricted to this repository/environment. Define the workflow environment variables
only after reviewed infrastructure exists. No push or deployment occurs automatically here.

Rollback uses the previous compatible image digest/task definition. Never automatically
run destructive Alembic downgrade. Test encrypted backups by restoring to isolated RDS,
validating PostGIS geometry and comparing row/source digest counts. Record measured RPO/RTO;
a successful local build cannot certify these cloud operational gates.
