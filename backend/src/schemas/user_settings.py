"""Pydantic schemas for user settings endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserSettingsBase(BaseModel):
    """Base schema with common fields."""

    preferred_locations: list[str] = Field(
        default_factory=list, description="Preferred locations to filter jobs by default"
    )
    title_keywords: list[str] = Field(
        default_factory=list, description="Keywords: only show jobs whose titles contain at least one"
    )
    description_keywords: list[str] = Field(
        default_factory=list, description="Keywords: only show jobs whose descriptions contain at least one"
    )
    excluded_keywords: list[str] = Field(
        default_factory=list, description="Keywords in job titles to exclude"
    )
    default_location: str | None = Field(
        None, max_length=255, description="Default location filter"
    )
    default_remote: bool = Field(False, description="Default to remote-only filter")
    posted_after: str | None = Field(
        None, description="Date filter: 'today', 'week', or 'month'"
    )
    min_glassdoor_rating: int | None = Field(
        None, description="Minimum Glassdoor rating filter (1-4)"
    )
    job_type: str | None = Field(
        None, description="Job type filter: full_time, part_time, contract, internship"
    )


class UserSettingsUpdate(BaseModel):
    """Schema for updating user settings (all fields optional)."""

    preferred_locations: list[str] | None = None
    title_keywords: list[str] | None = None
    description_keywords: list[str] | None = None
    excluded_keywords: list[str] | None = None
    default_location: str | None = None
    default_remote: bool | None = None
    posted_after: str | None = None
    min_glassdoor_rating: int | None = None
    job_type: str | None = None


class UserSettingsResponse(UserSettingsBase):
    """Response schema for user settings."""

    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime
