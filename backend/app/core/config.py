from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import EMBEDDING_DIMENSION

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: SecretStr | None = None
    app_environment: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = "INFO"
    jwt_secret_key: SecretStr | None = None
    jwt_access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimension: int = Field(default=EMBEDDING_DIMENSION, ge=1)

    @model_validator(mode="after")
    def embedding_dimension_matches_schema(self) -> "Settings":
        if self.gemini_embedding_dimension != EMBEDDING_DIMENSION:
            raise ValueError(
                "GEMINI_EMBEDDING_DIMENSION must match the database vector dimension "
                f"({EMBEDDING_DIMENSION}); change it only with a reviewed migration."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
