"""Pydantic schemas for job-related responses.

These schemas match the frontend TypeScript types in api.ts exactly.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Type literals matching frontend/database
JobType = Literal["full_time", "part_time", "contract", "internship"]
SalaryInterval = Literal["yearly", "monthly", "weekly", "daily", "hourly"]
CompanySize = Literal["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]
ApplicationStatus = Literal["applied", "interviewing", "rejected", "offer"]


class ApplicationResponse(BaseModel):
    """Application status for a job (Phase 4)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    status: ApplicationStatus
    notes: str | None
    applied_at: datetime | None
    updated_at: datetime


class JobResponse(BaseModel):
    """Job response for list endpoints.

    Matches the Job interface in frontend/src/types/api.ts.
    Does not include description (use JobDetailResponse for full details).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int | None = None
    title: str
    company: str
    company_url: str | None
    location_raw: str | None
    location_city: str | None
    location_state: str | None
    location_country: str | None
    is_remote: bool
    job_url: str
    job_type: JobType | None
    salary_min: Decimal | None
    salary_max: Decimal | None
    salary_interval: SalaryInterval | None
    date_posted: datetime | None
    first_seen: datetime
    company_size: CompanySize | None
    company_industry: str | None
    sources: list[str] = Field(default_factory=list)
    is_favorite: bool = False
    is_hidden: bool = False
    is_seen: bool = False
    glassdoor_rating: float | None = None
    glassdoor_url: str | None = None
    is_applied: bool = False


class JobDetailResponse(JobResponse):
    """Extended job response with full description.

    Matches the JobDetail interface in frontend/src/types/api.ts.
    Used for GET /api/jobs/{id} endpoint.
    """

    description: str | None
    last_seen: datetime
    application: ApplicationResponse | None = None


class JobListResponse(BaseModel):
    """Paginated job list response.

    Matches the JobListResponse interface in frontend/src/types/api.ts.
    """

    jobs: list[JobResponse]
    total: int = Field(..., ge=0, description="Total number of matching jobs")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class JobWithDescription(JobResponse):
    """Job response including description field for bulk/client-side filtering.

    Used by GET /api/jobs/all to support loading all jobs into memory at once.
    """

    description: str | None = None


class JobBulkResponse(BaseModel):
    """Bulk job response for client-side filtering.

    Returns all active jobs with descriptions in a single response.
    Matches the JobBulkResponse interface in frontend/src/types/api.ts.
    """

    jobs: list[JobWithDescription]
    total: int = Field(..., ge=0, description="Total number of jobs returned")


class FavoriteResponse(BaseModel):
    """Response for favorite add/remove operations.

    Matches FavoriteResponse interface in frontend.
    """

    id: int
    is_favorite: bool
    favorited_at: datetime | None = None


class HideResponse(BaseModel):
    """Response for hide/unhide operations.

    Matches HideResponse interface in frontend.
    """

    id: int
    is_hidden: bool
    hidden_at: datetime | None = None


class SeenResponse(BaseModel):
    """Response for mark-as-seen operation.

    Matches SeenResponse interface in frontend.
    """

    id: int
    is_seen: bool
    seen_at: datetime | None = None


class ApplyResponse(BaseModel):
    """Response for apply/unapply operations."""

    id: int
    is_applied: bool
    applied_at: datetime | None = None
