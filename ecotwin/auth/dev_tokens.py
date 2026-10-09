from datetime import UTC, datetime, timedelta

import jwt

from ecotwin.errors import TwinError


def issue_token(settings, subject: str, minutes: int = 60):
    if (
        settings.auth_mode != "dev"
        or settings.app_env == "production"
        or not 1 <= minutes <= 60
        or not subject
    ):
        raise TwinError(
            "AUTH_CONFIGURATION_ERROR",
            "Local tokens require development mode and a 1–60 minute lifetime",
        )
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "iss": "ecotwin-local",
            "aud": "ecotwin-local",
            "iat": now,
            "exp": now + timedelta(minutes=minutes),
            "token_use": "access",
        },
        settings.dev_jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
