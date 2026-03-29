import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  ClearRatingsResponse,
  CompanyImportResponse,
  TrackedCompany,
  TrackedCompanyCreate,
  TrackedCompanyUpdate,
  CompanyDetectRequest,
  CompanyDetectResponse,
  SyncResponse,
} from '@/types/api'
import { useApi } from '@/composables/useApi'

export const useCompaniesStore = defineStore('companies', () => {
  const api = useApi()

  // State
  const companies = ref<TrackedCompany[]>([])
  const selectedCompanyId = ref<number | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const selectedCompany = computed(() =>
    selectedCompanyId.value !== null
      ? companies.value.find((c) => c.id === selectedCompanyId.value) ?? null
      : null
  )

  const enabledCompanies = computed(() =>
    companies.value.filter((c) => c.enabled)
  )

  // Actions

  async function fetchCompanies() {
    isLoading.value = true
    error.value = null
    try {
      companies.value = await api.get<TrackedCompany[]>('/api/companies')
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load companies'
    } finally {
      isLoading.value = false
    }
  }

  function selectCompany(id: number | null) {
    selectedCompanyId.value = id
  }

  async function detectAts(url: string): Promise<CompanyDetectResponse> {
    const body: CompanyDetectRequest = { url }
    return api.post<CompanyDetectResponse>('/api/companies/detect', body as unknown as Record<string, unknown>)
  }

  async function createCompany(data: TrackedCompanyCreate): Promise<TrackedCompany> {
    const company = await api.post<TrackedCompany>('/api/companies', data as unknown as Record<string, unknown>)
    companies.value = [company, ...companies.value]
    return company
  }

  async function updateCompany(id: number, data: TrackedCompanyUpdate): Promise<TrackedCompany> {
    const updated = await api.put<TrackedCompany>(`/api/companies/${id}`, data as unknown as Record<string, unknown>)
    const idx = companies.value.findIndex((c) => c.id === id)
    if (idx !== -1) companies.value[idx] = updated
    return updated
  }

  async function deleteCompany(id: number): Promise<void> {
    await api.delete(`/api/companies/${id}`)
    companies.value = companies.value.filter((c) => c.id !== id)
    if (selectedCompanyId.value === id) {
      selectedCompanyId.value = null
    }
  }

  async function exportCompanies(): Promise<void> {
    const response = await fetch('/api/companies/export')
    if (!response.ok) throw new Error('Export failed')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const disposition = response.headers.get('Content-Disposition') ?? ''
    const match = disposition.match(/filename="?([^"]+)"?/)
    a.download = match ? match[1] : 'hirewire-companies.csv'
    a.href = url
    a.click()
    URL.revokeObjectURL(url)
  }

  async function importCompanies(file: File): Promise<CompanyImportResponse> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch('/api/companies/import', { method: 'POST', body: formData })
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Import failed' }))
      throw new Error(err.detail ?? 'Import failed')
    }
    const result: CompanyImportResponse = await response.json()
    await fetchCompanies()
    return result
  }

  async function clearGlassdoorRatings(): Promise<ClearRatingsResponse> {
    const result = await api.post<ClearRatingsResponse>('/api/companies/clear-ratings')
    await fetchCompanies()
    return result
  }

  async function syncCompany(id: number): Promise<SyncResponse | null> {
    let result: SyncResponse | null = null
    try {
      result = await api.post<SyncResponse>(`/api/companies/${id}/sync`)
    } finally {
      // Always refresh data even if sync errored, so UI stays consistent
      await fetchCompanies()
      const { useJobsStore } = await import('./jobs')
      useJobsStore().fetchAllJobs()
    }
    return result
  }

  return {
    companies,
    selectedCompanyId,
    selectedCompany,
    enabledCompanies,
    isLoading,
    error,
    fetchCompanies,
    selectCompany,
    detectAts,
    createCompany,
    updateCompany,
    deleteCompany,
    syncCompany,
    exportCompanies,
    importCompanies,
    clearGlassdoorRatings,
  }
})
