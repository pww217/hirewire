"""Favorite, hide, and seen endpoints for jobs.

Implements:
- POST /api/jobs/{id}/favorite - Add job to favorites
- DELETE /api/jobs/{id}/favorite - Remove job from favorites
- POST /api/jobs/{id}/hide - Hide job from results
- DELETE /api/jobs/{id}/hide - Unhide job
- POST /api/jobs/{id}/seen - Mark a single job as seen
- POST /api/jobs/seen/all - Bulk mark all (or company-scoped) jobs as seen
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.job import Application, Job, UserJobState
from ..schemas.job import ApplyResponse, FavoriteResponse, HideResponse, SeenResponse


class SeenBatchRequest(BaseModel):
    """Request body for batch-seen endpoint."""

    job_ids: list[int]

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
    log.debug("add_favorite_request", job_id=job_id)

    # Verify job exists
    await get_job_or_404(db, job_id)

    # Get or create user state
    state = await get_or_create_user_state(db, job_id)

    # Update favorite status
    state.is_favorite = True
    state.favorited_at = datetime.now(timezone.utc)

    await db.flush()

    log.debug("add_favorite_success", job_id=job_id)

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
    log.debug("remove_favorite_request", job_id=job_id)

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

    log.debug("remove_favorite_success", job_id=job_id)

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
    log.debug("hide_job_request", job_id=job_id)

    # Verify job exists
    await get_job_or_404(db, job_id)

    # Get or create user state
    state = await get_or_create_user_state(db, job_id)

    # Update hidden status
    state.is_hidden = True
    state.hidden_at = datetime.now(timezone.utc)

    await db.flush()

    log.debug("hide_job_success", job_id=job_id)

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
    log.debug("unhide_job_request", job_id=job_id)

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

    log.debug("unhide_job_success", job_id=job_id)

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
    log.debug("mark_seen_request", job_id=job_id)

    await get_job_or_404(db, job_id)

    state = await get_or_create_user_state(db, job_id)

    if not state.is_seen:
        state.is_seen = True
        state.seen_at = datetime.now(timezone.utc)
        await db.flush()

    log.debug("mark_seen_success", job_id=job_id)

    return SeenResponse(
        id=job_id,
        is_seen=True,
        seen_at=state.seen_at,
    )


@router.delete("/jobs/{job_id}/seen", response_model=SeenResponse)
async def mark_unseen(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> SeenResponse:
    """Mark a job as unseen (unread) by the user."""
    await get_job_or_404(db, job_id)
    state = await get_or_create_user_state(db, job_id)

    if state.is_seen:
        state.is_seen = False
        state.seen_at = None
        await db.flush()

    return SeenResponse(
        id=job_id,
        is_seen=False,
        seen_at=None,
    )


@router.post("/jobs/seen/all")
async def mark_all_seen(
    company_id: int | None = Query(None, description="Scope to a specific company; omit for all jobs"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Bulk-mark all active non-hidden jobs as seen.

    Args:
        company_id: Optional company ID to scope the operation

    Returns:
        Count of newly marked jobs
    """
    log.info("mark_all_seen_request", company_id=company_id)

    now = datetime.now(timezone.utc)

    # Gather job IDs that are active and not hidden, scoped by company if provided
    job_query = (
        select(Job.id)
        .outerjoin(UserJobState, Job.id == UserJobState.job_id)
        .where(Job.is_active == True)  # noqa: E712
        .where(
            or_(
                UserJobState.is_hidden.is_(False),
                UserJobState.is_hidden.is_(None),
            )
        )
        .where(
            or_(
                UserJobState.is_seen.is_(False),
                UserJobState.is_seen.is_(None),
            )
        )
    )
    if company_id is not None:
        job_query = job_query.where(Job.company_id == company_id)

    result = await db.execute(job_query)
    job_ids = [row[0] for row in result]

    if not job_ids:
        return {"marked_count": 0}

    # Upsert user_job_state rows: set is_seen=True for all matching jobs
    for jid in job_ids:
        state_result = await db.execute(
            select(UserJobState).where(UserJobState.job_id == jid)
        )
        state = state_result.scalar_one_or_none()
        if state is None:
            state = UserJobState(job_id=jid, is_favorite=False, is_hidden=False, is_seen=True, seen_at=now)
            db.add(state)
        elif not state.is_seen:
            state.is_seen = True
            state.seen_at = now

    await db.flush()

    log.info("mark_all_seen_success", company_id=company_id, marked_count=len(job_ids))
    return {"marked_count": len(job_ids)}


@router.post("/jobs/seen/batch")
async def mark_seen_batch(
    body: SeenBatchRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Bulk-mark a specific set of job IDs as seen in a single query.

    Uses a PostgreSQL upsert so it is safe to call even if state rows
    don't exist yet for some of the jobs.
    """
    if not body.job_ids:
        return {"marked_count": 0}

    log.debug("mark_seen_batch_request", count=len(body.job_ids))
    now = datetime.now(timezone.utc)

    stmt = (
        pg_insert(UserJobState)
        .values([
            {"job_id": jid, "is_favorite": False, "is_hidden": False, "is_seen": True, "seen_at": now}
            for jid in body.job_ids
        ])
        .on_conflict_do_update(
            index_elements=["job_id"],
            set_={"is_seen": True, "seen_at": now},
        )
    )
    await db.execute(stmt)
    await db.flush()

    log.debug("mark_seen_batch_success", count=len(body.job_ids))
    return {"marked_count": len(body.job_ids)}


@router.post("/jobs/{job_id}/apply", response_model=ApplyResponse)
async def apply_to_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> ApplyResponse:
    """Mark a job as applied to.

    Creates an application record with status 'applied'.
    Idempotent — returns existing record if already applied.
    """
    log.info("apply_job_request", job_id=job_id)
    await get_job_or_404(db, job_id)

    result = await db.execute(
        select(Application).where(Application.job_id == job_id)
    )
    application = result.scalar_one_or_none()

    if application is None:
        application = Application(
            job_id=job_id,
            status="applied",
            applied_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(application)
        await db.flush()

    log.info("apply_job_success", job_id=job_id)
    return ApplyResponse(id=job_id, is_applied=True, applied_at=application.applied_at)


@router.delete("/jobs/{job_id}/apply", response_model=ApplyResponse)
async def unapply_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> ApplyResponse:
    """Remove an application record for a job."""
    log.info("unapply_job_request", job_id=job_id)
    await get_job_or_404(db, job_id)

    result = await db.execute(
        select(Application).where(Application.job_id == job_id)
    )
    application = result.scalar_one_or_none()

    if application is not None:
        await db.delete(application)
        await db.flush()

    log.info("unapply_job_success", job_id=job_id)
    return ApplyResponse(id=job_id, is_applied=False, applied_at=None)
