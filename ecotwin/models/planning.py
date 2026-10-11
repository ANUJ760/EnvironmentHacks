"""Small, auditable city-intervention calculations. No ML inference or 3D engine."""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ecotwin.models.removal import (
    CURVE_NUMBERS,
    RemovalMetric,
    carbon_stock,
    metric,
    rain_events,
    runoff_depth,
)


class PlanningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    geometry: dict
    selection_type: Literal["area", "tree", "building", "road", "park", "water"] = "area"
    location: tuple[float, float] | None = None
    action: Literal["remove", "fill", "green"] = "remove"
    replacement: Literal["unchanged", "grass", "bare", "impervious"] = "grass"
    soil_group: Literal["A", "B", "C", "D"] = "B"
    forecast_hours: int = Field(default=24, ge=6, le=72)
    rainfall_mm: float | None = Field(default=None, ge=0, le=300)
    crown_diameter_m: float = Field(default=8, ge=1, le=30)
    trunk_diameter_cm: float = Field(default=30, ge=3, le=150)
    road_width_m: float = Field(default=6, ge=1, le=30)
    road_length_m: float = Field(default=50, ge=5, le=300)
    building_levels: float = Field(default=3, ge=1, le=60)
    energy_kwh_m2_year: float = Field(default=100, ge=0, le=600)
    floor_m2_per_person: float = Field(default=40, ge=5, le=500)
    waste_kg_person_day: float = Field(default=1, ge=0, le=10)
    displaced_fraction: float = Field(default=1, ge=0, le=1)
    demolition_t_m2: float = Field(default=0.8, ge=0, le=5)
    recovery_fraction: float = Field(default=0.6, ge=0, le=1)
    forest_carbon_kg_m2: float = Field(default=7, ge=0, le=50)
    water_depth_m: float = Field(default=1.5, ge=0, le=30)
    fill_height_m: float = Field(default=0.5, ge=0, le=20)
    fill_density_t_m3: float = Field(default=1.6, ge=0.5, le=3)
    leaf_area_index: float = Field(default=3, ge=0, le=10)
    deposition_velocity_mm_s: float = Field(default=1, ge=0, le=10)


