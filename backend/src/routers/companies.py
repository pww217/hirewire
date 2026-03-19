"""Companies CRUD and sync endpoints.

Implements:
- POST /api/companies/detect           - Detect ATS type + slug from a career page URL
- GET  /api/companies                  - List all tracked companies
- POST /api/companies                  - Add a new company to track
- GET  /api/companies/export           - Export all companies as CSV
- POST /api/companies/import           - Batch import companies from CSV
- GET  /api/companies/{id}             - Get company details
- PUT  /api/companies/{id}             - Update company
- DELETE /api/companies/{id}           - Remove company (jobs retain history, company_id set NULL)
- POST /api/companies/sync-all         - Trigger full sync of all enabled companies
- POST /api/companies/{id}/sync        - Trigger on-demand sync for a single company
- POST /api/companies/refresh-ratings  - Re-fetch Glassdoor ratings for companies missing them
"""

import csv
import io
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.company import TrackedCompany
from ..schemas.company import (
    CompanyCreate,
    CompanyDetectRequest,
    CompanyDetectResponse,
    CompanyImportResponse,
    CompanyResponse,
    CompanyUpdate,
    RefreshRatingResult,
    RefreshRatingsResponse,
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


@router.get("/export")
async def export_companies(
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export all tracked companies as a CSV file.

    Columns: name, website, ats_type, ats_identifier, enabled, job_count, last_scraped
    The ats_type + ats_identifier pair is the canonical dedup key on import.
    """
    result = await db.execute(
        select(TrackedCompany).order_by(TrackedCompany.name.asc())
    )
    companies = list(result.scalars().all())

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["name", "website", "ats_type", "ats_identifier", "enabled", "job_count", "last_scraped"],
    )
    writer.writeheader()
    for c in companies:
        writer.writerow({
            "name": c.name,
            "website": c.website or "",
            "ats_type": c.ats_type or "",
            "ats_identifier": c.ats_identifier or "",
            "enabled": str(c.enabled).lower(),
            "job_count": c.job_count,
            "last_scraped": c.last_scraped.isoformat() if c.last_scraped else "",
        })

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"hirewire-companies-{date_str}.csv"
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_VALID_ATS_TYPES = {"greenhouse", "lever", "ashby"}


@router.post("/import", response_model=CompanyImportResponse)
async def import_companies(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> CompanyImportResponse:
    """Batch import tracked companies from a CSV file.

    Deduplicates by (ats_type, ats_identifier) -- rows matching an existing
    company are skipped. Rows missing ats_type or ats_identifier are rejected.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")  # handle BOM from Excel
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    required_cols = {"name", "ats_type", "ats_identifier"}
    missing_cols = required_cols - {f.strip().lower() for f in reader.fieldnames}
    if missing_cols:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required columns: {', '.join(sorted(missing_cols))}",
        )

    rows: list[dict] = [
        {k.strip().lower(): v.strip() for k, v in row.items() if k}
        for row in reader
    ]

    errors: list[str] = []
    to_insert: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()

    for i, row in enumerate(rows, start=2):  # row 1 = header
        name = row.get("name", "").strip()
        ats_type = row.get("ats_type", "").strip().lower()
        ats_identifier = row.get("ats_identifier", "").strip().lower()

        if not name:
            errors.append(f"Row {i}: missing name")
            continue
        if not ats_type:
            errors.append(f"Row {i} ({name}): missing ats_type")
            continue
        if ats_type not in _VALID_ATS_TYPES:
            errors.append(f"Row {i} ({name}): invalid ats_type '{ats_type}' (must be greenhouse, lever, or ashby)")
            continue
        if not ats_identifier:
            errors.append(f"Row {i} ({name}): missing ats_identifier")
            continue

        key = (ats_type, ats_identifier)
        if key in seen_keys:
            errors.append(f"Row {i} ({name}): duplicate in file, skipped")
            continue
        seen_keys.add(key)

        enabled_raw = row.get("enabled", "true").strip().lower()
        enabled = enabled_raw not in ("false", "0", "no")

        to_insert.append({
            "name": name,
            "website": row.get("website") or None,
            "ats_type": ats_type,
            "ats_identifier": ats_identifier,
            "enabled": enabled,
        })

    skipped = 0
    imported = 0

    if to_insert:
        # Fetch existing (ats_type, ats_identifier) pairs in one query
        keys = [(r["ats_type"], r["ats_identifier"]) for r in to_insert]
        existing_result = await db.execute(
            select(TrackedCompany.ats_type, TrackedCompany.ats_identifier).where(
                tuple_(TrackedCompany.ats_type, TrackedCompany.ats_identifier).in_(keys)
            )
        )
        existing_keys = {(row[0], row[1]) for row in existing_result.all()}

        for r in to_insert:
            key = (r["ats_type"], r["ats_identifier"])
            if key in existing_keys:
                skipped += 1
                continue
            db.add(TrackedCompany(
                name=r["name"],
                website=r["website"],
                ats_type=r["ats_type"],
                ats_identifier=r["ats_identifier"],
                enabled=r["enabled"],
            ))
            imported += 1

        await db.commit()

    log.info("company_import", imported=imported, skipped=skipped, errors=len(errors))
    return CompanyImportResponse(imported=imported, skipped=skipped, errors=errors)


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


@router.post("/refresh-ratings", response_model=RefreshRatingsResponse)
async def refresh_missing_ratings(
    db: AsyncSession = Depends(get_db),
) -> RefreshRatingsResponse:
    """Re-fetch Glassdoor ratings for all enabled companies that currently have none.

    Only targets companies where glassdoor_rating IS NULL, so it won't re-hit
    companies that already have a rating. Uses adaptive delays between lookups —
    backs off significantly after consecutive failures to avoid triggering
    Glassdoor rate limits.
    """
    import asyncio
    import random
    from scraper.src.glassdoor import lookup_company_rating
    from scraper.src.db import Database as ScraperDB

    query = select(TrackedCompany).where(
        TrackedCompany.enabled == True,  # noqa: E712
        TrackedCompany.glassdoor_rating == None,  # noqa: E711
    )
    result = await db.execute(query)
    companies = list(result.scalars().all())

    # Shuffle to avoid always hitting the same companies first
    random.shuffle(companies)

    log.info("refresh_ratings_start", missing_count=len(companies))

    results: list[RefreshRatingResult] = []
    refreshed = 0
    consecutive_failures = 0
    BASE_DELAY = 5.0

    from scraper.src.config import settings as scraper_settings
    scraper_db = ScraperDB(scraper_settings.database_url)
    await scraper_db.connect()
    try:  # noqa: SIM105
        for i, company in enumerate(companies):
            if i > 0:
                # Adaptive delay: back off after consecutive failures
                delay = BASE_DELAY * (1.5 ** min(consecutive_failures, 4))
                jitter = delay * (0.7 + random.random() * 0.6)
                await asyncio.sleep(jitter)
            try:
                gd = await lookup_company_rating(company.name)
                if gd and gd.rating is not None:
                    await scraper_db.update_glassdoor_rating(
                        company.id, gd.glassdoor_id, gd.rating, gd.url
                    )
                    results.append(RefreshRatingResult(
                        company_id=company.id,
                        name=company.name,
                        rating=gd.rating,
                        success=True,
                    ))
                    refreshed += 1
                    consecutive_failures = 0
                    log.info(
                        "refresh_rating_success",
                        company=company.name,
                        rating=gd.rating,
                    )
                else:
                    if gd:
                        await scraper_db.update_glassdoor_info(
                            company.id, gd.glassdoor_id, gd.url
                        )
                    results.append(RefreshRatingResult(
                        company_id=company.id,
                        name=company.name,
                        rating=None,
                        success=False,
                    ))
                    consecutive_failures += 1
                    log.warning(
                        "refresh_rating_still_missing",
                        company=company.name,
                        consecutive_failures=consecutive_failures,
                    )
            except Exception as e:
                results.append(RefreshRatingResult(
                    company_id=company.id,
                    name=company.name,
                    rating=None,
                    success=False,
                ))
                consecutive_failures += 1
                log.warning("refresh_rating_error", company=company.name, error=str(e))
    finally:
        await scraper_db.disconnect()

    still_missing = len(companies) - refreshed
    log.info(
        "refresh_ratings_complete",
        refreshed=refreshed,
        still_missing=still_missing,
    )
    return RefreshRatingsResponse(
        refreshed=refreshed,
        still_missing=still_missing,
        companies=results,
    )


@router.post("/sync-all", response_model=SyncResponse)
async def sync_all_companies() -> SyncResponse:
    """Trigger a full scrape of all enabled companies."""
    from scraper.src.main import main as scraper_main
    log.info("on_demand_sync_all")
    result = await scraper_main()
    if not result.success:
        error_detail = result.error or "Sync failed — check scraper logs for details"
        log.error("on_demand_sync_all_failed", error=error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
    log.info("on_demand_sync_all_complete", new_jobs=result.new_jobs, updated_jobs=result.updated_jobs)
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
    log.info("on_demand_sync_company", company_id=company_id, company_name=company.name)
    result = await scraper_main(company_id=company_id)
    if not result.success:
        error_detail = result.error or f"Sync failed for '{company.name}' — check scraper logs"
        if "not found" in error_detail.lower():
            raise HTTPException(status_code=404, detail=error_detail)
        log.error("on_demand_sync_company_failed", company_id=company_id, error=error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
    log.info("on_demand_sync_company_complete", company_id=company_id, new_jobs=result.new_jobs)
    return SyncResponse(
        success=result.success,
        new_jobs=result.new_jobs,
        updated_jobs=result.updated_jobs,
        duration_ms=result.duration_ms,
        error=result.error,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
