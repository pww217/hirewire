# HireWire - Frontend

> Specification for the Vue 3 + Vite frontend with Linear-inspired dark mode UI.

## Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Design System](#design-system)
- [Project Structure](#project-structure)
- [Vue Router](#vue-router)
- [Pinia Stores](#pinia-stores)
- [Component Specifications](#component-specifications)
- [TypeScript Interfaces](#typescript-interfaces)
- [Build and Deployment](#build-and-deployment)

---

## Overview

Single-page application built with Vue 3 Composition API. Company-first layout: the left sidebar lists tracked companies; clicking one filters the job list to that company's listings. A master-detail panel shows the full job description.

Design follows Linear's aesthetic: dark mode, minimal chrome, clean typography.

---

## Tech Stack

- **Vue 3** — Composition API (`<script setup>`)
- **Vite** — build tool and dev server
- **TypeScript** — strict mode
- **Pinia** — state management
- **Vue Router 4** — client-side routing
- **vue-tsc** — TypeScript checking in CI

---

## Design System

CSS custom properties defined in `frontend/src/styles/main.css`. Dark mode only.

Key variables:

```css
--bg-primary        /* main content background */
--bg-secondary      /* sidebar, card backgrounds */
--bg-tertiary       /* inputs, hover states */
--bg-hover          /* hover highlight */
--bg-active         /* selected/active item */
--text-primary      /* headings, body */
--text-secondary    /* labels, secondary text */
--text-muted        /* placeholders, hints */
--accent-primary    /* blue action color */
--border-color      /* dividers, input borders */
--border-focus      /* focused input border */
--radius-sm/md/lg   /* border radii */
--space-1..6        /* spacing scale */
--text-xs/sm/base/lg/xl/2xl  /* type scale */
--font-mono         /* monospace font */
--transition-fast   /* animation duration */
```

---

## Project Structure

```
frontend/src/
├── main.ts                  # App bootstrap
├── App.vue                  # Root component, AddCompanyModal overlay
├── router/
│   └── index.ts             # Route definitions
├── stores/
│   ├── companies.ts         # Tracked companies CRUD + sync
│   ├── jobs.ts              # Job list, filters, pagination
│   ├── settings.ts          # User preferences
│   ├── favorites.ts         # Favorited job IDs
│   ├── stats.ts             # Aggregate stats
│   ├── ui.ts                # Toast notifications, loading states
│   └── viewed.ts            # Viewed job tracking (localStorage)
├── components/
│   ├── Sidebar.vue          # Company nav, sync/delete buttons
│   ├── AddCompanyModal.vue  # ATS URL detection + company form
│   ├── JobList.vue          # Paginated job cards
│   ├── JobCard.vue          # Single job card
│   ├── JobCardSkeleton.vue  # Loading placeholder
│   ├── JobDetail.vue        # Full job description panel
│   ├── FilterPanel.vue      # Job filter controls
│   ├── SearchBar.vue        # Full-text search input
│   ├── SortControls.vue     # Sort field/order selector
│   └── FilterCheckbox.vue   # Reusable checkbox component
├── views/
│   ├── DashboardView.vue    # Main layout: sidebar + job list + detail
│   ├── FavoritesView.vue    # Favorited jobs list
│   ├── JobDetailView.vue    # Standalone job detail page (/jobs/:id)
│   └── SettingsView.vue     # User preferences form
├── types/
│   └── api.ts               # TypeScript interfaces matching backend schemas
├── composables/
│   └── useApi.ts            # HTTP client with error handling
└── styles/
    └── main.css             # Global CSS variables + base styles
```

---

## Vue Router

```
/                    → DashboardView    (job list, company-scoped when company selected)
/favorites           → FavoritesView   (favorited jobs)
/jobs/:id            → JobDetailView   (standalone job detail)
/settings            → SettingsView    (user preferences)
```

All unknown paths redirect to `/`. The backend returns `index.html` for non-API routes to support client-side navigation.

---

## Pinia Stores

### `useCompaniesStore`

Manages tracked companies.

**State:**
- `companies: TrackedCompany[]` — sorted by `last_scraped DESC`
- `selectedCompanyId: number | null` — drives job list scoping
- `isLoading: boolean`
- `error: string | null`

**Computed:**
- `selectedCompany` — company object for selected ID

**Actions:**
- `fetchCompanies()` — load all companies from API
- `selectCompany(id)` — set active company
- `detectAts(url)` → `CompanyDetectResponse` — call `/api/companies/detect`
- `createCompany(data)` — POST to `/api/companies`
- `updateCompany(id, data)` — PUT to `/api/companies/{id}`
- `deleteCompany(id)` — DELETE `/api/companies/{id}`
- `syncCompany(id)` — POST `/api/companies/{id}/sync`, then refetches companies + jobs

### `useJobsStore`

Manages job list display and filtering.

**State:**
- `jobs: Job[]`
- `total: number`
- `totalPages: number`
- `page: number`
- `perPage: number`
- `isLoading: boolean`
- `filters: JobFilters` — q, location, isRemote, companySizes, jobType, source, postedAfter

**Actions:**
- `fetchJobs(reset?)` — fetch with current filters + selected company scope
- `setFilters(partial)` — merge filter update and refetch
- `resetFilters()` — clear all filters
- `nextPage()` / `prevPage()` — pagination

Jobs are automatically scoped to `companiesStore.selectedCompanyId` when set. Settings store values (`preferredLocations`, `includedKeywords`, `excludedKeywords`, `defaultRemote`) are automatically applied to each fetch when the corresponding active filter is not overriding.

### `useSettingsStore`

**State:**
- `settings: UserSettingsResponse | null`

**Computed:**
- `preferredLocations: string[]`
- `includedKeywords: string[]`
- `excludedKeywords: string[]`
- `defaultRemote: boolean`

**Actions:**
- `fetchSettings()` — load from API on app startup
- `updateSettings(partial)` — PUT to `/api/settings`

### `useFavoritesStore`

**State:**
- `favoriteIds: Set<number>` — maintained in sync with backend

**Actions:**
- `fetchFavorites()` — load all favorited job IDs
- `addFavorite(jobId)` — POST `/api/jobs/{id}/favorite`
- `removeFavorite(jobId)` — DELETE `/api/jobs/{id}/favorite`
- `isFavorite(jobId) → boolean`

### `useUIStore`

**State:**
- `toasts: Toast[]` — active notification messages

**Actions:**
- `showSuccess(msg)` — green toast
- `showError(msg)` — red toast
- `showInfo(msg)` — neutral toast

### `useStatsStore`

**State:**
- `stats: StatsResponse | null`

**Actions:**
- `fetchStats()` — load aggregate counts

---

## Component Specifications

### `Sidebar.vue`

Left navigation panel (240px fixed width).

Sections (top to bottom):
1. **Header** — HireWire brand logo + title
2. **Search** — company name filter input (client-side, no API call)
3. **Static nav** — "All Jobs" and "Favorites" links
4. **Companies section header** — "Companies" label + global sync (↻) + add (+) buttons
5. **Company list** — scrollable; each item shows name, job count badge; hover reveals per-company sync (↻) and delete (✕) buttons

Behavior:
- Clicking a company sets `selectedCompanyId` → jobs store auto-fetches scoped jobs
- Sync button triggers `companiesStore.syncCompany(id)`, spins while in progress
- Global sync (↻) calls `POST /api/companies/sync-all` then refreshes companies + jobs
- Delete (✕) calls `companiesStore.deleteCompany(id)` with a confirm dialog

### `AddCompanyModal.vue`

Modal overlay for adding a new tracked company.

Flow:
1. User pastes a career page URL
2. "Detect" button calls `companiesStore.detectAts(url)`
3. On success: ATS type, slug, and capitalized slug as name are pre-filled
4. User can edit the name; ATS fields are shown read-only after detection
5. "Add Company" submits `companiesStore.createCompany()`, then:
   - Immediately selects the new company (`companiesStore.selectCompany(id)`)
   - Triggers `companiesStore.syncCompany(id)` in the background

### `DashboardView.vue`

Main layout: `Sidebar` on the left, job list + detail on the right. Title shows selected company name or "All Jobs".

### `JobList.vue`

Paginated list of `JobCard` components. Shows skeleton cards while loading. Includes `SearchBar`, `FilterPanel`, and `SortControls` above the list.

### `JobDetail.vue`

Right-hand detail panel. Renders `description` as HTML (`v-html`). Shows company, location, job type, salary, date posted, and a link to the original posting.

### `SettingsView.vue`

User preferences form with three sections:

**Job Filters**
- Preferred Locations — chip/tag input; press Enter or comma to add; backspace to remove last
- Show only remote jobs by default — checkbox (suppresses location filters when checked)

**Content Filters**
- Included Keywords — comma-separated; title must match at least one
- Excluded Keywords — comma-separated; title must not match any

**About HireWire**
- Version number

---

## TypeScript Interfaces

Defined in `frontend/src/types/api.ts`. Match Pydantic response schemas exactly.

```typescript
type ATSType = 'greenhouse' | 'lever' | 'ashby'

interface TrackedCompany {
  id: number
  name: string
  website: string | null
  ats_type: ATSType | null
  ats_identifier: string | null
  last_scraped: string | null
  job_count: number
  enabled: boolean
  created_at: string
}

interface TrackedCompanyCreate {
  name: string
  ats_type?: ATSType | null
  ats_identifier?: string | null
  enabled?: boolean
}

interface TrackedCompanyUpdate {
  name?: string
  ats_type?: ATSType | null
  ats_identifier?: string | null
  enabled?: boolean
}

interface CompanyDetectRequest {
  url: string
}

interface CompanyDetectResponse {
  url: string
  ats_type: ATSType | null
  ats_identifier: string | null
  detected: boolean
}

type JobType = 'full_time' | 'part_time' | 'contract' | 'internship'
type SalaryInterval = 'yearly' | 'monthly' | 'weekly' | 'daily' | 'hourly'
type CompanySize = '1-10' | '11-50' | '51-200' | '201-500' | '501-1000' | '1000+'

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
  job_type: JobType | null
  salary_min: number | null
  salary_max: number | null
  salary_interval: SalaryInterval | null
  date_posted: string | null
  first_seen: string
  company_size: CompanySize | null
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

interface JobListParams {
  page?: number
  per_page?: number
  q?: string
  company_id?: number | null
  location?: string
  is_remote?: boolean
  company_size?: CompanySize[]
  job_type?: JobType
  source?: string
  posted_after?: string
  sort_by?: 'date_posted' | 'company' | 'title'
  sort_order?: 'asc' | 'desc'
  include_hidden?: boolean
  favorites_only?: boolean
  // From settings
  preferred_locations?: string[]
  included_keywords?: string[]
  excluded_keywords?: string[]
}

interface UserSettings {
  preferred_locations: string[]
  included_keywords: string[]
  excluded_keywords: string[]
  default_remote: boolean
}

interface UserSettingsResponse extends UserSettings {
  updated_at: string
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

---

## Build and Deployment

```bash
# Development (Vite HMR, requires Node.js)
cd frontend && npm run dev

# Production build
cd frontend && npm run build
# Output: frontend/dist/

# TypeScript check (also runs in CI)
cd frontend && npx vue-tsc --noEmit
```

In Docker, the frontend is built during the image build stage and copied to `/app/static`. The FastAPI backend serves it directly — no separate web server needed.
