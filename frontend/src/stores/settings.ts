import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserSettings, UserSettingsResponse } from '@/types/api'
import { useApi } from '@/composables/useApi'

export const useSettingsStore = defineStore('settings', () => {
  const api = useApi()

  // State
  const settings = ref<UserSettingsResponse | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const isInitialized = ref(false)

  // Getters
  const excludedCompanies = computed(() => settings.value?.excluded_companies || [])
  const excludedKeywords = computed(() => settings.value?.excluded_keywords || [])
  const defaultLocation = computed(() => settings.value?.default_location || null)
  const defaultRemote = computed(() => settings.value?.default_remote || false)

  // Actions

  /**
   * Fetch user settings from API
   */
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

  /**
   * Update user settings
   */
  async function updateSettings(data: Partial<UserSettings>): Promise<void> {
    try {
      settings.value = await api.put<UserSettingsResponse>('/api/settings', data as Record<string, unknown>)
    } catch (e) {
      console.error('Failed to update settings:', e)
      throw e
    }
  }

  return {
    // State
    settings,
    isLoading,
    error,
    isInitialized,

    // Getters
    excludedCompanies,
    excludedKeywords,
    defaultLocation,
    defaultRemote,

    // Actions
    fetchSettings,
    updateSettings,
  }
})
