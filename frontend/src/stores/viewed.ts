import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'hirewire_viewed_jobs'
const MAX_VIEWED_JOBS = 1000 // Limit storage size

/**
 * Store for tracking which jobs have been viewed
 * Persisted to localStorage
 */
export const useViewedStore = defineStore('viewed', () => {
  // State - Set of viewed job IDs
  const viewedJobIds = ref<Set<number>>(new Set())
  
  // Load from localStorage on init
  function loadFromStorage() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const ids = JSON.parse(stored) as number[]
        viewedJobIds.value = new Set(ids)
      }
    } catch (e) {
      console.warn('Failed to load viewed jobs from storage:', e)
    }
  }
  
  // Save to localStorage
  function saveToStorage() {
    try {
      const ids = Array.from(viewedJobIds.value)
      // Keep only the most recent jobs if we exceed the limit
      const recentIds = ids.slice(-MAX_VIEWED_JOBS)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(recentIds))
    } catch (e) {
      console.warn('Failed to save viewed jobs to storage:', e)
    }
  }
  
  // Initialize
  loadFromStorage()
  
  // Getters
  const viewedCount = computed(() => viewedJobIds.value.size)
  
  // Actions
  function isViewed(jobId: number): boolean {
    return viewedJobIds.value.has(jobId)
  }
  
  function markAsViewed(jobId: number) {
    if (!viewedJobIds.value.has(jobId)) {
      viewedJobIds.value.add(jobId)
      saveToStorage()
    }
  }
  
  function markMultipleAsViewed(jobIds: number[]) {
    let changed = false
    for (const id of jobIds) {
      if (!viewedJobIds.value.has(id)) {
        viewedJobIds.value.add(id)
        changed = true
      }
    }
    if (changed) {
      saveToStorage()
    }
  }
  
  function clearViewed() {
    viewedJobIds.value.clear()
    saveToStorage()
  }
  
  return {
    viewedJobIds,
    viewedCount,
    isViewed,
    markAsViewed,
    markMultipleAsViewed,
    clearViewed,
  }
})
