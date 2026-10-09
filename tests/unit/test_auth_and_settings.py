from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from ecotwin.auth.dev_tokens import issue_token
from ecotwin.auth.jwt import verify_token
from ecotwin.config import Settings
from ecotwin.errors import TwinError


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": "sqlite:///local.db"},
        {"dev_jwt_secret": "short"},
        {"auth_mode": "cognito"},
        {"ecotwin_storage_mode": "s3"},
        {"ecotwin_storage_mode": "auto", "ecotwin_s3_bucket": "bucket"},
        {"ecotwin_queue_backend": "sqs"},
        {"openaq_enabled": True},
        {"open_meteo_base_url": "https://evil.example"},
        {"worker_lease_seconds": 1},
        {"max_study_area_km2": 26},
        {"enable_uncalibrated_heat_prediction": True},
        {"verify_dataset_sha256": False},
    ],
)
def test_invalid_runtime_combinations(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)


@pytest.mark.parametrize(
    "case", ["valid", "id-token", "wrong-client", "expired", "wrong-issuer", "malformed"]
)
def test_cognito_access_token_checks(monkeypatch, case):
    import ecotwin.auth.jwt as module

    settings = Settings(
        _env_file=None, auth_mode="cognito", cognito_client_id="client", cognito_user_pool_id="pool"
    )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())
    )
    monkeypatch.setattr(module, "jwks_client", lambda issuer: client)
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "alice",
        "iss": settings.issuer,
        "iat": now,
        "exp": now + timedelta(hours=1),
        "client_id": "client",
        "token_use": "access",
    }
    if case == "id-token":
        claims["token_use"] = "id"
    if case == "wrong-client":
        claims["client_id"] = "other"
    if case == "expired":
        claims["exp"] = now - timedelta(seconds=10)
    if case == "wrong-issuer":
        claims["iss"] = "https://wrong.example"
    token = jwt.encode(claims, key, algorithm="RS256") if case != "malformed" else "broken"
    if case == "valid":
        assert verify_token(token, settings) == "alice"
    else:
        with pytest.raises(TwinError):
            verify_token(token, settings)


def test_token_issue_constraints():
    settings = Settings(_env_file=None)
    for minutes in [0, 61]:
        with pytest.raises(TwinError):
            issue_token(settings, "alice", minutes)
    with pytest.raises(TwinError):
        issue_token(settings, "", 10)


def test_production_guards(monkeypatch):
    values = {
        "app_env": "production",
        "auth_mode": "cognito",
        "cognito_client_id": "client",
        "cognito_user_pool_id": "pool",
        "ecotwin_storage_mode": "s3",
        "ecotwin_s3_bucket": "bucket",
        "ecotwin_queue_backend": "sqs",
        "ecotwin_sqs_queue_url": "https://sqs.region.amazonaws.com/account/queue",
        "cors_allowed_origins": "https://app.example.org",
    }
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert Settings(_env_file=None, **values).issuer.endswith("/pool")
    for overrides in [
        {"cors_allowed_origins": "http://app.example.org"},
        {"cors_allowed_origins": "https://*"},
        {"ecotwin_allow_local_fallback": True},
    ]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{**values, **overrides})
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "never-real-test-key")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)
