"""Pydantic schemas for tracked company endpoints."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ATSType = Literal["greenhouse", "lever", "ashby"]

# ============================================================================
# URL detection patterns
# ============================================================================
_ATS_PATTERNS: list[tuple[str, ATSType]] = [
    # Greenhouse
    (r"boards\.greenhouse\.io/([^/?#]+)", "greenhouse"),
    (r"([^.]+)\.greenhouse\.io", "greenhouse"),
    # Lever
    (r"jobs\.lever\.co/([^/?#]+)", "lever"),
    # Ashby
    (r"jobs\.ashbyhq\.com/([^/?#]+)", "ashby"),
    (r"app\.ashbyhq\.com/jobs/([^/?#]+)", "ashby"),
]


def detect_ats_from_url(url: str) -> tuple[ATSType | None, str | None]:
    """Detect ATS type and company slug from a career page URL.

    Returns:
        (ats_type, slug) or (None, None) if not detected
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    for pattern, ats_type in _ATS_PATTERNS:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            slug = match.group(1).rstrip("/").lower()
            if slug:
                return ats_type, slug

    return None, None


# ============================================================================
# Request schemas
# ============================================================================

class CompanyDetectRequest(BaseModel):
    """Request body for URL-based ATS detection."""

    url: str = Field(..., min_length=3, max_length=500)


class CompanyDetectResponse(BaseModel):
    """Result of ATS URL detection."""

    url: str
    ats_type: ATSType | None
    ats_identifier: str | None
    detected: bool


class CompanyCreate(BaseModel):
    """Create a new tracked company."""

    name: str = Field(..., min_length=1, max_length=255)
    website: str | None = Field(default=None, max_length=500)
    ats_type: ATSType | None = None
    ats_identifier: str | None = Field(default=None, max_length=255)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_ats_fields(self) -> "CompanyCreate":
        if self.ats_type and not self.ats_identifier:
            raise ValueError("ats_identifier is required when ats_type is set")
        if self.ats_identifier and not self.ats_type:
            raise ValueError("ats_type is required when ats_identifier is set")
        return self


class CompanyUpdate(BaseModel):
    """Partial update for a tracked company."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    website: str | None = Field(default=None, max_length=500)
    ats_type: ATSType | None = None
    ats_identifier: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None

    @field_validator("ats_type", "ats_identifier", mode="before")
    @classmethod
    def allow_empty_string_as_none(cls, v: str | None) -> str | None:
        if v == "":
            return None
        return v


# ============================================================================
# Sync response schema (matches frontend SyncResponse contract)
# ============================================================================

class SyncResponse(BaseModel):
    """Response from a scraper sync operation."""

    success: bool
    new_jobs: int
    updated_jobs: int
    duration_ms: int
    error: str | None = None
    started_at: str


# ============================================================================
# Response schemas
# ============================================================================

class CompanyResponse(BaseModel):
    """Tracked company response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    website: str | None
    ats_type: str | None
    ats_identifier: str | None
    last_scraped: datetime | None
    job_count: int
    enabled: bool
    created_at: datetime
    glassdoor_id: int | None = None
    glassdoor_rating: float | None = None
    glassdoor_url: str | None = None
    rating_updated_at: datetime | None = None


class RefreshRatingResult(BaseModel):
    """Result for a single company in a ratings refresh."""

    company_id: int
    name: str
    rating: float | None
    success: bool


class RefreshRatingsResponse(BaseModel):
    """Response from POST /api/companies/refresh-ratings."""

    refreshed: int
    still_missing: int
    companies: list[RefreshRatingResult]
