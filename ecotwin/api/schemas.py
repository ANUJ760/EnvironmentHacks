from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ecotwin.models.landcover import CLASS_CODES

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class Reclassify(StrictModel):
    edit_type: Literal['LAND_COVER_RECLASSIFY']
    polygon_geojson: dict[str,Any]
    from_class_code: int
    to_class_code: int
    fraction: float = Field(gt=0,le=1)
    @model_validator(mode='after')
    def classes(self):
        if self.from_class_code not in CLASS_CODES or self.to_class_code not in CLASS_CODES or self.from_class_code==self.to_class_code:
            raise ValueError('Source and destination must be distinct WorldCover classes')
        return self

class SolarInstall(StrictModel):
    edit_type: Literal['SOLAR_PV_INSTALL']
    footprint_geojson: dict[str,Any]
    installed_kwp: float = Field(gt=0,le=1e6)
    performance_ratio: float = Field(default=0.75,gt=0,le=1)
    panel_tilt_deg: float = Field(default=0,ge=0,le=90)
    panel_azimuth_deg: float = Field(default=0,ge=-180,le=180)

class WasteOverride(StrictModel):
    edit_type: Literal['WASTE_ROUTING_OVERRIDE']
    stream_category: str
    origin_id: str
    facility_id: str
    allocation_fraction: float = Field(ge=0,le=1)

Edit=Annotated[Reclassify|SolarInstall|WasteOverride,Field(discriminator='edit_type')]

class ScenarioCreate(StrictModel):
    city_id: UUID
    snapshot_id: UUID
    name: str = Field(min_length=1,max_length=200)

class EditsReplace(StrictModel):
    edits: list[Edit] = Field(max_length=100)

class SimulationRequest(StrictModel):
    requested_models: list[str] = Field(min_length=1,max_length=10)
    event_rainfall_mm: float | None = Field(default=None,ge=0,le=10000)
    start_at: datetime | None = None
    end_at: datetime | None = None
    optimize_waste: bool = False
    report_schema_version: Literal[1] = 1
    @model_validator(mode='after')
    def period(self):
        if len(set(self.requested_models)) != len(self.requested_models):
            raise ValueError('Duplicate requested models')
        if (self.start_at is None)!=(self.end_at is None):
            raise ValueError('Both start_at and end_at are required')
        if self.start_at and (not self.start_at.tzinfo or not self.end_at.tzinfo or self.end_at <= self.start_at):
            raise ValueError('Period must be increasing timezone-aware timestamps')
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
    edits: list[dict[str,Any]]

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
    model_versions: dict[str,str]
    metrics: list[dict[str,Any]]
    warnings: list[str]
    evidence: dict[str,Any]
    created_at: datetime
