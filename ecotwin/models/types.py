from enum import StrEnum
from typing import Any
from pydantic import BaseModel

class EvidenceClass(StrEnum):
    OBSERVED='OBSERVED'
    DETERMINISTIC_CALCULATION='DETERMINISTIC_CALCULATION'
    SCREENING_ESTIMATE='SCREENING_ESTIMATE'
    CALIBRATED_PREDICTION='CALIBRATED_PREDICTION'
    ASSUMED_INPUT='ASSUMED_INPUT'
    UNAVAILABLE='UNAVAILABLE'

class Metric(BaseModel):
    name: str
    baseline_value: float | None
    scenario_value: float | None
    absolute_delta: float | None
    percentage_delta: float | None
    unit: str
    spatial_scope: str
    start_at: str | None = None
    end_at: str | None = None
    evidence_class: EvidenceClass
    model_id: str
    model_version: str
    source_revision_ids: list[str]
    parameter_digest: str
    confidence_interval: dict[str,Any] | None = None
    limitations: list[str]
