"""Companies CRUD and sync endpoints.

Implements:
- POST /api/companies/detect         - Detect ATS type + slug from a career page URL
- GET  /api/companies                - List all tracked companies
- POST /api/companies                - Add a new company to track
- GET  /api/companies/{id}           - Get company details
- PUT  /api/companies/{id}           - Update company
- DELETE /api/companies/{id}         - Remove company (jobs retain history, company_id set NULL)
- POST /api/companies/sync-all       - Trigger full sync of all enabled companies
- POST /api/companies/{id}/sync      - Trigger on-demand sync for a single company
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.company import TrackedCompany
from ..schemas.company import (
    CompanyCreate,
    CompanyDetectRequest,
    CompanyDetectResponse,
    CompanyResponse,
    CompanyUpdate,
    SyncResponse,
    detect_ats_from_url,
)

router = APIRouter(prefix="/api/companies", tags=["companies"])
log = structlog.get_logger()


@router.post("/detect", response_model=CompanyDetectResponse)
async def detect_ats(body: CompanyDetectRequest) -> CompanyDetectResponse:
    """Detect ATS type and slug from a career page URL.

    Pass the company's careers/jobs page URL and this endpoint will identify
    which ATS is in use and extract the company slug for API calls.

    Returns detected=False if the URL doesn't match any known ATS pattern.
    """
    ats_type, slug = detect_ats_from_url(body.url)
    return CompanyDetectResponse(
        url=body.url,
        ats_type=ats_type,
        ats_identifier=slug,
        detected=ats_type is not None,
    )


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    db: AsyncSession = Depends(get_db),
) -> list[TrackedCompany]:
    """List all tracked companies.

    Sorted by most recently scraped (active companies with new listings first),
    then by name for companies not yet scraped.
    """
    query = select(TrackedCompany).order_by(
        TrackedCompany.last_scraped.desc().nulls_last(),
        TrackedCompany.name.asc(),
    )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    body: CompanyCreate,
    db: AsyncSession = Depends(get_db),
) -> TrackedCompany:
    """Add a new company to track.

    If you provide a URL via the /detect endpoint first, you can pass the
    detected ats_type and ats_identifier here.
    """
    # Check for duplicate name
    existing = await db.execute(
        select(TrackedCompany).where(TrackedCompany.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company '{body.name}' is already being tracked",
        )

    company = TrackedCompany(
        name=body.name,
        website=body.website,
        ats_type=body.ats_type,
        ats_identifier=body.ats_identifier,
        enabled=body.enabled,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)

    log.info("company_created", id=company.id, name=company.name, ats_type=company.ats_type)
    return company


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
) -> TrackedCompany:
    """Get a single tracked company by ID."""
    company = await db.get(TrackedCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    body: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
) -> TrackedCompany:
    """Update a tracked company's settings."""
    company = await db.get(TrackedCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(company, field, value)

    await db.commit()
    await db.refresh(company)

    log.info("company_updated", id=company_id, fields=list(updates.keys()))
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a tracked company.

    Disables the company and removes it from the tracking list.
    Existing jobs are preserved (company_id set to NULL via ON DELETE SET NULL).
    """
    company = await db.get(TrackedCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    await db.delete(company)
    await db.commit()

    log.info("company_deleted", id=company_id, name=company.name)


@router.post("/sync-all", response_model=SyncResponse)
async def sync_all_companies() -> SyncResponse:
    """Trigger a full scrape of all enabled companies."""
    from scraper.src.main import main as scraper_main
    log.info("on_demand_sync_all")
    result = await scraper_main()
    return SyncResponse(
        success=result.success,
        new_jobs=result.new_jobs,
        updated_jobs=result.updated_jobs,
        duration_ms=result.duration_ms,
        error=result.error,
        started_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/{company_id}/sync", response_model=SyncResponse)
async def sync_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """Trigger an on-demand scrape for a single company."""
    company = await db.get(TrackedCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    from scraper.src.main import main as scraper_main
    log.info("on_demand_sync_company", company_id=company_id)
    result = await scraper_main(company_id=company_id)
    if not result.success and result.error and "not found" in (result.error or "").lower():
        raise HTTPException(status_code=404, detail=result.error)
    return SyncResponse(
        success=result.success,
        new_jobs=result.new_jobs,
        updated_jobs=result.updated_jobs,
        duration_ms=result.duration_ms,
        error=result.error,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
