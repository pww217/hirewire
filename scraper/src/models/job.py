"""Normalized job models for database insertion.

These models represent the final processed form after normalization,
matching the PostgreSQL schema defined in shared/schema.sql.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class JobSource(BaseModel):
    """Source information for a job.

    Matches job_sources table in schema.sql.
    """

    source: Literal["ashby", "greenhouse", "lever"]
    source_site: str = Field(..., max_length=50)
    external_id: str | None = Field(default=None, max_length=255)


class Job(BaseModel):
    """Normalized job ready for database insertion.

    Schema matches shared/schema.sql jobs table exactly.
    Field constraints match database VARCHAR limits.
    """

    # Deduplication
    dedup_hash: str = Field(..., min_length=32, max_length=32)

    # Source company FK
    company_id: int | None = None

    # Core fields
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=255)
    company_url: str | None = Field(default=None, max_length=500)

    # Location (normalized)
    location_raw: str | None = Field(default=None, max_length=255)
    location_city: str | None = Field(default=None, max_length=100)
    location_state: str | None = Field(default=None, max_length=100)
    location_country: str | None = Field(default=None, max_length=100)
    is_remote: bool = False

    # Job details
    description: str | None = None
    job_url: str = Field(..., min_length=1, max_length=1000)
    job_type: Literal["full_time", "part_time", "contract", "internship"] | None = None

    # Salary
    salary_min: float | None = None
    salary_max: float | None = None
    salary_interval: Literal["yearly", "monthly", "weekly", "daily", "hourly"] | None = None

    # Dates (all UTC)
    date_posted: datetime | None = None
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Company metadata
    company_size: str | None = Field(default=None, max_length=50)
    company_industry: str | None = Field(default=None, max_length=100)

    # Status
    is_active: bool = True

    # Sources (for job_sources table)
    sources: list[JobSource] = Field(default_factory=list)


class TrackedCompany(BaseModel):
    """Tracked company from database.

    Matches tracked_companies table in schema.sql.
    """

    id: int
    name: str = Field(..., max_length=255)
    website: str | None = Field(default=None, max_length=500)
    ats_type: str | None = Field(default=None, max_length=50)
    ats_identifier: str | None = Field(default=None, max_length=255)
    last_scraped: datetime | None = None
    enabled: bool = True

    # Glassdoor ratings (cached)
    glassdoor_id: int | None = None
    glassdoor_rating: float | None = None
    glassdoor_url: str | None = Field(default=None, max_length=500)
    rating_updated_at: datetime | None = None

    model_config = {"from_attributes": True}
