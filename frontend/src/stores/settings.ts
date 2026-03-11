import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UserSettingsResponse } from '@/types/api'
import { useApi } from '@/composables/useApi'

/**
 * Settings store — kept for future non-filter preferences (theme, notifications, etc).
 * Job filtering has moved to the FilterPanel and jobs store (client-side).
 */
export const useSettingsStore = defineStore('settings', () => {
  const api = useApi()

  const settings = ref<UserSettingsResponse | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const isInitialized = ref(false)

  async function fetchSettings() {
    isLoading.value = true
    error.value = null
    try {
      settings.value = await api.get<UserSettingsResponse>('/api/settings')
      isInitialized.value = true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load settings'
      console.error('Failed to fetch settings:', e)
    } finally {
      isLoading.value = false
    }
  }

  async function updateSettings(data: Partial<UserSettingsResponse>): Promise<void> {
    try {
      settings.value = await api.put<UserSettingsResponse>('/api/settings', data as Record<string, unknown>)
    } catch (e) {
      console.error('Failed to update settings:', e)
      throw e
    }
  }

  return {
    settings,
    isLoading,
    error,
    isInitialized,
    fetchSettings,
    updateSettings,
  }
})
