from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from uuid import UUID

import jwt

from app.core.config import Settings

JWT_ALGORITHM = "HS256"
_MIN_SECRET_BYTES = 32


def _secret(settings: Settings) -> str:
    if settings.jwt_secret_key is None:
        raise RuntimeError("JWT_SECRET_KEY must be configured for authentication.")
    secret = settings.jwt_secret_key.get_secret_value()
    if len(secret.encode("utf-8")) < _MIN_SECRET_BYTES:
        raise RuntimeError("JWT_SECRET_KEY must be at least 32 bytes.")
    if any(
        marker in secret.strip().lower()
        for marker in (
            "replace-with",
            "your-secret",
            "change-me",
            "changeme",
            "placeholder",
        )
    ):
        raise RuntimeError("JWT_SECRET_KEY must not use a placeholder value.")
    return secret


def validate_jwt_settings(settings: Settings) -> None:
    _secret(settings)


@dataclass(frozen=True)
class AccessTokenClaims:
    subject: UUID
    rate_limit_identity: str | None
    is_demo: bool


def create_access_token(
    subject: UUID,
    settings: Settings,
    *,
    rate_limit_identity: str | None = None,
    is_demo: bool = False,
    expires_minutes: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=expires_minutes or settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": expires_at,
    }
    if rate_limit_identity is not None:
        payload["rate_limit_identity"] = rate_limit_identity
    if is_demo:
        payload["is_demo"] = True
    return jwt.encode(payload, _secret(settings), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> UUID:
    return decode_access_token_claims(token, settings).subject


def decode_access_token_claims(token: str, settings: Settings) -> AccessTokenClaims:
    payload = jwt.decode(
        token,
        _secret(settings),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub"]},
    )
    identity = payload.get("rate_limit_identity")
    return AccessTokenClaims(
        subject=UUID(payload["sub"]),
        rate_limit_identity=identity if isinstance(identity, str) and identity else None,
        is_demo=payload.get("is_demo") is True,
    )


def decode_rate_limit_identity(token: str, settings: Settings) -> str | None:
    return decode_access_token_claims(token, settings).rate_limit_identity
