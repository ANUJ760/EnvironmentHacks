# EcoTwin Frontend UX Flows & Interaction Specification

## 1. Public Discovery Journey
1. **Landing (`/`)**:
   - Welcome banner introducing EcoTwin as an evidence-backed urban environmental simulation platform.
   - Core capability cards (ESA WorldCover GIS mapping, stormwater runoff screening, indicative solar PV potential).
   - Clear CTA button to `/explore`.
2. **City Directory (`/explore`)**:
   - Paginated list of registered city study areas retrieved via `GET /v1/cities`.
   - Real-time client-side filter by city name and slug.
   - Status badge (`READY`, `INGESTING`), analysis CRS (`analysis_srid`), and data product capabilities.
   - Direct links to **View Map** (`/city/[cityId]`) and **Simulate Lab** (`/city/[cityId]/simulate`).

## 2. Interactive Map & Environmental Inspection (`/city/[cityId]`)
1. **Map Viewport**:
   - Central WebGL-accelerated 2D canvas rendered via PixiJS v8.
   - Automatic fallback to an accessible DOM/SVG renderer if WebGL is unavailable or when toggled by keyboard/accessibility tools.
   - Smooth mouse/touch panning, wheel zooming, and responsive canvas resizing.
   - Viewport bounding-box queries debounced by 150 ms to fetch visible features (`GET /v1/cities/{id}/features?bbox=...`).
2. **Left Rail (Layers)**:
   - Independent toggles for Buildings, Roads, Parks & Canopy, Water Bodies, Land Cover, Air Stations, Weather, and Waste Facilities.
3. **Right Inspector**:
   - **Feature Tab**: Displays selected geographic feature attributes, geometry type, calculated area (ha), dataset source, and custom tags.
   - **Observations Tab**: Live weather conditions (temperature, precipitation, GHI solar irradiance) and active air monitoring station readings (PM2.5 with units and measurement timestamps).
   - **Sources Tab**: Registered ingestion revisions, SHA-256 digests, and licenses.

## 3. Scenario Lab Journey (`/city/[cityId]/simulate`)
1. **Scenario Initialization**:
   - Opens modal to name scenario and binds it to the city's active dataset snapshot.
   - Submits `POST /v1/scenarios` to receive immutable UUID, version 1, and ETag.
2. **Intervention Staging**:
   - **Land Cover Reclassification**: Selects a polygon feature or boundary, source class (e.g. 50 Built-up), target class (e.g. 10 Tree cover), and conversion fraction (0.01 to 1.00).
   - **Solar PV Installation**: Sets installed kWp, performance ratio (default 0.75), panel tilt, and panel azimuth.
   - Staged edits are displayed with undo/redo capability and instant canvas preview.
3. **Saving Revisions**:
   - Submits `PUT /v1/scenarios/{id}/edits` with `If-Match: <eTag>`.
   - Updates local revision and ETag on 200 OK.
4. **Concurrency Conflict Recovery**:
   - If HTTP 409 or 412 is returned due to another session's edit, a non-destructive modal presents the server state vs the local draft, allowing safe reload or export of the draft to JSON.

## 4. Simulation Execution & Reporting (`/results/[resultId]`)
1. **Model Selection**:
   - Dialog displays runnable models (`landcover_summary`, `runoff_screen`, `solar_pv`, `waste_balance`) with requirements.
   - Displays unsupported domains (`heat_delta`, `pm25_delta`, `biodiversity`) with scientific rationale.
   - Sets event rainfall (mm) for runoff screening.
2. **Submission & Polling**:
   - Submits `POST /v1/scenarios/{id}/simulate` with UUID `Idempotency-Key`.
   - Transitions to job progress panel; polls `GET /v1/jobs/{job_id}` every 2 seconds.
   - Supports job cancellation request (`POST /v1/jobs/{job_id}/cancel`).
3. **Immutable Report**:
   - On job completion, navigates to `/results/[resultId]`.
   - Displays summary metric grid with baseline, scenario, deltas, and evidence class badges (`OBSERVED`, `DETERMINISTIC_CALCULATION`, `SCREENING_ESTIMATE`).
   - Cryptographic provenance card with input/output SHA-256 digests, model versions, and warnings.
   - Report export to JSON.
