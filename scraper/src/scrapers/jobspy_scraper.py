"""JobSpy scraper implementation.

Scrapes jobs from Indeed, Glassdoor, and other job boards via the JobSpy library.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import pandas as pd
import structlog

from ..models.job import SearchConfig
from ..models.raw_job import RawJob
from . import BaseScraper, ScrapingError

log = structlog.get_logger()

# Thread pool for running sync JobSpy in async context
_executor = ThreadPoolExecutor(max_workers=2)


class JobSpyScraper(BaseScraper):
    """Scraper that uses JobSpy library to fetch jobs from major job boards."""

    def __init__(
        self,
        sites: list[str],
        search_configs: list[SearchConfig],
    ):
        """Initialize JobSpy scraper.

        Args:
            sites: List of sites to scrape (e.g., ["indeed", "glassdoor"])
            search_configs: List of search configurations from database
        """
        self.sites = sites
        self.search_configs = search_configs

    @property
    def source_name(self) -> str:
        return "jobspy"

    async def fetch(self) -> list[RawJob]:
        """Fetch jobs from all configured sites using search configs.

        Returns:
            List of RawJob objects
        """
        all_jobs: list[RawJob] = []

        for config in self.search_configs:
            try:
                jobs = await self._scrape_config(config)
                all_jobs.extend(jobs)
                log.info(
                    "jobspy_config_scraped",
                    config_name=config.name,
                    jobs_found=len(jobs),
                )
            except Exception as e:
                log.error(
                    "jobspy_config_failed",
                    config_name=config.name,
                    error=str(e),
                )
                # Continue with other configs

        return all_jobs

    async def _scrape_config(self, config: SearchConfig) -> list[RawJob]:
        """Scrape jobs for a single search configuration.

        Args:
            config: Search configuration from database

        Returns:
            List of RawJob objects
        """
        loop = asyncio.get_event_loop()

        # Run synchronous JobSpy in thread pool
        try:
            df = await loop.run_in_executor(
                _executor,
                self._sync_scrape,
                config,
            )
        except Exception as e:
            raise ScrapingError(self.source_name, f"JobSpy scrape failed: {e}")

        if df is None or df.empty:
            return []

        # Convert DataFrame rows to RawJob objects
        jobs = []
        for _, row in df.iterrows():
            try:
                job = self._row_to_raw_job(row)
                if job:
                    jobs.append(job)
            except Exception as e:
                log.warning(
                    "jobspy_row_parse_failed",
                    error=str(e),
                    title=getattr(row, "title", "unknown"),
                )
                continue

        return jobs

    def _sync_scrape(self, config: SearchConfig) -> Optional[pd.DataFrame]:
        """Synchronous JobSpy scrape (runs in thread pool).

        Args:
            config: Search configuration

        Returns:
            DataFrame with job results, or None on failure
        """
        from jobspy import scrape_jobs

        try:
            # Build kwargs - only include is_remote if explicitly True
            # (False means "all jobs", not "only non-remote")
            kwargs = {
                "site_name": self.sites,
                "search_term": config.search_term,
                "location": config.location,
                "distance": config.distance,
                "hours_old": config.hours_old,
                "results_wanted": config.results_wanted,
                "country_indeed": config.country,
                "description_format": "html",  # Return HTML instead of markdown
                "linkedin_fetch_description": True,  # Fetch full descriptions for LinkedIn
                "verbose": 0,  # Suppress JobSpy logs
            }
            if config.is_remote is True:
                kwargs["is_remote"] = True

            df = scrape_jobs(**kwargs)
            return df
        except Exception as e:
            log.error("jobspy_sync_scrape_error", error=str(e))
            return None

    def _row_to_raw_job(self, row: pd.Series) -> Optional[RawJob]:
        """Convert a pandas row to RawJob model.

        Args:
            row: DataFrame row from JobSpy

        Returns:
            RawJob object or None if conversion fails
        """
        # Extract required fields
        title = self._safe_str(row.get("title"))
        company = self._safe_str(row.get("company"))
        job_url = self._safe_str(row.get("job_url"))

        if not title or not company or not job_url:
            return None

        # Extract location components
        location = row.get("location")
        location_city = None
        location_state = None
        location_country = None
        location_raw = None

        if location is not None:
            # JobSpy returns location as a Location object with city, state, country attrs
            location_city = self._safe_str(getattr(location, "city", None))
            location_state = self._safe_str(getattr(location, "state", None))
            location_country = self._safe_str(getattr(location, "country", None))

            # Build raw location string
            parts = [p for p in [location_city, location_state] if p]
            location_raw = ", ".join(parts) if parts else None

        # Extract salary info
        salary_min = self._safe_float(row.get("min_amount"))
        salary_max = self._safe_float(row.get("max_amount"))
        salary_interval = self._safe_str(row.get("interval"))

        # Parse date_posted
        date_posted = self._parse_date(row.get("date_posted"))

        # Get source site
        source_site = self._safe_str(row.get("site")) or "unknown"

        # External ID (JobSpy uses job_url as ID for many sites)
        external_id = self._safe_str(row.get("id")) or job_url

        return RawJob(
            source="jobspy",
            source_site=source_site,
            external_id=external_id[:255] if external_id else None,
            title=title[:500],
            company=company[:255],
            job_url=job_url[:1000],
            company_url=self._safe_str(row.get("company_url"), max_len=500),
            location_raw=location_raw[:255] if location_raw else None,
            location_city=location_city[:100] if location_city else None,
            location_state=location_state[:100] if location_state else None,
            location_country=location_country[:100] if location_country else None,
            is_remote=bool(row.get("is_remote", False)),
            description=self._safe_str(row.get("description")),
            job_type=self._safe_str(row.get("job_type")),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_interval=salary_interval,
            date_posted=date_posted,
            company_size=self._safe_str(
                row.get("company_employees_label"), max_len=50
            ),
            company_industry=self._safe_str(row.get("company_industry"), max_len=100),
        )

    @staticmethod
    def _safe_str(value, max_len: Optional[int] = None) -> Optional[str]:
        """Safely convert value to string, handling NaN and None.

        Args:
            value: Value to convert
            max_len: Optional maximum length to truncate to

        Returns:
            String value or None
        """
        if value is None:
            return None
        if pd.isna(value):
            return None
        result = str(value).strip()
        if not result:
            return None
        if max_len and len(result) > max_len:
            return result[:max_len]
        return result

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        """Safely convert value to float.

        Args:
            value: Value to convert

        Returns:
            Float value or None
        """
        if value is None:
            return None
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_date(value) -> Optional[datetime]:
        """Parse date value from JobSpy.

        Args:
            value: Date value (could be date, datetime, string, or None)

        Returns:
            datetime object or None
        """
        if value is None:
            return None
        if pd.isna(value):
            return None

        # Already a datetime
        if isinstance(value, datetime):
            return value

        # date object
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            return datetime(value.year, value.month, value.day)

        # Try parsing string
        if isinstance(value, str):
            try:
                from dateutil import parser

                return parser.parse(value)
            except Exception:
                return None

        return None
