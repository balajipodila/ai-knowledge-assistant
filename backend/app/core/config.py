from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
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
    upload_directory: Path = ROOT_DIR / ".local" / "uploads"
    max_upload_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=200, gt=0)
    chunk_size: int = Field(default=900, ge=100, le=4000)
    chunk_overlap: int = Field(default=150, ge=0, le=1000)
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimension: int = Field(default=EMBEDDING_DIMENSION, ge=1)

    @field_validator("upload_directory", mode="before")
    @classmethod
    def resolve_upload_directory(cls, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else ROOT_DIR / path

    @model_validator(mode="after")
    def embedding_dimension_matches_schema(self) -> "Settings":
        if self.gemini_embedding_dimension != EMBEDDING_DIMENSION:
            raise ValueError(
                "GEMINI_EMBEDDING_DIMENSION must match the database vector dimension "
                f"({EMBEDDING_DIMENSION}); change it only with a reviewed migration."
            )
        return self

    @model_validator(mode="after")
    def chunk_overlap_is_smaller_than_chunk_size(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
