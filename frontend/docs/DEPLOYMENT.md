# EcoTwin Deployment Guide

## 1. Local Development Quickstart

### Prerequisites
- Node.js 22 LTS & npm
- Docker Engine & Docker Compose
- Python 3.12+ (for backend tooling)

### Step 1: Environment Configuration
```bash
# Repository root
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

Generate a short-lived local development bearer token:
```bash
# If using uv directly:
uv run ecotwin auth issue-dev-token --subject local-developer --minutes 120

# Or via docker compose:
docker compose exec api ecotwin auth issue-dev-token --subject local-developer --minutes 120
```
Paste the returned token into `frontend/.env.local` as `ECOTWIN_DEV_BEARER_TOKEN`.

### Step 2: Running via Docker Compose
```bash
docker compose up -d db api worker migrate frontend
```
The frontend will be available at `http://localhost:3000`.

### Step 3: Running Directly on Host
```bash
cd frontend
npm ci
npm run api:generate
npm run dev
```

---

## 2. Production AWS Release Runbook

### Topology
- **Amazon ECR**: Immutable repository `ecotwin-frontend`
- **Amazon ECS Fargate**: 2 tasks in private subnets across 2 AZs
- **Application Load Balancer**: HTTPS listener routing port 443 to frontend port 3000
- **AWS Secrets Manager**: Runtime storage for `NEXTAUTH_SECRET` and Cognito client credentials

### Build & Push Immutable Image
```bash
export AWS_REGION="$(terraform -chdir=infra/terraform output -raw aws_region)"
export ECR_REPO="$(terraform -chdir=infra/terraform output -raw frontend_ecr_repository_url)"
export IMAGE_TAG="$(git rev-parse --short=12 HEAD)"

aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${ECR_REPO%%/*}"

docker build --pull --file frontend/Dockerfile --tag "$ECR_REPO:$IMAGE_TAG" ./frontend
docker push "$ECR_REPO:$IMAGE_TAG"
```

### ECS Rollout
```bash
export ECS_CLUSTER="$(terraform -chdir=infra/terraform output -raw ecs_cluster_name)"
export FRONTEND_SERVICE="$(terraform -chdir=infra/terraform output -raw frontend_ecs_service_name)"
export FRONTEND_URL="$(terraform -chdir=infra/terraform output -raw frontend_https_url)"

aws ecs update-service --cluster "$ECS_CLUSTER" --service "$FRONTEND_SERVICE" --force-new-deployment
aws ecs wait services-stable --cluster "$ECS_CLUSTER" --services "$FRONTEND_SERVICE"

# Verification
curl --fail --silent --show-error "$FRONTEND_URL/api/health"
```
