# Bounded load smoke

Run `uv run python tests/load/read_smoke.py --base-url https://STAGING_HOST --city-id CITY_UUID`
after real city import. It issues 50 concurrent city/land-cover reads and records actual
latency/error counts as JSON. No throughput target is certified before representative
geography/hardware measurement. Simulations require an authenticated staged test user;
use the operator smoke script for queued runs and monitor worker lag separately.
