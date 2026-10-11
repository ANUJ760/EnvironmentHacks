"""Strict analyst/municipal waste inputs without synthetic fallback."""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


# Exported schema supports operator preparation before any real dataset download.


class ProcessingProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    material_recovery_rate: float = Field(ge=0, le=1)
    landfill_residue_rate: float = Field(ge=0, le=1)
    process_loss_rate: float = Field(ge=0, le=1)
    specific_energy_kwh_per_tonne: float = Field(ge=0)
    energy_efficiency: float = Field(ge=0, le=1)


class FacilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    facility_id: str
    facility_type: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    capacity_tpd: float = Field(ge=0)
    accepted_categories: list[str] = Field(min_length=1)
    profiles: dict[str, ProcessingProfileInput]
    effective_date: str
    source_url: str
    measurement_type: Literal["MEASURED", "ASSUMED"]


class WasteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal[1] = 1
    source_url: str
    source_license: str
    attribution: str
    origin_id: str
    measurement_type: Literal["MEASURED", "ASSUMED"]
    daily_waste_tonnes: float = Field(ge=0)
    composition: dict[str, float]
    facilities: list[FacilityInput] = Field(min_length=1, max_length=1000)
    routing: dict[str, str | list[tuple[str, float]]]
    optimization_weights: dict[str, float] | None = None
    synthetic: Literal[False] = False
