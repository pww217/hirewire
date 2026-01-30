"""Database connection and session management.

Uses SQLAlchemy 2.0 async with asyncpg for PostgreSQL connections.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    pass


def create_engine() -> AsyncEngine:
    """Create async database engine.

    Returns:
        AsyncEngine configured for the application.
    """
    # Ensure URL uses asyncpg driver
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif not url.startswith("postgresql+asyncpg://"):
        url = f"postgresql+asyncpg://{url.split('://', 1)[-1]}"

    return create_async_engine(
        url,
        echo=settings.environment == "development",
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


# Global engine instance
engine = create_engine()

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session.

    Yields:
        AsyncSession for database operations.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


