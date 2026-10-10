# Real datasets: operator download checklist

No real city dataset is included. `data/raw/` and `data/processed/` are deliberately
empty and ignored by Git. Never place confidential or restricted data in a commit.
The tests use hand-built CC0 geometry and parser contract shapes, not city measurements.

1. Choose a WGS84 bounding box of **at most 25 km²**, and register it:
   `docker compose run --rm ingest ecotwin city create --city-id my-area --name 'My study area' --bbox WEST,SOUTH,EAST,NORTH --timezone Asia/Kolkata`.
2. **OSM required:** download the appropriate regional `.osm.pbf` from
   https://download.geofabrik.de/ (index https://download.geofabrik.de/index-v1.json).
   Crop once outside API requests, preserving complete way/relation references:
   `osmium extract --bbox WEST,SOUTH,EAST,NORTH --strategy complete_ways regional.osm.pbf --output data/raw/osm/city.osm.pbf`.
   Import with `docker compose run --rm ingest ecotwin ingest osm --city my-area --file /app/data/raw/osm/city.osm.pbf`.
   ODbL attribution: © OpenStreetMap contributors; review derived-database obligations.
   Bounded development alternative: `--method overpass` without `--file`.
3. **WorldCover required:** `ecotwin ingest worldcover --city my-area` prints the
   exact intersecting 2021 v200 tile URLs and exits without downloading anything.
   Download these GeoTIFFs to `data/raw/worldcover/`. If the area crosses a tile
   boundary, mosaic/crop them into one native-resolution classified city GeoTIFF
   using `scripts/prepare_worldcover.py` before importing. Import:
   `docker compose run --rm ingest ecotwin ingest worldcover --city my-area --file /app/data/raw/worldcover/city.tif`.
   Source: https://esa-worldcover.org/en/data-access ; credit ESA WorldCover 2021 v200,
   CC BY 4.0. This is 2021 land-cover class area, never a present tree inventory.
4. **Weather required:** download explicitly with
   `docker compose run --rm ingest ecotwin ingest weather --city my-area --forecast-hours 72`.
   Review https://open-meteo.com/en/terms for your intended use. Offline alternative:
   `--file /app/data/raw/weather/forecast.json --issued-at ORIGINAL_UTC_TIMESTAMP`.
   Cache must contain the original hourly arrays and units from the provider.
5. **Air conditional:** register a key at https://explore.openaq.org/register,
   set `OPENAQ_ENABLED=true` and `OPENAQ_API_KEY` only in untracked `.env`, then
   `docker compose run --rm ingest ecotwin ingest air --city my-area --lookback-hours 48`.
   Review original-provider licenses. Zero stations yields an unavailable layer.
6. **Waste conditional:** provide municipality records or explicitly labeled
   analyst assumptions. See `data/manifests/waste-input.schema.json`. Download to
   `data/raw/waste/`; import with `ecotwin ingest waste --city my-area --file PATH`.
   Capacity, accepted categories, processing efficiencies, effective dates, stream
   composition, baseline routes and provenance are mandatory. No synthetic city fallback.
7. **Landsat optional:** download Collection 2 Level-2 ST and QA_PIXEL bands from
   https://earthexplorer.usgs.gov/ plus product scale/offset metadata. Use
   `ecotwin ingest landsat --city my-area --scene-dir PATH --manifest JSON_PATH`.
   Required manifest fields: scene_id, acquired_at, st_band, qa_pixel_band,
   scale_factor, add_offset, source_url, source_license, attribution. Output is
   cloud-masked Kelvin **surface** temperature, not causal urban air-temperature change.
8. Verify then publish: `ecotwin datasets verify --city my-area`;
   `ecotwin city snapshot --city my-area`. Simulation needs no live provider calls.

On the host, replace Compose DB hostname `db` with `localhost` and set
`ECOTWIN_LOCAL_DATA_DIR=./data`; inside containers paths begin `/app/data/`.
Every imported source is content-addressed by SHA256 with an immutable license manifest.
Downloading a file is not proof of local scientific calibration or redistribution rights.

## Local Zurich map

The registered `zurich-center` study area uses bbox `8.53,47.37,8.55,47.39`.
Its local baseline now contains OSM, WorldCover 2021 v200, and a 72-hour
Open-Meteo forecast. Source files and imported objects remain in ignored `data/raw/`.
For host CLI commands set `DATABASE_URL` to the loopback Compose database and
`ECOTWIN_LOCAL_DATA_DIR=./data` as described above.

