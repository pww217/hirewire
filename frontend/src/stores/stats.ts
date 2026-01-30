import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { StatsResponse } from '@/types/api'
import { useApi } from '@/composables/useApi'

export const useStatsStore = defineStore('stats', () => {
  const api = useApi()

  // State
  const stats = ref<StatsResponse | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const totalJobs = computed(() => stats.value?.total_jobs || 0)
  const jobsLast24h = computed(() => stats.value?.jobs_last_24h || 0)
  const jobsLast7d = computed(() => stats.value?.jobs_last_7d || 0)
  const enabledConfigs = computed(() => stats.value?.enabled_configs || 0)
  const lastJobAdded = computed(() => stats.value?.last_job_added || null)
  const jobsBySource = computed(() => stats.value?.jobs_by_source || [])

  /**
   * Format relative time for last job added
   */
  const lastUpdatedFormatted = computed(() => {
    if (!lastJobAdded.value) return 'Never'
    
    const date = new Date(lastJobAdded.value)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor(diff / (1000 * 60))
    
    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  })

  // Actions

  /**
   * Fetch stats from API
   */
  async function fetchStats() {
    isLoading.value = true
    error.value = null

    try {
      stats.value = await api.get<StatsResponse>('/api/stats', undefined, { showErrorToast: false })
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load stats'
      console.error('Failed to fetch stats:', e)
    } finally {
      isLoading.value = false
    }
  }

  return {
    // State
    stats,
    isLoading,
    error,

    // Getters
    totalJobs,
    jobsLast24h,
    jobsLast7d,
    enabledConfigs,
    lastJobAdded,
    lastUpdatedFormatted,
    jobsBySource,

    // Actions
    fetchStats,
  }
})
