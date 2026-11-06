from fastapi import HTTPException, status

from app.core.config import Settings


def require_ai_features_enabled(settings: Settings) -> None:
    if not settings.ai_features_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI features are temporarily unavailable. Please try again later.",
        )
