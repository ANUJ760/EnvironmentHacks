# Interactive feature removal

Click a mapped tree, building, park or road in the city view. The **Impact** tab
opens automatically. Adjust the ground replacement, soil group, forecast window
and feature-specific assumptions. Calculations debounce by 300 ms and refresh
every minute while the panel is open. **Preview removal on map** paints the
affected footprint with a lightweight 2D replacement; **Before**, **After removal**
and **Restore feature** are reversible. Closing the panel or changing the selection
clears the preview. This does not delete source data or change saved scenarios.

## Data and calculations

`POST /v1/cities/{identifier}/removal-preview` is a read-only screening endpoint.
It prefers a matching feature in the city's published OSM revision. Otherwise it
uses the clicked vector-tile geometry and explicitly labels the result exploratory.
Coordinates and shapes are validated and converted to the city's metric analysis
CRS before measuring area. A road preview is a bounded segment, not an entire road
network. Trees use an assumed circular crown; buildings use mapped footprints.

Open-Meteo provides current hourly forecast rainfall, solar radiation, temperature,
humidity and wind from the city-center weather-model grid. The forecast is cached
for five minutes. Provider failure falls back to published weather **only if it
covers the requested time window**. Incomplete weather omits dependent estimates;
missing weather never becomes a fabricated zero. The interface displays acquisition
time, stale status, sample coverage and the coarse spatial scope. These are forecasts,
not live street sensors. A design storm can replace forecast rainfall independently.

Quantified consequences:

- Surface runoff: [NRCS Urban Soil Primer, table 3.3](https://www.nrcs.usda.gov/sites/default/files/2022-10/urban_soil_primer.pdf)
  curve numbers for good grass, bare ground and impervious surfaces, with the
  standard `Ia = 0.2 S` equation. Sensitivity spans soil groups A–D, not a statistical
  confidence interval. Forecast storms separate after six dry hours, an explicit
  screening assumption. No flood depth, drainage routing or leaf interception is
  modeled. Removing a tree without changing its ground gives zero *modeled ground
  runoff change*, not zero overall hydrological impact.
- Tree crown area and aboveground carbon stock: assumed diameter and
  [Jenkins et al. (2003)](https://research.fs.usda.gov/treesearch/6996) mixed-hardwood
  biomass with [IPCC carbon fraction 0.47, table 4.3](https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/4_Volume4/V4_04_Ch4_Forest_Land.pdf).
  The sensitivity uses four hardwood groups and ±20% diameter. This US forest-tree
  proxy is **not calibrated to Swiss urban trees**. Carbon stock removal is not
  immediate CO₂ emissions; wood fate matters. Roots and soil carbon are excluded.
- Extra sunlight at ground after tree removal: forecast horizontal irradiation
  multiplied by assumed crown area and foliage shade fraction. This is radiant
  energy, not electricity, a temperature change or a verified shadow simulation.
- Building removal: footprint/sealed-area change and lost *hypothetical* roof-solar
  opportunity (assumed usable fraction, 0.2 kWp/m² and 0.75 performance ratio).
  Installed panels, roof tilt and shading are not observed.

[EPA tree and vegetation research guidance](https://www.epa.gov/heatislands/benefits-trees-and-vegetation)
supports qualitative shade, evapotranspiration and vegetation trade-offs. Park habitat,
demolition, pollution and road-access consequences remain qualitative. No invented
temperature, biodiversity, traffic or pollution deltas are returned. Feature size,
soil, species and cover measurements are incomplete: use measured inputs for better
screening, and calibrated local models for planning decisions.

## Optional local Ollama explanation

The deterministic calculations and evidence work without AI. The Next.js server
can connect to an existing local Ollama instance:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma:4b
```

These optional variables belong in the ignored `frontend/.env.local`; restart
Next.js after changing them. When Next.js runs in Compose and Ollama runs on the
host, use a reachable host alias configured for that container. Only local configured
hostnames are accepted. No model is downloaded automatically. An installed Gemma or
Qwen model is selected if `OLLAMA_MODEL` is unset; an explicit installed model wins.

`GET /api/removal/explain` reports availability. `POST` takes a city UUID and the
removal request. The server recalculates a trusted report and asks Ollama to rank
existing research findings using a restricted JSON schema. It renders those exact
verified findings, **not free-form generated numerical predictions**. Model output
cannot add claims or alter impacts. One generation at a time, bounded context,
four CPU threads and a 45-second timeout limit resource use. No external AI service
receives data. Provider errors leave the original consequences fully available.

## Verification

```bash
.venv/bin/pytest -q tests/unit tests/contracts
cd frontend
npm run test
npm run typecheck
npm run lint
RUN_LIVE_MAP_TESTS=1 RUN_LOCAL_AI_TESTS=1 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/path/to/chromium npm run test:e2e -- tests/e2e/removal.test.ts tests/e2e/city-map.test.ts
ECOTWIN_NEXT_DIST_DIR=.next-check npm run build
```

The live test requires the imported Zurich snapshot, running API/frontend and
internet tile access. It clicks an actual rendered feature, changes assumptions,
checks forecast/design-storm results, and verifies the same map canvas survives
before/after comparison. The optional local model was also smoke-tested against
the running `gemma:4b` Ollama instance.

Validated locally on 2026-10-11: 113 backend unit/contract tests, 36 frontend tests,
both live browser tests (including the local explanation), the four-type live API test, TypeScript, ESLint and
the isolated production build passed. Real published tree, building, park and road
requests all returned HTTP 200 with live forecast metadata.
