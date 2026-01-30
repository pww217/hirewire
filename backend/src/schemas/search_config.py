"""Pydantic schemas for search configuration endpoints.

These schemas are used for API request/response validation.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SearchConfigBase(BaseModel):
    """Base schema with common fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Config name")
    search_term: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search keywords (supports OR operators)",
    )
    location: str | None = Field(
        None, max_length=255, description="Location filter (e.g., 'San Francisco, CA')"
    )
    distance: int | None = Field(50, ge=0, le=500, description="Search radius in miles")
    is_remote: bool = Field(False, description="Search for remote jobs only")
    hours_old: int = Field(
        48, ge=1, le=720, description="Max age of job postings in hours"
    )
    results_wanted: int = Field(
        100, ge=10, le=500, description="Max results per search"
    )
    country: str = Field("USA", max_length=10, description="Country code")
    enabled: bool = Field(True, description="Whether this config is active")


class SearchConfigCreate(SearchConfigBase):
    """Schema for creating a new search config."""

    pass


class SearchConfigUpdate(BaseModel):
    """Schema for updating a search config (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    search_term: str | None = Field(None, min_length=1, max_length=500)
    location: str | None = Field(None, max_length=255)
    distance: int | None = Field(None, ge=0, le=500)
    is_remote: bool | None = None
    hours_old: int | None = Field(None, ge=1, le=720)
    results_wanted: int | None = Field(None, ge=10, le=500)
    country: str | None = Field(None, max_length=10)
    enabled: bool | None = None


class SearchConfigResponse(SearchConfigBase):
    """Response schema for a search config."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class SearchConfigListResponse(BaseModel):
    """Response schema for listing search configs."""

    configs: list[SearchConfigResponse]
    total: int = Field(..., ge=0, description="Total number of configs")


class SearchConfigToggleResponse(BaseModel):
    """Response schema for toggling a config's enabled status."""

    id: int
    enabled: bool
