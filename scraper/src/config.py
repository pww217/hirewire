"""Scraper configuration from environment variables."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str

    # Scraping configuration
    scrape_schedule: str = "09:00,17:00"
    scrape_timeout_seconds: int = 300
    http_timeout_seconds: int = 30

    # Database pool
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # Job lifecycle
    stale_job_days: int = 14
    glassdoor_rating_stale_days: int = 7

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    environment: str = "production"

    @property
    def scrape_schedule_list(self) -> list[str]:
        """Parse schedule into list of HH:MM strings."""
        return [s.strip() for s in self.scrape_schedule.split(",") if s.strip()]


settings = Settings()
