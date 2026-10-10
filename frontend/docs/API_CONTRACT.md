# EcoTwin Frontend Backend API Contract

## 1. Gateway BFF Architecture
The browser client communicates exclusively with the Next.js same-origin BFF endpoint at `/api/gateway/*`.
The BFF:
- Validates the incoming HTTP method and path against an explicit allowlist.
- Attaches the server-side bearer token (`ECOTWIN_DEV_BEARER_TOKEN` in dev mode; Cognito OIDC access token in production).
- Forwards `If-Match`, `Idempotency-Key`, and `X-Request-ID` headers.
- Rejects bodies larger than 1 MB, path traversal (`..`), and URL double-encoding.
- Preserves RFC 7807 problem details JSON and response HTTP status codes.

## 2. Supported Endpoint Map

| BFF Route | Method | Backend Target | Auth Required | Purpose |
|---|---|---|---|---|
| `/api/gateway/readyz` | GET | `/readyz` | No | Backend operational readiness check |
| `/api/gateway/livez` | GET | `/livez` | No | Backend process liveness |
| `/api/gateway/v1/cities` | GET | `/v1/cities` | No | List registered city study areas |
| `/api/gateway/v1/cities/{id}` | GET | `/v1/cities/{id}` | No | City boundary, analysis SRID, active snapshot |
| `/api/gateway/v1/cities/{id}/features` | GET | `/v1/cities/{id}/features` | No | Viewport bounded GeoJSON features |
| `/api/gateway/v1/cities/{id}/landcover` | GET | `/v1/cities/{id}/landcover` | No | ESA WorldCover class area breakdown |
| `/api/gateway/v1/cities/{id}/observations/weather` | GET | `/v1/cities/{id}/observations/weather` | No | Time-series weather readings |
| `/api/gateway/v1/cities/{id}/observations/air` | GET | `/v1/cities/{id}/observations/air` | No | PM2.5 / PM10 monitoring station readings |
| `/api/gateway/v1/cities/{id}/datasets` | GET | `/v1/cities/{id}/datasets` | No | Ingested dataset revisions & checksums |
| `/api/gateway/v1/models` | GET | `/v1/models` | No | Runnable and unsupported model registry |
| `/api/gateway/v1/scenarios` | POST | `/v1/scenarios` | Yes | Create snapshot-bound scenario |
| `/api/gateway/v1/scenarios/{id}` | GET | `/v1/scenarios/{id}` | Yes | Load owned scenario revision |
| `/api/gateway/v1/scenarios/{id}/edits` | PUT | `/v1/scenarios/{id}/edits` | Yes (If-Match) | Replace ordered scenario edits |
| `/api/gateway/v1/scenarios/{id}/simulate` | POST | `/v1/scenarios/{id}/simulate` | Yes (Idempotency) | Submit simulation job |
| `/api/gateway/v1/scenarios/{id}/reports` | GET | `/v1/scenarios/{id}/reports` | Yes | Query scenario report history |
| `/api/gateway/v1/jobs/{id}` | GET | `/v1/jobs/{id}` | Yes | Poll job execution state & progress |
| `/api/gateway/v1/jobs/{id}/cancel` | POST | `/v1/jobs/{id}/cancel` | Yes | Request async job cancellation |
| `/api/gateway/v1/results/{id}` | GET | `/v1/results/{id}` | Yes | Retrieve immutable simulation result |

## 3. Concurrency & Idempotency Rules
1. **Scenario Optimistic Locking**:
   - `PUT /v1/scenarios/{id}/edits` requires `If-Match: <ETag>`.
   - If version conflict occurs, backend returns HTTP 409 or 412 (`SCENARIO_VERSION_CONFLICT`).
2. **Simulation Submission**:
   - `POST /v1/scenarios/{id}/simulate` requires `Idempotency-Key: <UUID>`.
   - Returns HTTP 202 Accepted with `{ job_id, status_url }`.
