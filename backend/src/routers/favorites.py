"""Favorite and hide endpoints for jobs.

Implements:
- POST /api/jobs/{id}/favorite - Add job to favorites
- DELETE /api/jobs/{id}/favorite - Remove job from favorites
- POST /api/jobs/{id}/hide - Hide job from results
- DELETE /api/jobs/{id}/hide - Unhide job
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.job import Job, UserJobState
from ..schemas.job import FavoriteResponse, HideResponse, SeenResponse

router = APIRouter(tags=["favorites"])
log = structlog.get_logger()


async def get_job_or_404(db: AsyncSession, job_id: int) -> Job:
    """Get a job by ID or raise 404.

    Args:
        db: Database session
        job_id: Job ID to find

    Returns:
        Job model instance

    Raises:
        HTTPException: 404 if job not found
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


async def get_or_create_user_state(
    db: AsyncSession, job_id: int
) -> UserJobState:
    """Get existing user state or create new one.

    Args:
        db: Database session
        job_id: Job ID

    Returns:
        UserJobState instance (existing or new)
    """
    result = await db.execute(
        select(UserJobState).where(UserJobState.job_id == job_id)
    )
    state = result.scalar_one_or_none()

    if not state:
        state = UserJobState(job_id=job_id, is_favorite=False, is_hidden=False)
        db.add(state)

    return state


@router.post("/jobs/{job_id}/favorite", response_model=FavoriteResponse)
async def add_favorite(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> FavoriteResponse:
    """Mark a job as favorite.

    Args:
        job_id: The job ID to favorite

    Returns:
        Updated favorite state

    Raises:
        HTTPException: 404 if job not found
    """
    log.info("add_favorite_request", job_id=job_id)

    # Verify job exists
    await get_job_or_404(db, job_id)

    # Get or create user state
    state = await get_or_create_user_state(db, job_id)

    # Update favorite status
    state.is_favorite = True
    state.favorited_at = datetime.now(timezone.utc)

    await db.flush()

    log.info("add_favorite_success", job_id=job_id)

    return FavoriteResponse(
        id=job_id,
        is_favorite=True,
        favorited_at=state.favorited_at,
    )


@router.delete("/jobs/{job_id}/favorite", response_model=FavoriteResponse)
async def remove_favorite(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> FavoriteResponse:
    """Remove a job from favorites.

    Args:
        job_id: The job ID to unfavorite

    Returns:
        Updated favorite state

    Raises:
        HTTPException: 404 if job not found
    """
    log.info("remove_favorite_request", job_id=job_id)

    # Verify job exists
    await get_job_or_404(db, job_id)

    # Get user state - if it doesn't exist, nothing to remove
    result = await db.execute(
        select(UserJobState).where(UserJobState.job_id == job_id)
    )
    state = result.scalar_one_or_none()

    if state:
        state.is_favorite = False
        state.favorited_at = None
        await db.flush()

    log.info("remove_favorite_success", job_id=job_id)

    return FavoriteResponse(
        id=job_id,
        is_favorite=False,
        favorited_at=None,
    )


@router.post("/jobs/{job_id}/hide", response_model=HideResponse)
async def hide_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> HideResponse:
    """Hide a job from results.

    Args:
        job_id: The job ID to hide

    Returns:
        Updated hide state

    Raises:
        HTTPException: 404 if job not found
    """
    log.info("hide_job_request", job_id=job_id)

    # Verify job exists
    await get_job_or_404(db, job_id)

    # Get or create user state
    state = await get_or_create_user_state(db, job_id)

    # Update hidden status
    state.is_hidden = True
    state.hidden_at = datetime.now(timezone.utc)

    await db.flush()

    log.info("hide_job_success", job_id=job_id)

    return HideResponse(
        id=job_id,
        is_hidden=True,
        hidden_at=state.hidden_at,
    )


@router.delete("/jobs/{job_id}/hide", response_model=HideResponse)
async def unhide_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> HideResponse:
    """Unhide a job (show in results again).

    Args:
        job_id: The job ID to unhide

    Returns:
        Updated hide state

    Raises:
        HTTPException: 404 if job not found
    """
    log.info("unhide_job_request", job_id=job_id)

    # Verify job exists
    await get_job_or_404(db, job_id)

    # Get user state - if it doesn't exist, nothing to unhide
    result = await db.execute(
        select(UserJobState).where(UserJobState.job_id == job_id)
    )
    state = result.scalar_one_or_none()

    if state:
        state.is_hidden = False
        state.hidden_at = None
        await db.flush()

    log.info("unhide_job_success", job_id=job_id)

    return HideResponse(
        id=job_id,
        is_hidden=False,
        hidden_at=None,
    )


@router.post("/jobs/{job_id}/seen", response_model=SeenResponse)
async def mark_seen(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> SeenResponse:
    """Mark a job as seen by the user.

    Args:
        job_id: The job ID to mark as seen

    Returns:
        Updated seen state

    Raises:
        HTTPException: 404 if job not found
    """
    log.info("mark_seen_request", job_id=job_id)

    await get_job_or_404(db, job_id)

    state = await get_or_create_user_state(db, job_id)

    if not state.is_seen:
        state.is_seen = True
        state.seen_at = datetime.now(timezone.utc)
        await db.flush()

    log.info("mark_seen_success", job_id=job_id)

    return SeenResponse(
        id=job_id,
        is_seen=True,
        seen_at=state.seen_at,
    )
