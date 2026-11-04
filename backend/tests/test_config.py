import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def test_settings_accept_python_312_default_embedding_configuration() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://example.invalid/database",
        APP_ENV="test",
        GEMINI_EMBEDDING_MODEL="test-embedding-model",
        GEMINI_EMBEDDING_DIMENSION=768,
    )

    assert settings.app_environment == "test"
    assert settings.gemini_embedding_model == "test-embedding-model"
    assert settings.gemini_embedding_dimension == 768
    assert settings.search_max_top_k == 20
    assert settings.search_min_similarity == 0.0
    assert settings.chat_generation_deadline_seconds == 30
    assert settings.chat_attempt_timeout_seconds == 15
    assert settings.gemini_chat_fallback_model is None
    assert isinstance(settings.database_url, SecretStr)
    assert "example.invalid" not in repr(settings.database_url)


def test_settings_accept_chat_deadline_and_optional_fallback_model() -> None:
    settings = Settings(
        _env_file=None,
        CHAT_GENERATION_DEADLINE_SECONDS=24,
        CHAT_ATTEMPT_TIMEOUT_SECONDS=12,
        GEMINI_CHAT_FALLBACK_MODEL="confirmed-fallback-model",
    )

    assert settings.chat_generation_deadline_seconds == 24
    assert settings.chat_attempt_timeout_seconds == 12
    assert settings.gemini_chat_fallback_model == "confirmed-fallback-model"


def test_settings_reject_dimension_that_does_not_match_schema() -> None:
    with pytest.raises(ValidationError, match="must match the database vector dimension"):
        Settings(_env_file=None, gemini_embedding_dimension=512)
