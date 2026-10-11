"""Provider-only, bounded streaming HTTP with explicit retry semantics."""

import random
import time
from urllib.parse import urlsplit

import httpx

from ecotwin.errors import TwinError

ALLOWED_HOSTS = {
    "api.open-meteo.com",
    "air-quality-api.open-meteo.com",
    "api.openaq.org",
    "overpass-api.de",
    "esa-worldcover.s3.eu-central-1.amazonaws.com",
    "download.geofabrik.de",
}


class ProviderClient:
    def __init__(self, client=None, sleep=time.sleep):
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(30, connect=5), follow_redirects=False
        )
        self.sleep = sleep

    def close(self):
        self.client.close()

    def request(self, method, url, **kwargs):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username
            or parsed.port not in {None, 443}
        ):
            raise TwinError("UPSTREAM_URL_REJECTED", "Provider URL is not allowlisted")
        for attempt in range(3):
            try:
                response = self.client.request(method, url, **kwargs)
                if response.status_code in {429, 500, 502, 503, 504}:
                    if attempt == 2:
                        raise TwinError("UPSTREAM_UNAVAILABLE", "Provider retry limit reached", 503)
                    delay = response.headers.get("Retry-After", "")
                    self.sleep(
                        min(30, float(delay)) if delay.isdigit() else 2**attempt + random.random()
                    )
                    continue
                if response.status_code in {401, 403}:
                    raise TwinError(
                        "UPSTREAM_PERMISSION_DENIED",
                        "Provider authentication or license rejected",
                        403,
                    )
                if response.status_code >= 400:
                    raise TwinError("UPSTREAM_PAYLOAD_INVALID", "Provider request rejected")
                if len(response.content) > 50_000_000:
                    raise TwinError(
                        "UPSTREAM_PAYLOAD_INVALID", "Provider JSON exceeds bounded import size"
                    )
                return response
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt == 2:
                    raise TwinError(
                        "UPSTREAM_UNAVAILABLE", "Provider network unavailable", 503
                    ) from exc
                self.sleep(2**attempt + random.random())
        raise TwinError("UPSTREAM_UNAVAILABLE", "Provider unavailable", 503)

    def json(self, url, **kwargs):
        try:
            document = self.request("GET", url, **kwargs).json()
            if document.get("error"):
                raise TwinError("UPSTREAM_PAYLOAD_INVALID", "Provider returned an error document")
            return document
        except (ValueError, AttributeError) as exc:
            raise TwinError(
                "UPSTREAM_PAYLOAD_INVALID", "Provider did not return a valid JSON object"
            ) from exc