class PlanningReport(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    model_version: str = "planning-screen-v1"
    computed_at: str
    city_id: str
    snapshot_id: str
    area_m2: float
    affected_geometry: dict
    geometry_source: str
    within_analysis_area: bool
    inventory: dict
    landcover: list[dict]
    coverage_fraction: float
    metrics: list[RemovalMetric]
    findings: list[dict]
    limitations: list[str]
    sources: list[dict]
    weather: dict
    air: dict
    hourly: list[dict]
    inputs: dict
    provenance: dict
    input_sha256: str
    result_sha256: str


# NRCS woods in good hydrologic condition; good lawn and bare ground use
# the existing, referenced NRCS table. Unknown cover is never assumed to be zero.
WOODS_CN = (30, 55, 70, 77)
CLASS_NAMES = {
    10: "Trees / forest",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare ground",
    70: "Snow / ice",
    80: "Water",
    90: "Wetland",
    95: "Mangroves",
    100: "Moss / lichen",
}


def cover_cn(code, soil):
    if code == 10:
        return WOODS_CN[soil]
    if code == 50:
        return 98
    if code == 60:
        return CURVE_NUMBERS["bare"][soil]
    if code in {20, 30, 40, 100}:
        return CURVE_NUMBERS["grass"][soil]
    return None  # Water, wetland and snow require storage/snow models.


def calculate_planning(request, inventory, cover, area, weather_samples, air_samples, coverage):
    metrics, findings, hourly, limitations = [], [], [], []
    replacement = "grass" if request.action == "green" else request.replacement
    vegetation = sum(
        value for code, value in cover.items() if code in {10, 20, 30, 40, 90, 95, 100}
    )
    forest, water = cover.get(10, 0), cover.get(80, 0)
    if request.selection_type == "water":
        water = area  # The clicked mapped water outline is finer than WorldCover.
    # Selecting a single object is not equivalent to bulldozing everything in
    # its vicinity. Mixed-area interventions explicitly remove all mapped elements.
    clears_buildings = request.selection_type in {"area", "building"}
    clears_vegetation = request.selection_type in {"area", "park", "tree"}
    floor = inventory["floor_area_m2"] if clears_buildings else 0
    canopy = (
        math.pi * (request.crown_diameter_m / 2) ** 2
        if request.selection_type == "tree"
        else forest
        if clears_vegetation
        else 0
    )
    removed_vegetation = (
        min(area, canopy)
        if request.selection_type == "tree"
        else vegetation
        if clears_vegetation
        else 0
    )
    if removed_vegetation > 0:
        metrics.append(
            metric(
                "vegetation",
                "Existing vegetation footprint removed",
                "m²",
                removed_vegetation,
                0,
                "ASSUMED_INPUT" if request.selection_type == "tree" else "MAPPED_GEOMETRY",
                "Assumed circular tree crown"
                if request.selection_type == "tree"
                else "Clipped WorldCover 2021 vegetation classes",
                "Replacement grass is newly established, not equivalent to mature trees or the original habitat.",
            )
        )
        findings.append(
            {
                "id": "vegetation",
                "text": "Existing vegetation is cleared. New grass does not immediately replace mature-tree shade, carbon storage or habitat.",
                "source": "epa",
            }
        )
    if canopy > 0:
        stock = (
            carbon_stock(request.trunk_diameter_cm)
            if request.selection_type == "tree"
            else forest * request.forest_carbon_kg_m2
        )
        metrics.append(
            metric(
                "carbon",
                "Aboveground standing carbon removed",
                "kg C",
                stock,
                0,
                "ASSUMED_INPUT",
                "Jenkins mixed-hardwood proxy"
                if request.selection_type == "tree"
                else "Mapped forest area × user-assumed carbon density",
                "Not a measured stock or immediate CO₂ release. Roots, soil and wood fate are excluded.",
                [-stock * 1.5, -stock * 0.5],
            )
        )
    rain = (
        [request.rainfall_mm]
        if request.rainfall_mm is not None
        else rain_events(weather_samples)
        if weather_samples and all(row.get("rain_mm") is not None for row in weather_samples)
        else None
    )
    unsupported = [
        code for code, value in cover.items() if value > 0.1 and cover_cn(code, 0) is None
    ]
    # Water surfaces are never represented as soil. Filling them needs a routed
    # hydraulic model; report material volume, not a fabricated flood change.
    if coverage >= 0.98 and not unsupported and rain is not None:

        def runoff(soil):
            before = sum(
                value * sum(runoff_depth(p, cover_cn(code, soil)) for p in rain) / 1000
                for code, value in cover.items()
            )
            if replacement == "unchanged":
                after = before
            else:
                after = (
                    area
                    * sum(runoff_depth(p, CURVE_NUMBERS[replacement][soil]) for p in rain)
                    / 1000
                )
            return before, after

        soil = "ABCD".index(request.soil_group)
        before, after = runoff(soil)
        metrics.append(
            metric(
                "runoff",
                "Storm surface runoff",
                "m³",
                before,
                after,
                "SCREENING_ESTIMATE",
                "NRCS event equation on each clipped cover class; six dry hours separate storms",
                "Built-up treated as sealed; shrub/crop/moss use lawn proxy; soil group assumed. No drainage routing or flood depth.",
                [runoff(group)[1] - runoff(group)[0] for group in range(4)],
            )
        )
    else:
        limitations.append(
            "Runoff unavailable where cover is incomplete or contains water, wetland or snow, or rainfall is missing. These require additional hydrological data."
        )
    if floor > 0:
        energy = floor * request.energy_kwh_m2_year
        daily_waste = floor / request.floor_m2_per_person * request.waste_kg_person_day
        for key, label, unit, before in [
            ("energy_local", "On-site operational energy", "kWh/year", energy),
            ("waste_local", "On-site operational waste", "kg/day", daily_waste),
        ]:
            metrics.append(
                metric(
                    key,
                    label,
                    unit,
                    before,
                    0,
                    "ASSUMED_INPUT",
                    "Clipped gross floor area × scenario intensity",
                    "Archetype assumption, not metered consumption or a measured occupant count.",
                    [-before * 1.5, -before * 0.5],
                )
            )
        metrics.append(
            metric(
                "energy_system",
                "Energy including displaced activity",
                "kWh/year",
                energy,
                energy * request.displaced_fraction,
                "ASSUMED_INPUT",
                "Displaced activity keeps the same energy intensity",
                "Default 100% displacement avoids claiming demolition eliminates city-wide demand.",
            )
        )
        metrics.append(
            metric(
                "waste_system",
                "Waste including displaced activity",
                "kg/day",
                daily_waste,
                daily_waste * request.displaced_fraction,
                "ASSUMED_INPUT",
                "Displaced activity keeps the same waste intensity",
                "Waste generated elsewhere remains in the system; destination and treatment are not modeled.",
            )
        )
        debris = floor * request.demolition_t_m2
        for key, label, value in [
            ("demolition", "One-time demolition material", debris),
            (
                "recovered",
                "Potential recovered demolition material",
                debris * request.recovery_fraction,
            ),
            ("residual", "Residual demolition material", debris * (1 - request.recovery_fraction)),
        ]:
            metrics.append(
                metric(
                    key,
                    label,
                    "t",
                    0,
                    value,
                    "ASSUMED_INPUT",
                    "Gross floor area × material intensity; recovery is a user assumption",
                    "One-time flow, separate from daily waste. No confirmed recycler capacity, hazardous fraction or treatment destination.",
                )
            )
        findings.append(
            {
                "id": "displacement",
                "text": "Demolition creates material waste immediately. Energy and daily waste disappear on-site, but displaced occupants and activities may continue using energy and producing waste elsewhere.",
                "source": "scenario",
            }
        )
    if request.action == "fill":
        volume = water * request.water_depth_m + max(0, area - water) * request.fill_height_m
        metrics.append(
            metric(
                "fill_volume",
                "One-time fill volume",
                "m³",
                0,
                volume,
                "ASSUMED_INPUT",
                "Water area × assumed depth + remaining area × assumed ground raise",
                "No surveyed bathymetry, compaction or earthworks design.",
            )
        )
        metrics.append(
            metric(
                "fill_material",
                "One-time imported fill material",
                "t",
                0,
                volume * request.fill_density_t_m3,
                "ASSUMED_INPUT",
                "Fill volume × assumed bulk density",
                "Material sourcing, truck emissions and contamination require separate records.",
            )
        )
    if water > 0 or request.selection_type == "water":
        metrics.append(
            metric(
                "water_area",
                "Water footprint affected",
                "m²",
                water,
                0,
                "MAPPED_GEOMETRY",
                "Clicked water outline or clipped WorldCover water class",
                "Footprint only, not measured water volume, storage capacity or chemistry.",
            )
        )
        findings.append(
            {
                "id": "water",
                "text": "Changing or filling water can alter habitat, flow, storage and downstream conditions. Water depth, chemistry, drainage connectivity and hydraulic observations are required to quantify those effects.",
                "source": "swmm",
            }
        )
    if inventory.get("roads_count", 0) and request.selection_type in {"road", "area"}:
        findings.append(
            {
                "id": "roads",
                "text": "Road removal changes access and can reroute traffic. Vehicle emissions and emergency access require a traffic-demand and network simulation.",
                "source": "osm",
            }
        )
    complete_sun = bool(weather_samples) and all(
        row.get("ghi_w_m2") is not None for row in weather_samples
    )
    if complete_sun:
        factors = {
            "solar_exposure": canopy * 0.8,
            "roof_solar": inventory["building_area_m2"] * 0.5 * 0.2 * 0.75
            if clears_buildings
            else 0,
        }
        for key, factor in factors.items():
            if factor <= 0:
                continue
            total = sum(row["ghi_w_m2"] for row in weather_samples) * factor / 1000
            tree = key == "solar_exposure"
            metrics.append(
                metric(
                    key,
                    "Potential extra ground sunlight"
                    if tree
                    else "Hypothetical roof-solar opportunity",
                    "kWh",
                    0 if tree else total,
                    total if tree else 0,
                    "ASSUMED_INPUT",
                    "Hourly horizontal radiation × assumed exposed canopy area (80% shade)"
                    if tree
                    else "Mapped roof × 50% usable × 0.2 kWp/m² × PR 0.75 × hourly radiation",
                    "Radiant energy, not temperature or electricity."
                    if tree
                    else "Not an observed PV installation; no roof tilt, shading or structural check.",
                )
            )
            hourly.extend(
                {
                    "valid_at": row["valid_at"],
                    "key": key,
                    "delta_kwh": row["ghi_w_m2"] * factor / 1000 * (1 if tree else -1),
                }
                for row in weather_samples
            )
    complete_air = bool(air_samples) and all(row.get("pm2_5") is not None for row in air_samples)
    if canopy > 0 and complete_air:
        mass = (
            sum(row["pm2_5"] for row in air_samples)
            * canopy
            * request.leaf_area_index
            * request.deposition_velocity_mm_s
            / 1000
            * 3600
            / 1e6
        )
        metrics.append(
            metric(
                "pm_deposition",
                "Gross PM₂.₅ deposition capacity foregone",
                "g",
                mass,
                0,
                "ASSUMED_INPUT",
                "Regional PM₂.₅ × assumed leaf area × deposition velocity × hourly duration",
                "Gross capacity proxy only. No resuspension, stomatal response, street dispersion or air-concentration prediction.",
                [-mass * 2, -mass * 0.5],
            )
        )
    limitations.extend(
        [
            "Screening, not a calibrated causal city model. Sensitivity ranges are not confidence intervals.",
            "Water chemistry, atmospheric oxygen, local pollution concentration, air temperature and landfill hazards are not inferred from imagery.",
            "2021 land cover and OSM are incomplete/datable. Partial-building selection uses proportional floor area, not a structural demolition plan.",
        ]
    )
    return metrics, findings, hourly, limitations
