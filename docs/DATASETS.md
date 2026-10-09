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
