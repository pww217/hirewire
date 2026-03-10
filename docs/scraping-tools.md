# HireWire - ATS Scraping Tools

> Documentation of the ATS APIs used by HireWire to fetch job listings directly from company job boards.

## Contents

- [Overview](#overview)
- [Greenhouse API](#greenhouse-api)
- [Lever API](#lever-api)
- [Ashby API](#ashby-api)
- [Smoke Test Results](#smoke-test-results)
- [Data Normalization Mapping](#data-normalization-mapping)
- [Integration Contract](#integration-contract)

---

## Overview

HireWire polls three ATS (Applicant Tracking System) platforms that are commonly used by startups and tech companies. All three expose **public, unauthenticated REST APIs** for their job boards — no API keys or scraping required.

| ATS | API Style | Auth | Companies using it |
|-----|-----------|------|-------------------|
| Greenhouse | REST (JSON) | None | Stripe, Airbnb, DoorDash, thousands more |
| Lever | REST (JSON) | None | Spotify, Shopify, Netlify, and others |
| Ashby | REST (JSON) | None | Notion, Linear, Ramp, and others |

---

## Greenhouse API

**Base URL**: `https://api.greenhouse.io/v1/boards/{slug}/jobs`

### Fetch all jobs

```
GET https://api.greenhouse.io/v1/boards/{slug}/jobs?content=true
```

The `?content=true` parameter includes the full HTML job description in the `content` field.

### Response shape

```json
{
  "jobs": [
    {
      "id": 12345678,
      "title": "Senior Data Analyst",
      "location": { "name": "San Francisco, CA" },
      "content": "&lt;h2&gt;About the Role&lt;/h2&gt;&lt;p&gt;...&lt;/p&gt;",
      "absolute_url": "https://boards.greenhouse.io/stripe/jobs/12345678",
      "updated_at": "2026-02-20T18:00:00.000Z",
      "departments": [{ "name": "Data" }],
      "offices": [{ "name": "San Francisco" }]
    }
  ]
}
```

### Notes

- The `content` field is **HTML-entity-escaped** (`&lt;h2&gt;` etc.). HireWire applies `html.unescape()` before storing.
- No `is_remote` or `job_type` fields are available directly; remote detection is inferred from the location string.
- `updated_at` is used as the `date_posted` value.

### URL patterns detected

- `boards.greenhouse.io/{slug}` → slug is the company identifier
- `{slug}.greenhouse.io` → same

---

## Lever API

**Base URL**: `https://api.lever.co/v0/postings/{slug}`

### Fetch all jobs

```
GET https://api.lever.co/v0/postings/{slug}
```

Returns a JSON **array** (not an object).

### Response shape

```json
[
  {
    "id": "abc123-def456",
    "text": "Product Manager",
    "description": "<div><p>Intro paragraph...</p></div>",
    "descriptionPlain": "Intro paragraph...",
    "lists": [
      {
        "text": "What you'll do",
        "content": "<li>Own the roadmap</li><li>Work with engineers</li>"
      }
    ],
    "additional": "<div><p>Compensation: $150k-$200k</p></div>",
    "categories": {
      "location": "New York, NY",
      "team": "Product",
      "department": "Product",
      "commitment": "Full-time"
    },
    "hostedUrl": "https://jobs.lever.co/spotify/abc123-def456",
    "applyUrl": "https://jobs.lever.co/spotify/abc123-def456/apply",
    "createdAt": 1700000000000
  }
]
```

### Description assembly

Lever splits job content across three fields. HireWire assembles them in order:

1. `description` — intro HTML
2. `lists[]` — each section becomes `<h3>{text}</h3><ul>{content}</ul>`
3. `additional` — compensation, benefits, etc.

### Notes

- `createdAt` is a **milliseconds-since-epoch** integer.
- Job type is derived from `categories.commitment` (e.g. "Full-time" → `full_time`).
- Remote detection is inferred from `categories.location`.

### URL patterns detected

- `jobs.lever.co/{slug}` → slug is the company identifier

---

## Ashby API

**Base URL**: `https://api.ashbyhq.com/posting-api/job-board/{slug}`

### Fetch all jobs

```
GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
```

### Response shape

```json
{
  "jobs": [
    {
      "id": "abc123",
      "title": "Software Engineer",
      "location": "New York, NY",
      "isRemote": false,
      "workplaceType": "OnSite",
      "employmentType": "FullTime",
      "jobUrl": "https://jobs.ashbyhq.com/notion/abc123",
      "applyUrl": "https://jobs.ashbyhq.com/notion/abc123/application",
      "descriptionHtml": "<div><h2>About the Role</h2><p>...</p></div>",
      "descriptionPlain": "About the Role\n...",
      "publishedAt": "2026-02-01T00:00:00.000Z",
      "compensation": {
        "compensationTiers": [
          {
            "min": 140000,
            "max": 200000,
            "currency": "USD",
            "interval": "yearly"
          }
        ]
      }
    }
  ]
}
```

### Notes

- `descriptionHtml` is pre-rendered HTML — no entity escaping needed.
- Salary compensation is available via `?includeCompensation=true`; HireWire uses the first tier.
- `workplaceType` values: `Remote`, `OnSite`, `Hybrid`.
- `employmentType` values: `FullTime`, `PartTime`, `Contract`, `Intern`.

### URL patterns detected

- `jobs.ashbyhq.com/{slug}` → slug is the company identifier
- `app.ashbyhq.com/jobs/{slug}` → same

---

## Smoke Test Results

Verified against real company job boards before implementation:

| Company | ATS | Jobs fetched | Response time | Description quality |
|---------|-----|-------------|---------------|---------------------|
| Notion | Ashby | ~120 | ~400ms | Full HTML, no issues |
| Stripe | Greenhouse | ~800 | ~900ms | Full HTML (after unescape) |
| Spotify | Lever | ~300 | ~600ms | Full HTML (assembled from 3 fields) |

All three APIs are reliable, fast, and require no authentication.

---

## Data Normalization Mapping

How raw ATS fields map to HireWire's normalized `RawJob` model:

| HireWire field | Greenhouse | Lever | Ashby |
|----------------|------------|-------|-------|
| `external_id` | `id` | `id` | `id` |
| `title` | `title` | `text` | `title` |
| `job_url` | `absolute_url` | `hostedUrl` | `jobUrl` |
| `location_raw` | `location.name` | `categories.location` | `location` |
| `is_remote` | inferred from location | inferred from location | `isRemote` or `workplaceType` |
| `description` | `content` (unescaped) | assembled from `description` + `lists` + `additional` | `descriptionHtml` |
| `job_type` | not available | `categories.commitment` | `employmentType` |
| `date_posted` | `updated_at` | `createdAt` (ms epoch) | `publishedAt` |
| `salary_min` | not available | not available | `compensation.compensationTiers[0].min` |
| `salary_max` | not available | not available | `compensation.compensationTiers[0].max` |
| `salary_interval` | not available | not available | `compensation.compensationTiers[0].interval` |

---

## Integration Contract

All scrapers implement `BaseScraper` and return `list[RawJob]`:

```python
class BaseScraper(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    async def fetch(self) -> list[RawJob]: ...
```

Scrapers must:
- Return an empty list (not raise) if the company slug is not found (404)
- Raise `ScrapingError` for non-404 HTTP errors or JSON parse failures
- Populate `company_id` from the `TrackedCompany` passed at construction
- Truncate fields to their database `VARCHAR` limits before returning

The `RawJob` model validates and normalizes fields via Pydantic validators before the scraper returns.
