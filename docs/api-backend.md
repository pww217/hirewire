# HireWire - API Backend

> Design specification for the FastAPI backend service and PostgreSQL database schema.

## Contents

- [Overview](#overview)
- [Technology Stack](#technology-stack)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Request/Response Contracts](#requestresponse-contracts)
- [Filter Engine](#filter-engine)
- [FastAPI Project Structure](#fastapi-project-structure)
- [TypeScript Interfaces](#typescript-interfaces)

---

## Overview

The API backend serves the Vue 3 frontend and exposes endpoints for:

- Listing and filtering jobs (with full-text search)
- Managing tracked companies (CRUD + sync triggers)
- Favorites
- User settings (locations, keywords, remote toggle)
- Aggregate stats
- Scraper trigger pass-through

The backend and compiled frontend are served from a single container on port 8000. Vue's SPA routes are handled by a catch-all that returns `index.html`.

---

## Technology Stack

- **FastAPI** — async Python web framework
- **SQLAlchemy (async)** — ORM for all backend DB access
- **asyncpg** — low-level driver (used directly by scraper service)
- **PostgreSQL 16** — primary data store with full-text search via `TSVECTOR`
- **Pydantic v2** — request/response validation
- **structlog** — structured JSON logging
- **pydantic-settings** — environment-based configuration

---

## Database Schema

### `tracked_companies`

| Column | Type | Notes |
|--------|------|-------|
| `id` | SERIAL PK | |
| `name` | VARCHAR(255) UNIQUE | Display name |
| `website` | VARCHAR(500) | Optional |
| `ats_type` | VARCHAR(50) | `greenhouse`, `lever`, `ashby` |
| `ats_identifier` | VARCHAR(255) | Company slug for ATS API |
| `last_scraped` | TIMESTAMPTZ | Set after each scrape |
| `job_count` | INTEGER | Active job count (denormalized) |
| `enabled` | BOOLEAN | Whether to include in scrapes |
| `created_at` | TIMESTAMPTZ | |

### `jobs`

| Column | Type | Notes |
|--------|------|-------|
| `id` | SERIAL PK | |
| `dedup_hash` | VARCHAR(32) UNIQUE | SHA-256 of company+title+location |
| `company_id` | INTEGER FK | → `tracked_companies.id` ON DELETE SET NULL |
| `title` | VARCHAR(500) | |
| `company` | VARCHAR(255) | Display name from ATS |
| `company_url` | VARCHAR(500) | |
| `location_raw` | VARCHAR(255) | Original location string |
| `location_city` | VARCHAR(100) | Parsed |
| `location_state` | VARCHAR(100) | Parsed |
| `location_country` | VARCHAR(100) | Default: `USA` |
| `is_remote` | BOOLEAN | |
| `description` | TEXT | Full HTML job description |
| `job_url` | VARCHAR(1000) | Direct link to posting |
| `job_type` | VARCHAR(50) | `full_time`, `part_time`, `contract`, `internship` |
| `salary_min` | DECIMAL(12,2) | |
| `salary_max` | DECIMAL(12,2) | |
| `salary_interval` | VARCHAR(20) | `yearly`, `monthly`, etc. |
| `date_posted` | TIMESTAMPTZ | From ATS API |
| `first_seen` | TIMESTAMPTZ | When HireWire first saw it |
| `last_seen` | TIMESTAMPTZ | Updated each scrape |
| `company_size` | VARCHAR(50) | |
| `company_industry` | VARCHAR(100) | |
| `is_active` | BOOLEAN | Set false when job disappears from ATS |
| `search_vector` | TSVECTOR | Auto-updated by trigger on insert/update |

### `job_sources`

Tracks which ATS a job was found on. Jobs can appear on multiple sources.

| Column | Type | Notes |
|--------|------|-------|
| `id` | SERIAL PK | |
| `job_id` | INTEGER FK | → `jobs.id` CASCADE |
| `source` | VARCHAR(50) | `greenhouse`, `lever`, `ashby` |
| `source_site` | VARCHAR(50) | Same as source for ATS scrapers |
| `external_id` | VARCHAR(255) | ID from the ATS API |

### `user_job_state`

Per-job user state (favorites, hidden).

| Column | Type | Notes |
|--------|------|-------|
| `job_id` | INTEGER UNIQUE FK | → `jobs.id` CASCADE |
| `is_favorite` | BOOLEAN | |
| `is_hidden` | BOOLEAN | |
| `favorited_at` | TIMESTAMPTZ | |

### `user_settings`

Single row (id=1) storing global preferences.

| Column | Type | Default |
|--------|------|---------|
| `preferred_locations` | TEXT[] | `{}` |
| `included_keywords` | TEXT[] | `{}` |
| `excluded_keywords` | TEXT[] | `{}` |
| `default_remote` | BOOLEAN | `false` |

### `applications`

Placeholder for future application tracking (not yet exposed in UI).

| Column | Type | Notes |
|--------|------|-------|
| `job_id` | INTEGER UNIQUE FK | → `jobs.id` |
| `status` | VARCHAR(50) | `applied`, `interviewing`, `rejected`, `offer` |
| `notes` | TEXT | |
| `applied_at` | TIMESTAMPTZ | |

---

## API Endpoints

### Companies

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/companies/detect` | Detect ATS type + slug from a URL |
| `GET` | `/api/companies` | List all tracked companies |
| `POST` | `/api/companies` | Add a new company to track |
| `GET` | `/api/companies/{id}` | Get single company |
| `PUT` | `/api/companies/{id}` | Update company |
| `DELETE` | `/api/companies/{id}` | Remove company (jobs SET NULL on company_id) |
| `POST` | `/api/companies/sync-all` | Trigger full sync of all companies |
| `POST` | `/api/companies/{id}/sync` | Trigger sync for a single company |

### Jobs

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/jobs` | List jobs with filters and pagination |
| `GET` | `/api/jobs/{id}` | Get job with full description |

### Favorites

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/jobs/{id}/favorite` | Add to favorites |
| `DELETE` | `/api/jobs/{id}/favorite` | Remove from favorites |
| `GET` | `/api/favorites` | List all favorited jobs |

### Settings

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/settings` | Get user settings |
| `PUT` | `/api/settings` | Update user settings |

### Stats

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/stats` | Aggregate job counts |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |

---

## Request/Response Contracts

### `POST /api/companies/detect`

```json
// Request
{ "url": "https://jobs.ashbyhq.com/monarchmoney" }

// Response
{
  "url": "https://jobs.ashbyhq.com/monarchmoney",
  "ats_type": "ashby",
  "ats_identifier": "monarchmoney",
  "detected": true
}
```

URL patterns matched:

| ATS | Pattern |
|-----|---------|
| Greenhouse | `boards.greenhouse.io/{slug}` or `{slug}.greenhouse.io` |
| Lever | `jobs.lever.co/{slug}` |
| Ashby | `jobs.ashbyhq.com/{slug}` or `app.ashbyhq.com/jobs/{slug}` |

### `POST /api/companies`

```json
// Request
{
  "name": "Monarchmoney",
  "ats_type": "ashby",
  "ats_identifier": "monarchmoney",
  "enabled": true
}

// Response: CompanyResponse (see below)
```

### `GET /api/jobs`

Query parameters:

| Param | Type | Description |
|-------|------|-------------|
| `page` | int | Page number (default: 1) |
| `per_page` | int | Items per page (default: 50, max: 100) |
| `q` | string | Full-text search. Commas = OR (e.g. `python, java`) |
| `company_id` | int | Scope to a single tracked company |
| `location` | string | Location filter (partial match on city/state/raw) |
| `is_remote` | bool | Remote-only filter |
| `company_size` | string[] | Filter by company size |
| `job_type` | string | `full_time`, `part_time`, `contract`, `internship` |
| `posted_after` | date | ISO date string |
| `sort_by` | string | `date_posted`, `first_seen`, `company`, `title` |
| `sort_order` | string | `asc` or `desc` |
| `include_hidden` | bool | Include hidden jobs (default: false) |
| `favorites_only` | bool | Only favorites (default: false) |
| `preferred_locations` | string[] | OR location filter from settings |
| `included_keywords` | string[] | Title must match at least one |
| `excluded_keywords` | string[] | Title must not match any |

---

## Filter Engine

Filters are applied in this order in `build_job_query()`:

1. `is_active = true` (always)
2. `company_id` exact match
3. Full-text search via `search_vector @@ plainto_tsquery()`
4. `location` — explicit override (OR across city/state/raw)
5. `preferred_locations` — OR across all provided locations (only when no explicit `location`)
6. `is_remote = true`
7. `company_size IN (...)`
8. `job_type = ...`
9. `source` — via `job_sources` subquery
10. `date_posted >= posted_after`
11. Hidden jobs exclusion
12. Favorites only
13. `included_keywords` — title ILIKE any (OR)
14. `excluded_keywords` — title NOT ILIKE each (AND NOT)

---

## FastAPI Project Structure

```
backend/src/
├── main.py              # App factory, lifespan, static file serving
├── config.py            # pydantic-settings config (DATABASE_URL, SCRAPER_URL, etc.)
├── database.py          # SQLAlchemy engine + session factory
├── routers/
│   ├── __init__.py
│   ├── companies.py     # Company CRUD + sync
│   ├── jobs.py          # Job listing + detail
│   ├── favorites.py     # Favorite/unfavorite
│   ├── settings.py      # User settings
│   ├── stats.py         # Aggregate stats
│   └── health.py        # Health check
├── models/
│   ├── company.py       # TrackedCompany ORM model
│   ├── job.py           # Job, JobSource, UserJobState, Application models
│   └── user_settings.py # UserSettings ORM model
└── schemas/
    ├── company.py       # CompanyCreate/Update/Response, detect schemas
    ├── job.py           # JobResponse, JobDetailResponse, JobListResponse
    ├── user_settings.py # UserSettingsUpdate, UserSettingsResponse
    └── stats.py         # StatsResponse
```

---

## TypeScript Interfaces

These match the Pydantic response schemas exactly (`frontend/src/types/api.ts`):

```typescript
interface TrackedCompany {
  id: number
  name: string
  website: string | null
  ats_type: 'greenhouse' | 'lever' | 'ashby' | null
  ats_identifier: string | null
  last_scraped: string | null
  job_count: number
  enabled: boolean
  created_at: string
}

interface Job {
  id: number
  company_id: number | null
  title: string
  company: string
  company_url: string | null
  location_raw: string | null
  location_city: string | null
  location_state: string | null
  location_country: string | null
  is_remote: boolean
  job_url: string
  job_type: 'full_time' | 'part_time' | 'contract' | 'internship' | null
  salary_min: number | null
  salary_max: number | null
  salary_interval: 'yearly' | 'monthly' | 'weekly' | 'daily' | 'hourly' | null
  date_posted: string | null
  first_seen: string
  company_size: string | null
  company_industry: string | null
  sources: string[]
  is_favorite: boolean
  is_hidden: boolean
}

interface JobDetail extends Job {
  description: string | null
  last_seen: string
}

interface JobListResponse {
  jobs: Job[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

interface UserSettings {
  preferred_locations: string[]
  included_keywords: string[]
  excluded_keywords: string[]
  default_remote: boolean
}

interface CompanyDetectResponse {
  url: string
  ats_type: 'greenhouse' | 'lever' | 'ashby' | null
  ats_identifier: string | null
  detected: boolean
}

interface SyncResponse {
  success: boolean
  new_jobs: number
  updated_jobs: number
  duration_ms: number
  error: string | null
  started_at: string
}
```
