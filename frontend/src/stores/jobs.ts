import { defineStore } from 'pinia'
import { shallowRef, ref, computed } from 'vue'
import MiniSearch from 'minisearch'
import type { JobWithDescription, JobDetail, JobBulkResponse } from '@/types/api'
import { useApi } from '@/composables/useApi'
import { useCompaniesStore } from './companies'

export type SortBy = 'date_posted' | 'company' | 'title' | 'first_seen'
export type SortOrder = 'asc' | 'desc'

export interface FilterState {
  q: string
  locations: string[]
  isRemote: boolean | null
  jobType: string | null
  postedAfter: string | null
  titleKeywords: string[]
  descriptionKeywords: string[]
  excludedKeywords: string[]
  excludedBodyKeywords: string[]
  favoritesOnly: boolean
  minGlassdoorRating: number | null
}

export const DEFAULT_FILTERS: FilterState = {
  q: '',
  locations: [],
  isRemote: null,
  jobType: null,
  postedAfter: null,
  titleKeywords: [],
  descriptionKeywords: [],
  excludedKeywords: [],
  excludedBodyKeywords: [],
  favoritesOnly: false,
  minGlassdoorRating: null,
}

/** Strip HTML tags for plain-text search indexing */
function stripHtml(html: string | null | undefined): string {
  if (!html) return ''
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

/** Escape special regex chars in a user-provided string */
function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Build a regex that matches a keyword at word boundaries.
 * e.g. "data" matches "Data Scientist" but not "Metadata Engineer".
 */
function keywordRegex(kw: string): RegExp {
  return new RegExp(`(?:^|[\\s/\\-_,()])${escapeRegex(kw)}(?=[\\s/\\-_,().]|$)`, 'i')
}

/** Compare dates for sorting, nulls last */
function compareDates(a: string | null, b: string | null, asc: boolean): number {
  if (!a && !b) return 0
  if (!a) return 1
  if (!b) return -1
  const diff = new Date(a).getTime() - new Date(b).getTime()
  return asc ? diff : -diff
}

export const useJobsStore = defineStore('jobs', () => {
  const api = useApi()

  // ── State ──────────────────────────────────────────────────────────────────
  // shallowRef avoids deep reactivity overhead on potentially thousands of objects
  const allJobs = shallowRef<JobWithDescription[]>([])
  const currentJob = ref<JobDetail | null>(null)

  const filters = ref<FilterState>({ ...DEFAULT_FILTERS })
  const sortBy = ref<SortBy>('date_posted')
  const sortOrder = ref<SortOrder>('desc')

  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // ── MiniSearch index ───────────────────────────────────────────────────────
  // Description intentionally excluded: body keyword filters handle that;
  // removing it from the index avoids indexing HTML blobs we may not even have.
  let searchIndex = new MiniSearch<{ id: number; title: string; company: string; location: string }>({
    fields: ['title', 'company', 'location'],
    storeFields: ['id'],
    searchOptions: {
      prefix: true,
      fuzzy: 0.2,
      boost: { title: 3, company: 2, location: 1.5 },
    },
  })

  // IDs matching current text search; null = no text search active
  const searchResultIds = ref<Set<number> | null>(null)

  function buildSearchIndex(jobs: JobWithDescription[]) {
    searchIndex = new MiniSearch({
      fields: ['title', 'company', 'location'],
      storeFields: ['id'],
      searchOptions: {
        prefix: true,
        fuzzy: 0.2,
        boost: { title: 3, company: 2, location: 1.5 },
      },
    })
    searchIndex.addAll(
      jobs.map(j => ({
        id: j.id,
        title: j.title,
        company: j.company,
        location: [j.location_raw, j.location_city, j.location_state, j.location_country]
          .filter(Boolean)
          .join(' '),
      }))
    )
  }

  // ── Debounced search ───────────────────────────────────────────────────────
  let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

  function runSearch(q: string) {
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
    if (!q.trim()) {
      searchResultIds.value = null
      return
    }
    searchDebounceTimer = setTimeout(() => {
      const results = searchIndex.search(q, { combineWith: 'AND' })
      searchResultIds.value = new Set(results.map(r => r.id))
    }, 300)
  }

  // Whether descriptions were included in the last fetch (only true when body filters are active)
  const descriptionsLoaded = ref(false)

  // ── Cached regex patterns (recompute only when keyword arrays change) ──────
  const titleIncludePatterns = computed(() => filters.value.titleKeywords.map(keywordRegex))
  const titleExcludePatterns = computed(() => filters.value.excludedKeywords.map(keywordRegex))
  const bodyIncludePatterns = computed(() => filters.value.descriptionKeywords.map(keywordRegex))
  const bodyExcludePatterns = computed(() => filters.value.excludedBodyKeywords.map(keywordRegex))
  const locationPatterns = computed(() => filters.value.locations.map(keywordRegex))

  // ── Getters ────────────────────────────────────────────────────────────────
  const activeFilterCount = computed(() => {
    let count = 0
    if (filters.value.q) count++
    if (filters.value.locations.length > 0) count++
    if (filters.value.isRemote !== null) count++
    if (filters.value.jobType) count++
    if (filters.value.postedAfter) count++
    if (filters.value.titleKeywords.length > 0) count++
    if (filters.value.descriptionKeywords.length > 0) count++
    if (filters.value.excludedKeywords.length > 0) count++
    if (filters.value.excludedBodyKeywords.length > 0) count++
    if (filters.value.favoritesOnly) count++
    if (filters.value.minGlassdoorRating !== null) count++
    return count
  })

  const filteredJobs = computed(() => {
    const companiesStore = useCompaniesStore()
    let result = allJobs.value

    // 1. Company scope (sidebar selection)
    if (companiesStore.selectedCompanyId !== null) {
      const cid = companiesStore.selectedCompanyId
      result = result.filter(j => j.company_id === cid)
    }

    // 2. Full-text search via MiniSearch
    if (filters.value.q.trim() && searchResultIds.value !== null) {
      const ids = searchResultIds.value
      result = result.filter(j => ids.has(j.id))
    }

    // 3. Location — OR across all chips (word-boundary)
    if (filters.value.locations.length > 0) {
      const patterns = locationPatterns.value
      result = result.filter(j =>
        patterns.some(re =>
          (j.location_city && re.test(j.location_city)) ||
          (j.location_state && re.test(j.location_state)) ||
          (j.location_raw && re.test(j.location_raw)) ||
          (j.location_country && re.test(j.location_country))
        )
      )
    }

    // 4. Remote only
    if (filters.value.isRemote === true) {
      result = result.filter(j => j.is_remote)
    }

    // 5. Job type
    if (filters.value.jobType) {
      const jt = filters.value.jobType
      result = result.filter(j => j.job_type === jt)
    }

    // 6. Posted after
    if (filters.value.postedAfter) {
      const now = new Date()
      let cutoff: Date | null = null
      switch (filters.value.postedAfter) {
        case 'today':
          cutoff = new Date(now.getFullYear(), now.getMonth(), now.getDate())
          break
        case 'week':
          cutoff = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
          break
        case 'month':
          cutoff = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
          break
      }
      if (cutoff) {
        const cutoffMs = cutoff.getTime()
        result = result.filter(j => j.date_posted && new Date(j.date_posted).getTime() >= cutoffMs)
      }
    }

    // 7a. Title keywords (OR) — word-boundary; cached patterns
    if (filters.value.titleKeywords.length > 0) {
      const patterns = titleIncludePatterns.value
      result = result.filter(j => patterns.some(re => re.test(j.title)))
    }

    // 7b. Title exclude keywords — word-boundary; cached patterns
    if (filters.value.excludedKeywords.length > 0) {
      const patterns = titleExcludePatterns.value
      result = result.filter(j => !patterns.some(re => re.test(j.title)))
    }

    // 8. Body keyword filters — strip description once, test include + exclude together
    const hasBodyInclude = filters.value.descriptionKeywords.length > 0
    const hasBodyExclude = filters.value.excludedBodyKeywords.length > 0
    if ((hasBodyInclude || hasBodyExclude) && descriptionsLoaded.value) {
      const incPatterns = bodyIncludePatterns.value
      const excPatterns = bodyExcludePatterns.value
      result = result.filter(j => {
        const text = stripHtml(j.description)
        if (hasBodyInclude && !incPatterns.some(re => re.test(text))) return false
        if (hasBodyExclude && excPatterns.some(re => re.test(text))) return false
        return true
      })
    }

    // 9. Favorites only
    if (filters.value.favoritesOnly) {
      result = result.filter(j => j.is_favorite)
    }

    // 10. Min Glassdoor rating — jobs without ratings are included, not excluded
    if (filters.value.minGlassdoorRating !== null) {
      const min = filters.value.minGlassdoorRating
      result = result.filter(j => j.glassdoor_rating === null || j.glassdoor_rating >= min)
    }

    // 11. Sort
    const asc = sortOrder.value === 'asc'
    return [...result].sort((a, b) => {
      switch (sortBy.value) {
        case 'date_posted':
          return compareDates(a.date_posted, b.date_posted, asc)
        case 'first_seen':
          return compareDates(a.first_seen, b.first_seen, asc)
        case 'company': {
          const cmp = a.company.localeCompare(b.company)
          return asc ? cmp : -cmp
        }
        case 'title': {
          const cmp = a.title.localeCompare(b.title)
          return asc ? cmp : -cmp
        }
        default:
          return compareDates(a.date_posted, b.date_posted, asc)
      }
    })
  })

  const total = computed(() => filteredJobs.value.length)
  const hasJobs = computed(() => allJobs.value.length > 0)

  const unfilteredTotal = computed(() => {
    const companiesStore = useCompaniesStore()
    if (companiesStore.selectedCompanyId !== null) {
      const cid = companiesStore.selectedCompanyId
      return allJobs.value.filter(j => j.company_id === cid).length
    }
    return allJobs.value.length
  })

  /** Count of filtered jobs not yet seen by the user */
  const unseenTotal = computed(() => filteredJobs.value.filter(j => !j.is_seen).length)

  /** Map of company_id -> unseen job count */
  const unseenByCompany = computed(() => {
    const map = new Map<number, number>()
    for (const job of allJobs.value) {
      if (!job.is_seen && job.company_id !== null) {
        map.set(job.company_id, (map.get(job.company_id) ?? 0) + 1)
      }
    }
    return map
  })

  // ── Settings persistence ───────────────────────────────────────────────────

  interface UserSettingsResponse {
    preferred_locations: string[]
    title_keywords: string[]
    description_keywords: string[]
    excluded_keywords: string[]
    excluded_body_keywords: string[]
    default_remote: boolean
    min_glassdoor_rating: number | null
    job_type: string | null
  }

  /** Hydrate filters from persisted user settings (called on store init). */
  async function loadSettings() {
    try {
      const s = await api.get<UserSettingsResponse>('/api/settings', undefined, { showErrorToast: false })
      filters.value = {
        ...filters.value,
        locations: s.preferred_locations ?? [],
        titleKeywords: s.title_keywords ?? [],
        descriptionKeywords: s.description_keywords ?? [],
        excludedKeywords: s.excluded_keywords ?? [],
        excludedBodyKeywords: s.excluded_body_keywords ?? [],
        isRemote: s.default_remote ? true : null,
        minGlassdoorRating: s.min_glassdoor_rating ?? null,
        jobType: s.job_type ?? null,
      }
    } catch {
      // Non-fatal: silently fall back to defaults
    }
  }

  let persistTimer: ReturnType<typeof setTimeout> | null = null

  /** Debounced persist of filter state to user_settings (500ms). */
  function schedulePersist() {
    if (persistTimer) clearTimeout(persistTimer)
    persistTimer = setTimeout(() => {
      const f = filters.value
      api.put('/api/settings', {
        preferred_locations: f.locations,
        title_keywords: f.titleKeywords,
        description_keywords: f.descriptionKeywords,
        excluded_keywords: f.excludedKeywords,
        excluded_body_keywords: f.excludedBodyKeywords,
        default_remote: f.isRemote === true,
        min_glassdoor_rating: f.minGlassdoorRating,
        job_type: f.jobType,
      } as Record<string, unknown>, { showErrorToast: false }).catch(() => {/* ignore */})
    }, 500)
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  /**
   * Fetch all active jobs from the bulk endpoint.
   * When body keyword filters are active, requests descriptions; otherwise omits them
   * to reduce payload size. Called on mount, after sync, and when body filters are activated.
   */
  async function fetchAllJobs() {
    const needsDescriptions =
      filters.value.descriptionKeywords.length > 0 ||
      filters.value.excludedBodyKeywords.length > 0
    const url = needsDescriptions
      ? '/api/jobs/all?include_descriptions=true'
      : '/api/jobs/all'

    isLoading.value = true
    error.value = null
    try {
      const response = await api.get<JobBulkResponse>(url)
      allJobs.value = response.jobs
      descriptionsLoaded.value = needsDescriptions
      buildSearchIndex(response.jobs)
      if (filters.value.q.trim()) {
        runSearch(filters.value.q)
      }
      // Fire-and-forget: mark stale unseen jobs as seen
      markStaleAsSeen(response.jobs)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load jobs'
      console.error('Failed to fetch jobs:', e)
    } finally {
      isLoading.value = false
    }
  }

  const STALE_DAYS = 10

  /**
   * Batch-mark stale unseen jobs (date_posted > STALE_DAYS ago) as seen.
   * Fire-and-forget — failures are silently ignored.
   * Uses the batch endpoint to reduce N individual API calls to one.
   */
  function markStaleAsSeen(jobs: JobWithDescription[]) {
    const cutoff = Date.now() - STALE_DAYS * 86_400_000
    const staleUnseen = jobs.filter(
      (j) => !j.is_seen && j.date_posted && new Date(j.date_posted).getTime() < cutoff
    )
    if (staleUnseen.length === 0) return

    // Optimistic local update
    for (const j of staleUnseen) {
      updateJobInList(j.id, { is_seen: true })
    }

    // Single batch call instead of N individual calls
    api.post('/api/jobs/seen/batch', { job_ids: staleUnseen.map(j => j.id) })
      .catch(() => {/* ignore */})
  }

  /**
   * Fetch single job detail (still uses the individual endpoint)
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
   * Update filters. Text search (q) triggers debounced MiniSearch query.
   * If body keyword filters become active and descriptions aren't loaded, re-fetches with them.
   */
  function setFilters(newFilters: Partial<FilterState>) {
    const prevQ = filters.value.q
    const hadBodyFilters =
      filters.value.descriptionKeywords.length > 0 ||
      filters.value.excludedBodyKeywords.length > 0

    filters.value = { ...filters.value, ...newFilters }

    if (newFilters.q !== undefined && newFilters.q !== prevQ) {
      runSearch(newFilters.q)
    }

    // Re-fetch with descriptions if body filters just became active
    const hasBodyFilters =
      filters.value.descriptionKeywords.length > 0 ||
      filters.value.excludedBodyKeywords.length > 0
    if (!hadBodyFilters && hasBodyFilters && !descriptionsLoaded.value) {
      fetchAllJobs()
    }

    // Persist everything except transient fields (q, favoritesOnly)
    if (Object.keys(newFilters).some(k => k !== 'q' && k !== 'favoritesOnly')) {
      schedulePersist()
    }
  }

  function clearFilters() {
    filters.value = { ...DEFAULT_FILTERS }
    searchResultIds.value = null
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
    schedulePersist()
  }

  function setSort(by: SortBy, order: SortOrder) {
    sortBy.value = by
    sortOrder.value = order
  }

  /**
   * Update a job's is_favorite / is_hidden in local state without refetch.
   */
  function updateJobInList(jobId: number, updates: Partial<JobWithDescription>) {
    allJobs.value = allJobs.value.map(j => j.id === jobId ? { ...j, ...updates } : j)
  }

  function removeJobsByCompany(companyId: number) {
    allJobs.value = allJobs.value.filter(j => j.company_id !== companyId)
  }

  /**
   * Hide a job locally (remove from visible list immediately)
   */
  async function hideJob(jobId: number): Promise<JobWithDescription | null> {
    const jobToHide = allJobs.value.find(j => j.id === jobId) ?? null
    try {
      await api.post(`/api/jobs/${jobId}/hide`)
      allJobs.value = allJobs.value.filter(j => j.id !== jobId)
      return jobToHide
    } catch (e) {
      console.error('Failed to hide job:', e)
      throw e
    }
  }

  /**
   * Unhide a job (undo hide)
   */
  async function unhideJob(jobId: number, jobData?: JobWithDescription) {
    try {
      await api.delete(`/api/jobs/${jobId}/hide`)
      if (jobData && !allJobs.value.find(j => j.id === jobId)) {
        allJobs.value = [jobData, ...allJobs.value]
      } else {
        await fetchAllJobs()
      }
    } catch (e) {
      console.error('Failed to unhide job:', e)
      throw e
    }
  }

  // ── Auto-refresh ───────────────────────────────────────────────────────────
  const AUTO_REFRESH_INTERVAL = 60_000
  const lastRefresh = ref<Date>(new Date())
  const autoRefreshEnabled = ref(true)
  let refreshTimer: ReturnType<typeof setInterval> | null = null

  function startAutoRefresh() {
    if (refreshTimer) return
    refreshTimer = setInterval(() => {
      if (autoRefreshEnabled.value && document.visibilityState === 'visible') {
        fetchAllJobs()
        lastRefresh.value = new Date()
      }
    }, AUTO_REFRESH_INTERVAL)
    document.addEventListener('visibilitychange', handleVisibilityChange)
  }

  function stopAutoRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }

  function toggleAutoRefresh() {
    autoRefreshEnabled.value = !autoRefreshEnabled.value
  }

  function handleVisibilityChange() {
    if (document.visibilityState === 'visible' && autoRefreshEnabled.value) {
      const elapsed = Date.now() - lastRefresh.value.getTime()
      if (elapsed > AUTO_REFRESH_INTERVAL) {
        fetchAllJobs()
        lastRefresh.value = new Date()
      }
    }
  }

  const lastRefreshFormatted = computed(() => lastRefresh.value.toLocaleTimeString())

  return {
    // State
    allJobs,
    currentJob,
    filters,
    sortBy,
    sortOrder,
    isLoading,
    error,
    searchResultIds,
    descriptionsLoaded,

    // Auto-refresh state
    lastRefresh,
    lastRefreshFormatted,
    autoRefreshEnabled,

    // Getters
    filteredJobs,
    total,
    unfilteredTotal,
    hasJobs,
    activeFilterCount,
    unseenTotal,
    unseenByCompany,

    // Actions
    fetchAllJobs,
    fetchJobDetail,
    loadSettings,
    setFilters,
    clearFilters,
    setSort,
    updateJobInList,
    removeJobsByCompany,
    hideJob,
    unhideJob,
    runSearch,

    // Auto-refresh
    startAutoRefresh,
    stopAutoRefresh,
    toggleAutoRefresh,
  }
})
