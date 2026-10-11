.PHONY: setup up download up-ai migrate ingest-demo test integration smoke down contracts
setup:
	uv sync --frozen
	python scripts/setup_local.py
up:
	python3 scripts/local.py up
download:
	python3 scripts/local.py download
up-ai:
	python3 scripts/local.py up --with-ollama
migrate:
	docker compose run --rm migrate
# Uses your downloaded files; never fetches a country-sized extract.
ingest-demo:
	docker compose run --rm ingest ecotwin city create --city-id operator-area --name 'Operator study area' --bbox '$(BBOX)' --timezone '$(TIMEZONE)'
	docker compose run --rm ingest ecotwin ingest osm --city operator-area --file /app/data/raw/osm/city.osm.pbf
	docker compose run --rm ingest ecotwin ingest worldcover --city operator-area --file /app/data/raw/worldcover/city.tif
	docker compose run --rm ingest ecotwin ingest weather --city operator-area
	docker compose run --rm ingest ecotwin city snapshot --city operator-area
test:
	uv run pytest -q
integration:
	RUN_POSTGIS_TESTS=1 uv run pytest -q tests/integration
smoke:
	uv run python scripts/smoke_local.py
down:
	docker compose down
contracts:
	uv run python scripts/generate_openapi.py
	cd frontend && npm ci && npm run api:generate && npm run typecheck
