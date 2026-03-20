"""Ashby ATS scraper.

Fetches job listings from Ashby's public job board API.
No authentication required.

API: GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true

Response shape (confirmed via smoke test on notion):
  jobs[]: { id, title, department, team, employmentType, location,
            isRemote, workplaceType, jobUrl, applyUrl,
            descriptionHtml, descriptionPlain, publishedAt,
            compensation: { compensationTiers: [{min, max, currency, interval}] } }
"""

import httpx
import structlog

from ..models.job import TrackedCompany
from ..models.raw_job import RawJob
from ..utils import parse_iso, parse_location
from . import BaseScraper, ScrapingError

log = structlog.get_logger()

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"

EMPLOYMENT_TYPE_MAP = {
    "fulltime": "full_time",
    "parttime": "part_time",
    "intern": "internship",
    "contract": "contract",
    "contractor": "contract",
}


class AshbyScraper(BaseScraper):
    """Scraper for Ashby ATS job boards."""

    def __init__(self, company: TrackedCompany, http_timeout: float = 30.0):
        self.company = company
        self.http_timeout = http_timeout

    @property
    def source_name(self) -> str:
        return "ashby"

    async def fetch(self) -> list[RawJob]:
        """Fetch all jobs from company's Ashby board."""
        url = f"{BASE_URL}/{self.company.ats_identifier}"

        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            try:
                response = await client.get(url, params={"includeCompensation": "true"})
            except httpx.TimeoutException:
                raise ScrapingError(self.source_name, f"Timeout for {self.company.name}")
            except httpx.RequestError as e:
                raise ScrapingError(self.source_name, f"Request error for {self.company.name}: {e}")

        if response.status_code == 404:
            log.warning(
                "ashby_company_not_found",
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
        log.info("ashby_fetched", company=self.company.name, count=len(jobs))

        result = []
        for job in jobs:
            raw = self._parse_job(job)
            if raw:
                result.append(raw)

        return result

    def _parse_job(self, job: dict) -> RawJob | None:
        """Convert a single Ashby job dict to a RawJob."""
        job_id = job.get("id")
        title = job.get("title", "").strip()
        job_url = job.get("jobUrl", "")

        if not title or not job_url:
            log.debug("ashby_job_missing_fields", job_id=job_id)
            return None

        # Location
        location_raw, city, state = parse_location(job.get("location"))

        # Remote: use workplaceType (Remote/OnSite/Hybrid) or isRemote bool
        workplace = (job.get("workplaceType") or "").lower()
        is_remote = job.get("isRemote", False) or workplace == "remote"

        # Employment type
        emp_type = (job.get("employmentType") or "").lower().replace("-", "").replace(" ", "")
        job_type = EMPLOYMENT_TYPE_MAP.get(emp_type)

        # Compensation (first tier only)
        salary_min = salary_max = salary_interval = None
        comp = job.get("compensation") or {}
        tiers = comp.get("compensationTiers") or []
        if tiers:
            tier = tiers[0]
            salary_min = tier.get("min")
            salary_max = tier.get("max")
            raw_interval = (tier.get("interval") or "").lower()
            salary_interval = raw_interval if raw_interval else None

        # Date posted
        date_posted = parse_iso(job.get("publishedAt"))

        return RawJob(
            source="ashby",
            source_site="ashby",
            external_id=str(job_id)[:255] if job_id else None,
            company_id=self.company.id,
            title=title[:500],
            company=self.company.name[:255],
            job_url=job_url[:1000],
            location_raw=location_raw,
            location_city=city,
            location_state=state,
            is_remote=is_remote,
            description=job.get("descriptionHtml") or job.get("descriptionPlain"),
            job_type=job_type,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_interval=salary_interval,
            date_posted=date_posted,
        )


