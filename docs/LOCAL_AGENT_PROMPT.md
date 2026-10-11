# Prompt for an agent on a freshly pulled checkout

Copy the following into your coding agent while its workspace is this repository:

```text
Run this project locally from the latest pulled checkout. Read README.md,
docs/DEPLOYMENT.md, and any applicable AGENTS.md first. Preserve all existing
changes, .env secrets, downloaded data, and Docker volumes. Do not deploy to AWS,
push commits, expose services publicly, or delete data.

Check Python 3.10+, Docker Engine/Desktop and Docker Compose v2 availability and
Docker access. Inspect occupied ports 3000, 8000, 5432; if necessary use the
ECOTWIN_FRONTEND_PORT, ECOTWIN_API_PORT and ECOTWIN_DB_PORT overrides without
stopping unrelated processes. Run python3 scripts/local.py up from the repo root.
This must automatically download the registered real datasets, migrate/import
PostGIS, publish the Zurich snapshot, generate the tree asset before building the
frontend, and start healthy services. Allow initial ingestion several minutes.
Use python3 scripts/local.py up --with-ollama only if optional explanations are
wanted and the machine has sufficient RAM/disk; scientific estimates do not need
an LLM. Do not put Ollama in pip requirements or invent missing measurement data.

If a command fails, inspect Compose logs, permissions and network access; repair
only what is necessary and rerun the idempotent harness. Never wipe pgdata, use
docker compose down --volumes, or replace genuine data with mocks to pass checks.
Verify frontend /api/health, backend /readyz and /v1/cities; open the planner in a
browser if available. Confirm buildings/trees render, click a removable feature,
check before/after results, and test a custom-area intervention. Confirm downloaded
raw data/receipts and on-demand imagery/tile cache are in the documented folders.
Report the local URL, commands run, test results, data coverage limitations and
whether optional Ollama was actually tested. Clearly report any prerequisites
you could not install or any remaining failure; do not claim success from a build
alone. Keep the working local app running at the end.
```
