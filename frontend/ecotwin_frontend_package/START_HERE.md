# EcoTwin frontend AI-agent handoff

## Primary build instructions

1. Attach/check out the actual EcoTwin/EnvironmentHacks repository; do not build from these documents alone.
2. Read `EcoTwin_Backend_Agent_Implementation_Guide.md` for the backend's authoritative `/v1` OpenAPI, simulation, data and auth contracts.
3. Read `EcoTwin_Frontend_Agent_Implementation_Guide.md` completely, then implement the `frontend/` source tree and matching Terraform/Compose/CI changes described in it.
4. Read `assets/ecotwin-ui-concept.png` only for visual direction. Its numerical outcomes are illustrative; never hardcode those numbers in application output.
5. Generate frontend API types from the real backend OpenAPI schema before coding service calls; do not invent endpoint data shapes.
6. Run actual local and browser tests; report PASS/FAIL/BLOCKED faithfully. Do not call live AWS deployment completed without account access and HTTPS verification.

## Required dependencies

- Backend implemented per companion spec, producing generated `backend/openapi.json` and a working local PostGIS dataset.
- Node 22/npm, Python backend tooling, Docker and Docker Compose.
- Production deployment additionally requires real AWS, Cognito, TLS domain and Secrets Manager values from the operator.

## Contents

- Frontend guide in DOCX (reviewable document) and Markdown (source-readable coding-agent contract)
- Companion backend guide in Markdown
- Frontend architecture diagram and previous UI inspiration image

The guide specifies an implementation; it does not contain a completed running EcoTwin frontend.
