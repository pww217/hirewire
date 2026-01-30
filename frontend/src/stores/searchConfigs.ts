import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SearchConfig } from '@/types/api'
import { useApi } from '@/composables/useApi'

export interface SearchConfigCreate {
  name: string
  search_term: string
  location?: string | null
  distance?: number | null
  is_remote?: boolean
  hours_old?: number
  results_wanted?: number
  country?: string
  enabled?: boolean
}

export interface SearchConfigUpdate {
  name?: string
  search_term?: string
  location?: string | null
  distance?: number | null
  is_remote?: boolean
  hours_old?: number
  results_wanted?: number
  country?: string
  enabled?: boolean
}

interface SearchConfigListResponse {
  configs: SearchConfig[]
  total: number
}

interface SearchConfigToggleResponse {
  id: number
  enabled: boolean
}

export const useSearchConfigsStore = defineStore('searchConfigs', () => {
  const api = useApi()

  // State
  const configs = ref<SearchConfig[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const enabledConfigs = computed(() => configs.value.filter(c => c.enabled))
  const disabledConfigs = computed(() => configs.value.filter(c => !c.enabled))
  const totalConfigs = computed(() => configs.value.length)

  // Actions

  /**
   * Fetch all search configs
   */
  async function fetchConfigs() {
    isLoading.value = true
    error.value = null

    try {
      const response = await api.get<SearchConfigListResponse>('/api/search-configs')
      configs.value = response.configs
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load search configs'
      console.error('Failed to fetch search configs:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Create a new search config
   */
  async function createConfig(data: SearchConfigCreate): Promise<SearchConfig | null> {
    try {
      const newConfig = await api.post<SearchConfig>('/api/search-configs', data as Record<string, unknown>)
      configs.value.push(newConfig)
      return newConfig
    } catch (e) {
      console.error('Failed to create search config:', e)
      throw e
    }
  }

  /**
   * Update a search config
   */
  async function updateConfig(id: number, data: SearchConfigUpdate): Promise<SearchConfig | null> {
    try {
      const updated = await api.put<SearchConfig>(`/api/search-configs/${id}`, data as Record<string, unknown>)
      const index = configs.value.findIndex(c => c.id === id)
      if (index !== -1) {
        configs.value[index] = updated
      }
      return updated
    } catch (e) {
      console.error('Failed to update search config:', e)
      throw e
    }
  }

  /**
   * Delete a search config
   */
  async function deleteConfig(id: number): Promise<void> {
    try {
      await api.delete(`/api/search-configs/${id}`)
      configs.value = configs.value.filter(c => c.id !== id)
    } catch (e) {
      console.error('Failed to delete search config:', e)
      throw e
    }
  }

  /**
   * Toggle a search config's enabled status
   */
  async function toggleConfig(id: number): Promise<void> {
    try {
      const response = await api.patch<SearchConfigToggleResponse>(`/api/search-configs/${id}/toggle`)
      const index = configs.value.findIndex(c => c.id === id)
      if (index !== -1) {
        configs.value[index].enabled = response.enabled
      }
    } catch (e) {
      console.error('Failed to toggle search config:', e)
      throw e
    }
  }

  return {
    // State
    configs,
    isLoading,
    error,

    // Getters
    enabledConfigs,
    disabledConfigs,
    totalConfigs,

    // Actions
    fetchConfigs,
    createConfig,
    updateConfig,
    deleteConfig,
    toggleConfig,
  }
})
