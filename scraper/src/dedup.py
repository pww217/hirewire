"""Deduplication logic for HireWire scraper.

Uses SHA-256 hash of normalized (company, title, location) to identify
duplicate job postings across different sources.
"""

import hashlib
import re

import structlog

from .models.job import Job, JobSource
from .models.raw_job import RawJob

log = structlog.get_logger()

# Common company suffixes to strip for normalization
COMPANY_SUFFIXES = re.compile(
    r"\b(inc|llc|ltd|corp|co|company|incorporated|limited|corporation|group|holdings|international|intl)\.?\b",
    re.IGNORECASE,
)


def normalize_company(company: str) -> str:
    """Normalize company name for deduplication.

    Strips common suffixes like Inc, LLC, Ltd, Corp, etc.

    Args:
        company: Raw company name

    Returns:
        Normalized company name
    """
    # Lowercase and strip
    normalized = company.lower().strip()

    # Remove common suffixes
    normalized = COMPANY_SUFFIXES.sub("", normalized)

    # Remove punctuation
    normalized = re.sub(r"[,.\-'\"()]", " ", normalized)

    # Normalize whitespace
    normalized = " ".join(normalized.split())

    return normalized


def generate_dedup_hash(
    company: str, title: str, location: str | None
) -> str:
    """Generate SHA-256 hash for deduplication.

    Hash is based on: company + title + location (normalized)
    This catches the same job posted on multiple sites.

    Args:
        company: Company name
        title: Job title
        location: Location string (can be None)

    Returns:
        32-character hex string (SHA-256 truncated)
    """
    # Normalize inputs
    company_norm = normalize_company(company)
    title_norm = (title or "").lower().strip()
    location_norm = (location or "").lower().strip()

    # Combine with delimiter
    combined = f"{company_norm}|{title_norm}|{location_norm}"

    # SHA-256 hash, truncate to 32 chars
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]


def raw_job_to_job(raw_job: RawJob) -> Job:
    """Convert a RawJob to a normalized Job ready for database insertion.

    Args:
        raw_job: Raw job from scraper

    Returns:
        Normalized Job object with dedup_hash set
    """
    # Generate dedup hash
    dedup_hash = generate_dedup_hash(
        company=raw_job.company,
        title=raw_job.title,
        location=raw_job.location_raw,
    )

    # Create source record
    source = JobSource(
        source=raw_job.source,
        source_site=raw_job.source_site,
        external_id=raw_job.external_id,
    )

    return Job(
        dedup_hash=dedup_hash,
        company_id=raw_job.company_id,
        title=raw_job.title,
        company=raw_job.company,
        company_url=raw_job.company_url,
        location_raw=raw_job.location_raw,
        location_city=raw_job.location_city,
        location_state=raw_job.location_state,
        location_country=raw_job.location_country or "USA",
        is_remote=raw_job.is_remote,
        description=raw_job.description,
        job_url=raw_job.job_url,
        job_type=raw_job.job_type,
        salary_min=raw_job.salary_min,
        salary_max=raw_job.salary_max,
        salary_interval=raw_job.salary_interval,
        date_posted=raw_job.date_posted,
        company_size=raw_job.company_size,
        company_industry=raw_job.company_industry,
        sources=[source],
    )


def normalize_jobs(raw_jobs: list[RawJob]) -> list[Job]:
    """Convert a list of RawJobs to normalized Jobs.

    Also handles deduplication within the batch (same hash from multiple
    sources in a single scrape run).

    Args:
        raw_jobs: List of raw jobs from scrapers

    Returns:
        List of normalized Job objects (deduplicated within batch)
    """
    jobs_by_hash: dict[str, Job] = {}

    for raw_job in raw_jobs:
        try:
            job = raw_job_to_job(raw_job)

            if job.dedup_hash in jobs_by_hash:
                # Duplicate within batch - add source to existing job
                existing = jobs_by_hash[job.dedup_hash]
                # Only add if source not already present
                existing_sources = {
                    (s.source, s.source_site) for s in existing.sources
                }
                for source in job.sources:
                    if (source.source, source.source_site) not in existing_sources:
                        existing.sources.append(source)
            else:
                jobs_by_hash[job.dedup_hash] = job

        except Exception as e:
            log.warning(
                "normalize_job_failed",
                error=str(e),
                title=raw_job.title,
                company=raw_job.company,
            )
            continue

    return list(jobs_by_hash.values())


class Deduplicator:
    """Handles job deduplication against the database."""

    def __init__(self, db: "Database"):  # noqa: F821
        """Initialize deduplicator with database connection.

        Args:
            db: Database instance for checking existing hashes
        """
        self.db = db

    async def filter_new_jobs(
        self,
        jobs: list[Job],
    ) -> tuple[list[Job], set[str]]:
        """Filter jobs to only new ones.

        Args:
            jobs: List of normalized Job objects

        Returns:
            Tuple of (new_jobs, existing_hashes)
        """
        if not jobs:
            return [], set()

        # Get hashes of all input jobs
        input_hashes = {job.dedup_hash for job in jobs}

        # Query existing hashes from DB
        existing_hashes = await self.db.get_existing_hashes(list(input_hashes))

        # Partition into new vs existing
        new_jobs = []
        for job in jobs:
            if job.dedup_hash not in existing_hashes:
                new_jobs.append(job)

        log.debug(
            "dedup_filter_complete",
            input_count=len(jobs),
            existing_count=len(existing_hashes),
            new_count=len(new_jobs),
        )

        return new_jobs, existing_hashes
