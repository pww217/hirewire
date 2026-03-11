"""SQLAlchemy model for tracked companies."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class TrackedCompany(Base):
    """Company whose job board we're tracking via ATS API."""

    __tablename__ = "tracked_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    website: Mapped["str | None"] = mapped_column(String(500), nullable=True)
    ats_type: Mapped["str | None"] = mapped_column(String(50), nullable=True)
    ats_identifier: Mapped["str | None"] = mapped_column(String(255), nullable=True)
    last_scraped: Mapped["datetime | None"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    job_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Glassdoor ratings (cached, refreshed weekly)
    glassdoor_id: Mapped["int | None"] = mapped_column(Integer, nullable=True)
    glassdoor_rating: Mapped["Decimal | None"] = mapped_column(
        Numeric(2, 1), nullable=True
    )
    glassdoor_url: Mapped["str | None"] = mapped_column(String(500), nullable=True)
    rating_updated_at: Mapped["datetime | None"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_tracked_companies_ats_type", "ats_type"),
        Index(
            "ix_tracked_companies_enabled",
            "enabled",
            postgresql_where=(enabled == True),  # noqa: E712
        ),
    )
