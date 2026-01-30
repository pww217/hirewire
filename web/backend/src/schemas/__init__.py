"""Pydantic schemas for API request/response validation."""

from .common import ErrorResponse, PaginationParams, ValidationErrorDetail
from .job import (
    FavoriteResponse,
    HideResponse,
    JobDetailResponse,
    JobListResponse,
    JobResponse,
)

__all__ = [
    "PaginationParams",
    "ErrorResponse",
    "ValidationErrorDetail",
    "JobResponse",
    "JobListResponse",
    "JobDetailResponse",
    "FavoriteResponse",
    "HideResponse",
]
