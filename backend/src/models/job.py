"""SQLAlchemy models for jobs and related tables.

Models match the PostgreSQL schema defined in shared/schema.sql.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Job(Base):
    """Core job listing model."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dedup_hash: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    # Source company FK (references tracked_companies)
    company_id: Mapped["Optional[int]"] = mapped_column(Integer, nullable=True)

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    company_url: Mapped["Optional[str]"] = mapped_column(String(500), nullable=True)

    # Location (normalized)
    location_raw: Mapped["Optional[str]"] = mapped_column(String(255), nullable=True)
    location_city: Mapped["Optional[str]"] = mapped_column(String(100), nullable=True)
    location_state: Mapped["Optional[str]"] = mapped_column(String(100), nullable=True)
    location_country: Mapped["Optional[str]"] = mapped_column(
        String(100), default="USA", nullable=True
    )
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)

    # Job details
    description: Mapped["Optional[str]"] = mapped_column(Text, nullable=True)
    job_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    job_type: Mapped["Optional[str]"] = mapped_column(String(50), nullable=True)

    # Salary (normalized to yearly)
    salary_min: Mapped["Optional[Decimal]"] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    salary_max: Mapped["Optional[Decimal]"] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    salary_interval: Mapped["Optional[str]"] = mapped_column(
        String(20), default="yearly", nullable=True
    )

    # Dates
    date_posted: Mapped["Optional[datetime]"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Company metadata
    company_size: Mapped["Optional[str]"] = mapped_column(String(50), nullable=True)
    company_industry: Mapped["Optional[str]"] = mapped_column(
        String(100), nullable=True
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Full-text search vector (managed by PostgreSQL trigger)
    search_vector: Mapped["Optional[str]"] = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    sources: Mapped[list["JobSource"]] = relationship(
        "JobSource", back_populates="job", cascade="all, delete-orphan"
    )
    user_state: Mapped["Optional[UserJobState]"] = relationship(
        "UserJobState", back_populates="job", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_jobs_dedup_hash", "dedup_hash"),
        Index("ix_jobs_date_posted", "date_posted", postgresql_ops={"date_posted": "DESC"}),
        Index("ix_jobs_first_seen", "first_seen", postgresql_ops={"first_seen": "DESC"}),
        Index("ix_jobs_company", "company"),
        Index("ix_jobs_location", "location_city", "location_state"),
        Index("ix_jobs_is_remote", "is_remote", postgresql_where=(is_remote == True)),
        Index("ix_jobs_company_size", "company_size"),
        Index("ix_jobs_is_active", "is_active", postgresql_where=(is_active == True)),
        Index("ix_jobs_search_vector", "search_vector", postgresql_using="gin"),
    )


class JobSource(Base):
    """Track where each job was found."""

    __tablename__ = "job_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'greenhouse', 'lever', 'ashby'
    source_site: Mapped["Optional[str]"] = mapped_column(
        String(50), nullable=True
    )  # same as source for ATS scrapers
    external_id: Mapped["Optional[str]"] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Relationship
    job: Mapped["Job"] = relationship("Job", back_populates="sources")

    __table_args__ = (
        Index("ix_job_sources_job_id", "job_id"),
        Index("ix_job_sources_source", "source"),
        UniqueConstraint("job_id", "source", "source_site", name="ix_job_sources_unique"),
    )


class UserJobState(Base):
    """User state for jobs - favorites and hidden."""

    __tablename__ = "user_job_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_seen: Mapped[bool] = mapped_column(Boolean, default=False)
    favorited_at: Mapped["Optional[datetime]"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hidden_at: Mapped["Optional[datetime]"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    seen_at: Mapped["Optional[datetime]"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship
    job: Mapped["Job"] = relationship("Job", back_populates="user_state")

    __table_args__ = (
        Index("ix_user_job_state_job_id", "job_id"),
        Index(
            "ix_user_job_state_favorite",
            "is_favorite",
            postgresql_where=(is_favorite == True),
        ),
        Index(
            "ix_user_job_state_hidden",
            "is_hidden",
            postgresql_where=(is_hidden == True),
        ),
        Index(
            "ix_user_job_state_seen",
            "is_seen",
            postgresql_where=(is_seen == False),
        ),
    )


class Application(Base):
    """Track application status for jobs (Phase 4)."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="applied")
    notes: Mapped["Optional[str]"] = mapped_column(Text, nullable=True)
    applied_at: Mapped["Optional[datetime]"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_applications_job_id", "job_id"),
        Index("ix_applications_status", "status"),
    )
