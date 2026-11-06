from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

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
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    trusted_proxy_cidrs: list[str] = Field(default_factory=list)
    app_environment: str = Field(default="development", validation_alias="APP_ENV")
    signup_enabled: bool = True
    ai_features_enabled: bool = True
    demo_mode: bool = False
    demo_user_email: str = "demo@example.com"
    demo_document_id: str | None = None
    demo_session_expire_minutes: int = Field(default=15, gt=0, le=60)
    demo_max_documents_per_user: int = Field(default=3, ge=1, le=100000)
    demo_max_pdf_pages: int = Field(default=50, ge=1, le=200)
    demo_max_users: int = Field(default=100, ge=1, le=100000000)
    demo_max_documents: int = Field(default=300, ge=1, le=100000000)
    demo_session_requests_per_minute: int = Field(default=120, ge=1, le=100000)
    demo_session_requests_per_day: int = Field(default=2000, ge=1, le=10000000)
    demo_chat_requests_per_minute: int = Field(default=5, ge=1, le=10000)
    demo_chat_requests_per_day: int = Field(default=100, ge=1, le=1000000)
    demo_search_requests_per_minute: int = Field(default=20, ge=1, le=10000)
    demo_search_requests_per_day: int = Field(default=500, ge=1, le=1000000)
    demo_chat_global_requests_per_day: int = Field(default=1000, ge=1, le=10000000)
    demo_search_global_requests_per_day: int = Field(default=5000, ge=1, le=10000000)
    log_level: str = "INFO"
    jwt_secret_key: SecretStr | None = None
    jwt_access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)
    file_storage_backend: Literal["none", "local", "s3"] = "local"
    upload_directory: Path = ROOT_DIR / ".local" / "uploads"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "auto"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    s3_read_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    s3_max_attempts: int = Field(default=3, ge=1, le=10)
    s3_request_checksum_calculation: Literal["when_supported", "when_required"] = (
        "when_required"
    )
    s3_response_checksum_validation: Literal["when_supported", "when_required"] = (
        "when_required"
    )
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
    gemini_chat_fallback_model: str | None = Field(default=None, min_length=1)
    chat_max_output_tokens: int = Field(default=2048, ge=1, le=65536)
    chat_generation_deadline_seconds: int = Field(default=30, ge=1, le=300)
    chat_attempt_timeout_seconds: int = Field(default=15, ge=1, le=300)
    chat_max_question_chars: int = Field(default=2000, ge=1, le=4000)
    chat_max_context_chunks: int = Field(default=5, ge=1, le=20)
    chat_max_context_chars: int = Field(default=12000, ge=256, le=100000)
    chat_max_attempts: int = Field(default=3, ge=1, le=5)
    chat_backoff_base_seconds: float = Field(default=0.5, ge=0, le=30)
    chat_backoff_max_seconds: float = Field(default=4, ge=0, le=120)
    rate_limit_cleanup_interval_seconds: int = Field(default=60, ge=1, le=3600)
    chat_requests_per_minute: int = Field(default=5, ge=1, le=10000)
    chat_requests_per_day: int = Field(default=100, ge=1, le=1000000)
    chat_concurrent_requests_per_user: int = Field(default=2, ge=1, le=100)
    upload_requests_per_minute: int = Field(default=3, ge=1, le=10000)
    upload_requests_per_day: int = Field(default=20, ge=1, le=1000000)
    search_requests_per_minute: int = Field(default=20, ge=1, le=10000)
    search_requests_per_day: int = Field(default=500, ge=1, le=1000000)
    auth_email_attempts_per_minute: int = Field(default=5, ge=1, le=10000)
    auth_ip_attempts_per_minute: int = Field(default=20, ge=1, le=100000)
    max_documents_per_user: int = Field(default=25, ge=1, le=100000)

    @field_validator("upload_directory", mode="before")
    @classmethod
    def resolve_upload_directory(cls, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else ROOT_DIR / path

    @field_validator("cors_origins")
    @classmethod
    def cors_origins_must_be_explicit(cls, origins: list[str]) -> list[str]:
        normalized = [origin.strip().rstrip("/") for origin in origins]
        if not normalized or any(not origin or origin == "*" for origin in normalized):
            raise ValueError("CORS_ORIGINS must contain explicit origins; '*' is not allowed.")
        if any("://" not in origin or "/" in origin.split("://", 1)[1] for origin in normalized):
            raise ValueError("CORS_ORIGINS entries must be origins without paths.")
        return normalized

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def trusted_proxy_entries_must_be_networks(cls, cidrs: list[str]) -> list[str]:
        try:
            return [str(ip_network(cidr, strict=False)) for cidr in cidrs]
        except ValueError as error:
            raise ValueError("TRUSTED_PROXY_CIDRS must contain valid IP networks.") from error

    @field_validator("s3_endpoint_url")
    @classmethod
    def s3_endpoint_must_be_an_absolute_http_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        endpoint = value.strip()
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("S3_ENDPOINT_URL must be an absolute HTTP(S) URL.")
        return endpoint

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
    def s3_storage_requires_configuration(self) -> "Settings":
        if self.file_storage_backend == "s3" and (
            not self.s3_endpoint_url
            or not self.s3_bucket
            or not self.s3_bucket.strip()
            or not self.s3_region.strip()
            or self.s3_access_key_id is None
            or not self.s3_access_key_id.get_secret_value().strip()
            or self.s3_secret_access_key is None
            or not self.s3_secret_access_key.get_secret_value().strip()
        ):
            raise ValueError(
                "S3 storage requires S3_ENDPOINT_URL, S3_BUCKET, "
                "S3_ACCESS_KEY_ID, and S3_SECRET_ACCESS_KEY."
            )
        return self

    @model_validator(mode="after")
    def chat_backoff_max_is_not_smaller_than_base(self) -> "Settings":
        if self.chat_backoff_max_seconds < self.chat_backoff_base_seconds:
            raise ValueError(
                "CHAT_BACKOFF_MAX_SECONDS must be at least "
                "CHAT_BACKOFF_BASE_SECONDS."
            )
        return self

    @model_validator(mode="after")
    def demo_email_is_normalized(self) -> "Settings":
        self.demo_user_email = self.demo_user_email.strip().lower()
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
