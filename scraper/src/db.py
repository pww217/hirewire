"""Database operations for HireWire scraper.

Uses asyncpg for async PostgreSQL operations.
"""

from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
import structlog

from .models.job import Job, JobSource, TrackedCompany

log = structlog.get_logger()


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""

    pass


class Database:
    """Database interface for scraper operations.

    Uses asyncpg connection pool for efficient async database access.
    """

    def __init__(self, database_url: str):
        """Initialize database with connection URL.

        Args:
            database_url: PostgreSQL connection string
        """
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(
        self, min_size: int = 2, max_size: int = 10
    ) -> None:
        """Establish connection pool.

        Args:
            min_size: Minimum number of connections in pool
            max_size: Maximum number of connections in pool

        Raises:
            DatabaseConnectionError: If connection fails
        """
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=min_size,
                max_size=max_size,
                command_timeout=30,
            )
            # Test connection
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            log.info("database_pool_created", min_size=min_size, max_size=max_size)
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to connect to database: {e}")

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            log.info("database_pool_closed")

    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    # =========================================================================
    # Configuration queries
    # =========================================================================

    async def get_enabled_tracked_companies(self) -> list[TrackedCompany]:
        """Get all enabled tracked companies with ATS configuration."""
        query = """
            SELECT id, name, website, ats_type, ats_identifier,
                   last_scraped, enabled
            FROM tracked_companies
            WHERE enabled = true
              AND ats_type IS NOT NULL
              AND ats_identifier IS NOT NULL
            ORDER BY id
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [TrackedCompany(**dict(row)) for row in rows]

    # =========================================================================
    # Deduplication queries
    # =========================================================================

    async def get_existing_hashes(self, hashes: list[str]) -> set[str]:
        """Check which hashes already exist in database.

        Args:
            hashes: List of dedup_hash values to check

        Returns:
            Set of hashes that exist in database
        """
        if not hashes:
            return set()

        query = """
            SELECT dedup_hash
            FROM jobs
            WHERE dedup_hash = ANY($1::text[])
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, hashes)
            return {row["dedup_hash"] for row in rows}

    # =========================================================================
    # Insert/Update queries
    # =========================================================================

    async def insert_jobs(self, jobs: list[Job]) -> int:
        """Insert new jobs into database.

        Uses a transaction to insert job + sources atomically.

        Args:
            jobs: List of Job objects to insert

        Returns:
            Number of jobs inserted
        """
        if not jobs:
            return 0

        inserted = 0

        async with self.transaction() as conn:
            for job in jobs:
                try:
                    # Insert job
                    job_id = await conn.fetchval(
                        """
                        INSERT INTO jobs (
                            dedup_hash,
                            company_id,
                            title,
                            company,
                            company_url,
                            location_raw,
                            location_city,
                            location_state,
                            location_country,
                            is_remote,
                            description,
                            job_url,
                            job_type,
                            salary_min,
                            salary_max,
                            salary_interval,
                            date_posted,
                            first_seen,
                            last_seen,
                            company_size,
                            company_industry,
                            is_active
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22
                        )
                        ON CONFLICT (dedup_hash) DO NOTHING
                        RETURNING id
                        """,
                        job.dedup_hash,
                        job.company_id,
                        job.title,
                        job.company,
                        job.company_url,
                        job.location_raw,
                        job.location_city,
                        job.location_state,
                        job.location_country,
                        job.is_remote,
                        job.description,
                        job.job_url,
                        job.job_type,
                        job.salary_min,
                        job.salary_max,
                        job.salary_interval,
                        job.date_posted,
                        job.first_seen,
                        job.last_seen,
                        job.company_size,
                        job.company_industry,
                        job.is_active,
                    )

                    if job_id:
                        # Insert sources
                        for source in job.sources:
                            await conn.execute(
                                """
                                INSERT INTO job_sources (job_id, source, source_site, external_id)
                                VALUES ($1, $2, $3, $4)
                                ON CONFLICT (job_id, source, source_site) DO NOTHING
                                """,
                                job_id,
                                source.source,
                                source.source_site,
                                source.external_id,
                            )
                        inserted += 1

                except Exception as e:
                    log.error(
                        "job_insert_failed",
                        dedup_hash=job.dedup_hash,
                        error=str(e),
                    )
                    # Continue with other jobs - don't fail entire batch
                    continue

        return inserted

    async def update_last_seen_batch(self, hashes: set[str]) -> int:
        """Update last_seen timestamp for existing jobs.

        Args:
            hashes: Set of dedup_hash values to update

        Returns:
            Number of rows updated
        """
        if not hashes:
            return 0

        query = """
            UPDATE jobs
            SET last_seen = NOW()
            WHERE dedup_hash = ANY($1::text[])
        """

        async with self.pool.acquire() as conn:
            result = await conn.execute(query, list(hashes))
            # Result is like "UPDATE 42"
            count = int(result.split()[-1])
            return count

    async def add_job_source(
        self, dedup_hash: str, source: JobSource
    ) -> bool:
        """Add a source to an existing job if not already present.

        Args:
            dedup_hash: Job's dedup hash
            source: Source to add

        Returns:
            True if source was added, False if already exists
        """
        query = """
            INSERT INTO job_sources (job_id, source, source_site, external_id)
            SELECT j.id, $2::VARCHAR(50), $3::VARCHAR(50), $4::VARCHAR(255)
            FROM jobs j
            WHERE j.dedup_hash = $1
              AND NOT EXISTS (
                  SELECT 1 FROM job_sources js
                  WHERE js.job_id = j.id
                    AND js.source = $2::VARCHAR(50)
                    AND js.source_site = $3::VARCHAR(50)
              )
            RETURNING id
        """

        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                query,
                dedup_hash,
                source.source,
                source.source_site,
                source.external_id,
            )
            return result is not None

    async def add_sources_batch(
        self, jobs: list[Job], existing_hashes: set[str]
    ) -> int:
        """Add sources for jobs that already exist in the database.

        When we find a job that's already in the DB but came from a different
        source, we want to track that additional source.

        Args:
            jobs: List of jobs (may include existing ones)
            existing_hashes: Set of hashes that exist in DB

        Returns:
            Number of sources added
        """
        added = 0

        for job in jobs:
            if job.dedup_hash in existing_hashes:
                for source in job.sources:
                    if await self.add_job_source(job.dedup_hash, source):
                        added += 1

        return added

    # =========================================================================
    # Maintenance queries
    # =========================================================================

    async def mark_stale_jobs_inactive(self, days: int = 14) -> int:
        """Mark jobs as inactive if not seen in N days.

        Args:
            days: Number of days without last_seen update to consider stale

        Returns:
            Number of jobs marked inactive
        """
        query = f"""
            UPDATE jobs
            SET is_active = false
            WHERE is_active = true
              AND last_seen < NOW() - INTERVAL '{days} days'
        """

        async with self.pool.acquire() as conn:
            result = await conn.execute(query)
            # Result is like "UPDATE 42"
            count = int(result.split()[-1])
            return count

    async def get_active_external_ids_for_company(
        self, company_id: int, source: str
    ) -> set[str]:
        """Get external_ids of all active jobs for a company from a given source.

        Used for disappearance detection: compare against fresh API results
        to find jobs that have been removed.

        Args:
            company_id: Tracked company ID
            source: ATS source name ('ashby', 'greenhouse', 'lever')

        Returns:
            Set of external_id strings
        """
        query = """
            SELECT js.external_id
            FROM job_sources js
            JOIN jobs j ON j.id = js.job_id
            WHERE j.company_id = $1
              AND js.source = $2
              AND j.is_active = true
              AND js.external_id IS NOT NULL
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, company_id, source)
            return {row["external_id"] for row in rows}

    async def deactivate_jobs_by_external_ids(
        self, company_id: int, source: str, external_ids: list[str]
    ) -> int:
        """Mark specific jobs as inactive (they disappeared from ATS).

        Args:
            company_id: Tracked company ID
            source: ATS source name
            external_ids: List of external_ids to deactivate

        Returns:
            Number of jobs deactivated
        """
        if not external_ids:
            return 0

        query = """
            UPDATE jobs
            SET is_active = false
            WHERE company_id = $1
              AND is_active = true
              AND id IN (
                  SELECT js.job_id
                  FROM job_sources js
                  WHERE js.source = $2
                    AND js.external_id = ANY($3::text[])
              )
        """

        async with self.pool.acquire() as conn:
            result = await conn.execute(query, company_id, source, external_ids)
            return int(result.split()[-1])

    async def update_company_after_scrape(
        self, company_id: int, job_count: int
    ) -> None:
        """Update last_scraped timestamp and job count for a tracked company.

        Args:
            company_id: ID of the tracked company
            job_count: Current number of active jobs found
        """
        query = """
            UPDATE tracked_companies
            SET last_scraped = NOW(),
                job_count = $2
            WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            await conn.execute(query, company_id, job_count)

    async def is_rating_stale(self, company_id: int, stale_days: int = 7) -> bool:
        """Check if a company's Glassdoor rating needs refreshing."""
        query = """
            SELECT rating_updated_at
            FROM tracked_companies
            WHERE id = $1
        """
        async with self.pool.acquire() as conn:
            ts = await conn.fetchval(query, company_id)
            if ts is None:
                return True
            from datetime import datetime, timezone, timedelta
            return datetime.now(timezone.utc) - ts > timedelta(days=stale_days)

    async def update_glassdoor_rating(
        self,
        company_id: int,
        glassdoor_id: int,
        rating: float | None,
        glassdoor_url: str,
    ) -> None:
        """Persist Glassdoor rating data for a tracked company."""
        query = """
            UPDATE tracked_companies
            SET glassdoor_id = $2,
                glassdoor_rating = $3,
                glassdoor_url = $4,
                rating_updated_at = NOW()
            WHERE id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, company_id, glassdoor_id, rating, glassdoor_url)

    # =========================================================================
    # Statistics queries
    # =========================================================================

    async def get_job_counts(self) -> dict[str, int]:
        """Get job counts for logging/metrics.

        Returns:
            Dictionary with total, active, and inactive counts
        """
        query = """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_active = true) as active,
                COUNT(*) FILTER (WHERE is_active = false) as inactive
            FROM jobs
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query)
            return {
                "total": row["total"],
                "active": row["active"],
                "inactive": row["inactive"],
            }
