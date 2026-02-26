"""Job listing and detail endpoints.

Implements:
- GET /api/jobs - List jobs with filters, pagination, sorting
- GET /api/jobs/{id} - Get single job with full description
"""

from datetime import datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models.job import Application, Job, JobSource, UserJobState
from ..schemas.job import (
    CompanySize,
    JobDetailResponse,
    JobListResponse,
    JobResponse,
    JobType,
)

router = APIRouter(tags=["jobs"])
log = structlog.get_logger()

# Valid sort fields
SortField = Literal["date_posted", "first_seen", "company", "title"]
SortOrder = Literal["asc", "desc"]


def build_job_query(
    q: str | None = None,
    location: str | None = None,
    is_remote: bool | None = None,
    company_size: list[str] | None = None,
    job_type: str | None = None,
    source: str | None = None,
    posted_after: datetime | None = None,
    include_hidden: bool = False,
    favorites_only: bool = False,
    excluded_companies: list[str] | None = None,
    excluded_keywords: list[str] | None = None,
) -> Select:
    """Build the job listing query with all filters.

    Args:
        q: Full-text search query
        location: Location filter (city/state)
        is_remote: Remote jobs only filter
        company_size: Company size filter (list)
        job_type: Job type filter
        source: Source filter (indeed, linkedin, etc.)
        posted_after: Filter jobs posted after date
        include_hidden: Include hidden jobs
        favorites_only: Only show favorites
        excluded_companies: List of company names to exclude
        excluded_keywords: List of keywords to exclude from titles

    Returns:
        SQLAlchemy Select query with filters applied
    """
    # Base query - select jobs with user state
    query = (
        select(Job)
        .outerjoin(UserJobState, Job.id == UserJobState.job_id)
        .where(Job.is_active == True)  # noqa: E712
    )

    # Full-text search using PostgreSQL ts_query
    # Commas are treated as OR (any term matches)
    # Spaces within terms are AND (all words required)
    # Example: "software engineer, python developer" finds jobs matching
    #          ("software" AND "engineer") OR ("python" AND "developer")
    if q:
        # Split by comma for OR logic
        terms = [t.strip() for t in q.split(",") if t.strip()]
        if len(terms) == 1:
            # Single term - use simple plainto_tsquery
            search_query = func.plainto_tsquery("english", terms[0])
        else:
            # Multiple comma-separated terms - combine with OR
            # Build: tsquery1 || tsquery2 || tsquery3
            combined = func.plainto_tsquery("english", terms[0])
            for term in terms[1:]:
                combined = combined.op("||")(func.plainto_tsquery("english", term))
            search_query = combined
        query = query.where(Job.search_vector.op("@@")(search_query))

    # Location filter (case-insensitive partial match)
    if location:
        location_filter = or_(
            Job.location_city.ilike(f"%{location}%"),
            Job.location_state.ilike(f"%{location}%"),
            Job.location_raw.ilike(f"%{location}%"),
        )
        query = query.where(location_filter)

    # Remote filter
    if is_remote is True:
        query = query.where(Job.is_remote == True)  # noqa: E712

    # Company size filter (multiple values)
    if company_size:
        query = query.where(Job.company_size.in_(company_size))

    # Job type filter
    if job_type:
        query = query.where(Job.job_type == job_type)

    # Source filter - jobs that have this source
    if source:
        source_subquery = select(JobSource.job_id).where(
            JobSource.source_site == source
        )
        query = query.where(Job.id.in_(source_subquery))

    # Date filter
    if posted_after:
        query = query.where(Job.date_posted >= posted_after)

    # Hidden jobs filter
    if not include_hidden:
        query = query.where(
            or_(
                UserJobState.is_hidden.is_(False),
                UserJobState.is_hidden.is_(None),
            )
        )

    # Favorites only filter
    if favorites_only:
        query = query.where(UserJobState.is_favorite == True)  # noqa: E712

    # Excluded companies filter (case-insensitive)
    if excluded_companies:
        for company in excluded_companies:
            query = query.where(~Job.company.ilike(f"%{company}%"))

    # Excluded keywords filter (case-insensitive title match)
    if excluded_keywords:
        for keyword in excluded_keywords:
            query = query.where(~Job.title.ilike(f"%{keyword}%"))

    return query


def apply_sorting(query: Select, sort_by: SortField, sort_order: SortOrder) -> Select:
    """Apply sorting to query.

    Args:
        query: Base query
        sort_by: Field to sort by
        sort_order: Sort direction

    Returns:
        Query with ordering applied
    """
    sort_columns = {
        "date_posted": Job.date_posted,
        "first_seen": Job.first_seen,
        "company": Job.company,
        "title": Job.title,
    }

    column = sort_columns.get(sort_by, Job.date_posted)

    if sort_order == "asc":
        query = query.order_by(column.asc().nulls_last())
    else:
        query = query.order_by(column.desc().nulls_last())

    return query


