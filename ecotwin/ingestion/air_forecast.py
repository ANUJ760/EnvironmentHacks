"""Regional CAMS context, never a street observation or intervention prediction."""

import math
from datetime import datetime

from ecotwin.errors import TwinError

URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
FIELDS = {
    "pm2_5": "μg/m³",
    "pm10": "μg/m³",
    "nitrogen_dioxide": "μg/m³",
    "ozone": "μg/m³",
    "sulphur_dioxide": "μg/m³",
    "carbon_monoxide": "μg/m³",
    "carbon_dioxide": "ppm",
    "methane": "μg/m³",
}


def fetch_air_forecast(client, latitude, longitude):
    return client.json(
        URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(FIELDS),
            "forecast_hours": 73,
            "timezone": "UTC",
        },
    )


def parse_air_forecast(document):
    try:
        acquired = datetime.fromisoformat(document["_ecotwin_issued_at"].replace("Z", "+00:00"))
        if not acquired.tzinfo:
            raise ValueError("Timezone required")
        latitude, longitude = float(document["latitude"]), float(document["longitude"])
        if not math.isfinite(latitude + longitude) or not (
            -90 <= latitude <= 90 and -180 <= longitude <= 180
        ):
            raise ValueError("Coordinates required")
        hourly, units = document["hourly"], document["hourly_units"]
        times = hourly["time"]
        if not 1 <= len(times) <= 384:
            raise ValueError("Bounded forecast required")
        rows, previous = [], None
        for index, timestamp in enumerate(times):
            stamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if not stamp.tzinfo:
                from datetime import UTC

                stamp = stamp.replace(tzinfo=UTC)
            if previous and (stamp - previous).total_seconds() != 3600:
                raise ValueError("Continuous hourly timestamps required")
            previous = stamp
            row = {"valid_at": stamp.isoformat()}
            for field, unit in FIELDS.items():
                values = hourly.get(field)
                if values is None:
                    row[field] = None
                    continue
                if len(values) != len(times) or units.get(field) != unit:
                    raise ValueError("Arrays or units mismatch")
                value = values[index]
                if value is not None and (
                    isinstance(value, bool) or not math.isfinite(value) or value < 0
                ):
                    raise ValueError("Invalid concentration")
                row[field] = value
            rows.append(row)
        return {
            "fetched_at": acquired.isoformat(),
            "source_lat": latitude,
            "source_lon": longitude,
            "series": rows,
            "units": FIELDS,
        }
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise TwinError(
            "UPSTREAM_PAYLOAD_INVALID", "Valid hourly regional air forecast required"
        ) from exc
