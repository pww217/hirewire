"""API backend configuration from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database - required, no default (must be provided via env var)
    database_url: str

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Pagination defaults
    default_page_size: int = 50
    max_page_size: int = 100

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    environment: Literal["development", "production"] = "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.

    Returns:
        Application settings instance.
    """
    return Settings()


# For convenience, pre-load settings on import
# This will fail fast if DATABASE_URL is not set
settings = get_settings()
