"""Pydantic schemas for user settings endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserSettingsBase(BaseModel):
    """Base schema with common fields."""

    excluded_companies: list[str] = Field(
        default_factory=list, description="Companies to exclude from results"
    )
    excluded_keywords: list[str] = Field(
        default_factory=list, description="Keywords in job titles to exclude"
    )
    default_location: str | None = Field(
        None, max_length=255, description="Default location filter"
    )
    default_remote: bool = Field(False, description="Default to remote-only filter")


class UserSettingsUpdate(BaseModel):
    """Schema for updating user settings (all fields optional)."""

    excluded_companies: list[str] | None = None
    excluded_keywords: list[str] | None = None
    default_location: str | None = None
    default_remote: bool | None = None


class UserSettingsResponse(UserSettingsBase):
    """Response schema for user settings."""

    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime
