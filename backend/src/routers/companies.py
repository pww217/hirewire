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

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.company import TrackedCompany
from ..schemas.company import (
    CompanyCreate,
    CompanyDetectRequest,
    CompanyDetectResponse,
    CompanyResponse,
    CompanyUpdate,
    detect_ats_from_url,
)

router = APIRouter(prefix="/api/companies", tags=["companies"])
log = structlog.get_logger()

# Lazy import httpx to avoid startup overhead
import httpx  # noqa: E402


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


@router.post("/sync-all")
async def sync_all_companies() -> dict:
    """Trigger a full scrape of all enabled companies.

    Calls the scraper service's /trigger endpoint.
    """
    scraper_url = getattr(settings, "scraper_url", None)
    if not scraper_url:
        raise HTTPException(
            status_code=503,
            detail="Scraper service URL not configured (SCRAPER_URL env var).",
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{scraper_url}/trigger")
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Scraper service timed out")
    except httpx.RequestError as e:
        log.error("scraper_unreachable", error=str(e))
        raise HTTPException(status_code=503, detail="Scraper service unreachable")


@router.post("/{company_id}/sync")
async def sync_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger an on-demand scrape for a single company.

    Calls the scraper service's HTTP trigger endpoint. If no scraper URL is
    configured, returns an error indicating scheduled-only mode.
    """
    company = await db.get(TrackedCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    scraper_url = getattr(settings, "scraper_url", None)
    if not scraper_url:
        raise HTTPException(
            status_code=503,
            detail="Scraper service URL not configured (SCRAPER_URL env var). "
                   "Syncs happen automatically on schedule.",
        )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{scraper_url}/trigger/company/{company_id}")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Company not found in scraper")
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Scraper service timed out")
    except httpx.RequestError as e:
        log.error("scraper_unreachable", error=str(e))
        raise HTTPException(status_code=503, detail="Scraper service unreachable")
