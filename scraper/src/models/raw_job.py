"""Raw job data model from scraping sources.

This is the contract between scrapers and the normalization layer.
All scrapers must output data conforming to this model.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RawJob(BaseModel):
    """Raw job data from scraping sources before normalization.

    Field constraints match database VARCHAR limits to prevent insertion errors.
    """

    # Source identification
    source: Literal["ashby", "greenhouse", "lever"]
    source_site: str = Field(..., max_length=50)
    external_id: str | None = Field(default=None, max_length=255)

    # Tracked company reference (set by scraper)
    company_id: int | None = None

    # Core fields (required)
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=255)
    job_url: str = Field(..., min_length=1, max_length=1000)

    # Optional fields
    company_url: str | None = Field(default=None, max_length=500)

    # Location (raw from source)
    location_raw: str | None = Field(default=None, max_length=255)
    location_city: str | None = Field(default=None, max_length=100)
    location_state: str | None = Field(default=None, max_length=100)
    location_country: str | None = Field(default=None, max_length=100)
    is_remote: bool = False

    # Details
    description: str | None = None
    job_type: Literal["full_time", "part_time", "contract", "internship"] | None = None

    # Salary
    salary_min: float | None = None
    salary_max: float | None = None
    salary_interval: Literal["yearly", "monthly", "weekly", "daily", "hourly"] | None = None

    # Dates
    date_posted: datetime | None = None

    # Company metadata (not available from all ATS providers)
    company_size: str | None = Field(default=None, max_length=50)
    company_industry: str | None = Field(default=None, max_length=100)

    model_config = {"extra": "ignore"}

    @field_validator("job_type", mode="before")
    @classmethod
    def normalize_job_type(cls, v: str | None) -> str | None:
        """Normalize job type values to snake_case."""
        if v is None:
            return None

        v_lower = str(v).lower().strip()

        mapping = {
            "fulltime": "full_time",
            "full-time": "full_time",
            "full time": "full_time",
            "full_time": "full_time",
            "parttime": "part_time",
            "part-time": "part_time",
            "part time": "part_time",
            "part_time": "part_time",
            "contract": "contract",
            "contractor": "contract",
            "internship": "internship",
            "intern": "internship",
        }
        return mapping.get(v_lower)

    @field_validator("salary_interval", mode="before")
    @classmethod
    def normalize_salary_interval(cls, v: str | None) -> str | None:
        """Normalize salary interval values to lowercase."""
        if v is None:
            return None

        v_lower = str(v).lower().strip()

        mapping = {
            "yearly": "yearly",
            "annual": "yearly",
            "annually": "yearly",
            "year": "yearly",
            "monthly": "monthly",
            "month": "monthly",
            "weekly": "weekly",
            "week": "weekly",
            "daily": "daily",
            "day": "daily",
            "hourly": "hourly",
            "hour": "hourly",
        }
        return mapping.get(v_lower, v_lower)

    @field_validator("title", "company", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace from string fields."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("job_url", "company_url", mode="before")
    @classmethod
    def clean_url(cls, v: str | None) -> str | None:
        """Clean and validate URLs."""
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
        return v
