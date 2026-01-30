import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Job, JobListResponse } from '@/types/api'
import { useApi } from '@/composables/useApi'
import { useJobsStore } from './jobs'

export const useFavoritesStore = defineStore('favorites', () => {
  const api = useApi()
  
  // State
  
  /** Set of favorite job IDs for fast lookup */
  const favoriteIds = ref<Set<number>>(new Set())
  
  /** Full favorite jobs list (for Favorites page) */
  const favorites = ref<Job[]>([])
  
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  
  // Getters
  const favoriteCount = computed(() => favoriteIds.value.size)
  
  function isFavorite(jobId: number): boolean {
    return favoriteIds.value.has(jobId)
  }
  
  // Actions
  
  /**
   * Fetch all favorites
   */
  async function fetchFavorites() {
    isLoading.value = true
    error.value = null
    
    try {
      const response = await api.get<JobListResponse>('/api/jobs', {
        favorites_only: true,
        per_page: 100,
      })
      favorites.value = response.jobs
      
      // Sync favoriteIds set
      favoriteIds.value = new Set(response.jobs.map(j => j.id))
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load favorites'
      console.error('Failed to fetch favorites:', e)
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Add job to favorites (optimistic update)
   */
  async function addFavorite(jobId: number) {
    const jobsStore = useJobsStore()
    
    // Optimistic update
    favoriteIds.value.add(jobId)
    jobsStore.updateJobInList(jobId, { is_favorite: true })
    
    try {
      await api.post(`/api/jobs/${jobId}/favorite`)
    } catch (e) {
      // Rollback on error
      favoriteIds.value.delete(jobId)
      jobsStore.updateJobInList(jobId, { is_favorite: false })
      throw e
    }
  }
  
  /**
   * Remove job from favorites (optimistic update)
   */
  async function removeFavorite(jobId: number) {
    const jobsStore = useJobsStore()
    
    // Optimistic update
    favoriteIds.value.delete(jobId)
    jobsStore.updateJobInList(jobId, { is_favorite: false })
    
    // Remove from favorites list if present
    const index = favorites.value.findIndex(j => j.id === jobId)
    let removed: Job | null = null
    if (index !== -1) {
      removed = favorites.value[index]
      favorites.value.splice(index, 1)
    }
    
    try {
      await api.delete(`/api/jobs/${jobId}/favorite`)
    } catch (e) {
      // Rollback on error
      favoriteIds.value.add(jobId)
      jobsStore.updateJobInList(jobId, { is_favorite: true })
      if (removed && index !== -1) {
        favorites.value.splice(index, 0, removed)
      }
      throw e
    }
  }
  
  /**
   * Toggle favorite status
   */
  async function toggleFavorite(jobId: number) {
    if (isFavorite(jobId)) {
      await removeFavorite(jobId)
    } else {
      await addFavorite(jobId)
    }
  }
  
  /**
   * Initialize favorites from job list
   * Call this after fetching jobs to sync the favoriteIds set
   */
  function syncFromJobs(jobs: Job[]) {
    jobs.forEach(job => {
      if (job.is_favorite) {
        favoriteIds.value.add(job.id)
      }
    })
  }
  
  return {
    // State
    favoriteIds,
    favorites,
    isLoading,
    error,
    
    // Getters
    favoriteCount,
    isFavorite,
    
    // Actions
    fetchFavorites,
    addFavorite,
    removeFavorite,
    toggleFavorite,
    syncFromJobs,
  }
})
