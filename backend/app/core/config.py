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
    test_database_url: SecretStr | None = None
    app_environment: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = "INFO"
    jwt_secret_key: SecretStr | None = None
    jwt_access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)
    upload_directory: Path = ROOT_DIR / ".local" / "uploads"
    max_upload_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=200, gt=0)
    chunk_size: int = Field(default=900, ge=100, le=4000)
    chunk_overlap: int = Field(default=150, ge=0, le=1000)
    gemini_api_key: SecretStr | None = None
    gemini_embedding_model: str = "gemini-embedding-2"
    gemini_embedding_dimension: int = Field(default=EMBEDDING_DIMENSION, ge=1)
    embedding_batch_size: int = Field(default=16, ge=1, le=100)
    embedding_max_attempts: int = Field(default=5, ge=1, le=10)
    embedding_backoff_base_seconds: float = Field(default=0.5, ge=0, le=30)
    embedding_backoff_max_seconds: float = Field(default=8, ge=0, le=120)
    embedding_batch_delay_seconds: float = Field(default=0.1, ge=0, le=10)
    search_max_top_k: int = Field(default=20, ge=1, le=100)
    search_min_similarity: float = Field(default=0.0, ge=-1, le=1)
    gemini_chat_model: str = "gemini-3.8-flash"
    chat_max_output_tokens: int = Field(default=2048, ge=1, le=65536)
    chat_timeout_seconds: int = Field(default=30, ge=1, le=300)
    chat_max_question_chars: int = Field(default=2000, ge=1, le=4000)
    chat_max_context_chunks: int = Field(default=5, ge=1, le=20)
    chat_max_context_chars: int = Field(default=12000, ge=256, le=100000)
    chat_max_attempts: int = Field(default=3, ge=1, le=5)
    chat_backoff_base_seconds: float = Field(default=0.5, ge=0, le=30)
    chat_backoff_max_seconds: float = Field(default=4, ge=0, le=120)

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

    @model_validator(mode="after")
    def chat_backoff_max_is_not_smaller_than_base(self) -> "Settings":
        if self.chat_backoff_max_seconds < self.chat_backoff_base_seconds:
            raise ValueError(
                "CHAT_BACKOFF_MAX_SECONDS must be at least "
                "CHAT_BACKOFF_BASE_SECONDS."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
