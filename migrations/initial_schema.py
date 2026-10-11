from datetime import datetime
from decimal import Decimal
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from migrations.initial_base import Base, Identity


class City(Identity, Base):
    __tablename__ = "cities"
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    boundary = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)
    analysis_srid: Mapped[int]
    timezone: Mapped[str]
    status: Mapped[str] = mapped_column(default="ACTIVE")
    __table_args__ = (
        CheckConstraint(
            "ST_IsValid(boundary) AND NOT ST_IsEmpty(boundary)", name="valid_city_boundary"
        ),
    )


class DatasetRevision(Identity, Base):
    __tablename__ = "dataset_revisions"
    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"))
    kind: Mapped[str]
    provider: Mapped[str]
    source_url: Mapped[str]
    object_key: Mapped[str]
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    source_license: Mapped[str]
    attribution: Mapped[str]
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    native_crs: Mapped[str]
    resolution_m: Mapped[float | None]
    coverage = mapped_column(Geometry("GEOMETRY", srid=4326))
    status: Mapped[str] = mapped_column(default="READY")
    quality_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (
        UniqueConstraint("city_id", "kind", "sha256"),
        CheckConstraint("byte_size >= 0 AND sha256 ~ '^[a-f0-9]{64}$'", name="dataset_integrity"),
        CheckConstraint(
            "status IN ('DOWNLOADING','VALIDATING','READY','FAILED')", name="revision_state"
        ),
    )


class ImportRun(Identity, Base):
    __tablename__ = "import_runs"
    dataset_revision_id: Mapped[UUID | None] = mapped_column(ForeignKey("dataset_revisions.id"))
    status: Mapped[str]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_read: Mapped[int] = mapped_column(default=0)
    rows_imported: Mapped[int] = mapped_column(default=0)
    rows_rejected: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None]
    details_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class GeoFeature(Identity, Base):
    __tablename__ = "geo_features"
    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"))
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_revisions.id"))
    provider_feature_id: Mapped[str]
    category: Mapped[str]
    tags: Mapped[dict] = mapped_column(JSONB)
    geom = mapped_column(Geometry("GEOMETRY", srid=4326), nullable=False)
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    length_m: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("revision_id", "provider_feature_id", "category"),
        Index("ix_feature_city_category", "city_id", "category"),
        CheckConstraint("ST_IsValid(geom)", name="valid_feature"),
    )


class LandcoverCell(Identity, Base):
    __tablename__ = "landcover_cells"
    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"))
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_revisions.id"))
    cell_x: Mapped[int]
    cell_y: Mapped[int]
    class_code: Mapped[int]
    area_m2: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    geom = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    __table_args__ = (
        UniqueConstraint("revision_id", "cell_x", "cell_y"),
        CheckConstraint(
            "area_m2 > 0 AND class_code IN (10,20,30,40,50,60,70,80,90,95,100)",
            name="valid_cover_cell",
        ),
        CheckConstraint("ST_IsValid(geom)", name="valid_cell_geometry"),
    )


class WeatherHour(Identity, Base):
    __tablename__ = "weather_hours"
    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"))
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_revisions.id"))
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    temperature_c: Mapped[float | None]
    rain_mm: Mapped[float | None]
    humidity_pct: Mapped[float | None]
    wind_mps: Mapped[float | None]
    ghi_w_m2: Mapped[float | None]
    model_name: Mapped[str]
    source_lat: Mapped[float]
    source_lon: Mapped[float]
    __table_args__ = (
        UniqueConstraint("city_id", "revision_id", "valid_at"),
        CheckConstraint(
            "rain_mm >= 0 AND ghi_w_m2 >= 0 AND humidity_pct BETWEEN 0 AND 100 AND wind_mps >= 0",
            name="weather_ranges",
        ),
    )


class AirStation(Identity, Base):
    __tablename__ = "air_stations"
    provider_station_id: Mapped[str]
    source: Mapped[str]
    location = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    name: Mapped[str]
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB)
    __table_args__ = (UniqueConstraint("source", "provider_station_id"),)


