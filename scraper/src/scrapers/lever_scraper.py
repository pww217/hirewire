"""Lever ATS scraper.

Fetches job listings from Lever's public postings API.
No authentication required.

API: GET https://api.lever.co/v0/postings/{slug}

Response shape (confirmed via smoke test on spotify):
  [{ id, text (title), description (HTML), descriptionPlain,
     categories: { location, team, department, commitment },
     hostedUrl, applyUrl, createdAt (ms epoch) }]
"""

from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog

from ..models.job import TrackedCompany
from ..models.raw_job import RawJob
from ..utils import parse_location
from . import BaseScraper, ScrapingError

log = structlog.get_logger()

BASE_URL = "https://api.lever.co/v0/postings"

COMMITMENT_MAP = {
    "full-time": "full_time",
    "fulltime": "full_time",
    "part-time": "part_time",
    "parttime": "part_time",
    "contract": "contract",
    "contractor": "contract",
    "intern": "internship",
    "internship": "internship",
}


class LeverScraper(BaseScraper):
    """Scraper for Lever ATS job boards."""

    def __init__(self, company: TrackedCompany, http_timeout: float = 30.0):
        self.company = company
        self.http_timeout = http_timeout

    @property
    def source_name(self) -> str:
        return "lever"

    async def fetch(self) -> list[RawJob]:
        """Fetch all jobs from company's Lever board."""
        url = f"{BASE_URL}/{self.company.ats_identifier}"

        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            try:
                response = await client.get(url)
            except httpx.TimeoutException:
                raise ScrapingError(self.source_name, f"Timeout for {self.company.name}")
            except httpx.RequestError as e:
                raise ScrapingError(self.source_name, f"Request error for {self.company.name}: {e}")

        if response.status_code == 404:
            log.warning(
                "lever_company_not_found",
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
            jobs = response.json()
        except Exception as e:
            raise ScrapingError(self.source_name, f"Invalid JSON for {self.company.name}: {e}")

        if not isinstance(jobs, list):
            raise ScrapingError(
                self.source_name,
                f"Unexpected response format for {self.company.name}: expected list",
            )

        log.info("lever_fetched", company=self.company.name, count=len(jobs))

        result = []
        for job in jobs:
            raw = self._parse_job(job)
            if raw:
                result.append(raw)

        return result

    def _parse_job(self, job: dict) -> Optional[RawJob]:
        """Convert a single Lever job dict to a RawJob."""
        job_id = job.get("id")
        title = (job.get("text") or "").strip()
        job_url = job.get("hostedUrl", "")

        if not title or not job_url:
            log.debug("lever_job_missing_fields", job_id=job_id)
            return None

        # Categories
        cats = job.get("categories") or {}
        location_str = cats.get("location")
        location_raw, city, state = parse_location(location_str)

        # Remote detection
        is_remote = False
        if location_raw and "remote" in location_raw.lower():
            is_remote = True

        # Job type from commitment
        commitment = (cats.get("commitment") or "").lower().strip()
        job_type = COMMITMENT_MAP.get(commitment)

        # Date posted: Lever uses milliseconds since epoch
        created_at_ms = job.get("createdAt")
        date_posted = _parse_ms_epoch(created_at_ms)

        # Assemble full description from all Lever content sections
        description = _build_description(job)

        return RawJob(
            source="lever",
            source_site="lever",
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
            job_type=job_type,
            date_posted=date_posted,
        )


def _build_description(job: dict) -> Optional[str]:
    """Assemble a full HTML description from all Lever content sections.

    Lever splits job content across:
      - description: intro paragraph(s)
      - lists[]:     body sections with a heading and <li> items
      - additional:  compensation, location, benefits etc.
    """
    parts: list[str] = []

    intro = job.get("description", "").strip()
    if intro:
        parts.append(intro)

    for section in job.get("lists") or []:
        heading = (section.get("text") or "").strip()
        content = (section.get("content") or "").strip()
        if heading:
            parts.append(f"<h3>{heading}</h3>")
        if content:
            parts.append(f"<ul>{content}</ul>")

    extra = job.get("additional", "").strip()
    if extra:
        parts.append(extra)

    if not parts:
        return job.get("descriptionPlain") or None

    return "\n".join(parts)


def _parse_ms_epoch(value: Optional[int]) -> Optional[datetime]:
    """Parse milliseconds-since-epoch timestamp."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None
