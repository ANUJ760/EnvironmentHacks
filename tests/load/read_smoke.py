import argparse
import asyncio
import json
import statistics
import time

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", required=True)
parser.add_argument("--city-id", required=True)
args = parser.parse_args()


async def main():
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30) as client:

        async def read(index):
            started = time.perf_counter()
            try:
                response = await client.get(f"/v1/cities/{args.city_id}/landcover")
                return time.perf_counter() - started, response.status_code
            except httpx.HTTPError:
                return time.perf_counter() - started, 0

        results = await asyncio.gather(*(read(index) for index in range(50)))
        durations = sorted(duration for duration, _ in results)
        print(
            json.dumps(
                {
                    "requests": 50,
                    "concurrency": 50,
                    "p95_seconds": durations[47],
                    "mean_seconds": statistics.mean(durations),
                    "errors": sum(status != 200 for _, status in results),
                    "scope": "operator_supplied_staging_city",
                }
            )
        )


asyncio.run(main())
