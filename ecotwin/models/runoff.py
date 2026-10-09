import math

from ecotwin.errors import TwinError

COEFFICIENTS = {10: 0.15, 20: 0.20, 30: 0.25, 40: 0.30, 50: 0.85, 60: 0.65}


def runoff_volume(
    areas: dict[int, float], rainfall_mm: float, coefficients: dict[int, float]
) -> float:
    if not math.isfinite(rainfall_mm) or rainfall_mm < 0:
        raise TwinError("MODEL_INPUT_UNSUPPORTED", "Rainfall must be finite and nonnegative")
    if any(not math.isfinite(a) or a < 0 for a in areas.values()) or any(
        not math.isfinite(c) or not 0 <= c <= 1 for c in coefficients.values()
    ):
        raise TwinError("MODEL_INPUT_UNSUPPORTED", "Invalid area or runoff coefficient")
    return (
        rainfall_mm
        / 1000
        * math.fsum(
            area * coefficients[k] for k, area in sorted(areas.items()) if k in coefficients
        )
    )