If Overpass is unavailable, the city-scale
[BBBike Zurich extract](https://download.bbbike.org/osm/bbbike/Zuerich/)
is an alternative. Download `Zuerich.osm.pbf` into `data/raw/osm/`, then crop
with complete references before import:

```bash
.venv/bin/python scripts/crop_osm.py --bbox 8.53,47.37,8.55,47.39 \
  --output data/raw/osm/zurich-center.osm.pbf data/raw/osm/Zuerich.osm.pbf
ecotwin ingest osm --city zurich-center --file data/raw/osm/zurich-center.osm.pbf
.venv/bin/python scripts/download_worldcover.py --bbox 8.53,47.37,8.55,47.39 \
  --output data/raw/worldcover/zurich-center.tif
ecotwin ingest worldcover --city zurich-center --file data/raw/worldcover/zurich-center.tif
ecotwin ingest weather --city zurich-center --forecast-hours 72
ecotwin datasets verify --city zurich-center
ecotwin city snapshot --city zurich-center
```

The WorldCover downloader reads only intersecting native pixels using HTTP range
requests and retains source URLs and attribution in the GeoTIFF metadata.
The map requires a published snapshot; registration alone does not provide features.
Start API/worker with `docker compose up -d --no-build api worker` when the local
backend image exists, and run `npm run dev` from `frontend/` for the frontend.

## Entire-city illustrated view

The city viewer and scenario workspace now use MapLibre GL JS with cached,
zoom-dependent vector tiles, not the legacy Pixi point renderer. The default is
a flat 2D illustration with real OSM building footprints, colored roof drawings,
roads, water and parks. There are no building extrusions or 3D camera controls.
Building colors, roof textures and shadows are presentation choices, not measurements.

Zurich is covered by these public sources:

- [OpenFreeMap](https://openfreemap.org/quick_start/): complete-city OpenStreetMap
  vector tiles, loaded on demand rather than 100-feature API pages.
- [swisstopo SWISSIMAGE](https://docs.geo.admin.ch/visualize-data/xyz.html):
  high-resolution **aerial orthophotography**, not orbital satellite imagery.
  The aerial view shows the original imagery; the illustrated view draws mapped
  footprints over a softened imagery background. Attribution is always visible.
- Local mapped trees from the downloaded BBBike Zurich extract. Generate the
  public visualization asset after obtaining that extract:

```bash
.venv/bin/python scripts/export_city_trees.py data/raw/osm/Zuerich.osm.pbf \
  --output frontend/public/maps/zurich-trees.geojson
```

This exports 33,346 OSM tree points in the Zurich visualization extent. They are
mapped objects, not a complete present-day tree inventory. The 6 MB generated
asset is ignored by Git and tiled/clustered by MapLibre's worker. Browser HTTP
caching retains vector, imagery and font tiles; internet access is needed for
new geographic coverage. The MapLibre worker modules are served from the app
and included in standalone production builds.

`View entire city` fits Zurich and the adjacent landscape. Zooming in reveals
individual buildings and finer details; `View analysis area` returns to the
published study boundary. The full-city visual extent does **not** expand the
scientific snapshot: pinned weather, WorldCover, runoff and solar models still
apply to the dashed verified study area. Selecting outside it remains available
for inspection but cannot stage a scenario intervention. The weather card uses
the pinned hourly forecast nearest the current time, with a stale-data label.
Air station markers appear only when observations are present.

The 2D view caps display resolution at 1.5x, requests a low-power GPU context,
uses two tile workers, retains at most 200 cached tiles, throttles hover queries,
and does not rebuild geographic objects during camera movement. Rain decoration
respects reduced-motion preferences and can be disabled via `Atmosphere`.

Validation for this change: 28 frontend unit/component tests, TypeScript, ESLint,
the standalone production build, and the live Zurich map browser test passed.
The browser test checks visible building geometry, canvas dimensions, canvas
reuse on zoom, aerial/illustrated switching, building-layer visibility, whole-city
navigation, and zero paginated feature requests. It uses software WebGL for CI;
it is not a frame-rate claim for every device. Run it against a running local app:

```bash
cd frontend
RUN_LIVE_MAP_TESTS=1 npm run test:e2e -- tests/e2e/city-map.test.ts
```

Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` if using an existing Chromium install.
To check a production build while the development app continues running, use
`ECOTWIN_NEXT_DIST_DIR=.next-check npm run build`.
