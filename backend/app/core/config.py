"""Application settings, loaded from environment variables / .env files.

Validation of required configuration (e.g. DATABASE_URL format) happens here at
import time so misconfiguration fails fast at startup rather than mid-request.
"""

from functools import lru_cache

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every value can be set via environment variable."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),  # repo root .env, then backend/.env override
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "VersionWise AI"
    app_version: str = "0.1.0"
    environment: str = Field(default="development")
    secret_key: str = Field(default="dev-only-insecure-secret")
    access_token_expire_minutes: int = 60 * 24 * 7

    # --- Server / CORS ---
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:3000"

    # --- Database ---
    # Validated as a PostgreSQL DSN at startup; accepts e.g.
    # postgresql+psycopg://user:pass@host:5432/dbname
    database_url: PostgresDsn | None = None

    # --- LLM provider ---
    llm_provider: str = "openai"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None

    # --- Embedding provider ---
    embedding_provider: str = "openai"
    embedding_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_base_url: str | None = None

    # --- Object storage ---
    object_storage_provider: str = "s3"  # s3 | local
    object_storage_endpoint: str | None = None
    object_storage_bucket: str = "versionwise-documents"
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    object_storage_region: str = "us-east-1"

    # --- Retrieval defaults ---
    retrieval_top_k: int = 8
    retrieval_similarity_threshold: float = 0.0
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64

    @field_validator("frontend_origin")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor for FastAPI dependency injection."""
    return Settings()
