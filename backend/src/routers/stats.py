"""Stats endpoint for dashboard metrics.

Implements:
- GET /api/stats - Get dashboard statistics
"""

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.job import Job, JobSource
from ..schemas.stats import SourceStats, StatsResponse

router = APIRouter(tags=["stats"])
log = structlog.get_logger()


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """Get dashboard statistics.

    Returns:
        Dashboard statistics including job counts and sources
    """
    log.info("get_stats_request")

    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    # Total active jobs
    total_result = await db.execute(
        select(func.count(Job.id)).where(Job.is_active == True)  # noqa: E712
    )
    total_jobs = total_result.scalar() or 0

    # Jobs added in last 24 hours
    jobs_24h_result = await db.execute(
        select(func.count(Job.id)).where(
            Job.is_active == True,  # noqa: E712
            Job.first_seen >= last_24h,
        )
    )
    jobs_last_24h = jobs_24h_result.scalar() or 0

    # Jobs added in last 7 days
    jobs_7d_result = await db.execute(
        select(func.count(Job.id)).where(
            Job.is_active == True,  # noqa: E712
            Job.first_seen >= last_7d,
        )
    )
    jobs_last_7d = jobs_7d_result.scalar() or 0

    # Jobs by source
    source_result = await db.execute(
        select(JobSource.source_site, func.count(JobSource.id))
        .where(JobSource.source_site.isnot(None))
        .group_by(JobSource.source_site)
        .order_by(func.count(JobSource.id).desc())
    )
    jobs_by_source = [
        SourceStats(source=source, count=count)
        for source, count in source_result
        if source
    ]

    # Last job added
    last_job_result = await db.execute(
        select(Job.first_seen)
        .where(Job.is_active == True)  # noqa: E712
        .order_by(Job.first_seen.desc())
        .limit(1)
    )
    last_job_row = last_job_result.first()
    last_job_added = last_job_row[0] if last_job_row else None

    return StatsResponse(
        total_jobs=total_jobs,
        jobs_last_24h=jobs_last_24h,
        jobs_last_7d=jobs_last_7d,
        jobs_by_source=jobs_by_source,
        last_job_added=last_job_added,
    )
