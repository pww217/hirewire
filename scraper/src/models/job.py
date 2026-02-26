"""Normalized job models for database insertion.

These models represent the final processed form after normalization,
matching the PostgreSQL schema defined in shared/schema.sql.
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


class JobSource(BaseModel):
    """Source information for a job.

    Matches job_sources table in schema.sql.
    """

    source: Literal["ashby", "greenhouse", "lever"]
    source_site: str = Field(..., max_length=50)
    external_id: Optional[str] = Field(default=None, max_length=255)


class Job(BaseModel):
    """Normalized job ready for database insertion.

    Schema matches shared/schema.sql jobs table exactly.
    Field constraints match database VARCHAR limits.
    """

    # Deduplication
    dedup_hash: str = Field(..., min_length=32, max_length=32)

    # Core fields
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=255)
    company_url: Optional[str] = Field(default=None, max_length=500)

    # Location (normalized)
    location_raw: Optional[str] = Field(default=None, max_length=255)
    location_city: Optional[str] = Field(default=None, max_length=100)
    location_state: Optional[str] = Field(default=None, max_length=100)
    location_country: Optional[str] = Field(default=None, max_length=100)
    is_remote: bool = False

    # Job details
    description: Optional[str] = None  # TEXT, no limit
    job_url: str = Field(..., min_length=1, max_length=1000)
    job_type: Optional[Literal["full_time", "part_time", "contract", "internship"]] = (
        None
    )

    # Salary
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_interval: Optional[
        Literal["yearly", "monthly", "weekly", "daily", "hourly"]
    ] = None

    # Dates (all UTC)
    date_posted: Optional[datetime] = None
    first_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Company metadata
    company_size: Optional[str] = Field(default=None, max_length=50)
    company_industry: Optional[str] = Field(default=None, max_length=100)

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
    website: Optional[str] = Field(default=None, max_length=500)
    ats_type: Optional[str] = Field(default=None, max_length=50)
    ats_identifier: Optional[str] = Field(default=None, max_length=255)
    last_scraped: Optional[datetime] = None
    enabled: bool = True

    model_config = {"from_attributes": True}
