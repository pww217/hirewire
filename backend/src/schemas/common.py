"""Common Pydantic schemas."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    database: str | None = Field(None, description="Database connection status")
    version: str = Field(..., description="API version")
    scrape_schedule: str | None = Field(None, description="Configured scrape schedule")
    next_runs: list[str] | None = Field(None, description="Next scheduled scrape times")
