from types import SimpleNamespace

import httpx
import pytest
from shapely.geometry import box

from ecotwin.config import Settings
from ecotwin.errors import TwinError
from ecotwin.ingestion.downloader import ProviderClient
from ecotwin.ingestion.open_meteo import fetch_weather
from ecotwin.ingestion.openaq import fetch_air, pages
from ecotwin.ingestion.osm import category, fetch_osm


def test_air_contract_empty_and_real_species():
    settings = Settings(_env_file=None, openaq_enabled=True, openaq_api_key="test-only-key")
    station = {
        "id": 1,
        "name": "fixture",
        "coordinates": {"latitude": 21.1, "longitude": 79.1},
        "sensors": [{"id": 2, "parameter": {"name": "pm25", "units": "µg/m³"}}],
    }

    class Client:
        def json(self, url, **kwargs):
            assert kwargs["headers"]["X-API-Key"] == "test-only-key"
            return {
                "results": [station]
                if url.endswith("/locations")
                else [
                    {
                        "value": 12,
                        "parameter": {"name": "pm25", "units": "µg/m³"},
                        "period": {"datetimeFrom": {"utc": "2026-10-09T00:00:00Z"}},
                    }
                ]
            }

    result = fetch_air(Client(), settings, (79, 21, 79.2, 21.2))
    assert result["observations"][0]["parameter"] == "pm25" and result["coverage"] == "stations"
    assert fetch_air(Client(), settings, (80, 22, 80.2, 22.2))["coverage"] == "none"
    with pytest.raises(TwinError):
        fetch_air(Client(), Settings(_env_file=None), (79, 21, 79.2, 21.2))
    with pytest.raises(TwinError):
        fetch_air(Client(), settings, (79, 21, 79.2, 21.2), 169)


def test_bounded_pagination_and_weather_fetch():
    class Client:
        def json(self, url, **kwargs):
            return {"results": [{}] * 100}

    with pytest.raises(TwinError):
        pages(Client(), "/locations", {}, {}, max_pages=1)

    class WeatherClient:
        def json(self, url, **kwargs):
            assert kwargs["params"]["wind_speed_unit"] == "ms"
            return {"hourly": {}}

    assert fetch_weather(WeatherClient(), 21, 79) == {"hourly": {}}
    with pytest.raises(TwinError):
        fetch_weather(WeatherClient(), 21, 79, 500)


def test_overpass_geometries():
    ring = [
        {"lon": 79, "lat": 21},
        {"lon": 79.001, "lat": 21},
        {"lon": 79.001, "lat": 21.001},
        {"lon": 79, "lat": 21},
    ]
    elements = [
        {"type": "node", "id": 1, "lon": 79, "lat": 21, "tags": {"natural": "tree"}},
        {"type": "way", "id": 2, "geometry": ring, "tags": {"building": "yes"}},
        {"type": "way", "id": 3, "geometry": ring[:2], "tags": {"highway": "residential"}},
        {
            "type": "relation",
            "id": 4,
            "tags": {"leisure": "park"},
            "members": [{"role": "outer", "geometry": ring}],
        },
    ]

    class Client:
        def request(self, *args, **kwargs):
            return SimpleNamespace(json=lambda: {"elements": elements})

    result = fetch_osm(Client(), box(79, 21, 79.002, 21.002))
    assert len(result["features"]) == 4
    assert {item["geometry"]["type"] for item in result["features"]} == {
        "Point",
        "LineString",
        "Polygon",
    }
    for tags, expected in [
        ({"natural": "tree"}, "mapped_tree"),
        ({"highway": "x"}, "road"),
        ({"natural": "water"}, "water"),
        ({"waterway": "stream"}, "water"),
        ({"leisure": "garden"}, "park"),
        ({"natural": "wood"}, "wood"),
        ({"amenity": "recycling"}, "waste_facility"),
        ({"power": "substation"}, "power"),
        ({"landuse": "residential"}, "landuse"),
    ]:
        assert category(tags) == expected


@pytest.mark.parametrize(
    "response,code",
    [
        (httpx.Response(200, json={"error": True}), "UPSTREAM_PAYLOAD_INVALID"),
        (httpx.Response(400), "UPSTREAM_PAYLOAD_INVALID"),
        (httpx.Response(200, text="bad json"), "UPSTREAM_PAYLOAD_INVALID"),
        (httpx.Response(503), "UPSTREAM_UNAVAILABLE"),
    ],
)
def test_provider_terminal_responses(response, code):
    client = ProviderClient(
        httpx.Client(transport=httpx.MockTransport(lambda request: response)), sleep=lambda _: None
    )
    with pytest.raises(TwinError) as exc:
        client.json("https://api.open-meteo.com/v1/forecast")
    assert exc.value.code == code


def test_provider_network_retry_limit():
    def failure(request):
        raise httpx.ConnectError("network", request=request)

    client = ProviderClient(
        httpx.Client(transport=httpx.MockTransport(failure)), sleep=lambda _: None
    )
    with pytest.raises(TwinError) as exc:
        client.json("https://api.open-meteo.com/v1/forecast")
    assert exc.value.code == "UPSTREAM_UNAVAILABLE"


def test_cached_air_rejects_missing_measurement():
    from ecotwin.ingestion.openaq import validate_cached_air

    with pytest.raises(TwinError):
        validate_cached_air(
            {"coverage": "stations", "observations": [{"value": float("nan")}]},
            box(79, 21, 79.2, 21.2),
        )
    assert (
        validate_cached_air({"coverage": "none", "observations": []}, box(79, 21, 79.2, 21.2))[
            "coverage"
        ]
        == "none"
    )
