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

    # CORS - comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    # Database pool
    db_pool_size: int = 5
    db_pool_overflow: int = 10

    # Scraper schedule - comma-separated HH:MM times in UTC
    scrape_schedule: str = "09:00,17:00"

    # Pagination defaults
    default_page_size: int = 50
    max_page_size: int = 100

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    environment: Literal["development", "production"] = "production"

    @property
    def scrape_schedule_list(self) -> list[str]:
        """Parse schedule into list of HH:MM strings."""
        return [s.strip() for s in self.scrape_schedule.split(",") if s.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Pre-load settings on import — fails fast if DATABASE_URL is not set
settings = get_settings()
