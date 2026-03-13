import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useJobsStore } from '@/stores/jobs'

/**
 * Store for tracking which jobs have been viewed.
 * Backed by the database via POST /api/jobs/{id}/seen.
 * isViewed reads from allJobs[].is_seen (already loaded into memory).
 */
export const useViewedStore = defineStore('viewed', () => {
  const api = useApi()
  const isMarkingAllSeen = ref(false)

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

  async function markAsUnread(jobId: number) {
    if (!isViewed(jobId)) return

    const jobsStore = useJobsStore()

    // Optimistic update
    jobsStore.updateJobInList(jobId, { is_seen: false })

    try {
      await api.delete(`/api/jobs/${jobId}/seen`)
    } catch (e) {
      // Roll back optimistic update on failure
      jobsStore.updateJobInList(jobId, { is_seen: true })
      console.warn('Failed to mark job as unread:', e)
    }
  }

  async function markAllSeen(companyId?: number) {
    if (isMarkingAllSeen.value) return
    isMarkingAllSeen.value = true

    const jobsStore = useJobsStore()

    // Optimistic: mark matching jobs as seen locally
    const params: Record<string, unknown> = {}
    if (companyId !== undefined) params.company_id = companyId

    const toMark = jobsStore.allJobs.filter(j =>
      !j.is_seen && (companyId === undefined || j.company_id === companyId)
    )
    for (const j of toMark) {
      jobsStore.updateJobInList(j.id, { is_seen: true })
    }

    try {
      const query = companyId !== undefined ? `?company_id=${companyId}` : ''
      await api.post(`/api/jobs/seen/all${query}`)
    } catch (e) {
      // Roll back optimistic updates
      for (const j of toMark) {
        jobsStore.updateJobInList(j.id, { is_seen: false })
      }
      console.warn('Failed to mark all as seen:', e)
      throw e
    } finally {
      isMarkingAllSeen.value = false
    }
  }

  return {
    isViewed,
    markAsViewed,
    markAsUnread,
    markAllSeen,
    isMarkingAllSeen,
  }
})
