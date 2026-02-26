"""Data models for scraper service."""

from .raw_job import RawJob
from .job import Job, JobSource, TrackedCompany

__all__ = ["RawJob", "Job", "JobSource", "TrackedCompany"]
