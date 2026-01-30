# HireWire - Scraper Service

> Design specification for the scraper container that fetches, normalizes, and stores job listings.

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Container Design](#container-design)
- [Execution Flow](#execution-flow)
- [Integration Contracts](#integration-contracts)
- [Deduplication Strategy](#deduplication-strategy)
- [Database Interaction](#database-interaction)
- [Configuration](#configuration)
- [Error Handling](#error-handling)
- [Logging and Observability](#logging-and-observability)
- [Scheduling](#scheduling)

## Overview

The scraper runs as a Kubernetes CronJob, executing every 2 hours to fetch new job listings from multiple sources.

**Current Implementation**: JobSpy (Indeed/Glassdoor)

> **Note**: Ashby API integration is documented below but not yet implemented (Phase 3). The current scraper only uses JobSpy.

```mermaid
flowchart LR
    subgraph cronjob [K8s CronJob]
        Main[main.py]
        JobSpyScraper[JobSpy Scraper]
        AshbyScraper[Ashby Scraper]
        Normalizer[Normalizer]
        Dedup[Deduplicator]
        DBWriter[DB Writer]
    end
    
    JobSpy[JobSpy API] --> JobSpyScraper
    Ashby[Ashby API] --> AshbyScraper
    
    Main --> JobSpyScraper
    Main --> AshbyScraper
    JobSpyScraper --> Normalizer
    AshbyScraper --> Normalizer
    Normalizer --> Dedup
    Dedup --> DBWriter
    DBWriter --> Postgres[(PostgreSQL)]
```

## Architecture

### Container Structure

```
hirewire-scraper/
├── Dockerfile
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration loading
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py          # Base scraper class
│   │   ├── jobspy.py        # JobSpy integration
│   │   └── ashby.py         # Ashby API
│   ├── models/
│   │   ├── __init__.py
│   │   ├── raw_job.py       # RawJob from scrapers
│   │   └── job.py           # Normalized Job for DB
│   ├── normalizer.py        # Normalize to common schema
│   ├── dedup.py             # Deduplication logic
│   └── db.py                # Database operations
└── tests/
    └── ...
```

## Container Design

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/

# Run as non-root
RUN useradd -m scraper
USER scraper

ENTRYPOINT ["python", "-m", "src.main"]
```

### requirements.txt

```
python-jobspy>=1.1.0
httpx>=0.25.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
structlog>=23.0.0
tenacity>=8.2.0
```

## Execution Flow

### Complete Flow Diagram

```mermaid
flowchart TB
    Start([Start]) --> LoadEnv[Load Environment Variables]
    LoadEnv --> ConnectDB[Connect to Database]
    ConnectDB --> ConnectFail{Connection OK?}
    ConnectFail -->|No| ExitFatal([Exit Code 1])
    ConnectFail -->|Yes| LoadConfig[Load Search Configs from DB]
    
    LoadConfig --> ConfigCheck{Configs Found?}
    ConfigCheck -->|No| LogWarn[Log Warning: No configs]
    ConfigCheck -->|Yes| InitScrapers[Initialize Scrapers]
    LogWarn --> InitScrapers
    
    InitScrapers --> FetchLoop[For Each Source]
    FetchLoop --> FetchJobs[Fetch Jobs]
    FetchJobs --> FetchOK{Fetch OK?}
    FetchOK -->|No| LogError[Log Error, Continue]
    FetchOK -->|Yes| Accumulate[Add to raw_jobs list]
    LogError --> NextSource{More Sources?}
    Accumulate --> NextSource
    NextSource -->|Yes| FetchLoop
    NextSource -->|No| CheckResults{Any Jobs?}
    
    CheckResults -->|No| LogNoJobs[Log: No jobs fetched]
    CheckResults -->|Yes| Normalize[Normalize Jobs]
    LogNoJobs --> Cleanup
    
    Normalize --> Dedup[Check Duplicates Against DB]
    Dedup --> HasNew{New Jobs?}
    HasNew -->|No| UpdateLastSeen[Update last_seen for existing]
    HasNew -->|Yes| InsertJobs[Insert New Jobs]
    UpdateLastSeen --> Cleanup
    InsertJobs --> Cleanup
    
    Cleanup[Update Scrape Timestamps]
    Cleanup --> LogSummary[Log Summary Metrics]
    LogSummary --> Exit([Exit Code 0])
```

### Step-by-Step Execution

#### 1. Startup Phase

```python
# src/main.py
import sys
import asyncio
import structlog
from datetime import datetime

from src.config import Settings, load_settings
from src.db import Database, DatabaseConnectionError
from src.scrapers.jobspy import JobSpyScraper
from src.scrapers.ashby import AshbyScraper
from src.normalizer import normalize_jobs
from src.dedup import Deduplicator
from src.models.raw_job import RawJob

log = structlog.get_logger()

async def main() -> int:
    """Main entry point. Returns exit code."""
    start_time = datetime.utcnow()
    
    # ─────────────────────────────────────────────────────────
    # STEP 1: Load environment configuration
    # ─────────────────────────────────────────────────────────
    try:
        settings = load_settings()
        log.info("config_loaded",
            enabled_sources=settings.enabled_sources,
            jobspy_sites=settings.jobspy_sites,
            log_level=settings.log_level,
        )
    except Exception as e:
        log.error("config_load_failed", error=str(e))
        return 1
    
    # ─────────────────────────────────────────────────────────
    # STEP 2: Connect to database
    # ─────────────────────────────────────────────────────────
    try:
        db = Database(settings.database_url)
        await db.connect()
        log.info("database_connected")
    except DatabaseConnectionError as e:
        log.error("database_connection_failed", error=str(e))
        return 1
    
    try:
        # ─────────────────────────────────────────────────────
        # STEP 3: Load search configurations from DB
        # ─────────────────────────────────────────────────────
        search_configs = await db.get_enabled_search_configs()
        tracked_companies = await db.get_enabled_tracked_companies()
        
        if not search_configs and not tracked_companies:
            log.warning("no_search_configs",
                message="No enabled search configs or tracked companies found"
            )
        
        log.info("configs_loaded",
            search_configs=len(search_configs),
            tracked_companies=len(tracked_companies),
        )
        
        # ─────────────────────────────────────────────────────
        # STEP 4: Scrape from all sources
        # ─────────────────────────────────────────────────────
        raw_jobs: list[RawJob] = []
        scrape_results = {
            "jobspy": {"attempted": False, "success": False, "count": 0, "error": None},
            "ashby": {"attempted": False, "success": False, "count": 0, "error": None},
        }
        
        # 4a. Scrape from JobSpy (Indeed/Glassdoor)
        if "jobspy" in settings.enabled_sources and search_configs:
            scrape_results["jobspy"]["attempted"] = True
            try:
                scraper = JobSpyScraper(
                    sites=settings.jobspy_sites,
                    search_configs=search_configs,
                )
                jobs = await scraper.fetch()
                raw_jobs.extend(jobs)
                scrape_results["jobspy"]["success"] = True
                scrape_results["jobspy"]["count"] = len(jobs)
                log.info("jobspy_scrape_complete", count=len(jobs))
            except Exception as e:
                scrape_results["jobspy"]["error"] = str(e)
                log.error("jobspy_scrape_failed", error=str(e))
        
        # 4b. Scrape from Ashby (tracked companies)
        if "ashby" in settings.enabled_sources:
            ashby_companies = [c for c in tracked_companies if c.ats_type == "ashby"]
            if ashby_companies:
                scrape_results["ashby"]["attempted"] = True
                try:
                    scraper = AshbyScraper(companies=ashby_companies)
                    jobs = await scraper.fetch()
                    raw_jobs.extend(jobs)
                    scrape_results["ashby"]["success"] = True
                    scrape_results["ashby"]["count"] = len(jobs)
                    log.info("ashby_scrape_complete", count=len(jobs))
                    
                    # Update last_scraped for companies
                    for company in ashby_companies:
                        await db.update_company_last_scraped(company.id)
                except Exception as e:
                    scrape_results["ashby"]["error"] = str(e)
                    log.error("ashby_scrape_failed", error=str(e))
        
        # ─────────────────────────────────────────────────────
        # STEP 5: Normalize jobs to common schema
        # ─────────────────────────────────────────────────────
        if not raw_jobs:
            log.info("no_jobs_fetched", scrape_results=scrape_results)
        else:
            normalized_jobs = normalize_jobs(raw_jobs)
            log.info("jobs_normalized", count=len(normalized_jobs))
            
            # ─────────────────────────────────────────────────
            # STEP 6: Deduplicate against database
            # ─────────────────────────────────────────────────
            deduplicator = Deduplicator(db)
            new_jobs, existing_hashes = await deduplicator.filter_new_jobs(normalized_jobs)
            
            log.info("deduplication_complete",
                total=len(normalized_jobs),
                new=len(new_jobs),
                duplicates=len(existing_hashes),
            )
            
            # ─────────────────────────────────────────────────
            # STEP 7: Store new jobs
            # ─────────────────────────────────────────────────
            if new_jobs:
                inserted_count = await db.insert_jobs(new_jobs)
                log.info("jobs_inserted", count=inserted_count)
            
            # Update last_seen for existing jobs
            if existing_hashes:
                updated_count = await db.update_last_seen_batch(existing_hashes)
                log.info("last_seen_updated", count=updated_count)
        
        # ─────────────────────────────────────────────────────
        # STEP 8: Log summary and exit
        # ─────────────────────────────────────────────────────
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        log.info("scraper_complete",
            duration_ms=duration_ms,
            scrape_results=scrape_results,
            total_raw=len(raw_jobs),
            total_new=len(new_jobs) if raw_jobs else 0,
        )
        
        return 0
        
    finally:
        await db.disconnect()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
```

## Integration Contracts

### Input: RawJob Model

This is the model returned by scrapers before normalization.

```python
# src/models/raw_job.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal

class RawJob(BaseModel):
    """Raw job data from scraping sources before normalization.
    
    Field constraints match database VARCHAR limits to prevent insertion errors.
    """
    
    # Source identification
    source: Literal["jobspy", "ashby", "greenhouse", "lever"]
    source_site: str = Field(..., max_length=50)
    external_id: Optional[str] = Field(None, max_length=255)
    
    # Core fields (required)
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=255)
    job_url: str = Field(..., min_length=1, max_length=1000)
    
    # Optional fields
    company_url: Optional[str] = Field(None, max_length=500)
    
    # Location (raw from source)
    location_raw: Optional[str] = Field(None, max_length=255)
    location_city: Optional[str] = Field(None, max_length=100)
    location_state: Optional[str] = Field(None, max_length=100)
    location_country: Optional[str] = Field(None, max_length=100)
    is_remote: bool = False
    
    # Details
    description: Optional[str] = None
    job_type: Optional[Literal["full_time", "part_time", "contract", "internship"]] = None
    
    # Salary
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_interval: Optional[Literal["yearly", "monthly", "weekly", "daily", "hourly"]] = None
    
    # Dates
    date_posted: Optional[datetime] = None
    
    # Company metadata (from JobSpy)
    company_size: Optional[str] = Field(None, max_length=50)
    company_industry: Optional[str] = Field(None, max_length=100)
    
    class Config:
        extra = "ignore"  # Ignore extra fields from sources
```

**Example RawJob from JobSpy (Indeed)**:

```json
{
  "source": "jobspy",
  "source_site": "indeed",
  "external_id": "https://www.indeed.com/viewjob?jk=abc123",
  "title": "Marketing Manager",
  "company": "TechStartup Inc",
  "company_url": "https://www.techstartup.com",
  "job_url": "https://www.indeed.com/viewjob?jk=abc123",
  "location_raw": "Seattle, WA",
  "location_city": "Seattle",
  "location_state": "WA",
  "location_country": "USA",
  "is_remote": false,
  "description": "We are looking for a marketing manager...",
  "job_type": "full_time",
  "salary_min": 80000.0,
  "salary_max": 120000.0,
  "salary_interval": "yearly",
  "date_posted": "2026-01-27T00:00:00Z",
  "company_size": "51-200",
  "company_industry": "Technology"
}
```

**Example RawJob from Ashby**:

```json
{
  "source": "ashby",
  "source_site": "ashby",
  "external_id": "job_abc123xyz",
  "title": "Content Marketing Lead",
  "company": "Notion",
  "company_url": null,
  "job_url": "https://jobs.ashbyhq.com/notion/job_abc123xyz",
  "location_raw": "San Francisco, CA",
  "location_city": "San Francisco",
  "location_state": "CA",
  "location_country": "USA",
  "is_remote": true,
  "description": "<p>Join our team as a Content Marketing Lead...</p>",
  "job_type": null,
  "salary_min": 150000.0,
  "salary_max": 200000.0,
  "salary_interval": "yearly",
  "date_posted": "2026-01-28T00:00:00Z",
  "company_size": null,
  "company_industry": null
}
```

### Output: Job Model (Database Schema)

This model matches the `jobs` table in `api-backend.md`.

```python
# src/models/job.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class JobSource(BaseModel):
    """Source information for a job.
    
    Matches job_sources table in api-backend.md.
    """
    source: Literal["jobspy", "ashby", "greenhouse", "lever"]
    source_site: str = Field(..., max_length=50)
    external_id: Optional[str] = Field(None, max_length=255)

class Job(BaseModel):
    """Normalized job ready for database insertion.
    
    Schema matches api-backend.md jobs table exactly.
    Field constraints match database VARCHAR limits.
    """
    
    # Deduplication
    dedup_hash: str = Field(..., min_length=32, max_length=32)
    
    # Core fields
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=255)
    company_url: Optional[str] = Field(None, max_length=500)
    
    # Location (normalized)
    location_raw: Optional[str] = Field(None, max_length=255)
    location_city: Optional[str] = Field(None, max_length=100)
    location_state: Optional[str] = Field(None, max_length=100)
    location_country: Optional[str] = Field(None, max_length=100)
    is_remote: bool = False
    
    # Job details
    description: Optional[str] = None  # TEXT, no limit
    job_url: str = Field(..., min_length=1, max_length=1000)
    job_type: Optional[Literal["full_time", "part_time", "contract", "internship"]] = None
    
    # Salary
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_interval: Optional[Literal["yearly", "monthly", "weekly", "daily", "hourly"]] = None
    
    # Dates (all UTC)
    date_posted: Optional[datetime] = None
    first_seen: datetime = Field(default_factory=lambda: datetime.utcnow())
    last_seen: datetime = Field(default_factory=lambda: datetime.utcnow())
    
    # Company metadata
    company_size: Optional[str] = Field(None, max_length=50)
    company_industry: Optional[str] = Field(None, max_length=100)
    
    # Status
    is_active: bool = True
    
    # Sources (for job_sources table)
    sources: List[JobSource]
```

**Example Job (Normalized, Ready for DB)**:

```json
{
  "dedup_hash": "a1b2c3d4e5f6789012345678901234ab",
  "title": "Marketing Manager",
  "company": "TechStartup Inc",
  "company_url": "https://www.techstartup.com",
  "location_raw": "Seattle, WA",
  "location_city": "Seattle",
  "location_state": "WA",
  "location_country": "USA",
  "is_remote": false,
  "description": "We are looking for a marketing manager...",
  "job_url": "https://www.indeed.com/viewjob?jk=abc123",
  "job_type": "full_time",
  "salary_min": 80000.0,
  "salary_max": 120000.0,
  "salary_interval": "yearly",
  "date_posted": "2026-01-27T00:00:00Z",
  "first_seen": "2026-01-28T14:30:00Z",
  "last_seen": "2026-01-28T14:30:00Z",
  "company_size": "51-200",
  "company_industry": "Technology",
  "is_active": true,
  "sources": [
    {
      "source": "jobspy",
      "source_site": "indeed",
      "external_id": "https://www.indeed.com/viewjob?jk=abc123"
    }
  ]
}
```

### SearchConfig Model (From Database)

Matches `search_configs` table in `api-backend.md`.

```python
# src/models/search_config.py
from pydantic import BaseModel

class SearchConfig(BaseModel):
    """Search configuration from database."""
    
    id: int                      # Integer, PK
    name: str                    # String(100), not null
    search_term: str             # String(500), not null
    location: str | None = None  # String(255)
    distance: int = 50           # Integer, default 50
    is_remote: bool = False      # Boolean, default False
    hours_old: int = 48          # Integer, default 48
    results_wanted: int = 100    # Integer, default 100
    country: str = "USA"         # String(10), default "USA"
    enabled: bool = True         # Boolean, default True
    
    class Config:
        from_attributes = True
```

### TrackedCompany Model (From Database)

Matches `tracked_companies` table in `api-backend.md`.

```python
# src/models/tracked_company.py
from pydantic import BaseModel
from datetime import datetime

class TrackedCompany(BaseModel):
    """Tracked company from database."""
    
    id: int                            # Integer, PK
    name: str                          # String(255), not null
    website: str | None = None         # String(500)
    ats_type: str | None = None        # String(50): greenhouse, lever, ashby
    ats_identifier: str | None = None  # String(255)
    last_scraped: datetime | None = None  # DateTime
    enabled: bool = True               # Boolean, default True
    
    class Config:
        from_attributes = True
```

## Deduplication Strategy

### Hash Algorithm

Deduplication uses SHA-256 hash truncated to 32 hex chars for better collision resistance:

```python
# src/dedup.py
import hashlib
import re
from typing import Tuple, List, Set
from src.models.raw_job import RawJob
from src.models.job import Job

# Common company suffixes to strip for normalization
COMPANY_SUFFIXES = re.compile(r'\b(inc|llc|ltd|corp|co|company|incorporated|limited)\.?\b', re.IGNORECASE)

def generate_dedup_hash(company: str, title: str, location: str | None) -> str:
    """Generate SHA-256 hash for deduplication.
    
    Hash is based on: company + title + location (normalized)
    This catches the same job posted on multiple sites.
    
    Returns:
        32-character hex string (SHA-256 truncated)
    """
    # Normalize inputs
    company_norm = (company or "").lower().strip()
    title_norm = (title or "").lower().strip()
    location_norm = (location or "").lower().strip()
    
    # Remove common company suffixes and punctuation
    # "TechCorp, Inc." -> "techcorp"
    company_norm = COMPANY_SUFFIXES.sub("", company_norm)
    company_norm = re.sub(r'[,.\-]', ' ', company_norm)
    company_norm = ' '.join(company_norm.split())  # Normalize whitespace
    
    # Combine with delimiter
    combined = f"{company_norm}|{title_norm}|{location_norm}"
    
    # SHA-256 hash, truncate to 32 chars
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]
```

### Fields Used for Deduplication

| Field | Normalization | Rationale |
|-------|---------------|-----------|
| `company` | lowercase, strip, remove "Inc.", "LLC" | Same company, different formats |
| `title` | lowercase, strip | Exact title match required |
| `location` | lowercase, strip | Same job, same location |

**Not included in hash**:
- `job_url` — Different per source
- `description` — Often slightly different
- `date_posted` — Can vary by source
- `salary` — Not always present

### Deduplicator Class

```python
# src/dedup.py
from datetime import datetime, timedelta
from typing import List, Set, Tuple
from src.db import Database
from src.models.job import Job

class Deduplicator:
    """Handles job deduplication against the database."""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def filter_new_jobs(
        self, 
        jobs: List[Job]
    ) -> Tuple[List[Job], Set[str]]:
        """Filter jobs to only new ones.
        
        Args:
            jobs: List of normalized Job objects
            
        Returns:
            Tuple of (new_jobs, existing_hashes)
        """
        # Get hashes of all input jobs
        input_hashes = {job.dedup_hash for job in jobs}
        
        # Query existing hashes from DB (last 30 days)
        existing_hashes = await self.db.get_existing_hashes(
            hashes=list(input_hashes),
            days_back=30
        )
        
        # Partition into new vs existing
        new_jobs = []
        seen_hashes: Set[str] = set()
        
        for job in jobs:
            if job.dedup_hash in existing_hashes:
                # Job exists, will update last_seen
                seen_hashes.add(job.dedup_hash)
            elif job.dedup_hash not in seen_hashes:
                # New job, add to insert list
                new_jobs.append(job)
                seen_hashes.add(job.dedup_hash)
            # else: duplicate within this batch, skip
        
        return new_jobs, existing_hashes
```

### SQL Queries for Duplicate Checking

```sql
-- Query: Get existing hashes from jobs table
-- Used by: Deduplicator.get_existing_hashes()
SELECT dedup_hash 
FROM jobs 
WHERE dedup_hash = ANY($1::text[])
  AND first_seen > NOW() - INTERVAL '30 days';

-- Parameters:
--   $1: Array of dedup_hash strings to check
```

```python
# src/db.py - Implementation
async def get_existing_hashes(
    self, 
    hashes: List[str], 
    days_back: int = 30
) -> Set[str]:
    """Check which hashes already exist in database.
    
    Args:
        hashes: List of dedup_hash values to check
        days_back: Only check jobs from last N days (default 30)
        
    Returns:
        Set of hashes that exist in database
    """
    if not hashes:
        return set()
    
    query = """
        SELECT dedup_hash 
        FROM jobs 
        WHERE dedup_hash = ANY($1::text[])
          AND first_seen > NOW() - INTERVAL '%s days'
    """ % days_back
    
    async with self.pool.acquire() as conn:
        rows = await conn.fetch(query, hashes)
        return {row["dedup_hash"] for row in rows}
```

### Handling Same Job from Multiple Sources

When the same job appears on Indeed and Glassdoor:

1. First occurrence is inserted with `sources = [{"source": "jobspy", "source_site": "indeed", ...}]`
2. Second occurrence matches hash, triggers `last_seen` update
3. **Add the new source to `job_sources` table** - this provides value to the user (shows all sites where job is posted)

**Decision**: Always add sources. This helps users see which sites have the job and provides dedup confidence.

```python
# src/db.py - Add source to existing job
async def add_job_source(self, dedup_hash: str, source: JobSource) -> bool:
    """Add a source to an existing job if not already present.
    
    Returns True if source was added, False if already exists.
    """
    query = """
        INSERT INTO job_sources (job_id, source, source_site, external_id)
        SELECT j.id, $2, $3, $4
        FROM jobs j
        WHERE j.dedup_hash = $1
          AND NOT EXISTS (
              SELECT 1 FROM job_sources js 
              WHERE js.job_id = j.id 
                AND js.source = $2 
                AND js.source_site = $3
          )
        RETURNING id
    """
    
    async with self.pool.acquire() as conn:
        result = await conn.fetchval(
            query, 
            dedup_hash, 
            source.source, 
            source.source_site, 
            source.external_id
        )
        return result is not None
```

## Database Interaction

### Connection Management

```python
# src/db.py
import asyncpg
from typing import Optional
from contextlib import asynccontextmanager

class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass

class Database:
    """Database interface for scraper operations."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self, min_size: int = 2, max_size: int = 10) -> None:
        """Establish connection pool.
        
        Raises:
            DatabaseConnectionError: If connection fails after retries
        """
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=min_size,
                max_size=max_size,
                command_timeout=30,
                # Retry connection 3 times
                connection_class=asyncpg.Connection,
            )
            # Test connection
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to connect to database: {e}")
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn
```

### INSERT Queries

```python
# src/db.py - Insert new jobs with transaction

async def insert_jobs(self, jobs: List[Job]) -> int:
    """Insert new jobs into database.
    
    Uses a transaction to insert job + sources atomically.
    
    Returns:
        Number of jobs inserted
    """
    if not jobs:
        return 0
    
    inserted = 0
    
    async with self.transaction() as conn:
        for job in jobs:
            # Insert job
            job_id = await conn.fetchval("""
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
                    await conn.execute("""
                        INSERT INTO job_sources (job_id, source, source_site, external_id)
                        VALUES ($1, $2, $3, $4)
                    """,
                        job_id,
                        source.source,
                        source.source_site,
                        source.external_id,
                    )
                inserted += 1
    
    return inserted
```

### UPDATE Queries

```python
# src/db.py - Update last_seen timestamps

async def update_last_seen_batch(self, hashes: Set[str]) -> int:
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
        return int(result.split()[-1])

async def update_company_last_scraped(self, company_id: int) -> None:
    """Update last_scraped timestamp for tracked company."""
    query = """
        UPDATE tracked_companies 
        SET last_scraped = NOW()
        WHERE id = $1
    """
    
    async with self.pool.acquire() as conn:
        await conn.execute(query, company_id)
```

### SELECT Queries

```python
# src/db.py - Read configurations

async def get_enabled_search_configs(self) -> List[SearchConfig]:
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

async def get_enabled_tracked_companies(self) -> List[TrackedCompany]:
    """Get all enabled tracked companies."""
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
```

### Transaction Handling

All job insertions use transactions to ensure atomicity:

```python
async def insert_jobs(self, jobs: List[Job]) -> int:
    """Atomically insert jobs with their sources."""
    async with self.transaction() as conn:
        # If any insert fails, entire batch rolls back
        for job in jobs:
            job_id = await conn.fetchval(...)  # INSERT job
            if job_id:
                for source in job.sources:
                    await conn.execute(...)    # INSERT source
```

**Rollback scenarios**:
- Database constraint violation (e.g., duplicate hash race condition)
- Connection lost mid-transaction
- Any exception within transaction block

### Job Staleness Handling

Jobs that haven't been seen in 14 days are marked `is_active = false`. This prevents showing jobs that have been filled or removed.

**Strategy**: Run staleness check at the end of each scrape cycle.

```python
# src/db.py - Mark stale jobs as inactive
async def mark_stale_jobs_inactive(self, days: int = 14) -> int:
    """Mark jobs as inactive if not seen in N days.
    
    Args:
        days: Number of days without last_seen update to consider stale
        
    Returns:
        Number of jobs marked inactive
    """
    query = """
        UPDATE jobs 
        SET is_active = false
        WHERE is_active = true
          AND last_seen < NOW() - INTERVAL '%s days'
        RETURNING id
    """
    
    async with self.pool.acquire() as conn:
        result = await conn.fetch(query % days)
        return len(result)
```

**Scraper calls at end of each run**:
```python
# In main.py, after all jobs processed
stale_count = await db.mark_stale_jobs_inactive(days=14)
if stale_count > 0:
    log.info("stale_jobs_deactivated", count=stale_count)
```

**API filters by default**: All job list queries filter `WHERE is_active = true` unless explicitly requested otherwise.

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `ENABLED_SOURCES` | No | `jobspy,ashby` | Comma-separated list of sources |
| `JOBSPY_SITES` | No | `indeed,glassdoor` | Sites for JobSpy to scrape |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | No | `json` | Log format (json, console) |
| `SCRAPE_TIMEOUT_SECONDS` | No | `300` | Max time for entire scrape operation |
| `HTTP_TIMEOUT_SECONDS` | No | `30` | Timeout for HTTP requests to ATS APIs |
| `DB_POOL_MIN_SIZE` | No | `2` | Minimum database connections |
| `DB_POOL_MAX_SIZE` | No | `10` | Maximum database connections |

### Config Class

```python
# src/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # Database
    database_url: str
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10
    
    # Sources
    enabled_sources: List[str] = ["jobspy", "ashby"]
    jobspy_sites: List[str] = ["indeed", "glassdoor"]
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Timeouts
    scrape_timeout_seconds: int = 300
    http_timeout_seconds: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            if field_name in ("enabled_sources", "jobspy_sites"):
                return [s.strip() for s in raw_val.split(",")]
            return raw_val

def load_settings() -> Settings:
    """Load and validate settings from environment."""
    return Settings()
```

### Database-Driven Search Configs

Search configurations are stored in the `search_configs` table and managed via the web UI. The scraper reads these at startup.

**Table Schema** (from api-backend.md):

```sql
CREATE TABLE search_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    search_term VARCHAR(500) NOT NULL,
    location VARCHAR(255),
    distance INTEGER DEFAULT 50,
    is_remote BOOLEAN DEFAULT FALSE,
    hours_old INTEGER DEFAULT 48,
    results_wanted INTEGER DEFAULT 100,
    country VARCHAR(10) DEFAULT 'USA',
    enabled BOOLEAN DEFAULT TRUE
);
```

**Example Seed Data**:

```sql
INSERT INTO search_configs (name, search_term, location, distance, is_remote, hours_old, results_wanted, country)
VALUES 
    ('SEO Remote', '"SEO" OR "search engine optimization"', 'United States', 0, true, 48, 100, 'USA'),
    ('Marketing Seattle', '"marketing manager" OR "content marketing"', 'Seattle, WA', 50, false, 48, 100, 'USA'),
    ('Analytics Remote', '"analytics" OR "data analyst" marketing', 'United States', 0, true, 48, 100, 'USA');
```

### Tracked Companies Schema

**Table Schema** (from api-backend.md):

```sql
CREATE TABLE tracked_companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    website VARCHAR(500),
    ats_type VARCHAR(50),        -- 'greenhouse', 'lever', 'ashby'
    ats_identifier VARCHAR(255), -- Company slug for ATS API
    last_scraped TIMESTAMP,
    enabled BOOLEAN DEFAULT TRUE
);
```

**Example Seed Data**:

```sql
INSERT INTO tracked_companies (name, website, ats_type, ats_identifier)
VALUES 
    ('Notion', 'https://notion.so', 'ashby', 'notion'),
    ('OpenAI', 'https://openai.com', 'ashby', 'openai'),
    ('Duolingo', 'https://duolingo.com', 'ashby', 'duolingo');
```

## Error Handling

### Error Hierarchy

```python
# src/exceptions.py

class ScraperError(Exception):
    """Base exception for scraper errors."""
    pass

class ConfigurationError(ScraperError):
    """Configuration loading failed."""
    pass

class DatabaseConnectionError(ScraperError):
    """Database connection failed."""
    pass

class ScrapingError(ScraperError):
    """Error during scraping operation."""
    def __init__(self, source: str, message: str):
        self.source = source
        super().__init__(f"[{source}] {message}")

class RateLimitError(ScrapingError):
    """Rate limited by source."""
    def __init__(self, source: str, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(source, f"Rate limited, retry after {retry_after}s")

class NormalizationError(ScraperError):
    """Error normalizing job data."""
    pass
```

### Retry Logic with Tenacity

```python
# src/scrapers/base.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import httpx

class BaseScraper:
    """Base class for all scrapers with retry logic."""
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def _fetch_with_retry(self, url: str, **kwargs) -> httpx.Response:
        """Fetch URL with automatic retry on transient errors."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, **kwargs)
            
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(self.source_name, retry_after)
            
            response.raise_for_status()
            return response
```

### Graceful Degradation

The scraper continues even if one source fails:

```python
# src/main.py (excerpt)

# Track results per source
scrape_results = {}

for source in settings.enabled_sources:
    scrape_results[source] = {
        "attempted": True,
        "success": False,
        "count": 0,
        "error": None,
    }
    
    try:
        scraper = get_scraper(source)
        jobs = await scraper.fetch()
        raw_jobs.extend(jobs)
        scrape_results[source]["success"] = True
        scrape_results[source]["count"] = len(jobs)
    except RateLimitError as e:
        log.warning("source_rate_limited",
            source=source,
            retry_after=e.retry_after,
        )
        scrape_results[source]["error"] = f"Rate limited: {e.retry_after}s"
    except ScrapingError as e:
        log.error("source_scrape_failed",
            source=source,
            error=str(e),
        )
        scrape_results[source]["error"] = str(e)
    except Exception as e:
        log.exception("source_unexpected_error",
            source=source,
            error=str(e),
        )
        scrape_results[source]["error"] = f"Unexpected: {str(e)}"

# Continue with whatever jobs we got
if raw_jobs:
    # Normalize, dedupe, store...
    pass

# Final log includes success/failure per source
log.info("scraper_complete",
    scrape_results=scrape_results,
    total_jobs=len(raw_jobs),
)
```

### Exit Codes

| Exit Code | Meaning |
|-----------|---------|
| 0 | Success (even if 0 new jobs) |
| 1 | Fatal error (config or DB connection failed) |

Partial failures (one source down) still exit 0 as long as the process completes.

## Logging and Observability

### Structured Log Format

All logs use JSON format for easy parsing by Loki/Grafana:

```python
# src/logging_config.py
import structlog
import logging
import sys

def configure_logging(log_level: str = "INFO", log_format: str = "json"):
    """Configure structured logging."""
    
    # Determine processors based on format
    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Set root logger level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
```

### Log Events

**Startup Events**:

```json
{"event": "config_loaded", "enabled_sources": ["jobspy", "ashby"], "log_level": "INFO", "timestamp": "2026-01-28T14:30:00Z", "level": "info"}
{"event": "database_connected", "timestamp": "2026-01-28T14:30:01Z", "level": "info"}
{"event": "configs_loaded", "search_configs": 3, "tracked_companies": 5, "timestamp": "2026-01-28T14:30:01Z", "level": "info"}
```

**Scraping Events**:

```json
{"event": "jobspy_scrape_complete", "count": 147, "timestamp": "2026-01-28T14:31:30Z", "level": "info"}
{"event": "ashby_scrape_complete", "count": 23, "timestamp": "2026-01-28T14:31:45Z", "level": "info"}
{"event": "source_scrape_failed", "source": "ashby", "error": "Connection timeout", "timestamp": "2026-01-28T14:31:50Z", "level": "error"}
```

**Processing Events**:

```json
{"event": "jobs_normalized", "count": 170, "timestamp": "2026-01-28T14:31:50Z", "level": "info"}
{"event": "deduplication_complete", "total": 170, "new": 42, "duplicates": 128, "timestamp": "2026-01-28T14:31:51Z", "level": "info"}
{"event": "jobs_inserted", "count": 42, "timestamp": "2026-01-28T14:31:52Z", "level": "info"}
{"event": "last_seen_updated", "count": 128, "timestamp": "2026-01-28T14:31:52Z", "level": "info"}
```

**Completion Event**:

```json
{
  "event": "scraper_complete",
  "duration_ms": 112000,
  "scrape_results": {
    "jobspy": {"attempted": true, "success": true, "count": 147, "error": null},
    "ashby": {"attempted": true, "success": true, "count": 23, "error": null}
  },
  "total_raw": 170,
  "total_new": 42,
  "timestamp": "2026-01-28T14:32:00Z",
  "level": "info"
}
```

### Key Metrics to Emit

These metrics can be scraped from logs by Loki or pushed to Prometheus Pushgateway:

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `hirewire_scraper_duration_seconds` | gauge | - | Total scrape duration |
| `hirewire_jobs_fetched_total` | counter | `source` | Jobs fetched per source |
| `hirewire_jobs_new_total` | counter | - | New jobs inserted |
| `hirewire_jobs_duplicate_total` | counter | - | Duplicate jobs skipped |
| `hirewire_scraper_errors_total` | counter | `source`, `error_type` | Errors per source |
| `hirewire_scraper_success` | gauge | - | 1 if successful, 0 if failed |

**Metric Log Format** (for Loki parsing):

```python
# Emit metrics as structured logs
log.info("metric",
    metric_name="hirewire_jobs_fetched_total",
    metric_type="counter",
    value=147,
    labels={"source": "jobspy"},
)
```

### Alerting

Add to existing Prometheus alerting rules:

```yaml
# prometheus/rules/hirewire.yaml
groups:
  - name: hirewire
    rules:
      - alert: HireWireScraperFailed
        expr: |
          time() - max(kube_cronjob_status_last_successful_time{cronjob="hirewire-scraper"}) > 14400
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "HireWire scraper hasn't succeeded in 4+ hours"
          description: "Check CronJob logs for errors"
      
      - alert: HireWireScraperNoNewJobs
        expr: |
          sum(increase(hirewire_jobs_new_total[24h])) == 0
        for: 1h
        labels:
          severity: info
        annotations:
          summary: "HireWire hasn't found new jobs in 24 hours"
          description: "May indicate scraping issues or search configs too narrow"
```

## Scheduling

### K8s CronJob Spec

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: hirewire-scraper
  namespace: hirewire
spec:
  schedule: "0 */2 * * *"           # Every 2 hours
  concurrencyPolicy: Forbid          # Don't run if previous still running
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  startingDeadlineSeconds: 600       # Miss deadline after 10 min
  jobTemplate:
    spec:
      activeDeadlineSeconds: 900     # Kill after 15 min
      backoffLimit: 2                # Retry twice on failure
      template:
        metadata:
          labels:
            app: hirewire-scraper
        spec:
          restartPolicy: Never
          serviceAccountName: hirewire-scraper
          containers:
            - name: scraper
              image: ghcr.io/pwilson/hirewire-scraper:latest
              imagePullPolicy: Always
              envFrom:
                - secretRef:
                    name: hirewire-db-credentials
              env:
                - name: ENABLED_SOURCES
                  value: "jobspy,ashby"
                - name: JOBSPY_SITES
                  value: "indeed,glassdoor"
                - name: LOG_LEVEL
                  value: "INFO"
                - name: LOG_FORMAT
                  value: "json"
              resources:
                requests:
                  cpu: 100m
                  memory: 256Mi
                limits:
                  cpu: 500m
                  memory: 512Mi
```

### Database Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: hirewire-db-credentials
  namespace: hirewire
type: Opaque
stringData:
  DATABASE_URL: "postgresql://hirewire:password@hirewire-postgres:5432/hirewire"
```
