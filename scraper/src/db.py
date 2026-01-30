"""Database operations for HireWire scraper.

Uses asyncpg for async PostgreSQL operations.
"""

from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
import structlog

from .models.job import Job, JobSource, SearchConfig, TrackedCompany

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

    async def get_enabled_search_configs(self) -> list[SearchConfig]:
        """Get all enabled search configurations."""
        query = """
            SELECT id, name, search_term, location, distance,
                   is_remote, hours_old, results_wanted, country, enabled
            FROM search_configs
            WHERE enabled = true
            ORDER BY id
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [SearchConfig(**dict(row)) for row in rows]

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
                            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
                        )
                        ON CONFLICT (dedup_hash) DO NOTHING
                        RETURNING id
                        """,
                        job.dedup_hash,
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

    async def update_company_last_scraped(self, company_id: int) -> None:
        """Update last_scraped timestamp for tracked company.

        Args:
            company_id: ID of the tracked company
        """
        query = """
            UPDATE tracked_companies
            SET last_scraped = NOW()
            WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            await conn.execute(query, company_id)

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
