"""Pydantic schemas for API request/response validation."""

from .common import ErrorResponse, PaginationParams, ValidationErrorDetail
from .job import (
    FavoriteResponse,
    HideResponse,
    JobDetailResponse,
    JobListResponse,
    JobResponse,
)
from .stats import SourceStats, StatsResponse
from .user_settings import (
    UserSettingsResponse,
    UserSettingsUpdate,
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
    "UserSettingsResponse",
    "UserSettingsUpdate",
    "SourceStats",
    "StatsResponse",
]
