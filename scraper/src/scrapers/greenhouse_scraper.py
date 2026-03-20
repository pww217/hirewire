"""Greenhouse ATS scraper.

Fetches job listings from Greenhouse's public job board API.
No authentication required.

API: GET https://api.greenhouse.io/v1/boards/{slug}/jobs?content=true

Response shape (confirmed via smoke test on stripe):
  jobs[]: { id, title, location: {name}, content (HTML),
            absolute_url, updated_at, departments[], offices[] }
"""

import html as html_lib

import httpx
import structlog

from ..models.job import TrackedCompany
from ..models.raw_job import RawJob
from ..utils import parse_iso, parse_location
from . import BaseScraper, ScrapingError

log = structlog.get_logger()

BASE_URL = "https://api.greenhouse.io/v1/boards"


class GreenhouseScraper(BaseScraper):
    """Scraper for Greenhouse ATS job boards."""

    def __init__(self, company: TrackedCompany, http_timeout: float = 30.0):
        self.company = company
        self.http_timeout = http_timeout

    @property
    def source_name(self) -> str:
        return "greenhouse"

    async def fetch(self) -> list[RawJob]:
        """Fetch all jobs from company's Greenhouse board."""
        url = f"{BASE_URL}/{self.company.ats_identifier}/jobs"

        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            try:
                response = await client.get(url, params={"content": "true"})
            except httpx.TimeoutException:
                raise ScrapingError(self.source_name, f"Timeout for {self.company.name}")
            except httpx.RequestError as e:
                raise ScrapingError(self.source_name, f"Request error for {self.company.name}: {e}")

        if response.status_code == 404:
            log.warning(
                "greenhouse_company_not_found",
                company=self.company.name,
                slug=self.company.ats_identifier,
            )
            return []

        if response.status_code != 200:
            raise ScrapingError(
                self.source_name,
                f"HTTP {response.status_code} for {self.company.name}",
            )

        try:
            data = response.json()
        except Exception as e:
            raise ScrapingError(self.source_name, f"Invalid JSON for {self.company.name}: {e}")

        jobs = data.get("jobs", [])
        log.info("greenhouse_fetched", company=self.company.name, count=len(jobs))

        result = []
        for job in jobs:
            raw = self._parse_job(job)
            if raw:
                result.append(raw)

        return result

    def _parse_job(self, job: dict) -> RawJob | None:
        """Convert a single Greenhouse job dict to a RawJob."""
        job_id = job.get("id")
        title = (job.get("title") or "").strip()
        job_url = job.get("absolute_url", "")

        if not title or not job_url:
            log.debug("greenhouse_job_missing_fields", job_id=job_id)
            return None

        # Location
        loc_obj = job.get("location") or {}
        location_str = loc_obj.get("name") if isinstance(loc_obj, dict) else None
        location_raw, city, state = parse_location(location_str)

        # Greenhouse doesn't provide is_remote or job_type fields directly
        is_remote = False
        if location_raw and "remote" in location_raw.lower():
            is_remote = True

        # Date posted (updated_at is ISO string)
        date_posted = parse_iso(job.get("updated_at"))

        # Description comes in `content` field when ?content=true
        # Greenhouse returns HTML-escaped content (&lt;h2&gt; etc.) — unescape it
        raw_content = job.get("content")
        description = html_lib.unescape(raw_content) if raw_content else None

        return RawJob(
            source="greenhouse",
            source_site="greenhouse",
            external_id=str(job_id)[:255] if job_id else None,
            company_id=self.company.id,
            title=title[:500],
            company=self.company.name[:255],
            job_url=job_url[:1000],
            location_raw=location_raw,
            location_city=city,
            location_state=state,
            is_remote=is_remote,
            description=description,
            date_posted=date_posted,
        )


