"""SQLAlchemy model for search configurations.

Models match the PostgreSQL schema defined in shared/schema.sql.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SearchConfig(Base):
    """Search configuration for the scraper.

    Defines what jobs to search for: keywords, location, remote preference, etc.
    The scraper loads enabled configs and runs searches for each.
    """

    __tablename__ = "search_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    search_term: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    distance: Mapped[int] = mapped_column(Integer, default=50)
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    hours_old: Mapped[int] = mapped_column(Integer, default=48)
    results_wanted: Mapped[int] = mapped_column(Integer, default=100)
    country: Mapped[str] = mapped_column(String(10), default="USA")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
