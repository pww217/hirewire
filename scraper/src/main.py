"""HireWire Scraper - Main entry point.

This module orchestrates the job scraping workflow:
1. Load configuration
2. Initialize database connection
3. Fetch jobs from ATS APIs (Greenhouse, Lever, Ashby)
4. Normalize and deduplicate
5. Insert new jobs, update last_seen for existing
6. Mark stale jobs as inactive
"""

import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog

from .config import settings
from .db import Database, DatabaseConnectionError
from .dedup import Deduplicator, normalize_jobs
from .glassdoor import RATING_STALE_DAYS, lookup_company_rating
from .models.raw_job import RawJob
from .scrapers import AshbyScraper, GreenhouseScraper, LeverScraper, ScrapingError


@dataclass
class ScrapeResult:
    """Result from the entire scraping run."""

    success: bool = True
    new_jobs: int = 0
    updated_jobs: int = 0
    duration_ms: int = 0
    error: str | None = None


def configure_logging() -> None:
    """Configure structured logging based on settings."""
    # Set up stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )

    # Determine renderer based on format
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


log = structlog.get_logger()


async def main(company_id: int | None = None) -> ScrapeResult:
    """Main scraper entry point.

    Args:
        company_id: If set, only scrape this specific company. Otherwise scrape all.

    Returns:
        ScrapeResult with detailed per-site results
    """
    start_time = datetime.now(timezone.utc)
    result = ScrapeResult()

    log.info(
        "scraper_starting",
        environment=settings.environment,
    )

    # =========================================================================
    # STEP 1: Connect to database
    # =========================================================================
    db = Database(settings.database_url)
    try:
        await db.connect(
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
        )
        log.info("database_connected")
    except DatabaseConnectionError as e:
        log.error("database_connection_failed", error=str(e))
        result.success = False
        result.error = f"Database connection failed: {e}"
        return result

    try:
        # =====================================================================
        # STEP 2: Load tracked companies from database
        # =====================================================================
        all_companies = await db.get_enabled_tracked_companies()

        if company_id is not None:
            tracked_companies = [c for c in all_companies if c.id == company_id]
            if not tracked_companies:
                log.warning("company_not_found_or_disabled", company_id=company_id)
        else:
            tracked_companies = all_companies

        if not tracked_companies:
            log.warning(
                "no_tracked_companies",
                message="No enabled tracked companies found -- add companies via the UI",
            )

        log.info("companies_loaded", tracked_companies=len(tracked_companies))

        # =====================================================================
        # STEP 3: Scrape from all tracked companies + disappearance detection
        # =====================================================================
        raw_jobs: list[RawJob] = []

        for company in tracked_companies:
            if not company.ats_type or not company.ats_identifier:
                log.warning(
                    "company_missing_ats_config",
                    company=company.name,
                    company_id=company.id,
                )
                continue

            ats = company.ats_type.lower()
            if ats == "ashby":
                scraper = AshbyScraper(company)
            elif ats == "greenhouse":
                scraper = GreenhouseScraper(company)
            elif ats == "lever":
                scraper = LeverScraper(company)
            else:
                log.warning("unknown_ats_type", company=company.name, ats_type=ats)
                continue

            try:
                company_jobs = await scraper.fetch()
            except ScrapingError as e:
                log.error("scraper_error", company=company.name, error=str(e))
                continue
            except Exception as e:
                log.exception("scraper_unexpected_error", company=company.name, error=str(e))
                continue

            # Disappearance detection: mark jobs inactive if not in fresh response
            fetched_ids = {j.external_id for j in company_jobs if j.external_id}
            existing_ids = await db.get_active_external_ids_for_company(company.id, ats)
            disappeared = existing_ids - fetched_ids
            if disappeared:
                deactivated = await db.deactivate_jobs_by_external_ids(
                    company.id, ats, list(disappeared)
                )
                log.info(
                    "jobs_disappeared",
                    company=company.name,
                    deactivated=deactivated,
                )

            # Update company stats
            await db.update_company_after_scrape(company.id, len(company_jobs))

            # Refresh Glassdoor rating if stale or missing
            if await db.is_rating_stale(company.id, RATING_STALE_DAYS):
                try:
                    gd = await lookup_company_rating(company.name)
                    if gd:
                        if gd.rating is not None:
                            # Full success: save rating and mark as fresh
                            await db.update_glassdoor_rating(
                                company.id, gd.glassdoor_id, gd.rating, gd.url
                            )
                        else:
                            # Found company on Glassdoor but couldn't get rating (e.g. 403).
                            # Save ID/URL but leave rating_updated_at unchanged so next
                            # sync retries rather than waiting 7 days.
                            await db.update_glassdoor_info(
                                company.id, gd.glassdoor_id, gd.url
                            )
                            log.warning(
                                "glassdoor_rating_missing",
                                company=company.name,
                                glassdoor_id=gd.glassdoor_id,
                            )
                except Exception as e:
                    log.warning("glassdoor_lookup_failed", company=company.name, error=str(e))

            raw_jobs.extend(company_jobs)

            log.info(
                "company_scraped",
                company=company.name,
                ats=ats,
                jobs=len(company_jobs),
                disappeared=len(disappeared),
            )

        # =====================================================================
        # STEP 4: Normalize and deduplicate
        # =====================================================================
        new_jobs_count = 0
        updated_jobs_count = 0
        sources_added_count = 0

        if not raw_jobs:
            log.info("no_jobs_fetched")
        else:
            # Normalize raw jobs to Job objects
            normalized_jobs = normalize_jobs(raw_jobs)
            log.info(
                "jobs_normalized",
                raw_count=len(raw_jobs),
                normalized_count=len(normalized_jobs),
            )

            # Check for duplicates against database
            deduplicator = Deduplicator(db)
            new_jobs, existing_hashes = await deduplicator.filter_new_jobs(
                normalized_jobs
            )

            log.info(
                "deduplication_complete",
                total=len(normalized_jobs),
                new=len(new_jobs),
                duplicates=len(existing_hashes),
            )

            # =================================================================
            # STEP 5: Insert new jobs
            # =================================================================
            if new_jobs:
                inserted_count = await db.insert_jobs(new_jobs)
                new_jobs_count = inserted_count
                log.info("jobs_inserted", count=inserted_count)

            # =================================================================
            # STEP 6: Update last_seen for existing jobs
            # =================================================================
            if existing_hashes:
                updated_count = await db.update_last_seen_batch(existing_hashes)
                updated_jobs_count = updated_count
                log.info("last_seen_updated", count=updated_count)

            # =================================================================
            # STEP 7: Add new sources for existing jobs
            # =================================================================
            # When a job is found from a new source, add that source
            if existing_hashes:
                added = await db.add_sources_batch(normalized_jobs, existing_hashes)
                sources_added_count = added
                if added > 0:
                    log.info("sources_added", count=added)

        # =====================================================================
        # STEP 8: Mark stale jobs as inactive
        # =====================================================================
        stale_count = await db.mark_stale_jobs_inactive(days=14)
        if stale_count > 0:
            log.info("stale_jobs_deactivated", count=stale_count)

        # =====================================================================
        # STEP 9: Build final result
        # =====================================================================
        job_counts = await db.get_job_counts()
        duration_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        result.new_jobs = new_jobs_count
        result.updated_jobs = updated_jobs_count
        result.duration_ms = duration_ms

        result.success = True

        log.info(
            "scraper_complete",
            duration_ms=duration_ms,
            total_raw=len(raw_jobs),
            total_new=new_jobs_count,
            total_updated=updated_jobs_count,
            sources_added=sources_added_count,
            stale_deactivated=stale_count,
            db_total_jobs=job_counts["total"],
            db_active_jobs=job_counts["active"],
        )

        return result

    except Exception as e:
        log.exception("scraper_fatal_error", error=str(e))
        result.success = False
        result.error = f"Fatal error: {str(e)}"
        result.duration_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )
        return result

    finally:
        await db.disconnect()


def run_cli() -> int:
    """CLI entry point that returns exit code."""
    configure_logging()
    result = asyncio.run(main())
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(run_cli())
