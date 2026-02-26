"""Pydantic schemas for stats endpoint."""

from datetime import datetime

from pydantic import BaseModel, Field


class SourceStats(BaseModel):
    """Stats for a single source."""

    source: str
    count: int


class StatsResponse(BaseModel):
    """Response schema for stats endpoint."""

    total_jobs: int = Field(..., ge=0, description="Total active jobs")
    jobs_last_24h: int = Field(..., ge=0, description="Jobs added in last 24 hours")
    jobs_last_7d: int = Field(..., ge=0, description="Jobs added in last 7 days")
    jobs_by_source: list[SourceStats] = Field(
        default_factory=list, description="Job counts by source"
    )
    last_job_added: datetime | None = Field(
        None, description="When the most recent job was added"
    )
