"""HireWire Scraper - Main entry point.

This module orchestrates the job scraping workflow:
1. Load configuration
2. Initialize database connection
3. Fetch jobs from enabled sources (JobSpy, ATS APIs)
4. Normalize and deduplicate
5. Insert new jobs, update last_seen for existing
6. Mark stale jobs as inactive
"""

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from .config import settings
from .db import Database, DatabaseConnectionError
from .dedup import Deduplicator, normalize_jobs
from .models.raw_job import RawJob
from .scrapers import JobSpyScraper, ScrapingError


@dataclass
class SiteResult:
    """Result from scraping a single site."""

    site: str
    attempted: bool = False
    success: bool = False
    count: int = 0
    error: str | None = None


@dataclass
class ScrapeResult:
    """Result from the entire scraping run."""

    success: bool = True
    new_jobs: int = 0
    updated_jobs: int = 0
    duration_ms: int = 0
    site_results: list[SiteResult] = field(default_factory=list)
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
        enabled_sources=settings.enabled_sources_list,
        jobspy_sites=settings.jobspy_sites_list,
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
        # STEP 2: Load search configurations from database
        # =====================================================================
        search_configs = await db.get_enabled_search_configs()
        tracked_companies = await db.get_enabled_tracked_companies()

        if not search_configs and not tracked_companies:
            log.warning(
                "no_search_configs",
                message="No enabled search configs or tracked companies found",
            )

        log.info(
            "configs_loaded",
            search_configs=len(search_configs),
            tracked_companies=len(tracked_companies),
        )

        # =====================================================================
        # STEP 3: Scrape from all enabled sources
        # =====================================================================
        raw_jobs: list[RawJob] = []

        # 3a. Scrape from JobSpy (Indeed/Glassdoor/LinkedIn)
        # Track results per site
        if "jobspy" in settings.enabled_sources_list and search_configs:
            # Initialize per-site results
            for site in settings.jobspy_sites_list:
                result.site_results.append(SiteResult(site=site, attempted=True))

            try:
                scraper = JobSpyScraper(
                    sites=settings.jobspy_sites_list,
                    search_configs=search_configs,
                )
                jobs = await scraper.fetch()
                raw_jobs.extend(jobs)

                # Count jobs per site from source_site field
                site_counts: dict[str, int] = {}
                for job in jobs:
                    site = job.source_site.lower()
                    site_counts[site] = site_counts.get(site, 0) + 1

                # Update site results
                for site_result in result.site_results:
                    count = site_counts.get(site_result.site, 0)
                    site_result.count = count
                    site_result.success = True  # No error means success
                    if count == 0:
                        # Site returned nothing - might be rate limited
                        site_result.error = "No results (may be rate limited)"

                log.info("jobspy_scrape_complete", count=len(jobs), per_site=site_counts)

            except ScrapingError as e:
                # Mark all sites as failed
                for site_result in result.site_results:
                    site_result.success = False
                    site_result.error = str(e)
                log.error("jobspy_scrape_failed", error=str(e))

            except Exception as e:
                # Mark all sites as failed
                error_msg = f"Unexpected: {str(e)}"
                for site_result in result.site_results:
                    site_result.success = False
                    site_result.error = error_msg
                log.exception("jobspy_unexpected_error", error=str(e))

        # 3b. TODO: Add Ashby scraper when tracked_companies are configured
        # This would iterate over tracked_companies with ats_type == "ashby"

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

        # Check if any sites had errors
        any_success = any(sr.success for sr in result.site_results)
        result.success = any_success  # Partial success is still success

        log.info(
            "scraper_complete",
            duration_ms=duration_ms,
            site_results=[
                {"site": sr.site, "success": sr.success, "count": sr.count, "error": sr.error}
                for sr in result.site_results
            ],
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
