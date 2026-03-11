import { defineStore } from 'pinia'
import { useApi } from '@/composables/useApi'
import { useJobsStore } from '@/stores/jobs'

/**
 * Store for tracking which jobs have been viewed.
 * Backed by the database via POST /api/jobs/{id}/seen.
 * isViewed reads from allJobs[].is_seen (already loaded into memory).
 */
export const useViewedStore = defineStore('viewed', () => {
  const api = useApi()

  function isViewed(jobId: number): boolean {
    const jobsStore = useJobsStore()
    const job = jobsStore.allJobs.find(j => j.id === jobId)
    return job?.is_seen ?? false
  }

  async function markAsViewed(jobId: number) {
    if (isViewed(jobId)) return

    const jobsStore = useJobsStore()

    // Optimistic update
    jobsStore.updateJobInList(jobId, { is_seen: true })

    try {
      await api.post(`/api/jobs/${jobId}/seen`)
    } catch (e) {
      // Roll back optimistic update on failure
      jobsStore.updateJobInList(jobId, { is_seen: false })
      console.warn('Failed to mark job as seen:', e)
    }
  }

  return {
    isViewed,
    markAsViewed,
  }
})
