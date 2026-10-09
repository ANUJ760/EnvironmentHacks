from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ecotwin.models.landcover import CLASS_CODES
from ecotwin.models.types import Metric


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Reclassify(StrictModel):
    edit_type: Literal["LAND_COVER_RECLASSIFY"]
    polygon_geojson: dict[str, Any]
    from_class_code: int
    to_class_code: int
    fraction: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def classes(self):
        if (
            self.from_class_code not in CLASS_CODES
            or self.to_class_code not in CLASS_CODES
            or self.from_class_code == self.to_class_code
        ):
            raise ValueError("Source and destination must be distinct WorldCover classes")
        return self


class SolarInstall(StrictModel):
    edit_type: Literal["SOLAR_PV_INSTALL"]
    footprint_geojson: dict[str, Any]
    installed_kwp: float = Field(gt=0, le=1e6)
    performance_ratio: float = Field(default=0.75, gt=0, le=1)
    panel_tilt_deg: float = Field(default=0, ge=0, le=90)
    panel_azimuth_deg: float = Field(default=0, ge=-180, le=180)


class WasteOverride(StrictModel):
    edit_type: Literal["WASTE_ROUTING_OVERRIDE"]
    stream_category: str
    origin_id: str
    facility_id: str
    allocation_fraction: float = Field(ge=0, le=1)


Edit = Annotated[Reclassify | SolarInstall | WasteOverride, Field(discriminator="edit_type")]


class ScenarioCreate(StrictModel):
    city_id: UUID
    snapshot_id: UUID
    name: str = Field(min_length=1, max_length=200)


class EditsReplace(StrictModel):
    edits: list[Edit] = Field(max_length=100)


class SimulationRequest(StrictModel):
    requested_models: list[str] = Field(min_length=1, max_length=10)
    event_rainfall_mm: float | None = Field(default=None, ge=0, le=10000)
    start_at: datetime | None = None
    end_at: datetime | None = None
    optimize_waste: bool = False
    report_schema_version: Literal[1] = 1

    @model_validator(mode="after")
    def period(self):
        if len(set(self.requested_models)) != len(self.requested_models):
            raise ValueError("Duplicate requested models")
        if (self.start_at is None) != (self.end_at is None):
            raise ValueError("Both start_at and end_at are required")
        if self.start_at and (
            not self.start_at.tzinfo or not self.end_at.tzinfo or self.end_at <= self.start_at
        ):
            raise ValueError("Period must be increasing timezone-aware timestamps")
        return self


class JobAccepted(BaseModel):
    job_id: UUID
    status_url: str


class ScenarioView(BaseModel):
    id: UUID
    snapshot_id: UUID
    name: str
    version: int
    scenario_sha256: str
    edits: list[dict[str, Any]]


class JobView(BaseModel):
    id: UUID
    state: str
    attempt: int
    progress_pct: int
    error_code: str | None
    error_message: str | None
    result_id: UUID | None


class ResultView(BaseModel):
    id: UUID
    job_id: UUID
    report_schema_version: int
    input_digest: str
    output_digest: str
    model_versions: dict[str, str]
    metrics: list[Metric]
    warnings: list[str]
    evidence: dict[str, Any]
    created_at: datetime


class CityView(BaseModel):
    id: UUID
    slug: str
    display_name: str
    boundary: dict[str, Any]
    analysis_srid: int
    timezone: str
    status: str
    active_snapshot_id: UUID | None
    capabilities: list[str]


class GeoFeatureView(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: UUID
    geometry: dict[str, Any]
    properties: dict[str, Any]


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoFeatureView]
    next_cursor: UUID | None


class DatasetView(BaseModel):
    id: UUID
    kind: str
    provider: str
    source_url: str
    sha256: str
    byte_size: int
    source_license: str
    attribution: str
    acquired_at: datetime
    coverage: dict[str, Any] | None
    status: str
    quality: dict[str, Any]


class LandcoverView(BaseModel):
    reference_year: Literal[2021] = 2021
    class_areas_m2: dict[int, float]
    class_percentages: dict[int, float]
    covered_area_m2: float
    city_area_m2: float
    source_revision_ids: list[UUID]
    limitations: list[str]


class WeatherReading(BaseModel):
    valid_at: datetime
    issued_at: datetime
    temperature_c: float | None
    rain_mm: float | None
    humidity_pct: float | None
    wind_mps: float | None
    ghi_w_m2: float | None
    model_name: str
    source_lat: float
    source_lon: float


class WeatherView(BaseModel):
    evidence_class: str = "UNAVAILABLE"
    status: str = "AVAILABLE"
    reason_code: str | None = None
    spatial_scope: str = "coarse_forecast_grid"
    age_hours: float | None = None
    stale: bool = False
    current: bool = False
    series: list[WeatherReading]


class AirReading(BaseModel):
    station_id: UUID
    station_name: str
    location: dict[str, Any]
    parameter: str
    value: float
    unit: str
    measured_at: datetime
    source_url: str
    revision_id: UUID
    stale: bool
    distance_from_city_centroid_m: float


class AirView(BaseModel):
    evidence_class: str
    reason_code: str | None
    spatial_scope: Literal["station_only"]
    readings: list[AirReading]
