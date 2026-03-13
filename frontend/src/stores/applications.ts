import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { JobWithDescription, JobListResponse } from '@/types/api'
import { useApi } from '@/composables/useApi'
import { useJobsStore } from './jobs'

export const useApplicationsStore = defineStore('applications', () => {
  const api = useApi()

  /** Set of applied job IDs for fast lookup */
  const appliedIds = ref<Set<number>>(new Set())

  /** Full applied jobs list (for Applied page) */
  const appliedJobs = ref<JobWithDescription[]>([])

  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const appliedCount = computed(() => appliedIds.value.size)

  function isApplied(jobId: number): boolean {
    return appliedIds.value.has(jobId)
  }

  async function fetchApplied() {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.get<JobListResponse>('/api/jobs', {
        applied_only: true,
        per_page: 100,
        include_hidden: true,
      })
      appliedJobs.value = response.jobs
      appliedIds.value = new Set(response.jobs.map((j) => j.id))
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load applied jobs'
    } finally {
      isLoading.value = false
    }
  }

  async function markApplied(jobId: number) {
    const jobsStore = useJobsStore()

    // Optimistic update
    appliedIds.value.add(jobId)
    jobsStore.updateJobInList(jobId, { is_applied: true })

    try {
      await api.post(`/api/jobs/${jobId}/apply`)
    } catch (e) {
      appliedIds.value.delete(jobId)
      jobsStore.updateJobInList(jobId, { is_applied: false })
      throw e
    }
  }

  async function unmarkApplied(jobId: number) {
    const jobsStore = useJobsStore()

    // Optimistic update
    appliedIds.value.delete(jobId)
    jobsStore.updateJobInList(jobId, { is_applied: false })

    const idx = appliedJobs.value.findIndex((j) => j.id === jobId)
    let removed: JobWithDescription | null = null
    if (idx !== -1) {
      removed = appliedJobs.value[idx]
      appliedJobs.value.splice(idx, 1)
    }

    try {
      await api.delete(`/api/jobs/${jobId}/apply`)
    } catch (e) {
      appliedIds.value.add(jobId)
      jobsStore.updateJobInList(jobId, { is_applied: true })
      if (removed && idx !== -1) {
        appliedJobs.value.splice(idx, 0, removed)
      }
      throw e
    }
  }

  async function toggleApplied(jobId: number) {
    if (isApplied(jobId)) {
      await unmarkApplied(jobId)
    } else {
      await markApplied(jobId)
    }
  }

  /** Sync applied state from bulk job load */
  function syncFromJobs(jobs: JobWithDescription[]) {
    for (const job of jobs) {
      if (job.is_applied) {
        appliedIds.value.add(job.id)
      }
    }
  }

  return {
    appliedIds,
    appliedJobs,
    isLoading,
    error,
    appliedCount,
    isApplied,
    fetchApplied,
    markApplied,
    unmarkApplied,
    toggleApplied,
    syncFromJobs,
  }
})
