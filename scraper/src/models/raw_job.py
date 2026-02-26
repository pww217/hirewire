"""Raw job data model from scraping sources.

This is the contract between scrapers and the normalization layer.
All scrapers must output data conforming to this model.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class RawJob(BaseModel):
    """Raw job data from scraping sources before normalization.

    Field constraints match database VARCHAR limits to prevent insertion errors.
    """

    # Source identification
    source: Literal["ashby", "greenhouse", "lever"]
    source_site: str = Field(..., max_length=50)
    external_id: Optional[str] = Field(default=None, max_length=255)

    # Core fields (required)
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=255)
    job_url: str = Field(..., min_length=1, max_length=1000)

    # Optional fields
    company_url: Optional[str] = Field(default=None, max_length=500)

    # Location (raw from source)
    location_raw: Optional[str] = Field(default=None, max_length=255)
    location_city: Optional[str] = Field(default=None, max_length=100)
    location_state: Optional[str] = Field(default=None, max_length=100)
    location_country: Optional[str] = Field(default=None, max_length=100)
    is_remote: bool = False

    # Details
    description: Optional[str] = None
    job_type: Optional[Literal["full_time", "part_time", "contract", "internship"]] = (
        None
    )

    # Salary
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_interval: Optional[
        Literal["yearly", "monthly", "weekly", "daily", "hourly"]
    ] = None

    # Dates
    date_posted: Optional[datetime] = None

    # Company metadata (not available from all ATS providers)
    company_size: Optional[str] = Field(default=None, max_length=50)
    company_industry: Optional[str] = Field(default=None, max_length=100)

    model_config = {"extra": "ignore"}  # Ignore extra fields from sources

    @field_validator("job_type", mode="before")
    @classmethod
    def normalize_job_type(cls, v: Optional[str]) -> Optional[str]:
        """Normalize job type values to snake_case."""
        if v is None:
            return None

        v_lower = str(v).lower().strip()

        # Map all variations to snake_case
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
    def normalize_salary_interval(cls, v: Optional[str]) -> Optional[str]:
        """Normalize salary interval values to lowercase."""
        if v is None:
            return None

        v_lower = str(v).lower().strip()

        # Map variations
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
    def clean_url(cls, v: Optional[str]) -> Optional[str]:
        """Clean and validate URLs."""
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
        return v
