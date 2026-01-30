"""Scraper configuration from environment variables."""

from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database
    database_url: str

    # Scraping configuration
    enabled_sources: str = "jobspy"  # Comma-separated: jobspy,ashby
    jobspy_sites: str = "indeed,glassdoor"  # Comma-separated
    scrape_timeout_seconds: int = 300
    http_timeout_seconds: int = 30

    # Database pool
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    environment: str = "production"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def enabled_sources_list(self) -> list[str]:
        """Parse enabled sources into list."""
        return [s.strip() for s in self.enabled_sources.split(",") if s.strip()]

    @property
    def jobspy_sites_list(self) -> list[str]:
        """Parse JobSpy sites into list."""
        return [s.strip() for s in self.jobspy_sites.split(",") if s.strip()]


settings = Settings()
