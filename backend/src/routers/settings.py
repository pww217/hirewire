"""User settings endpoints.

Implements:
- GET /api/settings - Get current user settings
- PUT /api/settings - Update user settings
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user_settings import UserSettings
from ..schemas.user_settings import UserSettingsResponse, UserSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])
log = structlog.get_logger()

# Single-user app - always use settings id=1
SETTINGS_ID = 1


async def get_or_create_settings(db: AsyncSession) -> UserSettings:
    """Get or create the user settings row.

    Args:
        db: Database session

    Returns:
        UserSettings instance
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.id == SETTINGS_ID)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # Create default settings
        settings = UserSettings(
            id=SETTINGS_ID,
            preferred_locations=[],
            included_keywords=[],
            excluded_keywords=[],
            default_remote=False,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(settings)
        await db.flush()

    return settings


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
) -> UserSettingsResponse:
    """Get current user settings.

    Returns:
        Current user settings
    """
    log.info("get_settings_request")

    settings = await get_or_create_settings(db)

    return UserSettingsResponse.model_validate(settings)


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    update: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserSettingsResponse:
    """Update user settings.

    Args:
        update: Fields to update

    Returns:
        Updated user settings
    """
    log.info("update_settings_request")

    settings = await get_or_create_settings(db)

    # Update only provided fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    settings.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(settings)

    log.info("update_settings_success")

    return UserSettingsResponse.model_validate(settings)