async def get_job_sources(db: AsyncSession, job_ids: list[int]) -> dict[int, list[str]]:
    """Get source sites for a list of jobs.

    Args:
        db: Database session
        job_ids: List of job IDs

    Returns:
        Dict mapping job_id to list of source_site names
    """
    if not job_ids:
        return {}

    result = await db.execute(
        select(JobSource.job_id, JobSource.source_site)
        .where(JobSource.job_id.in_(job_ids))
        .where(JobSource.source_site.isnot(None))
    )

    sources_map: dict[int, list[str]] = {}
    for job_id, source_site in result:
        if job_id not in sources_map:
            sources_map[job_id] = []
        if source_site and source_site not in sources_map[job_id]:
            sources_map[job_id].append(source_site)

    return sources_map


async def get_user_states(
    db: AsyncSession, job_ids: list[int]
) -> dict[int, tuple[bool, bool]]:
    """Get user state (favorite/hidden) for a list of jobs.

    Args:
        db: Database session
        job_ids: List of job IDs

    Returns:
        Dict mapping job_id to (is_favorite, is_hidden) tuple
    """
    if not job_ids:
        return {}

    result = await db.execute(
        select(
            UserJobState.job_id, UserJobState.is_favorite, UserJobState.is_hidden
        ).where(UserJobState.job_id.in_(job_ids))
    )

    return {row.job_id: (row.is_favorite, row.is_hidden) for row in result}


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    q: str | None = Query(None, description="Search query. Use commas for OR (e.g., 'python, java' matches either)"),
    location: str | None = Query(None, description="Location filter"),
    is_remote: bool | None = Query(None, description="Remote jobs only"),
    company_size: list[CompanySize] | None = Query(
        None, description="Company size filter"
    ),
    job_type: JobType | None = Query(None, description="Job type filter"),
    source: str | None = Query(None, description="Source filter"),
    posted_after: datetime | None = Query(None, description="Posted after date"),
    sort_by: SortField = Query("date_posted", description="Sort field"),
    sort_order: SortOrder = Query("desc", description="Sort order"),
    include_hidden: bool = Query(False, description="Include hidden jobs"),
    favorites_only: bool = Query(False, description="Only show favorites"),
    excluded_companies: list[str] | None = Query(
        None, description="Companies to exclude from results"
    ),
    excluded_keywords: list[str] | None = Query(
        None, description="Keywords to exclude from job titles"
    ),
) -> JobListResponse:
    """List jobs with filters and pagination.

    Supports full-text search, location filtering, company size filtering,
    exclusion filters, and various sorting options.
    """
    log.info(
        "list_jobs_request",
        page=page,
        per_page=per_page,
        q=q,
        location=location,
        is_remote=is_remote,
    )

    # Build base query with filters
    query = build_job_query(
        q=q,
        location=location,
        is_remote=is_remote,
        company_size=company_size,
        job_type=job_type,
        source=source,
        posted_after=posted_after,
        include_hidden=include_hidden,
        favorites_only=favorites_only,
        excluded_companies=excluded_companies,
        excluded_keywords=excluded_keywords,
    )

    # Get total count before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    query = apply_sorting(query, sort_by, sort_order)

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    # Execute query
    result = await db.execute(query)
    jobs = list(result.scalars().all())

    # Get sources and user states for all jobs
    job_ids = [job.id for job in jobs]
    sources_map = await get_job_sources(db, job_ids)
    states_map = await get_user_states(db, job_ids)

    # Build response
    job_responses = []
    for job in jobs:
        is_favorite, is_hidden = states_map.get(job.id, (False, False))
        sources = sources_map.get(job.id, [])

        job_responses.append(
            JobResponse(
                id=job.id,
                title=job.title,
                company=job.company,
                company_url=job.company_url,
                location_raw=job.location_raw,
                location_city=job.location_city,
                location_state=job.location_state,
                location_country=job.location_country,
                is_remote=job.is_remote,
                job_url=job.job_url,
                job_type=job.job_type,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_interval=job.salary_interval,
                date_posted=job.date_posted,
                first_seen=job.first_seen,
                company_size=job.company_size,
                company_industry=job.company_industry,
                sources=sources,
                is_favorite=is_favorite,
                is_hidden=is_hidden,
            )
        )

    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    return JobListResponse(
        jobs=job_responses,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> JobDetailResponse:
    """Get a single job with full description.

    Args:
        job_id: The job ID to retrieve

    Returns:
        Full job details including description

    Raises:
        HTTPException: 404 if job not found
    """
    log.info("get_job_request", job_id=job_id)

    # Query job with user state and application
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.user_state), selectinload(Job.sources))
        .where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get application if exists
    app_result = await db.execute(
        select(Application).where(Application.job_id == job_id)
    )
    application = app_result.scalar_one_or_none()

    # Extract sources
    sources = [s.source_site for s in job.sources if s.source_site]

    # Extract user state
    is_favorite = job.user_state.is_favorite if job.user_state else False
    is_hidden = job.user_state.is_hidden if job.user_state else False

    return JobDetailResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        company_url=job.company_url,
        location_raw=job.location_raw,
        location_city=job.location_city,
        location_state=job.location_state,
        location_country=job.location_country,
        is_remote=job.is_remote,
        description=job.description,
        job_url=job.job_url,
        job_type=job.job_type,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_interval=job.salary_interval,
        date_posted=job.date_posted,
        first_seen=job.first_seen,
        last_seen=job.last_seen,
        company_size=job.company_size,
        company_industry=job.company_industry,
        sources=sources,
        is_favorite=is_favorite,
        is_hidden=is_hidden,
        application=application,
    )


