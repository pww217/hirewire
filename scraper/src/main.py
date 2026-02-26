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
from .models.raw_job import RawJob


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


# Configure logging on module load
configure_logging()
log = structlog.get_logger()


async def main() -> ScrapeResult:
    """Main scraper entry point.

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
        tracked_companies = await db.get_enabled_tracked_companies()

        if not tracked_companies:
            log.warning(
                "no_tracked_companies",
                message="No enabled tracked companies found -- add companies via the UI",
            )

        log.info("companies_loaded", tracked_companies=len(tracked_companies))

        # =====================================================================
        # STEP 3: Scrape from all tracked companies
        # =====================================================================
        raw_jobs: list[RawJob] = []

        # TODO (Phase 2): iterate tracked_companies and call ATS scrapers

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
    result = asyncio.run(main())
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(run_cli())
