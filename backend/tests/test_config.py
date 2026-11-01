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
    assert isinstance(settings.database_url, SecretStr)
    assert "example.invalid" not in repr(settings.database_url)


def test_settings_reject_dimension_that_does_not_match_schema() -> None:
    with pytest.raises(ValidationError, match="must match the database vector dimension"):
        Settings(_env_file=None, gemini_embedding_dimension=512)
