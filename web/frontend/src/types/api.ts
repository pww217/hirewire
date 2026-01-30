/**
 * HireWire API Types
 * Shared TypeScript interfaces matching backend Pydantic models
 */

// ============================================================================
// Job Types
// ============================================================================

export type JobType = 'full_time' | 'part_time' | 'contract' | 'internship'
export type SalaryInterval = 'yearly' | 'monthly' | 'weekly' | 'daily' | 'hourly'
export type CompanySize = '1-10' | '11-50' | '51-200' | '201-500' | '501-1000' | '1000+'
export type ApplicationStatus = 'applied' | 'interviewing' | 'rejected' | 'offer'
export type ATSType = 'greenhouse' | 'lever' | 'ashby'

/**
 * Job response from API - matches JobResponse in api-backend.md
 */
export interface Job {
  id: number
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

/**
 * Extended job with description - matches JobDetailResponse
 */
export interface JobDetail extends Job {
  description: string | null
  last_seen: string
  application: Application | null
}

/**
 * Application object (nested in JobDetail)
 */
export interface Application {
  id: number
  job_id: number
  status: ApplicationStatus
  notes: string | null
  applied_at: string | null
  updated_at: string
}

// ============================================================================
// API Response Types
// ============================================================================

/**
 * Paginated job list response
 */
export interface JobListResponse {
  jobs: Job[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

/**
 * Validation error detail from FastAPI
 */
export interface ValidationError {
  loc: (string | number)[]
  msg: string
  type: string
}

/**
 * Generic API error response
 */
export interface ApiError {
  detail: string | ValidationError[]
}

// ============================================================================
// Query Parameters
// ============================================================================

/**
 * Job list query parameters
 */
export interface JobListParams {
  page?: number
  per_page?: number
  q?: string
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
}

// ============================================================================
// Settings Types
// ============================================================================

/**
 * Search configuration
 */
export interface SearchConfig {
  id: number
  name: string
  search_term: string
  location: string | null
  distance: number | null
  is_remote: boolean
  hours_old: number
  results_wanted: number
  country: string
  enabled: boolean
  created_at: string
  updated_at: string
}

/**
 * User settings
 */
export interface UserSettings {
  excluded_companies: string[]
  excluded_keywords: string[]
  default_location: string | null
  default_remote: boolean
}

export interface UserSettingsResponse extends UserSettings {
  updated_at: string
}

// ============================================================================
// Tracked Companies
// ============================================================================

export interface TrackedCompany {
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

export interface TrackedCompanyCreate {
  name: string
  website?: string | null
  ats_type?: ATSType | null
  ats_identifier?: string | null
}
