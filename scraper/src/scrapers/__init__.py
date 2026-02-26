"""Job scrapers for HireWire.

This module provides the base scraper interface and ATS implementations
(Ashby, Greenhouse, Lever).
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ..models.raw_job import RawJob

log = structlog.get_logger()


class BaseScraper(ABC):
    """Base class for all job scrapers.

    All scrapers must implement the fetch() method to return a list of RawJob objects.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the source identifier (e.g., 'ashby', 'greenhouse', 'lever')."""
        pass

    @abstractmethod
    async def fetch(self) -> list["RawJob"]:
        """Execute scrape and return raw job data.

        Returns:
            List of RawJob objects conforming to the integration contract.
            Empty list on failure (after logging error).
        """
        pass


class ScraperError(Exception):
    """Base exception for scraper errors."""

    pass


class ScrapingError(ScraperError):
    """Error during scraping operation."""

    def __init__(self, source: str, message: str):
        self.source = source
        super().__init__(f"[{source}] {message}")


class RateLimitError(ScrapingError):
    """Rate limited by source."""

    def __init__(self, source: str, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(source, f"Rate limited, retry after {retry_after}s")


__all__ = [
    "BaseScraper",
    "ScraperError",
    "ScrapingError",
    "RateLimitError",
]
