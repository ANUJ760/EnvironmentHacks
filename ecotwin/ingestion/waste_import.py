"""Strict analyst/municipal waste inputs without synthetic fallback."""

import math

from ecotwin.categories import WasteCategory
from ecotwin.errors import TwinError


def validate_waste(document):
    if (
        document.get("measurement_type") not in {"MEASURED", "ASSUMED"}
        or not document.get("source_url")
        or document.get("synthetic", False)
    ):
        raise TwinError(
            "INSUFFICIENT_INPUT_DATA",
            "Waste inputs require explicit provenance and MEASURED/ASSUMED classification",
        )
    generation = document["daily_waste_tonnes"]
    if not math.isfinite(generation) or generation < 0:
        raise TwinError("MODEL_INPUT_UNSUPPORTED", "Invalid waste mass")
    for facility in document["facilities"]:
        if (
            not facility.get("facility_id")
            or not facility.get("effective_date")
            or not facility.get("source_url")
            or facility.get("measurement_type") not in {"MEASURED", "ASSUMED"}
        ):
            raise TwinError(
                "INSUFFICIENT_INPUT_DATA",
                "Each facility requires identity, effective date and parameter provenance",
            )
        if not math.isfinite(facility["capacity_tpd"]) or facility["capacity_tpd"] < 0:
            raise TwinError("MODEL_INPUT_UNSUPPORTED", "Invalid facility capacity")
        for category in facility["accepted_categories"]:
            WasteCategory.from_str(category)
    return document
