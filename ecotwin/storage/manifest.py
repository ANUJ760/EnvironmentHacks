from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    city_id: str
    source_url: str
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    byte_size: int = Field(ge=0)
    media_type: str
    crs: str
    coverage: dict[str, Any] | None
    native_units: dict[str, str]
    normalized_units: dict[str, str]
    captured_at: datetime
    source_license: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    processing_version: str
    upstream_revision: str