class AirObservation(Identity, Base):
    __tablename__ = "air_observations"
    station_id: Mapped[UUID] = mapped_column(ForeignKey("air_stations.id"))
    sensor_id: Mapped[str]
    parameter: Mapped[str]
    value: Mapped[float]
    unit: Mapped[str]
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_url: Mapped[str]
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_revisions.id"))
    __table_args__ = (UniqueConstraint("station_id", "sensor_id", "measured_at", "parameter"),)


class FacilityProfile(Identity, Base):
    __tablename__ = "facility_profiles"
    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"))
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_revisions.id"))
    facility_kind: Mapped[str]
    geom = mapped_column(Geometry("POINT", srid=4326))
    capacity_tpd: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    accepted_categories: Mapped[list] = mapped_column(JSONB)
    efficiency_profile: Mapped[dict] = mapped_column(JSONB)
    parameter_source: Mapped[str]
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("capacity_tpd >= 0", name="facility_capacity"),)


class CitySnapshot(Identity, Base):
    __tablename__ = "city_snapshots"
    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"))
    dataset_revision_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid))
    composite_input_sha256: Mapped[str] = mapped_column(String(64))
    model_config_sha256: Mapped[str] = mapped_column(String(64))
    baseline_summary: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(default="PUBLISHED")


class UserAccount(Identity, Base):
    __tablename__ = "user_accounts"
    identity_issuer: Mapped[str]
    identity_subject: Mapped[str]
    __table_args__ = (UniqueConstraint("identity_issuer", "identity_subject"),)


class Scenario(Identity, Base):
    __tablename__ = "scenarios"
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("city_snapshots.id"))
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("user_accounts.id"), index=True)
    name: Mapped[str]
    status: Mapped[str] = mapped_column(default="DRAFT")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    scenario_sha256: Mapped[str] = mapped_column(String(64))
    __table_args__ = (CheckConstraint("version > 0", name="scenario_version"),)


class ScenarioEdit(Identity, Base):
    __tablename__ = "scenario_edits"
    scenario_id: Mapped[UUID] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"))
    ordinal: Mapped[int]
    edit_type: Mapped[str]
    target = mapped_column(Geometry("GEOMETRY", srid=4326))
    parameters: Mapped[dict] = mapped_column(JSONB)
    sha256: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint("scenario_id", "ordinal"),
        CheckConstraint(
            "edit_type IN ('LAND_COVER_RECLASSIFY','SOLAR_PV_INSTALL','WASTE_ROUTING_OVERRIDE')",
            name="edit_kind",
        ),
    )


class SimulationJob(Identity, Base):
    __tablename__ = "simulation_jobs"
    scenario_id: Mapped[UUID] = mapped_column(ForeignKey("scenarios.id"))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("user_accounts.id"))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_digest: Mapped[str] = mapped_column(String(64))
    frozen_input: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(default="QUEUED")
    attempt: Mapped[int] = mapped_column(default=0)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None]
    progress_pct: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_id: Mapped[UUID | None] = mapped_column(Uuid)
    __table_args__ = (
        UniqueConstraint("requested_by", "idempotency_key"),
        Index("ix_job_queue", "state", "not_before"),
        CheckConstraint(
            "state IN ('QUEUED','RUNNING','RETRY_WAIT','CANCEL_REQUESTED','SUCCEEDED','FAILED','CANCELED') AND attempt >= 0 AND progress_pct BETWEEN 0 AND 100",
            name="valid_job_state",
        ),
    )


class SimulationResult(Identity, Base):
    __tablename__ = "simulation_results"
    job_id: Mapped[UUID] = mapped_column(ForeignKey("simulation_jobs.id"), unique=True)
    report_schema_version: Mapped[int] = mapped_column(default=1)
    input_digest: Mapped[str] = mapped_column(String(64))
    output_digest: Mapped[str] = mapped_column(String(64))
    model_versions: Mapped[dict] = mapped_column(JSONB)
    metrics: Mapped[list] = mapped_column(JSONB)
    warnings: Mapped[list] = mapped_column(JSONB)
    evidence: Mapped[dict] = mapped_column(JSONB)
    object_key: Mapped[str | None]


class AuditEvent(Identity, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
    action: Mapped[str]
    resource_id: Mapped[UUID]
    details: Mapped[dict] = mapped_column(JSONB)
