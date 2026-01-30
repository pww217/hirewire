# HireWire - API Backend

> Design specification for the FastAPI backend service and PostgreSQL database schema.

## Contents

- [Overview](#overview)
- [Technology Stack](#technology-stack)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Request/Response Contracts](#requestresponse-contracts)
- [Filter Engine](#filter-engine)
- [Key SQL Queries](#key-sql-queries)
- [FastAPI Project Structure](#fastapi-project-structure)
- [Error Handling](#error-handling)
- [TypeScript Interfaces](#typescript-interfaces)

## Overview

The API backend serves the frontend and provides endpoints for:
- Listing and filtering jobs
- Managing favorites and hidden jobs
- Tracking applications (Phase 4)
- Managing search configurations
- Managing tracked companies

```mermaid
flowchart LR
    Frontend[Vue 3 Frontend] --> API[FastAPI]
    API --> DB[(PostgreSQL)]
    Scraper[Scraper CronJob] --> DB
    
    subgraph endpoints [API Endpoints]
        Jobs["/api/jobs"]
        Favorites["/api/favorites"]
        Settings["/api/settings"]
        Companies["/api/companies"]
        Stats["/api/stats"]
    end
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | FastAPI | Async, fast, auto OpenAPI docs |
| ORM | SQLAlchemy 2.0 | Mature, async support |
| Database | PostgreSQL 16 | Full-text search, JSON support, GIN indexes |
| Validation | Pydantic v2 | FastAPI native, type safety |
| Migrations | Alembic | SQLAlchemy integration |
| Static Files | FastAPI StaticFiles | Serve Vue 3 build |

---

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    jobs ||--o{ job_sources : "has many"
    jobs ||--o| user_job_state : "has one"
    jobs ||--o| applications : "may have"
    tracked_companies ||--o{ jobs : "source of"
    search_configs }o--o{ jobs : "found"
    
    jobs {
        int id PK
        varchar(32) dedup_hash UK
        varchar(500) title
        varchar(255) company
        varchar(500) company_url
        varchar(255) location_raw
        varchar(100) location_city
        varchar(100) location_state
        varchar(100) location_country
        boolean is_remote
        text description
        varchar(1000) job_url
        varchar(50) job_type
        decimal salary_min
        decimal salary_max
        varchar(20) salary_interval
        timestamptz date_posted
        varchar(50) company_size
        varchar(100) company_industry
        timestamptz first_seen
        timestamptz last_seen
        boolean is_active
        tsvector search_vector
    }
    
    job_sources {
        int id PK
        int job_id FK
        varchar(50) source
        varchar(50) source_site
        varchar(255) external_id
        timestamptz created_at
    }
    
    user_job_state {
        int id PK
        int job_id FK UK
        boolean is_favorite
        boolean is_hidden
        timestamptz favorited_at
        timestamptz hidden_at
    }
    
    applications {
        int id PK
        int job_id FK UK
        varchar(50) status
        text notes
        timestamptz applied_at
        timestamptz updated_at
    }
    
    tracked_companies {
        int id PK
        varchar(255) name UK
        varchar(500) website
        varchar(50) ats_type
        varchar(255) ats_identifier
        timestamptz last_scraped
        int job_count
        boolean enabled
        timestamptz created_at
    }
    
    search_configs {
        int id PK
        varchar(100) name
        varchar(500) search_term
        varchar(255) location
        int distance
        boolean is_remote
        int hours_old
        int results_wanted
        varchar(10) country
        boolean enabled
        timestamptz created_at
        timestamptz updated_at
    }
    
    user_settings {
        int id PK
        text excluded_companies
        text excluded_keywords
        varchar(255) default_location
        boolean default_remote
        timestamptz updated_at
    }
```

### Conventions

**Timestamps**: All `TIMESTAMPTZ` fields store UTC. API responses serialize as ISO 8601 with `Z` suffix (e.g., `"2026-01-28T15:30:00Z"`).

**String lengths**: VARCHAR limits match Pydantic `max_length` validators in scraper models. Data exceeding limits will fail validation before DB insertion.

### Complete Table Definitions (PostgreSQL DDL)

```sql
-- ============================================================================
-- CONVENTIONS:
-- - All timestamps are UTC (TIMESTAMPTZ)
-- - VARCHAR limits match Pydantic model validators
-- ============================================================================

-- ============================================================================
-- JOBS TABLE - Core job listings
-- ============================================================================
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    dedup_hash VARCHAR(32) NOT NULL UNIQUE,
    
    -- Core fields
    title VARCHAR(500) NOT NULL,
    company VARCHAR(255) NOT NULL,
    company_url VARCHAR(500),
    
    -- Location (normalized)
    location_raw VARCHAR(255),
    location_city VARCHAR(100),
    location_state VARCHAR(100),
    location_country VARCHAR(100) DEFAULT 'USA',
    is_remote BOOLEAN DEFAULT FALSE,
    
    -- Job details
    description TEXT,
    job_url VARCHAR(1000) NOT NULL,
    job_type VARCHAR(50),  -- 'full_time', 'part_time', 'contract', 'internship'
    
    -- Salary (normalized to yearly)
    salary_min DECIMAL(12, 2),
    salary_max DECIMAL(12, 2),
    salary_interval VARCHAR(20) DEFAULT 'yearly',  -- 'yearly', 'monthly', 'weekly', 'daily', 'hourly'
    
    -- Dates
    date_posted TIMESTAMPTZ,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    
    -- Company metadata
    company_size VARCHAR(50),  -- '1-10', '11-50', '51-200', '201-500', '501-1000', '1000+'
    company_industry VARCHAR(100),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Full-text search vector
    search_vector TSVECTOR
);

-- Indexes for jobs table
CREATE INDEX ix_jobs_dedup_hash ON jobs(dedup_hash);
CREATE INDEX ix_jobs_date_posted ON jobs(date_posted DESC);
CREATE INDEX ix_jobs_first_seen ON jobs(first_seen DESC);
CREATE INDEX ix_jobs_company ON jobs(company);
CREATE INDEX ix_jobs_location ON jobs(location_city, location_state);
CREATE INDEX ix_jobs_is_remote ON jobs(is_remote) WHERE is_remote = TRUE;
CREATE INDEX ix_jobs_company_size ON jobs(company_size);
CREATE INDEX ix_jobs_is_active ON jobs(is_active) WHERE is_active = TRUE;
CREATE INDEX ix_jobs_search_vector ON jobs USING GIN(search_vector);

-- Composite index for common filter combination
CREATE INDEX ix_jobs_active_posted ON jobs(is_active, date_posted DESC) 
    WHERE is_active = TRUE;

-- ============================================================================
-- JOB SOURCES TABLE - Track where each job was found
-- ============================================================================
CREATE TABLE job_sources (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL,       -- 'jobspy', 'greenhouse', 'lever', 'ashby'
    source_site VARCHAR(50),           -- 'indeed', 'linkedin', 'glassdoor', etc.
    external_id VARCHAR(255),          -- Source's unique ID for the job
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_job_sources_job_id ON job_sources(job_id);
CREATE INDEX ix_job_sources_source ON job_sources(source);
CREATE UNIQUE INDEX ix_job_sources_unique ON job_sources(job_id, source, source_site);

-- ============================================================================
-- USER JOB STATE TABLE - Favorites and hidden jobs
-- ============================================================================
CREATE TABLE user_job_state (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    is_favorite BOOLEAN DEFAULT FALSE,
    is_hidden BOOLEAN DEFAULT FALSE,
    favorited_at TIMESTAMPTZ,
    hidden_at TIMESTAMPTZ
);

CREATE INDEX ix_user_job_state_job_id ON user_job_state(job_id);
CREATE INDEX ix_user_job_state_favorite ON user_job_state(is_favorite) WHERE is_favorite = TRUE;
CREATE INDEX ix_user_job_state_hidden ON user_job_state(is_hidden) WHERE is_hidden = TRUE;

-- ============================================================================
-- APPLICATIONS TABLE - Track application status (Phase 4)
-- ============================================================================
CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'applied',  -- 'saved', 'applied', 'interviewing', 'offered', 'rejected', 'withdrawn'
    notes TEXT,
    applied_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_applications_job_id ON applications(job_id);
CREATE INDEX ix_applications_status ON applications(status);

-- ============================================================================
-- TRACKED COMPANIES TABLE - Companies to poll via ATS APIs
-- ============================================================================
CREATE TABLE tracked_companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    website VARCHAR(500),
    ats_type VARCHAR(50),              -- 'greenhouse', 'lever', 'ashby'
    ats_identifier VARCHAR(255),       -- Company slug for ATS API
    last_scraped TIMESTAMPTZ,
    job_count INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_tracked_companies_ats_type ON tracked_companies(ats_type);
CREATE INDEX ix_tracked_companies_enabled ON tracked_companies(enabled) WHERE enabled = TRUE;

-- ============================================================================
-- SEARCH CONFIGS TABLE - Saved search configurations for scraper
-- ============================================================================
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
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- USER SETTINGS TABLE - Global user preferences
-- ============================================================================
CREATE TABLE user_settings (
    id SERIAL PRIMARY KEY,
    excluded_companies TEXT[] DEFAULT '{}',   -- Array of company names to exclude
    excluded_keywords TEXT[] DEFAULT '{}',    -- Array of title keywords to exclude
    default_location VARCHAR(255),
    default_remote BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default settings row
INSERT INTO user_settings (id) VALUES (1);

-- ============================================================================
-- FULL-TEXT SEARCH TRIGGER
-- ============================================================================
CREATE OR REPLACE FUNCTION update_job_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.company, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER job_search_vector_update
    BEFORE INSERT OR UPDATE OF title, company, description ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_job_search_vector();
```

---

## API Endpoints

### Endpoints Overview

| Method | Endpoint | Description | Phase |
|--------|----------|-------------|-------|
| `GET` | `/api/jobs` | List jobs with filters and pagination | 1 |
| `GET` | `/api/jobs/{id}` | Get single job details | 1 |
| `POST` | `/api/sync` | Trigger manual job sync/scrape | 2 |
| `POST` | `/api/jobs/{id}/favorite` | Mark job as favorite | 2 |
| `DELETE` | `/api/jobs/{id}/favorite` | Remove from favorites | 2 |
| `POST` | `/api/jobs/{id}/hide` | Hide job from results | 2 |
| `DELETE` | `/api/jobs/{id}/hide` | Unhide job | 2 |
| `GET` | `/api/favorites` | List favorited jobs | 2 |
| `GET` | `/api/stats` | Get dashboard statistics | 1 |
| `GET` | `/api/search-configs` | List search configurations | 2 |
| `POST` | `/api/search-configs` | Create search configuration | 2 |
| `PUT` | `/api/search-configs/{id}` | Update search configuration | 2 |
| `DELETE` | `/api/search-configs/{id}` | Delete search configuration | 2 |
| `GET` | `/api/settings` | Get user settings | 2 |
| `PUT` | `/api/settings` | Update user settings | 2 |
| `GET` | `/api/companies` | List tracked companies | 3 |
| `POST` | `/api/companies` | Add tracked company | 3 |
| `DELETE` | `/api/companies/{id}` | Remove tracked company | 3 |
| `POST` | `/api/jobs/{id}/apply` | Mark as applied (create application) | 4 |
| `PUT` | `/api/jobs/{id}/application` | Update application status | 4 |
| `GET` | `/api/applications` | List all applications | 4 |
| `GET` | `/health` | Health check | 1 |

---

## Request/Response Contracts

### GET /api/jobs - List Jobs

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number (1-indexed) |
| `per_page` | int | 50 | Items per page (max 100) |
| `q` | string | null | Full-text search query |
| `location` | string | null | Location filter (city/state) |
| `is_remote` | bool | null | Remote jobs only filter |
| `company_size` | string[] | null | Company size filter (comma-separated) |
| `job_type` | string | null | Job type filter |
| `source` | string | null | Source filter (indeed, linkedin, etc.) |
| `posted_after` | datetime | null | Filter jobs posted after date |
| `sort_by` | string | "date_posted" | Sort field |
| `sort_order` | string | "desc" | Sort direction (asc/desc) |
| `include_hidden` | bool | false | Include hidden jobs |
| `favorites_only` | bool | false | Only show favorites |

**Request Example:**

```
GET /api/jobs?q=marketing&location=Seattle&is_remote=true&company_size=11-50,51-200&page=1&per_page=25
```

**Response (200 OK):**

```json
{
  "jobs": [
    {
      "id": 1234,
      "title": "Marketing Manager",
      "company": "Acme Corp",
      "company_url": "https://acme.com",
      "location_raw": "Seattle, WA",
      "location_city": "Seattle",
      "location_state": "WA",
      "location_country": "USA",
      "is_remote": true,
      "job_url": "https://acme.com/careers/marketing-manager",
      "job_type": "full_time",
      "salary_min": 80000,
      "salary_max": 120000,
      "salary_interval": "yearly",
      "date_posted": "2026-01-26T00:00:00Z",
      "first_seen": "2026-01-26T14:30:00Z",
      "company_size": "51-200",
      "company_industry": "Technology",
      "sources": ["indeed", "linkedin"],
      "is_favorite": false,
      "is_hidden": false
    }
  ],
  "total": 156,
  "page": 1,
  "per_page": 25,
  "total_pages": 7
}
```

### GET /api/jobs/{id} - Get Job Details

**Response (200 OK):**

```json
{
  "id": 1234,
  "title": "Marketing Manager",
  "company": "Acme Corp",
  "company_url": "https://acme.com",
  "location_raw": "Seattle, WA",
  "location_city": "Seattle",
  "location_state": "WA",
  "location_country": "USA",
  "is_remote": true,
  "description": "<p>We are looking for a Marketing Manager to lead our growth initiatives...</p>",
  "job_url": "https://acme.com/careers/marketing-manager",
  "job_type": "full_time",
  "salary_min": 80000,
  "salary_max": 120000,
  "salary_interval": "yearly",
  "date_posted": "2026-01-26T00:00:00Z",
  "first_seen": "2026-01-26T14:30:00Z",
  "last_seen": "2026-01-28T10:00:00Z",
  "company_size": "51-200",
  "company_industry": "Technology",
  "sources": ["indeed", "linkedin"],
  "is_favorite": false,
  "is_hidden": false,
  "application": null
}
```

**Response (404 Not Found):**

```json
{
  "detail": "Job not found"
}
```

### POST /api/sync - Trigger Manual Sync

Triggers the scraper to fetch new jobs from all configured sources. Returns immediately with sync status.

**Response (200 OK):**

```json
{
  "status": "success",
  "message": "Job sync completed successfully",
  "new_jobs": 0,
  "updated_jobs": 0,
  "duration_ms": 12543
}
```

**Response (500 Internal Server Error):**

```json
{
  "detail": "Sync failed: [error message]"
}
```

### POST /api/jobs/{id}/favorite - Add to Favorites

**Response (200 OK):**

```json
{
  "id": 1234,
  "is_favorite": true,
  "favorited_at": "2026-01-28T15:30:00Z"
}
```

### DELETE /api/jobs/{id}/favorite - Remove from Favorites

**Response (200 OK):**

```json
{
  "id": 1234,
  "is_favorite": false
}
```

### POST /api/jobs/{id}/hide - Hide Job

**Response (200 OK):**

```json
{
  "id": 1234,
  "is_hidden": true,
  "hidden_at": "2026-01-28T15:30:00Z"
}
```

### DELETE /api/jobs/{id}/hide - Unhide Job

**Response (200 OK):**

```json
{
  "id": 1234,
  "is_hidden": false
}
```

### GET /api/favorites - List Favorites

**Response (200 OK):**

```json
{
  "jobs": [
    {
      "id": 1234,
      "title": "Marketing Manager",
      "company": "Acme Corp",
      "location_raw": "Seattle, WA",
      "is_remote": true,
      "job_url": "https://acme.com/careers/marketing-manager",
      "salary_min": 80000,
      "salary_max": 120000,
      "salary_interval": "yearly",
      "date_posted": "2026-01-26T00:00:00Z",
      "company_size": "51-200",
      "sources": ["indeed"],
      "is_favorite": true,
      "is_hidden": false,
      "favorited_at": "2026-01-27T10:00:00Z"
    }
  ],
  "total": 12
}
```

### GET /api/stats - Dashboard Statistics

**Response (200 OK):**

```json
{
  "total_jobs": 1523,
  "new_today": 47,
  "new_this_week": 312,
  "favorites_count": 12,
  "hidden_count": 45,
  "applications_count": 8,
  "by_source": {
    "indeed": 823,
    "linkedin": 412,
    "glassdoor": 188,
    "greenhouse": 67,
    "lever": 33
  },
  "by_company_size": {
    "1-10": 89,
    "11-50": 342,
    "51-200": 567,
    "201-500": 312,
    "501-1000": 123,
    "1000+": 90
  },
  "last_scrape": "2026-01-28T14:00:00Z"
}
```

### GET /api/search-configs - List Search Configurations

**Response (200 OK):**

```json
{
  "configs": [
    {
      "id": 1,
      "name": "Marketing/SEO Remote",
      "search_term": "marketing OR SEO OR content",
      "location": "Seattle, WA",
      "distance": 50,
      "is_remote": true,
      "hours_old": 48,
      "results_wanted": 100,
      "country": "USA",
      "enabled": true,
      "created_at": "2026-01-20T00:00:00Z",
      "updated_at": "2026-01-25T00:00:00Z"
    }
  ]
}
```

### POST /api/search-configs - Create Search Configuration

**Request:**

```json
{
  "name": "Analytics Roles",
  "search_term": "analytics OR data analyst",
  "location": "Remote",
  "distance": null,
  "is_remote": true,
  "hours_old": 24,
  "results_wanted": 50,
  "country": "USA",
  "enabled": true
}
```

**Response (201 Created):**

```json
{
  "id": 2,
  "name": "Analytics Roles",
  "search_term": "analytics OR data analyst",
  "location": "Remote",
  "distance": null,
  "is_remote": true,
  "hours_old": 24,
  "results_wanted": 50,
  "country": "USA",
  "enabled": true,
  "created_at": "2026-01-28T15:00:00Z",
  "updated_at": "2026-01-28T15:00:00Z"
}
```

### PUT /api/search-configs/{id} - Update Search Configuration

**Request:**

```json
{
  "name": "Analytics Roles - Updated",
  "enabled": false
}
```

**Response (200 OK):**

```json
{
  "id": 2,
  "name": "Analytics Roles - Updated",
  "search_term": "analytics OR data analyst",
  "location": "Remote",
  "distance": null,
  "is_remote": true,
  "hours_old": 24,
  "results_wanted": 50,
  "country": "USA",
  "enabled": false,
  "created_at": "2026-01-28T15:00:00Z",
  "updated_at": "2026-01-28T16:00:00Z"
}
```

### GET /api/settings - Get User Settings

**Response (200 OK):**

```json
{
  "excluded_companies": ["Meta", "Amazon", "Google"],
  "excluded_keywords": ["senior", "director", "vp", "head of"],
  "default_location": "Seattle, WA",
  "default_remote": true
}
```

### PUT /api/settings - Update User Settings

**Request:**

```json
{
  "excluded_companies": ["Meta", "Amazon", "Google", "Microsoft"],
  "excluded_keywords": ["senior", "director", "vp", "head of", "principal"],
  "default_location": "Seattle, WA",
  "default_remote": true
}
```

**Response (200 OK):**

```json
{
  "excluded_companies": ["Meta", "Amazon", "Google", "Microsoft"],
  "excluded_keywords": ["senior", "director", "vp", "head of", "principal"],
  "default_location": "Seattle, WA",
  "default_remote": true,
  "updated_at": "2026-01-28T16:00:00Z"
}
```

### GET /api/companies - List Tracked Companies

**Response (200 OK):**

```json
{
  "companies": [
    {
      "id": 1,
      "name": "Notion",
      "website": "https://notion.so",
      "ats_type": "ashby",
      "ats_identifier": "notion",
      "last_scraped": "2026-01-28T14:00:00Z",
      "job_count": 12,
      "enabled": true,
      "created_at": "2026-01-15T00:00:00Z"
    },
    {
      "id": 2,
      "name": "Stripe",
      "website": "https://stripe.com",
      "ats_type": "greenhouse",
      "ats_identifier": "stripe",
      "last_scraped": "2026-01-28T14:00:00Z",
      "job_count": 45,
      "enabled": true,
      "created_at": "2026-01-16T00:00:00Z"
    }
  ],
  "total": 2
}
```

### POST /api/companies - Add Tracked Company

**Request:**

```json
{
  "name": "Figma",
  "website": "https://figma.com",
  "ats_type": null,
  "ats_identifier": null
}
```

**Response (201 Created):**

```json
{
  "id": 3,
  "name": "Figma",
  "website": "https://figma.com",
  "ats_type": "lever",
  "ats_identifier": "figma",
  "last_scraped": null,
  "job_count": 0,
  "enabled": true,
  "created_at": "2026-01-28T16:00:00Z"
}
```

### POST /api/jobs/{id}/apply - Create Application

**Request:**

```json
{
  "status": "applied",
  "notes": "Applied via company website. Submitted resume v3."
}
```

**Response (201 Created):**

```json
{
  "id": 1,
  "job_id": 1234,
  "status": "applied",
  "notes": "Applied via company website. Submitted resume v3.",
  "applied_at": "2026-01-28T16:30:00Z",
  "updated_at": "2026-01-28T16:30:00Z"
}
```

### PUT /api/jobs/{id}/application - Update Application

**Request:**

```json
{
  "status": "interviewing",
  "notes": "Phone screen scheduled for Feb 1st"
}
```

**Response (200 OK):**

```json
{
  "id": 1,
  "job_id": 1234,
  "status": "interviewing",
  "notes": "Phone screen scheduled for Feb 1st",
  "applied_at": "2026-01-28T16:30:00Z",
  "updated_at": "2026-01-29T10:00:00Z"
}
```

### GET /api/applications - List Applications

**Response (200 OK):**

```json
{
  "applications": [
    {
      "id": 1,
      "job": {
        "id": 1234,
        "title": "Marketing Manager",
        "company": "Acme Corp",
        "job_url": "https://acme.com/careers/marketing-manager"
      },
      "status": "interviewing",
      "notes": "Phone screen scheduled for Feb 1st",
      "applied_at": "2026-01-28T16:30:00Z",
      "updated_at": "2026-01-29T10:00:00Z"
    }
  ],
  "total": 1,
  "by_status": {
    "saved": 2,
    "applied": 5,
    "interviewing": 1,
    "offered": 0,
    "rejected": 3,
    "withdrawn": 1
  }
}
```

### GET /health - Health Check

**Response (200 OK):**

```json
{
  "status": "healthy",
  "database": "connected",
  "version": "0.1.0"
}
```

---

## Filter Engine

### How Filters Translate to SQL

The filter engine builds a dynamic WHERE clause based on query parameters:

```python
def build_job_query(
    db: AsyncSession,
    q: str | None = None,
    location: str | None = None,
    is_remote: bool | None = None,
    company_size: list[str] | None = None,
    job_type: str | None = None,
    source: str | None = None,
    posted_after: datetime | None = None,
    include_hidden: bool = False,
    favorites_only: bool = False,
    excluded_companies: list[str] | None = None,
    excluded_keywords: list[str] | None = None,
) -> Select:
    """Build the job listing query with all filters."""
    
    # Base query - join with user_job_state and aggregate sources
    query = (
        select(
            Job,
            func.coalesce(UserJobState.is_favorite, False).label("is_favorite"),
            func.coalesce(UserJobState.is_hidden, False).label("is_hidden"),
            func.array_agg(distinct(JobSource.source_site)).label("sources"),
        )
        .outerjoin(UserJobState, Job.id == UserJobState.job_id)
        .outerjoin(JobSource, Job.id == JobSource.job_id)
        .where(Job.is_active == True)
        .group_by(Job.id, UserJobState.is_favorite, UserJobState.is_hidden)
    )
    
    # Full-text search on title, company, description
    if q:
        # Use PostgreSQL full-text search with ranking
        search_query = func.plainto_tsquery("english", q)
        query = query.where(Job.search_vector.op("@@")(search_query))
        # Add relevance ranking
        query = query.add_columns(
            func.ts_rank(Job.search_vector, search_query).label("rank")
        )
    
    # Location filter (case-insensitive partial match)
    if location:
        location_filter = or_(
            Job.location_city.ilike(f"%{location}%"),
            Job.location_state.ilike(f"%{location}%"),
            Job.location_raw.ilike(f"%{location}%"),
        )
        query = query.where(location_filter)
    
    # Remote filter
    if is_remote is not None:
        if is_remote:
            query = query.where(Job.is_remote == True)
        # Note: is_remote=false means "any" not "non-remote only"
    
    # Company size filter (multiple values)
    if company_size:
        query = query.where(Job.company_size.in_(company_size))
    
    # Job type filter
    if job_type:
        query = query.where(Job.job_type == job_type)
    
    # Source filter
    if source:
        query = query.where(
            Job.id.in_(
                select(JobSource.job_id).where(JobSource.source_site == source)
            )
        )
    
    # Date filter
    if posted_after:
        query = query.where(Job.date_posted >= posted_after)
    
    # Hidden jobs filter
    if not include_hidden:
        query = query.where(
            or_(
                UserJobState.is_hidden == False,
                UserJobState.is_hidden.is_(None),
            )
        )
    
    # Favorites only filter
    if favorites_only:
        query = query.where(UserJobState.is_favorite == True)
    
    # Excluded companies (from user settings)
    if excluded_companies:
        for company in excluded_companies:
            query = query.where(~Job.company.ilike(f"%{company}%"))
    
    # Excluded keywords in title (from user settings)
    if excluded_keywords:
        for keyword in excluded_keywords:
            query = query.where(~Job.title.ilike(f"%{keyword}%"))
    
    return query
```

### Full-Text Search Implementation

PostgreSQL's full-text search provides fast, relevance-ranked searches:

```sql
-- Search query example
SELECT 
    j.*,
    COALESCE(ujs.is_favorite, false) as is_favorite,
    COALESCE(ujs.is_hidden, false) as is_hidden,
    array_agg(DISTINCT js.source_site) as sources,
    ts_rank(j.search_vector, plainto_tsquery('english', 'marketing manager')) as rank
FROM jobs j
LEFT JOIN user_job_state ujs ON j.id = ujs.job_id
LEFT JOIN job_sources js ON j.id = js.job_id
WHERE 
    j.is_active = true
    AND j.search_vector @@ plainto_tsquery('english', 'marketing manager')
    AND (ujs.is_hidden = false OR ujs.is_hidden IS NULL)
GROUP BY j.id, ujs.is_favorite, ujs.is_hidden
ORDER BY rank DESC, j.date_posted DESC
LIMIT 50 OFFSET 0;
```

**Search Vector Weights:**
- **A (highest)**: Job title
- **B (medium)**: Company name
- **C (lowest)**: Job description

### Pagination Strategy

Uses offset-based pagination for simplicity:

```python
def paginate_query(query: Select, page: int, per_page: int) -> Select:
    """Apply pagination to query."""
    offset = (page - 1) * per_page
    return query.offset(offset).limit(per_page)

async def get_total_count(db: AsyncSession, query: Select) -> int:
    """Get total count for pagination metadata."""
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    return result.scalar()
```

**Response format:**

```json
{
  "jobs": [...],
  "total": 156,
  "page": 2,
  "per_page": 50,
  "total_pages": 4
}
```

---

## Key SQL Queries

### 1. Job Listing with Filters (Main Query)

```sql
-- Full job listing query with all filters applied
SELECT 
    j.id,
    j.title,
    j.company,
    j.company_url,
    j.location_raw,
    j.location_city,
    j.location_state,
    j.location_country,
    j.is_remote,
    j.job_url,
    j.job_type,
    j.salary_min,
    j.salary_max,
    j.salary_interval,
    j.date_posted,
    j.first_seen,
    j.company_size,
    j.company_industry,
    COALESCE(ujs.is_favorite, false) AS is_favorite,
    COALESCE(ujs.is_hidden, false) AS is_hidden,
    array_agg(DISTINCT js.source_site) FILTER (WHERE js.source_site IS NOT NULL) AS sources
FROM jobs j
LEFT JOIN user_job_state ujs ON j.id = ujs.job_id
LEFT JOIN job_sources js ON j.id = js.job_id
WHERE 
    j.is_active = true
    AND (ujs.is_hidden = false OR ujs.is_hidden IS NULL)
    -- Optional filters below
    AND ($1::text IS NULL OR j.search_vector @@ plainto_tsquery('english', $1))
    AND ($2::text IS NULL OR j.location_city ILIKE '%' || $2 || '%' OR j.location_state ILIKE '%' || $2 || '%')
    AND ($3::boolean IS NULL OR j.is_remote = $3)
    AND ($4::text[] IS NULL OR j.company_size = ANY($4))
    AND ($5::timestamptz IS NULL OR j.date_posted >= $5)
GROUP BY j.id, ujs.is_favorite, ujs.is_hidden
ORDER BY j.date_posted DESC NULLS LAST
LIMIT $6 OFFSET $7;
```

### 2. Deduplication Check (Used by Scraper)

```sql
-- Check if jobs already exist by dedup_hash
-- Returns existing hashes from the provided list
SELECT dedup_hash 
FROM jobs 
WHERE dedup_hash = ANY($1::varchar[])
AND first_seen > NOW() - INTERVAL '30 days';

-- Batch insert new jobs (scraper uses this)
INSERT INTO jobs (
    dedup_hash, title, company, company_url, location_raw, location_city,
    location_state, location_country, is_remote, description, job_url,
    job_type, salary_min, salary_max, salary_interval, date_posted,
    company_size, company_industry
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18
)
ON CONFLICT (dedup_hash) DO UPDATE SET
    last_seen = NOW(),
    is_active = true
RETURNING id;

-- Add source for job
INSERT INTO job_sources (job_id, source, source_site, external_id)
VALUES ($1, $2, $3, $4)
ON CONFLICT (job_id, source, source_site) DO NOTHING;
```

### 3. Favorites/Hidden Management

```sql
-- Add to favorites
INSERT INTO user_job_state (job_id, is_favorite, favorited_at)
VALUES ($1, true, NOW())
ON CONFLICT (job_id) DO UPDATE SET
    is_favorite = true,
    favorited_at = NOW();

-- Remove from favorites
UPDATE user_job_state 
SET is_favorite = false, favorited_at = NULL
WHERE job_id = $1;

-- Hide job
INSERT INTO user_job_state (job_id, is_hidden, hidden_at)
VALUES ($1, true, NOW())
ON CONFLICT (job_id) DO UPDATE SET
    is_hidden = true,
    hidden_at = NOW();

-- Unhide job
UPDATE user_job_state 
SET is_hidden = false, hidden_at = NULL
WHERE job_id = $1;

-- Get all favorites with job details
SELECT 
    j.*,
    ujs.favorited_at,
    array_agg(DISTINCT js.source_site) AS sources
FROM jobs j
JOIN user_job_state ujs ON j.id = ujs.job_id
LEFT JOIN job_sources js ON j.id = js.job_id
WHERE ujs.is_favorite = true
GROUP BY j.id, ujs.favorited_at
ORDER BY ujs.favorited_at DESC;
```

### 4. Search Config CRUD

```sql
-- Create search config
INSERT INTO search_configs (name, search_term, location, distance, is_remote, hours_old, results_wanted, country, enabled)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
RETURNING *;

-- Get all enabled search configs (for scraper)
SELECT * FROM search_configs WHERE enabled = true ORDER BY id;

-- Update search config
UPDATE search_configs
SET name = COALESCE($2, name),
    search_term = COALESCE($3, search_term),
    location = COALESCE($4, location),
    distance = COALESCE($5, distance),
    is_remote = COALESCE($6, is_remote),
    hours_old = COALESCE($7, hours_old),
    results_wanted = COALESCE($8, results_wanted),
    enabled = COALESCE($9, enabled),
    updated_at = NOW()
WHERE id = $1
RETURNING *;

-- Delete search config
DELETE FROM search_configs WHERE id = $1;
```

### 5. Dashboard Statistics

```sql
-- Get dashboard stats
SELECT 
    (SELECT COUNT(*) FROM jobs WHERE is_active = true) AS total_jobs,
    (SELECT COUNT(*) FROM jobs WHERE is_active = true AND first_seen > NOW() - INTERVAL '1 day') AS new_today,
    (SELECT COUNT(*) FROM jobs WHERE is_active = true AND first_seen > NOW() - INTERVAL '7 days') AS new_this_week,
    (SELECT COUNT(*) FROM user_job_state WHERE is_favorite = true) AS favorites_count,
    (SELECT COUNT(*) FROM user_job_state WHERE is_hidden = true) AS hidden_count,
    (SELECT COUNT(*) FROM applications) AS applications_count;

-- Jobs by source
SELECT source_site, COUNT(DISTINCT job_id) AS count
FROM job_sources
GROUP BY source_site
ORDER BY count DESC;

-- Jobs by company size
SELECT company_size, COUNT(*) AS count
FROM jobs
WHERE is_active = true AND company_size IS NOT NULL
GROUP BY company_size
ORDER BY count DESC;
```

---

## FastAPI Project Structure

```
hirewire-api/
├── Dockerfile
├── requirements.txt
├── alembic/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── static/                    # Vue 3 production build (copied at build time)
│   ├── index.html
│   ├── assets/
│   └── ...
├── src/
│   ├── __init__.py
│   ├── main.py               # FastAPI app entry point
│   ├── config.py             # Settings via pydantic-settings
│   ├── database.py           # DB connection, async session
│   ├── dependencies.py       # Dependency injection (get_db, get_settings)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── job.py            # Job, JobSource SQLAlchemy models
│   │   ├── user_state.py     # UserJobState, Application models
│   │   ├── company.py        # TrackedCompany model
│   │   └── settings.py       # SearchConfig, UserSettings models
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── job.py            # JobResponse, JobListResponse Pydantic models
│   │   ├── company.py        # CompanyCreate, CompanyResponse
│   │   ├── settings.py       # SearchConfigCreate, UserSettingsUpdate
│   │   └── common.py         # Pagination, Error response models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── jobs.py           # /api/jobs endpoints
│   │   ├── favorites.py      # /api/favorites endpoints
│   │   ├── companies.py      # /api/companies endpoints
│   │   ├── settings.py       # /api/settings, /api/search-configs
│   │   ├── applications.py   # /api/applications endpoints (Phase 4)
│   │   └── stats.py          # /api/stats endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── job_service.py    # Job query building, filtering logic
│   │   ├── company_service.py # ATS detection logic
│   │   └── stats_service.py  # Statistics aggregation
│   └── utils/
│       ├── __init__.py
│       └── ats_detector.py   # Auto-detect company ATS type
└── tests/
    ├── __init__.py
    ├── conftest.py           # Pytest fixtures
    ├── test_jobs.py
    ├── test_favorites.py
    └── test_settings.py
```

### Main Application Entry Point

```python
# src/main.py
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.config import get_settings
from src.database import engine, Base
from src.routers import jobs, favorites, companies, settings, stats, applications


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup: create tables if they don't exist (dev only)
    settings = get_settings()
    if settings.environment == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: cleanup if needed


def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title="HireWire API",
        description="Job search aggregator API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )
    
    # API routes
    app.include_router(jobs.router, prefix="/api", tags=["jobs"])
    app.include_router(favorites.router, prefix="/api", tags=["favorites"])
    app.include_router(companies.router, prefix="/api", tags=["companies"])
    app.include_router(settings.router, prefix="/api", tags=["settings"])
    app.include_router(stats.router, prefix="/api", tags=["stats"])
    app.include_router(applications.router, prefix="/api", tags=["applications"])
    
    # Health check
    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": "0.1.0"}
    
    # Serve Vue 3 frontend
    static_dir = Path(__file__).parent.parent / "static"
    
    @app.get("/")
    async def serve_index():
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "HireWire API", "docs": "/docs"}
    
    # Mount static files for Vue assets (after API routes)
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    
    return app


app = create_app()
```

### Configuration

```python
# src/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # Database
    database_url: str = "postgresql+asyncpg://hirewire:hirewire@localhost:5432/hirewire"
    
    # Environment
    environment: str = "development"  # development, production
    
    # CORS
    cors_origins: list[str] = ["*"]
    
    # Pagination defaults
    default_page_size: int = 50
    max_page_size: int = 100
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Database Connection

```python
# src/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from src.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
```

### Dependency Injection Pattern

```python
# src/dependencies.py
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.config import Settings, get_settings
from src.schemas.common import PaginationParams


# Type aliases for dependency injection
DBSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_pagination(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    """Pagination parameters dependency."""
    return PaginationParams(page=page, per_page=per_page)


Pagination = Annotated[PaginationParams, Depends(get_pagination)]
```

---

## Error Handling

### Error Response Schema

All errors follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

For validation errors (422):

```json
{
  "detail": [
    {
      "loc": ["query", "page"],
      "msg": "ensure this value is greater than or equal to 1",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

### HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful GET, PUT, DELETE |
| 201 | Created | Successful POST creating new resource |
| 400 | Bad Request | Invalid request parameters |
| 404 | Not Found | Resource doesn't exist |
| 422 | Unprocessable Entity | Validation error |
| 500 | Internal Server Error | Unexpected server error |

### Exception Handler

```python
# src/main.py (additional)
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler."""
    # Log the error
    import logging
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Return generic error in production
    settings = get_settings()
    if settings.environment == "production":
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred"}
        )
    
    # Return detailed error in development
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )
```

---

## TypeScript Interfaces

These are the exact interfaces the frontend should use to consume the API:

```typescript
// types/api.ts - AUTO-GENERATED FROM API SPEC

// ============================================================================
// Job Types
// ============================================================================

export interface Job {
  id: number;
  title: string;
  company: string;
  company_url: string | null;
  location_raw: string | null;
  location_city: string | null;
  location_state: string | null;
  location_country: string | null;
  is_remote: boolean;
  job_url: string;
  job_type: JobType | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_interval: SalaryInterval | null;
  date_posted: string | null;  // ISO datetime
  first_seen: string;          // ISO datetime
  company_size: CompanySize | null;
  company_industry: string | null;
  sources: string[];
  is_favorite: boolean;
  is_hidden: boolean;
}

export interface JobDetail extends Job {
  description: string | null;
  last_seen: string;           // ISO datetime
  application: Application | null;
}

export type JobType = 'full_time' | 'part_time' | 'contract' | 'internship';

export type SalaryInterval = 'yearly' | 'monthly' | 'weekly' | 'daily' | 'hourly';

export type CompanySize = '1-10' | '11-50' | '51-200' | '201-500' | '501-1000' | '1000+';

// ============================================================================
// List Response Types
// ============================================================================

export interface JobListResponse {
  jobs: Job[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface FavoritesResponse {
  jobs: (Job & { favorited_at: string })[];
  total: number;
}

// ============================================================================
// Job Actions
// ============================================================================

export interface FavoriteResponse {
  id: number;
  is_favorite: boolean;
  favorited_at: string | null;
}

export interface HideResponse {
  id: number;
  is_hidden: boolean;
  hidden_at: string | null;
}

// ============================================================================
// Statistics
// ============================================================================

export interface Stats {
  total_jobs: number;
  new_today: number;
  new_this_week: number;
  favorites_count: number;
  hidden_count: number;
  applications_count: number;
  by_source: Record<string, number>;
  by_company_size: Record<CompanySize, number>;
  last_scrape: string | null;  // ISO datetime
}

// ============================================================================
// Search Configurations
// ============================================================================

export interface SearchConfig {
  id: number;
  name: string;
  search_term: string;
  location: string | null;
  distance: number | null;
  is_remote: boolean;
  hours_old: number;
  results_wanted: number;
  country: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface SearchConfigCreate {
  name: string;
  search_term: string;
  location?: string | null;
  distance?: number | null;
  is_remote?: boolean;
  hours_old?: number;
  results_wanted?: number;
  country?: string;
  enabled?: boolean;
}

export interface SearchConfigUpdate {
  name?: string;
  search_term?: string;
  location?: string | null;
  distance?: number | null;
  is_remote?: boolean;
  hours_old?: number;
  results_wanted?: number;
  country?: string;
  enabled?: boolean;
}

export interface SearchConfigsResponse {
  configs: SearchConfig[];
}

// ============================================================================
// User Settings
// ============================================================================

export interface UserSettings {
  excluded_companies: string[];
  excluded_keywords: string[];
  default_location: string | null;
  default_remote: boolean;
}

export interface UserSettingsUpdate {
  excluded_companies?: string[];
  excluded_keywords?: string[];
  default_location?: string | null;
  default_remote?: boolean;
}

export interface UserSettingsResponse extends UserSettings {
  updated_at: string;
}

// ============================================================================
// Tracked Companies
// ============================================================================

export type ATSType = 'greenhouse' | 'lever' | 'ashby';

export interface TrackedCompany {
  id: number;
  name: string;
  website: string | null;
  ats_type: ATSType | null;
  ats_identifier: string | null;
  last_scraped: string | null;
  job_count: number;
  enabled: boolean;
  created_at: string;
}

export interface TrackedCompanyCreate {
  name: string;
  website?: string | null;
  ats_type?: ATSType | null;
  ats_identifier?: string | null;
}

export interface TrackedCompaniesResponse {
  companies: TrackedCompany[];
  total: number;
}

// ============================================================================
// Applications (Phase 4)
// ============================================================================

export type ApplicationStatus = 
  | 'saved' 
  | 'applied' 
  | 'interviewing' 
  | 'offered' 
  | 'rejected' 
  | 'withdrawn';

export interface Application {
  id: number;
  job_id: number;
  status: ApplicationStatus;
  notes: string | null;
  applied_at: string | null;
  updated_at: string;
}

export interface ApplicationCreate {
  status?: ApplicationStatus;
  notes?: string | null;
}

export interface ApplicationUpdate {
  status?: ApplicationStatus;
  notes?: string | null;
}

export interface ApplicationWithJob extends Application {
  job: {
    id: number;
    title: string;
    company: string;
    job_url: string;
  };
}

export interface ApplicationsResponse {
  applications: ApplicationWithJob[];
  total: number;
  by_status: Record<ApplicationStatus, number>;
}

// ============================================================================
// Query Parameters
// ============================================================================

export interface JobsQueryParams {
  page?: number;
  per_page?: number;
  q?: string;
  location?: string;
  is_remote?: boolean;
  company_size?: CompanySize[];
  job_type?: JobType;
  source?: string;
  posted_after?: string;  // ISO datetime
  sort_by?: 'date_posted' | 'company' | 'title' | 'first_seen';
  sort_order?: 'asc' | 'desc';
  include_hidden?: boolean;
  favorites_only?: boolean;
}

// ============================================================================
// Error Response
// ============================================================================

export interface ErrorResponse {
  detail: string | ValidationError[];
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

// ============================================================================
// Health Check
// ============================================================================

export interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  database?: 'connected' | 'disconnected';
  version: string;
}
```

---

## Open Questions

1. **Authentication**: Currently single-user, no auth. Should we add basic auth or rely on Traefik IP allowlist for MVP?

2. **Caching**: Should we add Redis for caching frequently accessed data (stats, filtered results)?

3. **Rate Limiting**: Do we need rate limiting for the API, or is the internal-only access sufficient?

4. **Job Expiry**: How long should jobs stay in the database? Current plan: mark as `is_active=false` after 30 days of not being seen.

5. **Scraper Sync**: Should the scraper update `last_seen` for all existing jobs it finds, or only new ones?
