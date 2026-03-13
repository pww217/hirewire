"""Job listing and detail endpoints.

Implements:
- GET /api/jobs/all - Bulk fetch all active jobs with descriptions (client-side filtering)
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
from ..models.company import TrackedCompany
from ..models.job import Application, Job, JobSource, UserJobState
from ..schemas.job import (
    CompanySize,
    JobBulkResponse,
    JobDetailResponse,
    JobListResponse,
    JobResponse,
    JobType,
    JobWithDescription,
)

router = APIRouter(tags=["jobs"])
log = structlog.get_logger()

# Valid sort fields
SortField = Literal["date_posted", "first_seen", "company", "title"]
SortOrder = Literal["asc", "desc"]


def build_job_query(
    q: str | None = None,
    company_id: int | None = None,
    location: str | None = None,
    is_remote: bool | None = None,
    company_size: list[str] | None = None,
    job_type: str | None = None,
    source: str | None = None,
    posted_after: datetime | None = None,
    include_hidden: bool = False,
    hidden_only: bool = False,
    favorites_only: bool = False,
    applied_only: bool = False,
    preferred_locations: list[str] | None = None,
    included_keywords: list[str] | None = None,
    excluded_keywords: list[str] | None = None,
) -> Select:
    """Build the job listing query with all filters.

    Args:
        q: Full-text search query
        location: Location filter (city/state) — explicit override
        is_remote: Remote jobs only filter
        company_size: Company size filter (list)
        job_type: Job type filter
        source: Source filter
        posted_after: Filter jobs posted after date
        include_hidden: Include hidden jobs
        favorites_only: Only show favorites
        preferred_locations: Default location list from settings (OR'd together)
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

    # Company filter - scope jobs to a single tracked company
    if company_id is not None:
        query = query.where(Job.company_id == company_id)

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

    # Location filter — explicit query param takes precedence over preferred_locations
    if location:
        query = query.where(or_(
            Job.location_city.ilike(f"%{location}%"),
            Job.location_state.ilike(f"%{location}%"),
            Job.location_raw.ilike(f"%{location}%"),
        ))
    elif preferred_locations:
        # OR across all preferred locations
        location_clauses = []
        for loc in preferred_locations:
            location_clauses.append(Job.location_city.ilike(f"%{loc}%"))
            location_clauses.append(Job.location_state.ilike(f"%{loc}%"))
            location_clauses.append(Job.location_raw.ilike(f"%{loc}%"))
        query = query.where(or_(*location_clauses))

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

    # Hidden only — show ONLY hidden jobs (for the Hidden view)
    if hidden_only:
        query = query.where(UserJobState.is_hidden == True)  # noqa: E712

    # Favorites only filter
    if favorites_only:
        query = query.where(UserJobState.is_favorite == True)  # noqa: E712

    # Applied only — show only jobs with an application record
    if applied_only:
        applied_subquery = select(Application.job_id)
        query = query.where(Job.id.in_(applied_subquery))

    # Included keywords filter — title must match at least one (OR)
    if included_keywords:
        query = query.where(or_(*[Job.title.ilike(f"%{kw}%") for kw in included_keywords]))

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


async def get_glassdoor_info(
    db: AsyncSession, company_ids: list[int]
) -> dict[int, tuple[float | None, str | None]]:
    """Get Glassdoor rating and URL for a set of company IDs.

    Returns:
        Dict mapping company_id to (glassdoor_rating, glassdoor_url)
    """
    if not company_ids:
        return {}

    unique_ids = list(set(cid for cid in company_ids if cid is not None))
    if not unique_ids:
        return {}

    result = await db.execute(
        select(TrackedCompany.id, TrackedCompany.glassdoor_rating, TrackedCompany.glassdoor_url)
        .where(TrackedCompany.id.in_(unique_ids))
    )
    return {row[0]: (float(row[1]) if row[1] is not None else None, row[2]) for row in result}


# Keep backward-compat alias
async def get_glassdoor_ratings(
    db: AsyncSession, company_ids: list[int]
) -> dict[int, float]:
    info = await get_glassdoor_info(db, company_ids)
    return {cid: rating for cid, (rating, _url) in info.items() if rating is not None}


async def get_application_ids(
    db: AsyncSession, job_ids: list[int]
) -> set[int]:
    """Return set of job IDs that have an application record."""
    if not job_ids:
        return set()
    result = await db.execute(
        select(Application.job_id).where(Application.job_id.in_(job_ids))
    )
    return {row[0] for row in result}


async def get_user_states(
    db: AsyncSession, job_ids: list[int]
) -> dict[int, tuple[bool, bool, bool]]:
    """Get user state (favorite/hidden/seen) for a list of jobs.

    Args:
        db: Database session
        job_ids: List of job IDs

    Returns:
        Dict mapping job_id to (is_favorite, is_hidden, is_seen) tuple
    """
    if not job_ids:
        return {}

    result = await db.execute(
        select(
            UserJobState.job_id,
            UserJobState.is_favorite,
            UserJobState.is_hidden,
            UserJobState.is_seen,
        ).where(UserJobState.job_id.in_(job_ids))
    )

    return {row.job_id: (row.is_favorite, row.is_hidden, row.is_seen) for row in result}


@router.get("/jobs/all", response_model=JobBulkResponse)
async def list_all_jobs(
    db: AsyncSession = Depends(get_db),
) -> JobBulkResponse:
    """Return all active, non-hidden jobs with descriptions for client-side filtering.

    No pagination or filtering — the full dataset is returned in one response.
    The frontend loads this once on mount and filters/searches entirely in memory.
    """
    log.debug("list_all_jobs_request")

    query = (
        select(Job)
        .outerjoin(UserJobState, Job.id == UserJobState.job_id)
        .where(Job.is_active == True)  # noqa: E712
        .where(
            or_(
                UserJobState.is_hidden.is_(False),
                UserJobState.is_hidden.is_(None),
            )
        )
        .order_by(Job.date_posted.desc().nulls_last())
    )

    result = await db.execute(query)
    jobs = list(result.scalars().all())

    job_ids = [job.id for job in jobs]
    sources_map = await get_job_sources(db, job_ids)
    states_map = await get_user_states(db, job_ids)
    gd_map = await get_glassdoor_info(db, [j.company_id for j in jobs])
    applied_ids = await get_application_ids(db, job_ids)

    job_responses = []
    for job in jobs:
        is_favorite, is_hidden, is_seen = states_map.get(job.id, (False, False, False))
        sources = sources_map.get(job.id, [])
        gd_rating, gd_url = gd_map.get(job.company_id, (None, None))
        job_responses.append(
            JobWithDescription(
                id=job.id,
                company_id=job.company_id,
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
                is_seen=is_seen,
                description=job.description,
                glassdoor_rating=gd_rating,
                glassdoor_url=gd_url,
                is_applied=job.id in applied_ids,
            )
        )

    return JobBulkResponse(jobs=job_responses, total=len(job_responses))


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    q: str | None = Query(None, description="Search query. Use commas for OR (e.g., 'python, java' matches either)"),
    company_id: int | None = Query(None, description="Filter jobs by tracked company ID"),
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
    hidden_only: bool = Query(False, description="Only show hidden jobs"),
    favorites_only: bool = Query(False, description="Only show favorites"),
    applied_only: bool = Query(False, description="Only show jobs with an application"),
    preferred_locations: list[str] | None = Query(
        None, description="Preferred locations from settings (OR filter)"
    ),
    included_keywords: list[str] | None = Query(
        None, description="Title must contain at least one of these keywords (OR filter)"
    ),
    excluded_keywords: list[str] | None = Query(
        None, description="Keywords to exclude from job titles"
    ),
) -> JobListResponse:
    """List jobs with filters and pagination.

    Supports full-text search, location filtering, company size filtering,
    exclusion filters, and various sorting options.
    """
    log.debug(
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
        company_id=company_id,
        location=location,
        is_remote=is_remote,
        company_size=company_size,
        job_type=job_type,
        source=source,
        posted_after=posted_after,
        include_hidden=include_hidden or hidden_only,
        hidden_only=hidden_only,
        favorites_only=favorites_only,
        applied_only=applied_only,
        preferred_locations=preferred_locations,
        included_keywords=included_keywords,
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

    # Get sources, user states, Glassdoor info, and application IDs for all jobs
    job_ids = [job.id for job in jobs]
    sources_map = await get_job_sources(db, job_ids)
    states_map = await get_user_states(db, job_ids)
    gd_map = await get_glassdoor_info(db, [j.company_id for j in jobs])
    applied_ids = await get_application_ids(db, job_ids)

    # Build response
    job_responses = []
    for job in jobs:
        is_favorite, is_hidden, is_seen = states_map.get(job.id, (False, False, False))
        sources = sources_map.get(job.id, [])
        gd_rating, gd_url = gd_map.get(job.company_id, (None, None))

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
                is_seen=is_seen,
                glassdoor_rating=gd_rating,
                glassdoor_url=gd_url,
                is_applied=job.id in applied_ids,
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
    log.debug("get_job_request", job_id=job_id)

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
    is_seen = job.user_state.is_seen if job.user_state else False

    # Glassdoor info
    gd_rating = None
    gd_url = None
    if job.company_id:
        gd_info = await get_glassdoor_info(db, [job.company_id])
        gd_rating, gd_url = gd_info.get(job.company_id, (None, None))

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
        is_seen=is_seen,
        application=application,
        glassdoor_rating=gd_rating,
        glassdoor_url=gd_url,
        is_applied=application is not None,
    )


