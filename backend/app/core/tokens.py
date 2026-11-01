from datetime import datetime, timedelta, timezone
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
    return secret


def validate_jwt_settings(settings: Settings) -> None:
    _secret(settings)


def create_access_token(subject: UUID, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, _secret(settings), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> UUID:
    payload = jwt.decode(
        token,
        _secret(settings),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub"]},
    )
    return UUID(payload["sub"])
