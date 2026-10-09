"""Offline read and authenticated simulation smoke against an imported city."""

import os
import time

import httpx

base = os.environ.get("ECOTWIN_API_URL", "http://localhost:8000").rstrip("/")
token = os.environ.get("ECOTWIN_SMOKE_TOKEN")
with httpx.Client(base_url=base, timeout=30) as client:
    for path in ["/livez", "/readyz", "/v1/cities"]:
        response = client.get(path)
        response.raise_for_status()
        print(path, response.status_code)
    cities = response.json()
    if not cities:
        raise SystemExit(
            "Read health smoke passed; full simulation requires a downloaded/imported city (docs/DATASETS.md)."
        )
    if not token:
        raise SystemExit(
            "Set ECOTWIN_SMOKE_TOKEN from ecotwin auth issue-dev-token for authenticated scenario smoke."
        )
    city = cities[0]
    headers = {"Authorization": "Bearer " + token}
    response = client.post(
        "/v1/scenarios",
        headers=headers,
        json={
            "city_id": city["id"],
            "snapshot_id": city["active_snapshot_id"],
            "name": "Operator smoke",
        },
    )
    response.raise_for_status()
    scenario = response.json()
    import uuid

    response = client.post(
        f"/v1/scenarios/{scenario['id']}/simulate",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"requested_models": ["landcover_summary", "runoff_screen"], "event_rainfall_mm": 50},
    )
    response.raise_for_status()
    job = response.json()
    for attempt in range(90):
        response = client.get(job["status_url"], headers=headers)
        response.raise_for_status()
        status = response.json()
        if status["state"] == "SUCCEEDED":
            response = client.get("/v1/results/" + status["result_id"], headers=headers)
            response.raise_for_status()
            print("scenario/job/result smoke passed", response.json()["output_digest"])
            break
        if status["state"] in {"FAILED", "CANCELED"}:
            raise SystemExit(str(status))
        time.sleep(2)
    else:
        raise SystemExit("Smoke exceeded its polling deadline")
