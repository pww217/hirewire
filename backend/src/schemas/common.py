"""Common Pydantic schemas for pagination and error responses."""

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(
        default=50, ge=1, le=100, description="Items per page (max 100)"
    )

    @property
    def offset(self) -> int:
        """Calculate offset for SQL query."""
        return (self.page - 1) * self.per_page


class ValidationErrorDetail(BaseModel):
    """Individual validation error detail."""

    loc: list[str | int] = Field(..., description="Error location path")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    detail: str | list[ValidationErrorDetail] = Field(
        ..., description="Error message or validation errors"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    database: str | None = Field(None, description="Database connection status")
    version: str = Field(..., description="API version")
    scrape_schedule: str | None = Field(None, description="Configured scrape schedule")
    next_runs: list[str] | None = Field(None, description="Next scheduled scrape times")
