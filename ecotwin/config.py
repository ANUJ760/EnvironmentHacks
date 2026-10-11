"""Validated configuration. No network or secret discovery on import."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False, hide_input_in_errors=True
    )
    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://ecotwin:ecotwin_local_only@localhost:5432/ecotwin"
    )
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    cors_allowed_origins: str = "http://localhost:3000"
    max_study_area_km2: float = 25
    max_features_per_view: int = 5000
    max_scenario_edits: int = 100
    ecotwin_storage_mode: Literal["local", "s3", "auto"] = "local"
    ecotwin_local_data_dir: Path = Path("data")
    ecotwin_cache_dir: Path = Path("/tmp/ecotwin-cache")
    ecotwin_cache_quota_bytes: int = 8_000_000_000
    ecotwin_allow_local_fallback: bool = False
    ecotwin_s3_bucket: str = ""
    ecotwin_s3_prefix: str = "ecotwin/"
    aws_region: str = "ap-south-1"
    verify_dataset_sha256: bool = True
    ecotwin_queue_backend: Literal["database", "sqs"] = "database"
    ecotwin_sqs_queue_url: str = ""
    worker_poll_seconds: float = Field(default=2, gt=0, le=60)
    worker_lease_seconds: int = 180
    worker_max_attempts: int = Field(default=3, ge=1, le=5)
    max_pending_jobs_per_user: int = Field(default=10, ge=1, le=100)
    simulation_timeout_seconds: int = Field(default=120, ge=1, le=600)
    open_meteo_enabled: bool = True
    open_meteo_base_url: str = "https://api.open-meteo.com"
    openaq_enabled: bool = False
    openaq_base_url: str = "https://api.openaq.org/v3"
    openaq_api_key: SecretStr = SecretStr("")
    http_connect_timeout_seconds: float = 5
    http_read_timeout_seconds: float = 30
    auth_mode: Literal["dev", "cognito"] = "dev"
    dev_jwt_secret: SecretStr = SecretStr("")
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_aws_region: str = "ap-south-1"
    log_level: str = "INFO"
    runoff_model_version: Literal["runoff-coeff-v1"] = "runoff-coeff-v1"
    solar_model_version: Literal["solar-screen-v1"] = "solar-screen-v1"
    enable_uncalibrated_heat_prediction: bool = False

    @model_validator(mode="after")
    def validate_runtime(self) -> "Settings":
        if not self.database_url.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL/psycopg is required; no mutable database fallback")
        if self.auth_mode == "dev" and len(self.dev_jwt_secret.get_secret_value()) < 32:
            raise ValueError("Generate DEV_JWT_SECRET with openssl rand -hex 32")
        if self.auth_mode == "cognito" and not (
            self.cognito_client_id and self.cognito_user_pool_id
        ):
            raise ValueError("Cognito pool and client are required")
        if self.ecotwin_storage_mode != "local" and not self.ecotwin_s3_bucket:
            raise ValueError("S3 bucket required")
        if self.ecotwin_storage_mode == "auto" and not self.ecotwin_allow_local_fallback:
            raise ValueError("auto requires explicit verified local fallback")
        if self.ecotwin_queue_backend == "sqs" and not self.ecotwin_sqs_queue_url:
            raise ValueError("SQS queue URL required")
        if self.openaq_enabled and not self.openaq_api_key.get_secret_value():
            raise ValueError("OPENAQ_CREDENTIAL_REQUIRED")
        if (
            self.open_meteo_base_url != "https://api.open-meteo.com"
            or self.openaq_base_url != "https://api.openaq.org/v3"
        ):
            raise ValueError("Provider URL must match the approved HTTPS origin")
        if self.worker_lease_seconds <= self.simulation_timeout_seconds:
            raise ValueError("Lease must exceed simulation deadline")
        if not (0 < self.max_study_area_km2 <= 25 and 0 < self.max_scenario_edits <= 100):
            raise ValueError("Study area and edit limits exceed supported bounds")
        if self.enable_uncalibrated_heat_prediction or not self.verify_dataset_sha256:
            raise ValueError(
                "Uncalibrated causal heat predictions and unverified data are forbidden"
            )
        if self.app_env == "production":
            if os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_SECRET_ACCESS_KEY"):
                raise ValueError("Production uses IAM task roles, not ambient AWS keys")
            if "*" in self.cors_allowed_origins:
                raise ValueError("Explicit production origins required")
            if (
                self.auth_mode != "cognito"
                or self.ecotwin_storage_mode != "s3"
                or self.ecotwin_queue_backend != "sqs"
                or self.ecotwin_allow_local_fallback
            ):
                raise ValueError("Production requires Cognito, S3, SQS and no fallback")
            if any(
                not origin.startswith("https://") for origin in self.cors_allowed_origins.split(",")
            ):
                raise ValueError("Production CORS origins must use HTTPS")
        return self

    @property
    def issuer(self) -> str:
        return (
            f"https://cognito-idp.{self.cognito_aws_region}.amazonaws.com/{self.cognito_user_pool_id}"
            if self.auth_mode == "cognito"
            else "ecotwin-local"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
