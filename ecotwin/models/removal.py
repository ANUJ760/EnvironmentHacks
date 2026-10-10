"""Research-referenced screening of one hypothetical feature removal.

Geometry and forecast samples are supplied by the API. No LLM enters these
calculations. Ranges describe parameter sensitivity, not confidence intervals.
"""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ecotwin.errors import TwinError


class RemovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    kind: Literal["tree", "park", "building", "road"]
    geometry: dict
    location: tuple[float, float]
    replacement: Literal["unchanged", "grass", "bare", "impervious"] = "grass"
    baseline_cover: Literal["grass", "wood", "impervious"] = "grass"
    soil_group: Literal["A", "B", "C", "D"] = "B"
    forecast_hours: int = Field(default=24, ge=6, le=72)
    rainfall_mm: float | None = Field(default=None, ge=0, le=300)
    crown_diameter_m: float = Field(default=8, ge=1, le=30)
    trunk_diameter_cm: float = Field(default=30, ge=3, le=150)
    shade_fraction: float = Field(default=0.8, ge=0, le=1)
    road_width_m: float = Field(default=6, ge=1, le=30)
    road_length_m: float = Field(default=50, ge=5, le=300)
    roof_usable_fraction: float = Field(default=0.5, ge=0, le=1)


class RemovalMetric(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    key: str
    label: str
    unit: str
    before: float
    after: float
    delta: float
    low: float | None = None
    high: float | None = None
    evidence: str
    method: str
    caveat: str


class RemovalReport(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    model_version: str = "removal-screen-v1"
    computed_at: str
    kind: str
    affected_geometry: dict
    area_m2: float
    geometry_source: str
    within_analysis_area: bool
    weather: dict
    inputs: dict
    metrics: list[RemovalMetric]
    hourly: list[dict]
    findings: list[dict]
    limitations: list[str]
    sources: list[dict]


SOURCES = [
    {
        "id": "nrcs",
        "title": "USDA NRCS Urban Soil Primer, Table 3.3 (TR-55)",
        "url": "https://www.nrcs.usda.gov/sites/default/files/2022-10/urban_soil_primer.pdf",
    },
    {
        "id": "jenkins",
        "title": "Jenkins et al. (2003), national-scale tree biomass equations",
        "url": "https://research.fs.usda.gov/treesearch/6996",
    },
    {
        "id": "ipcc",
        "title": "IPCC 2006, Forest Land, Table 4.3: biomass carbon fraction",
        "url": "https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/4_Volume4/V4_04_Ch4_Forest_Land.pdf",
    },
    {
        "id": "epa",
        "title": "US EPA: trees, shade and evapotranspiration",
        "url": "https://www.epa.gov/heatislands/benefits-trees-and-vegetation",
    },
    {
        "id": "weather",
        "title": "Open-Meteo hourly weather-model forecast",
        "url": "https://open-meteo.com/en/docs",
    },
    {
        "id": "osm",
        "title": "OpenStreetMap geometry; ODbL attribution",
        "url": "https://www.openstreetmap.org/copyright",
    },
]

# NRCS Urban Soil Primer Table 3.3: good lawn, newly graded ground,
# directly connected impervious surfaces. Soil group is explicitly assumed.
CURVE_NUMBERS = {
    "grass": (39, 61, 74, 80),
    "bare": (77, 86, 91, 94),
    "impervious": (98, 98, 98, 98),
}
# All four Jenkins hardwood groups; no species inference from an unlabeled point.
HARDWOOD_GROUPS = [(-2.2094, 2.3867), (-1.9123, 2.3651), (-2.4800, 2.4835), (-2.0127, 2.4342)]


def runoff_depth(rain_mm: float, cn: float) -> float:
    if not math.isfinite(rain_mm) or rain_mm < 0 or not 0 < cn <= 100:
        raise TwinError("INVALID_REQUEST", "Invalid rainfall or curve number", 422)
    retention = 25400 / cn - 254
    initial_loss = 0.2 * retention
    return (
        0.0
        if rain_mm <= initial_loss
        else (rain_mm - initial_loss) ** 2 / (rain_mm + 0.8 * retention)
    )


def rain_events(samples: list[dict]) -> list[float]:
    """Separate forecast storms after six dry hourly intervals (explicit rule)."""
    events, total, dry = [], 0.0, 0
    for sample in samples:
        rain = sample.get("rain_mm")
        if rain is None:
            raise TwinError("INSUFFICIENT_INPUT_DATA", "Missing rainfall samples")
        if rain > 0:
            total += rain
            dry = 0
        else:
            dry += 1
            if dry >= 6 and total:
                events.append(total)
                total = 0.0
    if total:
        events.append(total)
    return events


def carbon_stock(dbh_cm: float, group=2) -> float:
    b0, b1 = HARDWOOD_GROUPS[group]
    # Aboveground dry biomass -> kg C; excludes roots, soil and wood disposal.
    return math.exp(b0 + b1 * math.log(dbh_cm)) * 0.47


def metric(key, label, unit, before, after, evidence, method, caveat, bounds=None):
    return RemovalMetric(
        key=key,
        label=label,
        unit=unit,
        before=before,
        after=after,
        delta=after - before,
        evidence=evidence,
        method=method,
        caveat=caveat,
        low=min(bounds) if bounds else None,
        high=max(bounds) if bounds else None,
    )


def evaluate_removal(request: RemovalRequest, area: float, samples: list[dict]):
    """Return metrics, deterministic explanations and a daylight exposure chart."""
    metrics, findings = [], []
    kind = request.kind
    before_cover = "impervious" if kind in {"road", "building"} else request.baseline_cover
    # Tree removal alone does not change the soil beneath it. Do not substitute
    # a woodland curve number for a single street tree's ground surface.
    if before_cover == "wood":
        # A forest park needs soil/litter survey. The grass proxy is visible.
        before_cover = "grass"
        findings.append(
            {
                "id": "wood_proxy",
                "text": "The park's ground is modeled as good lawn; forest litter and soil conditions require a site survey.",
                "source": "nrcs",
            }
        )
    after_cover = before_cover if request.replacement == "unchanged" else request.replacement
    if kind == "tree":
        canopy = math.pi * (request.crown_diameter_m / 2) ** 2
        metrics.append(
            metric(
                "canopy",
                "Potential canopy removed",
                "m²",
                canopy,
                0,
                "ASSUMED_INPUT",
                "Circular crown from the adjustable crown diameter",
                "Crown diameter is a scenario assumption, not an observed measurement.",
            )
        )
        carbon = carbon_stock(request.trunk_diameter_cm)
        alternatives = [
            carbon_stock(request.trunk_diameter_cm * factor, group)
            for factor in (0.8, 1.2)
            for group in range(4)
        ]
        metrics.append(
            metric(
                "carbon",
                "Aboveground carbon stock removed",
                "kg C",
                carbon,
                0,
                "ASSUMED_INPUT",
                "Jenkins mixed-hardwood biomass × IPCC carbon fraction 0.47",
                "US forest-tree proxy with assumed trunk diameter; not calibrated for this urban tree. Stock removal is not immediate CO₂ emission.",
                [-value for value in alternatives],
            )
        )
        findings.extend(
            [
                {
                    "id": "shade_loss",
                    "text": "Removing the crown reduces shade and evapotranspiration. The effect on local air temperature is not quantified without a calibrated microclimate model.",
                    "source": "epa",
                },
                {
                    "id": "carbon_fate",
                    "text": "Carbon held in the aboveground tree leaves the standing stock. Whether and when it becomes emissions depends on reuse, decay or burning of the wood.",
                    "source": "ipcc",
                },
                {
                    "id": "interception",
                    "text": "Rainfall interception by leaves is lost. The ground-runoff model below does not quantify that loss or claim that unchanged runoff means no hydrological effect.",
                    "source": "epa",
                },
            ]
        )
    else:
        metrics.append(
            metric(
                "footprint",
                "Feature footprint removed",
                "m²",
                area,
                0,
                "ASSUMED_INPUT" if kind == "road" else "MAPPED_GEOMETRY",
                "Mapped centerline segment buffered by assumed width in the city's metric CRS"
                if kind == "road"
                else "Area in the city's projected metric CRS",
                "Road width and segment length are scenario assumptions, not surveyed measurements."
                if kind == "road"
                else "OSM footprints may be dated or incomplete; map tiles can contain simplified outlines.",
            )
        )
        findings.append(
            {
                "id": "replacement",
                "text": f"The removal is modeled with {request.replacement} ground afterward. Environmental outcomes depend on this replacement, not removal alone.",
                "source": "nrcs",
            }
        )
        if kind == "building":
            findings.append(
                {
                    "id": "demolition",
                    "text": "Demolition emissions, debris, occupancy displacement and changes in heating demand need material and operational records; they are not estimated from a footprint.",
                    "source": "osm",
                }
            )
        elif kind == "park":
            findings.append(
                {
                    "id": "habitat",
                    "text": "Removing the mapped park changes its use and potentially its habitat. Net vegetation benefits depend on the replacement; replanting can retain some functions. Species counts and a numerical temperature change cannot be inferred from a park outline.",
                    "source": "epa",
                }
            )
        elif kind == "road":
            findings.append(
                {
                    "id": "traffic",
                    "text": "Removing this road segment changes access. Traffic rerouting, vehicle emissions and emergency-access impacts require a transport network model and traffic data.",
                    "source": "osm",
                }
            )

    complete_rain = bool(samples) and all(s.get("rain_mm") is not None for s in samples)
    events = (
        [request.rainfall_mm]
        if request.rainfall_mm is not None
        else rain_events(samples)
        if complete_rain
        else None
    )
    if events is not None:
        soil = "ABCD".index(request.soil_group)
        before = (
            math.fsum(runoff_depth(rain, CURVE_NUMBERS[before_cover][soil]) for rain in events)
            * area
            / 1000
        )
        after = (
            math.fsum(runoff_depth(rain, CURVE_NUMBERS[after_cover][soil]) for rain in events)
            * area
            / 1000
        )
        sensitivity = [
            math.fsum(
                runoff_depth(rain, CURVE_NUMBERS[after_cover][group])
                - runoff_depth(rain, CURVE_NUMBERS[before_cover][group])
                for rain in events
            )
            * area
            / 1000
            for group in range(4)
        ]
        metrics.append(
            metric(
                "runoff",
                "Surface runoff change",
                "m³",
                before,
                after,
                "SCREENING_ESTIMATE",
                "NRCS event curve-number equation, Ia = 0.2S",
                "Soil group, good-lawn condition and directly connected impervious ground are assumptions. Range spans soil groups A–D, not a confidence interval; no flood-depth or drainage prediction.",
                sensitivity,
            )
        )
        findings.append(
            {
                "id": "runoff",
                "text": "The runoff estimate compares the existing surface with the chosen replacement using rainfall and an assumed soil group. It does not predict flood depth or drainage capacity.",
                "source": "nrcs",
            }
        )
    else:
        findings.append(
            {
                "id": "rain_missing",
                "text": "Runoff is unavailable because hourly rainfall data are incomplete. A user-defined design storm can be tested instead.",
                "source": "weather",
            }
        )

    hourly = []
    complete_sun = bool(samples) and all(s.get("ghi_w_m2") is not None for s in samples)
    if complete_sun:
        if kind == "tree":
            area_factor = math.pi * (request.crown_diameter_m / 2) ** 2 * request.shade_fraction
            exposure = math.fsum(s["ghi_w_m2"] for s in samples) * area_factor / 1000
            metrics.append(
                metric(
                    "solar_exposure",
                    "Additional potential ground solar exposure",
                    "kWh",
                    0,
                    exposure,
                    "ASSUMED_INPUT",
                    "Hourly horizontal GHI × assumed crown area × shade fraction",
                    "Solar radiant energy, not cooling electricity or a temperature change. Assumes no overlapping shade and the selected foliage fraction.",
                )
            )
        elif kind == "building":
            area_factor = area * request.roof_usable_fraction * 0.2 * 0.75
            potential = math.fsum(s["ghi_w_m2"] for s in samples) * area_factor / 1000
            metrics.append(
                metric(
                    "roof_solar",
                    "Roof solar opportunity removed",
                    "kWh",
                    potential,
                    0,
                    "ASSUMED_INPUT",
                    "Horizontal unshaded PV: usable roof area × 0.2 kWp/m² × GHI × PR 0.75",
                    "Future screening potential under assumed roof availability, not loss of an observed installation; no shading or structural assessment.",
                )
            )
        else:
            area_factor = 0
        if kind in {"tree", "building"}:
            hourly = [
                {
                    "valid_at": s["valid_at"],
                    "ghi_w_m2": s["ghi_w_m2"],
                    "rain_mm": s.get("rain_mm"),
                    "delta_kwh": s["ghi_w_m2"] * area_factor / 1000 * (1 if kind == "tree" else -1),
                }
                for s in samples
            ]
    return metrics, findings, hourly
