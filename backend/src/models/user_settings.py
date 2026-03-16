"""SQLAlchemy model for user settings.

Models match the PostgreSQL schema defined in shared/schema.sql.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import ARRAY, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class UserSettings(Base):
    """User settings model.

    Stores user preferences including excluded companies/keywords and default filters.
    Currently single-user (id=1), but designed for multi-user support.
    """

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    preferred_locations: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default="{}"
    )
    title_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default="{}"
    )
    description_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default="{}"
    )
    excluded_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default="{}"
    )
    default_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    posted_after: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    min_glassdoor_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    job_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
