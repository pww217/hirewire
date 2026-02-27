import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Job, JobDetail, JobListParams, JobListResponse, CompanySize } from '@/types/api'
import { useApi } from '@/composables/useApi'
import { useSettingsStore } from './settings'
import { useCompaniesStore } from './companies'

export type SortBy = 'date_posted' | 'company' | 'title'
export type SortOrder = 'asc' | 'desc'

export interface FilterState {
  q: string
  location: string
  isRemote: boolean | null
  companySizes: CompanySize[]
  jobType: string | null
  source: string | null
  postedAfter: string | null
}

export const DEFAULT_FILTERS: FilterState = {
  q: '',
  location: '',
  isRemote: null,
  companySizes: [],
  jobType: null,
  source: null,
  postedAfter: null,
}

export const useJobsStore = defineStore('jobs', () => {
  const api = useApi()
  
  // State
  const jobs = ref<Job[]>([])
  const currentJob = ref<JobDetail | null>(null)
  const total = ref(0)
  const page = ref(1)
  const perPage = ref(25)  // Reduced from 50 for better UX - less cognitive load
  const totalPages = ref(0)
  
  const filters = ref<FilterState>({ ...DEFAULT_FILTERS })
  const sortBy = ref<SortBy>('date_posted')
  const sortOrder = ref<SortOrder>('desc')
  
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  
  // Getters
  const hasJobs = computed(() => jobs.value.length > 0)
  const hasNextPage = computed(() => page.value < totalPages.value)
  const hasPrevPage = computed(() => page.value > 1)
  
  const activeFilterCount = computed(() => {
    let count = 0
    if (filters.value.q) count++
    if (filters.value.location) count++
    if (filters.value.isRemote !== null) count++
    if (filters.value.companySizes.length > 0) count++
    if (filters.value.jobType) count++
    if (filters.value.source) count++
    if (filters.value.postedAfter) count++
    return count
  })
  
  // Actions
  
  /**
   * Fetch jobs from API with current filters and pagination
   */
  async function fetchJobs(resetPage = false) {
    if (resetPage) {
      page.value = 1
    }
    
    isLoading.value = true
    error.value = null
    
    try {
      const settingsStore = useSettingsStore()
      const companiesStore = useCompaniesStore()
      
      const params: JobListParams & { preferred_locations?: string[], included_keywords?: string[], excluded_keywords?: string[] } = {
        page: page.value,
        per_page: perPage.value,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
        include_hidden: false,
        favorites_only: false,
      }

      // Scope to selected company if one is active
      if (companiesStore.selectedCompanyId !== null) {
        params.company_id = companiesStore.selectedCompanyId
      }
      
      // Apply filters
      if (filters.value.q) params.q = filters.value.q
      if (filters.value.location) params.location = filters.value.location
      if (filters.value.isRemote !== null) params.is_remote = filters.value.isRemote
      if (filters.value.companySizes.length > 0) {
        params.company_size = filters.value.companySizes
      }
      if (filters.value.jobType) params.job_type = filters.value.jobType as JobListParams['job_type']
      if (filters.value.source) params.source = filters.value.source
      if (filters.value.postedAfter) {
        // Convert relative to absolute date
        const now = new Date()
        let date: Date | null = null
        switch (filters.value.postedAfter) {
          case 'today':
            date = new Date(now.getFullYear(), now.getMonth(), now.getDate())
            break
          case 'week':
            date = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
            break
          case 'month':
            date = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
            break
        }
        if (date) {
          params.posted_after = date.toISOString().split('T')[0]
        }
      }
      
      // Apply settings-based filters (only when no explicit location filter is active and not in remote-only mode)
      if (!filters.value.location && !settingsStore.defaultRemote && settingsStore.preferredLocations.length > 0) {
        params.preferred_locations = settingsStore.preferredLocations
      }
      if (settingsStore.includedKeywords.length > 0) {
        params.included_keywords = settingsStore.includedKeywords
      }
      if (settingsStore.excludedKeywords.length > 0) {
        params.excluded_keywords = settingsStore.excludedKeywords
      }
      
      const response = await api.get<JobListResponse>('/api/jobs', params as unknown as Record<string, unknown>)
      
      jobs.value = response.jobs
      total.value = response.total
      totalPages.value = response.total_pages
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load jobs'
      console.error('Failed to fetch jobs:', e)
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Fetch single job detail
   */
  async function fetchJobDetail(id: number) {
    isLoading.value = true
    error.value = null
    
    try {
      currentJob.value = await api.get<JobDetail>(`/api/jobs/${id}`)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load job'
      console.error('Failed to fetch job detail:', e)
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Set filters and refetch
   */
  function setFilters(newFilters: Partial<FilterState>) {
    filters.value = { ...filters.value, ...newFilters }
    fetchJobs(true)  // Reset to page 1
  }
  
  /**
   * Clear all filters
   */
  function clearFilters() {
    filters.value = { ...DEFAULT_FILTERS }
    fetchJobs(true)
  }
  
  /**
   * Set sort and refetch
   */
  function setSort(by: SortBy, order: SortOrder) {
    sortBy.value = by
    sortOrder.value = order
    fetchJobs(true)
  }
  
  /**
   * Go to specific page
   */
  function goToPage(newPage: number) {
    if (newPage >= 1 && newPage <= totalPages.value) {
      page.value = newPage
      fetchJobs()
    }
  }
  
  /**
   * Update a job in the local state (after favorite/hide)
   */
  function updateJobInList(jobId: number, updates: Partial<Job>) {
    const index = jobs.value.findIndex(j => j.id === jobId)
    if (index !== -1) {
      jobs.value[index] = { ...jobs.value[index], ...updates }
    }
  }
  
  /**
   * Hide a job
   * Returns the hidden job data for potential undo
   */
  async function hideJob(jobId: number): Promise<Job | null> {
    // Store the job data before hiding for undo
    const jobToHide = jobs.value.find(j => j.id === jobId)
    
    try {
      await api.post(`/api/jobs/${jobId}/hide`)
      // Remove from list since we don't show hidden jobs
      jobs.value = jobs.value.filter(j => j.id !== jobId)
      total.value = Math.max(0, total.value - 1)
      return jobToHide || null
    } catch (e) {
      console.error('Failed to hide job:', e)
      throw e
    }
  }
  
  /**
   * Unhide a job (undo hide action)
   */
  async function unhideJob(jobId: number, jobData?: Job) {
    try {
      await api.delete(`/api/jobs/${jobId}/hide`)
      // Add back to list if we have the job data
      if (jobData && !jobs.value.find(j => j.id === jobId)) {
        // Insert at original position or beginning
        jobs.value.unshift(jobData)
        total.value += 1
      } else {
        // Refresh the list to get the job back
        await fetchJobs(false)
      }
    } catch (e) {
      console.error('Failed to unhide job:', e)
      throw e
    }
  }
  
  // ─────────────────────────────────────────────────────────────────────────
  // AUTO-REFRESH
  // ─────────────────────────────────────────────────────────────────────────
  
  const AUTO_REFRESH_INTERVAL = 60_000  // 60 seconds
  const lastRefresh = ref<Date>(new Date())
  const autoRefreshEnabled = ref(true)
  let refreshTimer: ReturnType<typeof setInterval> | null = null
  
  /**
   * Start auto-refresh timer
   * Pauses when tab is not visible to save resources
   */
  function startAutoRefresh() {
    if (refreshTimer) return
    
    refreshTimer = setInterval(() => {
      if (autoRefreshEnabled.value && document.visibilityState === 'visible') {
        fetchJobs(false)  // silent refresh, don't reset page
        lastRefresh.value = new Date()
      }
    }, AUTO_REFRESH_INTERVAL)
    
    // Pause when tab hidden
    document.addEventListener('visibilitychange', handleVisibilityChange)
  }
  
  /**
   * Stop auto-refresh timer
   */
  function stopAutoRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }
  
  /**
   * Toggle auto-refresh on/off
   */
  function toggleAutoRefresh() {
    autoRefreshEnabled.value = !autoRefreshEnabled.value
  }
  
  /**
   * Handle tab visibility changes
   */
  function handleVisibilityChange() {
    if (document.visibilityState === 'visible' && autoRefreshEnabled.value) {
      // Refresh immediately when returning to tab if stale
      const elapsed = Date.now() - lastRefresh.value.getTime()
      if (elapsed > AUTO_REFRESH_INTERVAL) {
        fetchJobs(false)
        lastRefresh.value = new Date()
      }
    }
  }
  
  /**
   * Format last refresh time for display
   */
  const lastRefreshFormatted = computed(() => {
    return lastRefresh.value.toLocaleTimeString()
  })
  
  return {
    // State
    jobs,
    currentJob,
    total,
    page,
    perPage,
    totalPages,
    filters,
    sortBy,
    sortOrder,
    isLoading,
    error,
    
    // Auto-refresh state
    lastRefresh,
    lastRefreshFormatted,
    autoRefreshEnabled,
    
    // Getters
    hasJobs,
    hasNextPage,
    hasPrevPage,
    activeFilterCount,
    
    // Actions
    fetchJobs,
    fetchJobDetail,
    setFilters,
    clearFilters,
    setSort,
    goToPage,
    updateJobInList,
    hideJob,
    unhideJob,
    
    // Auto-refresh actions
    startAutoRefresh,
    stopAutoRefresh,
    toggleAutoRefresh,
  }
})
