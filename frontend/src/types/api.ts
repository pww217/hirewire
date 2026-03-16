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
  is_seen: boolean
  is_applied: boolean
  glassdoor_rating: number | null
  glassdoor_url: string | null
}

/**
 * Job with description included - matches JobWithDescription / GET /api/jobs/all
 * Used for client-side bulk loading and filtering.
 */
export interface JobWithDescription extends Job {
  description: string | null
}

/**
 * Bulk job response - matches JobBulkResponse / GET /api/jobs/all
 */
export interface JobBulkResponse {
  jobs: JobWithDescription[]
  total: number
}

/**
 * Extended job with description - matches JobDetailResponse
 */
export interface JobDetail extends JobWithDescription {
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
  jobs: JobWithDescription[]
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
}

// ============================================================================
// Settings Types
// ============================================================================

/**
 * User settings
 */
export interface UserSettings {
  preferred_locations: string[]
  title_keywords: string[]
  description_keywords: string[]
  excluded_keywords: string[]
  default_remote: boolean
  posted_after: string | null
  min_glassdoor_rating: number | null
  job_type: string | null
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
  glassdoor_id: number | null
  glassdoor_rating: number | null
  glassdoor_url: string | null
  rating_updated_at: string | null
}

export interface TrackedCompanyCreate {
  name: string
  website?: string | null
  ats_type?: ATSType | null
  ats_identifier?: string | null
  enabled?: boolean
}

export interface TrackedCompanyUpdate {
  name?: string
  website?: string | null
  ats_type?: ATSType | null
  ats_identifier?: string | null
  enabled?: boolean
}

export interface CompanyDetectRequest {
  url: string
}

export interface CompanyDetectResponse {
  url: string
  ats_type: ATSType | null
  ats_identifier: string | null
  detected: boolean
}

export interface SyncResponse {
  success: boolean
  new_jobs: number
  updated_jobs: number
  duration_ms: number
  error: string | null
  started_at: string
}

// ============================================================================
// Stats Types
// ============================================================================

export interface SourceStats {
  source: string
  count: number
}

export interface StatsResponse {
  total_jobs: number
  jobs_last_24h: number
  jobs_last_7d: number
  jobs_by_source: SourceStats[]
  last_job_added: string | null
}

// ============================================================================
// User Job State Response Types
// ============================================================================

export interface SeenResponse {
  id: number
  is_seen: boolean
  seen_at: string | null
}

export interface ApplyResponse {
  id: number
  is_applied: boolean
  applied_at: string | null
}
