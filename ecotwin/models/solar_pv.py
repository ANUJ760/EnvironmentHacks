import math

from ecotwin.errors import TwinError


def solar_energy(
    installed_kwp: float, ghi: list[float], performance_ratio: float = 0.75, tilt: float = 0
) -> float:
    if tilt != 0:
        raise TwinError(
            "MODEL_INPUT_UNSUPPORTED",
            "Tilted PV requires pinned plane-of-array irradiance; only horizontal PV is supported",
        )
    if (
        not math.isfinite(installed_kwp)
        or installed_kwp < 0
        or not math.isfinite(performance_ratio)
        or not 0 < performance_ratio <= 1
        or any(not math.isfinite(v) or v < 0 for v in ghi)
    ):
        raise TwinError("MODEL_INPUT_UNSUPPORTED", "Invalid PV or irradiance parameters")
    if not ghi:
        raise TwinError("INSUFFICIENT_INPUT_DATA", "Hourly irradiance required")
    return installed_kwp * math.fsum(ghi) / 1000 * performance_ratio
