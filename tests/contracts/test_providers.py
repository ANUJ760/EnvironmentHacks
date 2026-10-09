from datetime import UTC, datetime

import httpx
import pytest

from ecotwin.errors import TwinError
from ecotwin.ingestion.downloader import ProviderClient
from ecotwin.ingestion.open_meteo import FIELDS, parse_weather
from ecotwin.ingestion.openaq import pages


def weather_document():
    return {
        "latitude": 21.1,
        "longitude": 79.1,
        "hourly_units": {k: v[1] for k, v in FIELDS.items()},
        "hourly": {
            "time": ["2026-10-09T00:00", "2026-10-09T01:00"],
            **{k: [50, 50] for k in FIELDS},
        },
    }


def test_weather_contract_and_missing_values():
    doc = weather_document()
    doc["hourly"]["temperature_2m"][0] = None
    rows = parse_weather(doc, datetime.now(UTC))
    assert rows[0]["temperature_c"] is None
    doc["hourly_units"]["wind_speed_10m"] = "km/h"
    with pytest.raises(TwinError):
        parse_weather(doc, datetime.now(UTC))


@pytest.mark.parametrize("change", ["length", "time", "negative", "humidity", "nan"])
def test_weather_failures(change):
    doc = weather_document()
    if change == "length":
        doc["hourly"]["precipitation"] = []
    if change == "time":
        doc["hourly"]["time"][1] = doc["hourly"]["time"][0]
    if change == "negative":
        doc["hourly"]["precipitation"][0] = -1
    if change == "humidity":
        doc["hourly"]["relative_humidity_2m"][0] = 101
    if change == "nan":
        doc["hourly"]["shortwave_radiation"][0] = float("nan")
    with pytest.raises(TwinError):
        parse_weather(doc, datetime.now(UTC))


def test_http_retry_and_no_auth_retry():
    calls = []
    delays = []

    def responder(request):
        calls.append(request)
        return httpx.Response(
            429 if len(calls) == 1 else 200, json={"results": []}, headers={"Retry-After": "1"}
        )

    client = ProviderClient(
        httpx.Client(transport=httpx.MockTransport(responder)), sleep=delays.append
    )
    assert client.json("https://api.openaq.org/v3/locations")["results"] == []
    assert len(calls) == 2 and delays == [1]
    client = ProviderClient(
        httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(403))),
        sleep=delays.append,
    )
    with pytest.raises(TwinError, match="authentication"):
        client.json("https://api.openaq.org/v3/locations")
    with pytest.raises(TwinError):
        client.json("http://127.0.0.1/internal")


def test_openaq_pagination():
    class Client:
        def json(self, url, **kwargs):
            page = kwargs["params"]["page"]
            return {
                "results": [{"id": i} for i in range(100 if page == 1 else 2)],
                "meta": {"found": 102},
            }

    assert len(pages(Client(), "/locations", {}, {})) == 102


def test_timezone_aware_provider_hour_axis():
    document = weather_document()
    document["hourly"]["time"] = ["2026-10-09T00:00:00+00:00", "2026-10-09T01:00:00+00:00"]
    assert parse_weather(document, datetime.now(UTC))[0]["valid_at"].tzinfo is not None
